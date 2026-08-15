// ---------- Config ----------

const CATEGORY_COLORS = {
  "AI & automation": "var(--cat-ai)",
  "Local & professional services": "var(--cat-local)",
  "E-commerce": "var(--cat-ecom)",
  "Marketing & content": "var(--cat-marketing)",
  "Physical & print products": "var(--cat-physical)",
  "Digital & subscription products": "var(--cat-digital)"
};

// Scoring weights for soft ranking
const WEIGHT_CATEGORY = 3;
const WEIGHT_SEARCH_NAME = 5;
const WEIGHT_SEARCH_BODY = 1;

// ---------- State ----------

let ALL_IDEAS = [];
let state = {
  category: null,       // single-select or null
  search: ""
};

// ---------- Load data ----------

fetch('ideas.json')
  .then(r => r.json())
  .then(data => {
    ALL_IDEAS = data;
    buildCategoryPills();
    render();
  })
  .catch(err => {
    document.getElementById('gig-grid').innerHTML =
      '<p style="color: var(--text-muted)">Couldn\'t load the gig database right now. Try refreshing.</p>';
    console.error(err);
  });

// ---------- Build filter pills ----------

function buildCategoryPills() {
  const container = document.getElementById('category-pills');
  const categories = [...new Set(ALL_IDEAS.map(i => i.category))].sort();
  categories.forEach(cat => {
    const pill = document.createElement('button');
    pill.className = 'pill';
    pill.textContent = cat;
    pill.dataset.value = cat;
    pill.addEventListener('click', () => {
      state.category = state.category === cat ? null : cat;
      updatePillStates();
      render();
    });
    container.appendChild(pill);
  });
}

function updatePillStates() {
  document.querySelectorAll('#category-pills .pill').forEach(p => {
    p.classList.toggle('active', p.dataset.value === state.category);
  });
}

// ---------- Search ----------

document.getElementById('search-input').addEventListener('input', (e) => {
  state.search = e.target.value.trim().toLowerCase();
  render();
});

document.getElementById('browse-all-btn')?.addEventListener('click', () => {
  state.category = null;
  state.search = "";
  document.getElementById('search-input').value = "";
  updatePillStates();
  render();
});

// ---------- Soft-ranking scorer ----------
// Nothing is ever excluded. Every idea gets a score; the list re-sorts, best match first.
// A visitor's selections never hide anything, they just move things up or down the scroll.

function scoreIdea(idea) {
  let score = 0;

  if (state.category && idea.category === state.category) {
    score += WEIGHT_CATEGORY;
  }

  if (state.search) {
    const nameHit = idea.name.toLowerCase().includes(state.search);
    if (nameHit) score += WEIGHT_SEARCH_NAME;

    const bodyFields = [idea.what, idea.pitch, idea.found, idea.tags?.join(' ')].join(' ').toLowerCase();
    if (bodyFields.includes(state.search)) score += WEIGHT_SEARCH_BODY;
  }

  return score;
}

function getRankedIdeas() {
  return [...ALL_IDEAS]
    .map(idea => ({ idea, score: scoreIdea(idea) }))
    .sort((a, b) => b.score - a.score)
    .map(x => x.idea);
}

// ---------- Render ----------

function render() {
  const grid = document.getElementById('gig-grid');
  const ranked = getRankedIdeas();

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
    // preserve things like "AI", "$999", "7-Day" acronyms/numbers as-is if already capitalized/numeric
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

    <button class="copy-btn" type="button">Copy this gig</button>
  `;

  card.querySelector('.copy-btn').addEventListener('click', (e) => {
    const text = `${toTitleCase(idea.name)}\n${idea.category} | ${idea.cost}\nSource: ${idea.found} — ${idea.url}\n\nWhat It Is\n${idea.what}\n\nThe Pitch\n${idea.pitch}\n\nBest For\n${idea.best}\n\nThe Truth\n${idea.truth}\n`;
    navigator.clipboard.writeText(text).then(() => {
      const btn = e.target;
      const original = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = original; }, 1500);
    });
  });

  return card;
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
