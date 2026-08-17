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
// name match = 4, tag match = 3, category/source match = 2, body text match = 1
const WEIGHT_NAME = 4;
const WEIGHT_TAG = 3;
const WEIGHT_CATEGORY_OR_SOURCE = 2;
const WEIGHT_BODY = 1;

const SAVED_KEY = 'shi_saved_gigs';

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
    render();
  })
  .catch(err => {
    document.getElementById('gig-grid').innerHTML =
      '<p style="color: var(--text-muted)">Couldn\'t load the gig database right now. Try refreshing.</p>';
    console.error(err);
  });

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

document.getElementById('search-input').addEventListener('input', (e) => {
  state.search = e.target.value.trim().toLowerCase();
  render();
});

document.getElementById('saved-only-toggle').addEventListener('change', (e) => {
  state.savedOnly = e.target.checked;
  render();
});

document.getElementById('download-saved-btn').addEventListener('click', downloadSavedGigs);

// ---------- Soft-ranking scorer ----------
// Nothing is ever excluded from search. Every idea gets a score against each
// search word; the list re-sorts, best match first. A visitor's search never
// hides anything — it just moves things up or down the scroll.

function scoreIdea(idea, words) {
  if (words.length === 0) return 0;

  const nameL = idea.name.toLowerCase();
  const categoryL = idea.category.toLowerCase();
  const sourceL = (idea.found || '').toLowerCase();
  const tagsL = (idea.tags || []).map(t => t.toLowerCase());
  const situationTagsL = (idea.situation_tags || []).map(t => t.toLowerCase());
  const bodyL = [idea.what, idea.pitch, idea.best, idea.truth].join(' ').toLowerCase();

  let score = 0;

  words.forEach(word => {
    if (nameL.includes(word)) score += WEIGHT_NAME;
    if (tagsL.some(t => t.includes(word)) || situationTagsL.some(t => t.includes(word))) score += WEIGHT_TAG;
    if (categoryL.includes(word) || sourceL.includes(word)) score += WEIGHT_CATEGORY_OR_SOURCE;
    if (bodyL.includes(word)) score += WEIGHT_BODY;
  });

  return score;
}

function getRankedIdeas() {
  let pool = ALL_IDEAS;
  if (state.savedOnly) {
    pool = pool.filter(idea => savedIds.has(idea.id));
  }

  const words = state.search.length > 0 ? state.search.split(/\s+/).filter(Boolean) : [];

  if (words.length === 0) return pool;

  return [...pool]
    .map(idea => ({ idea, score: scoreIdea(idea, words) }))
    .sort((a, b) => b.score - a.score)
    .map(x => x.idea);
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

function buildCard(idea) {
  const card = document.createElement('article');
  card.className = 'card';
  const catColor = CATEGORY_COLORS[idea.category] || 'var(--accent)';
  card.style.setProperty('--cat-color', catColor);

  const isExpanded = expandedIds.has(idea.id);
  const isSaved = savedIds.has(idea.id);
  if (isExpanded) card.classList.add('expanded');

  card.innerHTML = `
    <div class="card-head">
      <h3 class="card-title">${escapeHtml(toTitleCase(idea.name))}</h3>
    </div>
    <div class="card-badges">
      <span class="badge badge-category">${escapeHtml(idea.category)}</span>
      <span class="badge badge-cost">${escapeHtml(idea.cost)}</span>
    </div>
    <div class="card-source-top">
      Source: <span class="card-source-creator">${escapeHtml(idea.found)}</span> &mdash; <a href="${escapeAttr(idea.url)}" target="_blank" rel="noopener">${escapeHtml(idea.url)}</a>
    </div>

    <div class="card-section">
      <div class="card-section-label">What It Is</div>
      <p class="card-what">${escapeHtml(idea.what)}</p>
    </div>

    <div class="card-more" ${isExpanded ? '' : 'hidden'}>
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
    </div>

    <button class="expand-toggle" type="button" aria-expanded="${isExpanded}">
      <span class="toggle-label">${isExpanded ? 'Collapse to Read Less' : 'Expand to Read More'}</span>
      <span class="chevron">&#9662;</span>
    </button>

    <div class="card-actions">
      <label class="save-toggle ${isSaved ? 'saved' : ''}">
        <input type="checkbox" class="save-checkbox" ${isSaved ? 'checked' : ''}>
        <span>Save for Later</span>
      </label>
      <button class="copy-btn" type="button">Copy This Gig to Clipboard</button>
    </div>
  `;

  card.querySelector('.expand-toggle').addEventListener('click', () => {
    if (expandedIds.has(idea.id)) {
      expandedIds.delete(idea.id);
    } else {
      expandedIds.add(idea.id);
    }
    render();
  });

  card.querySelector('.save-checkbox').addEventListener('change', () => {
    toggleSaved(idea.id);
    const label = card.querySelector('.save-toggle');
    label.classList.toggle('saved', savedIds.has(idea.id));
    if (state.savedOnly) render();
  });

  card.querySelector('.copy-btn').addEventListener('click', (e) => {
    const text = formatGigText(idea);
    navigator.clipboard.writeText(text).then(() => {
      const btn = e.target;
      const original = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = original; }, 1500);
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
