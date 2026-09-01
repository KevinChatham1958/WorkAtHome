// ---------- Config ----------

const CATEGORY_COLORS = {
  "AI & automation": "var(--cat-ai)",
  "Local & professional services": "var(--cat-local)",
  "E-commerce": "var(--cat-ecom)",
  "Marketing & content": "var(--cat-marketing)",
  "Physical & print products": "var(--cat-physical)",
  "Digital & subscription products": "var(--cat-digital)",
  "Content & personal brand": "var(--cat-marketing)"
};

// Soft-ranking scorer weights (per project standard):
// name match = 4, tag/search-term match = 3, category/source match = 2, body text match = 1
const WEIGHT_NAME = 4;
const WEIGHT_TAG = 3;
const WEIGHT_CATEGORY_OR_SOURCE = 2;
const WEIGHT_BODY = 1;

const SAVED_KEY = 'shi_saved_gigs';

// ---------- Icons (inline SVG, standard/recognizable shapes, matches search-icon styling) ----------

const CHEVRON_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M6 9L12 15L18 9" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const BOOKMARK_OUTLINE_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M6 3.5C6 2.95 6.45 2.5 7 2.5H17C17.55 2.5 18 2.95 18 3.5V21L12 17L6 21V3.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>`;

const BOOKMARK_FILLED_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M6 3.5C6 2.95 6.45 2.5 7 2.5H17C17.55 2.5 18 2.95 18 3.5V21L12 17L6 21V3.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>`;

const COPY_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" stroke-width="2"/><path d="M16 8V5.5C16 4.7 15.3 4 14.5 4H5.5C4.7 4 4 4.7 4 5.5V14.5C4 15.3 4.7 16 5.5 16H8" stroke="currentColor" stroke-width="2"/></svg>`;

const CHECK_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M5 13L10 18L19 7" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

// ---------- State ----------

let ALL_IDEAS = [];
let state = {
  search: "",
  savedOnly: false
};
let savedIds = new Set(loadSaved());
let expandedIds = new Set();

// ---------- Load data ----------

fetch('ideas.json')
  .then(r => r.json())
  .then(data => {
    ALL_IDEAS = data;
    updateDbStats(data);
    render();
  })
  .catch(err => {
    document.getElementById('gig-grid').innerHTML =
      '<p style="color: var(--text-muted)">Couldn\'t load the gig database right now. Try refreshing.</p>';
    console.error(err);
  });

// Fills in the live gig/producer counts in the tool-section's db-links-row.
// Computed from the same data the grid renders from, so it can never drift
// out of sync with what's actually searchable on the page.
function updateDbStats(data) {
  const gigCountEl = document.getElementById('gig-count');
  const producerCountEl = document.getElementById('producer-count');
  if (gigCountEl) {
    gigCountEl.textContent = data.length.toLocaleString();
  }
  if (producerCountEl) {
    const producers = new Set(data.map(idea => idea.found).filter(Boolean));
    producerCountEl.textContent = producers.size.toLocaleString();
  }
}

// ---------- Saved gigs (localStorage) ----------

function loadSaved() {
  try {
    const raw = localStorage.getItem(SAVED_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function persistSaved() {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify([...savedIds]));
  } catch (e) {
    console.error('Could not persist saved gigs', e);
  }
}

function toggleSaved(id) {
  if (savedIds.has(id)) {
    savedIds.delete(id);
  } else {
    savedIds.add(id);
  }
  persistSaved();
  updateSavedUI();
}

function updateSavedUI() {
  const countEl = document.getElementById('saved-count');
  countEl.textContent = `${savedIds.size} gig${savedIds.size === 1 ? '' : 's'} saved`;
  document.getElementById('download-saved-btn').disabled = savedIds.size === 0;
}

// ---------- Search input ----------
// Deliberately NOT live-as-you-type. Typing alone does nothing to the
// results — the search only runs when the visitor explicitly asks for it
// (Search button or Enter), at which point a brief spinner confirms the
// action happened, then the grid reorders. This is a single, predictable
// behavior regardless of which control triggers it, and the spinner doubles
// as feedback for the "nothing changed" case (e.g. a zero-match query),
// which previously looked identical to the search not working at all.

const SEARCH_SPINNER_MS = 3500;

const searchInputEl = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search-btn');
const searchSubmitBtn = document.getElementById('search-submit-btn');
const searchLoadingEl = document.getElementById('search-loading');
const gigGridEl = document.getElementById('gig-grid');

searchInputEl.addEventListener('input', (e) => {
  // Typing only toggles the clear (×) button — it does not trigger a search.
  clearSearchBtn.hidden = e.target.value.trim().length === 0;
});

searchInputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    runSearch(searchInputEl.value);
    searchInputEl.blur(); // dismiss mobile keyboard so results are visible
  }
});

searchSubmitBtn.addEventListener('click', () => {
  runSearch(searchInputEl.value);
});

clearSearchBtn.addEventListener('click', () => {
  searchInputEl.value = '';
  clearSearchBtn.hidden = true;
  // Clearing is an undo, not a search — snaps back instantly, no spinner.
  state.search = '';
  render();
  searchInputEl.focus();
});

function runSearch(rawValue) {
  const query = rawValue.trim().toLowerCase();

  searchLoadingEl.hidden = false;
  gigGridEl.hidden = true;
  searchSubmitBtn.disabled = true;

  setTimeout(() => {
    state.search = query;
    searchLoadingEl.hidden = true;
    gigGridEl.hidden = false;
    searchSubmitBtn.disabled = false;
    render();
  }, SEARCH_SPINNER_MS);
}

function updateSearchFeedback(topScore) {
  const el = document.getElementById('search-feedback');
  if (state.search.length === 0) {
    el.hidden = true;
    el.textContent = '';
    return;
  }
  el.hidden = false;
  el.textContent = topScore > 0
    ? `Showing results for "${state.search}"`
    : `No exact matches for "${state.search}" — showing everything, best guesses first`;
}

document.getElementById('saved-only-toggle').addEventListener('change', (e) => {
  state.savedOnly = e.target.checked;
  render();
});

document.getElementById('download-saved-btn').addEventListener('click', downloadSavedGigs);

// ---------- Soft-ranking scorer ----------
// Nothing is ever excluded from search. Every idea gets a score against each
// search word; the list re-sorts, best match first. A visitor's search never
// hides anything — it just moves things up or down the scroll.
//
// Matching is word-based rather than raw substring, with a light stem/prefix
// check, so a search word doesn't have to appear letter-for-letter in the
// data to count as a match — e.g. typing "pets" matches an entry that only
// says "pet," and "consult" matches "consulting." This is general-purpose
// normalization, not a hand-maintained list of synonyms, since there's no
// way to anticipate every word form a visitor might type.

function tokenize(str) {
  return (str || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function stem(word) {
  if (word.length > 4 && word.endsWith('ies')) return word.slice(0, -3) + 'y';
  if (word.length > 4 && word.endsWith('es')) return word.slice(0, -2);
  if (word.length > 3 && word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
  return word;
}

function sharedPrefixLength(a, b) {
  const len = Math.min(a.length, b.length);
  let i = 0;
  while (i < len && a[i] === b[i]) i++;
  return i;
}

function wordMatchesToken(word, token) {
  if (token === word) return true;
  if (stem(token) === stem(word)) return true;
  if (token.length >= 3 && word.length >= 3 && (token.startsWith(word) || word.startsWith(token))) return true;
  // Catches longer words that diverge only in suffix (e.g. "dropshippers" /
  // "dropshipping") without needing a full stemmer: if most of the shorter
  // word's letters line up from the start, treat it as the same word.
  const shorter = Math.min(word.length, token.length);
  if (shorter >= 5 && sharedPrefixLength(word, token) >= Math.ceil(shorter * 0.75)) return true;
  return false;
}

function fieldMatches(tokens, word) {
  return tokens.some(token => wordMatchesToken(word, token));
}

function scoreIdea(idea, words) {
  if (words.length === 0) return 0;

  const nameTokens = tokenize(idea.name);
  const categoryTokens = tokenize(idea.category);
  const sourceTokens = tokenize(idea.found || '');
  const tagTokens = (idea.tags || []).flatMap(tokenize);
  const situationTagTokens = (idea.situation_tags || []).flatMap(tokenize);
  // search_terms is an optional field (added going forward during
  // extraction): plain-language words/synonyms a visitor might type that
  // don't appear verbatim elsewhere in the entry. Safe no-op for any entry
  // that doesn't have it yet.
  const searchTermTokens = (idea.search_terms || []).flatMap(tokenize);
  const bodyTokens = tokenize([idea.what, idea.pitch, idea.best, idea.truth].join(' '));

  let score = 0;

  words.forEach(word => {
    if (fieldMatches(nameTokens, word)) score += WEIGHT_NAME;
    if (fieldMatches(tagTokens, word) || fieldMatches(situationTagTokens, word) || fieldMatches(searchTermTokens, word)) score += WEIGHT_TAG;
    if (fieldMatches(categoryTokens, word) || fieldMatches(sourceTokens, word)) score += WEIGHT_CATEGORY_OR_SOURCE;
    if (fieldMatches(bodyTokens, word)) score += WEIGHT_BODY;
  });

  return score;
}

function getRankedIdeas() {
  let pool = ALL_IDEAS;
  if (state.savedOnly) {
    pool = pool.filter(idea => savedIds.has(idea.id));
  }

  const words = state.search.length > 0 ? state.search.split(/\s+/).filter(Boolean) : [];

  if (words.length === 0) {
    updateSearchFeedback(0);
    return pool;
  }

  const scored = pool
    .map(idea => ({ idea, score: scoreIdea(idea, words) }))
    .sort((a, b) => b.score - a.score);

  updateSearchFeedback(scored.length > 0 ? scored[0].score : 0);

  return scored.map(x => x.idea);
}

// ---------- Render ----------

function render() {
  const grid = document.getElementById('gig-grid');
  const emptyState = document.getElementById('empty-state');
  const ranked = getRankedIdeas();

  updateSavedUI();

  if (state.savedOnly && ranked.length === 0) {
    grid.innerHTML = '';
    emptyState.hidden = false;
    return;
  }
  emptyState.hidden = true;

  grid.innerHTML = '';
  ranked.forEach(idea => {
    grid.appendChild(buildCard(idea));
  });
}

function toTitleCase(str) {
  const minorWords = new Set(['a','an','the','and','but','or','nor','for','so','yet','at','by','in','of','on','to','up','as','is','it','vs']);
  const words = str.split(' ');
  return words.map((word, i) => {
    if (word.length === 0) return word;
    if (/^[A-Z0-9$]/.test(word) && word === word.toUpperCase() && /[A-Z]/.test(word)) return word;
    const lower = word.toLowerCase();
    if (i !== 0 && i !== words.length - 1 && minorWords.has(lower)) return lower;
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }).join(' ');
}

function slugifyProducer(name) {
  let s = (name || '').toLowerCase();
  s = s.replace(/[^a-z0-9]+/g, '-');
  s = s.replace(/^-+|-+$/g, '');
  s = s.slice(0, 60);
  return s;
}

function avatarSrc(found) {
  return `assets/avatars/avatar-${slugifyProducer(found)}.jpg`;
}

function buildCard(idea) {
  const card = document.createElement('article');
  card.className = 'card';

  const isSaved = savedIds.has(idea.id);

  card.innerHTML = `
    <div class="card-head">
      <div class="card-title-block">
        <img class="card-avatar" src="${escapeAttr(avatarSrc(idea.found))}" alt="" loading="lazy" onerror="this.classList.add('card-avatar-hidden')">
        <div class="card-title-text">
          <h3 class="card-title">${escapeHtml(toTitleCase(idea.name))}</h3>
          <p class="card-meta">${escapeHtml(idea.category)} &middot; ${escapeHtml(idea.cost)}</p>
        </div>
      </div>
      <div class="card-actions">
        <button class="copy-btn" type="button">${COPY_SVG}<span>Copy This Entire Gig to Clipboard</span></button>
        <label class="save-toggle ${isSaved ? 'saved' : ''}">
          <input type="checkbox" class="save-checkbox" ${isSaved ? 'checked' : ''}>
          <span class="bookmark-icon">${isSaved ? BOOKMARK_FILLED_SVG : BOOKMARK_OUTLINE_SVG}</span>
          <span>Save for Later</span>
        </label>
      </div>
    </div>

    <div class="card-section">
      <div class="card-section-label">Source</div>
      <p class="card-text">${escapeHtml(idea.found)} &mdash; <a href="${escapeAttr(idea.url)}" target="_blank" rel="noopener">${escapeHtml(idea.url)}</a></p>
    </div>

    <div class="card-section">
      <div class="card-section-label">What It Is</div>
      <p class="card-text">${escapeHtml(idea.what)}</p>
    </div>

    <div class="card-section">
      <div class="card-section-label">The Pitch</div>
      <p class="card-text">${escapeHtml(idea.pitch)}</p>
    </div>

    <div class="card-section">
      <div class="card-section-label">Best For</div>
      <p class="card-text">${escapeHtml(idea.best)}</p>
    </div>

    <div class="card-section">
      <div class="card-section-label">The Truth</div>
      <p class="card-text">${escapeHtml(idea.truth)}</p>
    </div>
  `;

  card.querySelector('.save-checkbox').addEventListener('change', () => {
    toggleSaved(idea.id);
    const label = card.querySelector('.save-toggle');
    const nowSaved = savedIds.has(idea.id);
    label.classList.toggle('saved', nowSaved);
    label.querySelector('.bookmark-icon').innerHTML = nowSaved ? BOOKMARK_FILLED_SVG : BOOKMARK_OUTLINE_SVG;
    if (state.savedOnly) render();
  });

  card.querySelector('.copy-btn').addEventListener('click', (e) => {
    const text = formatGigText(idea);
    const btn = e.currentTarget;
    const label = btn.querySelector('span');
    navigator.clipboard.writeText(text).then(() => {
      const original = label.textContent;
      label.textContent = 'Copied!';
      setTimeout(() => { label.textContent = original; }, 1500);
    });
  });

  return card;
}

function formatGigText(idea) {
  return `${toTitleCase(idea.name)}\n${idea.category} | ${idea.cost}\nSource: ${idea.found} — ${idea.url}\n\nWhat It Is\n${idea.what}\n\nThe Pitch\n${idea.pitch}\n\nBest For\n${idea.best}\n\nThe Truth\n${idea.truth}\n`;
}

function downloadSavedGigs() {
  if (savedIds.size === 0) return;

  const saved = ALL_IDEAS.filter(idea => savedIds.has(idea.id));
  const body = saved.map(formatGigText).join('\n' + '-'.repeat(40) + '\n\n');
  const header = `Side Hustle Intel — Saved Gigs\nExported ${new Date().toLocaleString()}\n\n${'='.repeat(40)}\n\n`;

  const blob = new Blob([header + body], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');

  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  a.href = url;
  a.download = `side-hustle-intel-saved-gigs-${ts}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return (str || '').replace(/"/g, '&quot;');
}

// ---------- Back to search ----------

const backToSearchBtn = document.getElementById('back-to-search-btn');

window.addEventListener('scroll', () => {
  backToSearchBtn.hidden = window.scrollY < 500;
}, { passive: true });

backToSearchBtn.addEventListener('click', () => {
  const searchInput = document.getElementById('search-input');
  searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Give the smooth scroll a moment to land before focusing, so the page
  // doesn't jump again as the keyboard/focus ring appears mid-scroll.
  setTimeout(() => searchInput.focus(), 400);
});
