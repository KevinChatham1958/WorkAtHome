// ---------- Config ----------

const CATEGORY_COLORS = {
  "AI & automation": "var(--cat-ai)",
  "Local & professional services": "var(--cat-local)",
  "E-commerce": "var(--cat-ecom)",
  "Marketing & content": "var(--cat-marketing)",
  "Physical & print products": "var(--cat-physical)",
  "Digital & subscription products": "var(--cat-digital)"
};

// Fixed 13-tag closed list (Situation Tags Addendum). Order matters for display.
const SITUATION_TAGS = [
  "Strictly in-home",
  "Home office, client-facing",
  "Local travel required",
  "Requires travel to source or inspect goods",
  "Phone/sales-based",
  "E-commerce / fulfillment",
  "Needs a truck or cargo vehicle",
  "Needs a dedicated workspace",
  "Needs inventory storage",
  "Weekend/event-based schedule",
  "Requires a license or certification",
  "Requires hiring or managing others",
  "Requires equipment/vehicle investment"
];

// Scoring weights for soft ranking
const WEIGHT_CATEGORY = 3;
const WEIGHT_SITUATION_TAG = 2;
const WEIGHT_SEARCH_NAME = 5;
const WEIGHT_SEARCH_BODY = 1;

// ---------- State ----------

let ALL_IDEAS = [];
let state = {
  category: null,       // single-select or null
  situationTags: new Set(), // multi-select
  search: ""
};

// ---------- Load data ----------

fetch('ideas.json')
  .then(r => r.json())
  .then(data => {
    ALL_IDEAS = data;
    buildCategoryPills();
    buildSituationPills();
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

function buildSituationPills() {
  const container = document.getElementById('situation-pills');
  SITUATION_TAGS.forEach(tag => {
    const pill = document.createElement('button');
    pill.className = 'pill';
    pill.textContent = tag;
    pill.dataset.value = tag;
    pill.addEventListener('click', () => {
      if (state.situationTags.has(tag)) {
        state.situationTags.delete(tag);
      } else {
        state.situationTags.add(tag);
      }
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
  document.querySelectorAll('#situation-pills .pill').forEach(p => {
    p.classList.toggle('active', state.situationTags.has(p.dataset.value));
  });
}

// ---------- Search ----------

document.getElementById('search-input').addEventListener('input', (e) => {
  state.search = e.target.value.trim().toLowerCase();
  render();
});

document.getElementById('browse-all-btn').addEventListener('click', () => {
  state.category = null;
  state.situationTags.clear();
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

  if (state.situationTags.size > 0) {
    const tags = idea.situation_tags || [];
    for (const tag of state.situationTags) {
      if (tags.includes(tag)) score += WEIGHT_SITUATION_TAG; // match-any
    }
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

function buildCard(idea) {
  const card = document.createElement('article');
  card.className = 'card';
  const catColor = CATEGORY_COLORS[idea.category] || 'var(--accent)';
  card.style.setProperty('--cat-color', catColor);

  card.innerHTML = `
    <div class="card-head">
      <h3 class="card-title">${escapeHtml(idea.name)}</h3>
    </div>
    <div class="card-badges">
      <span class="badge badge-category">${escapeHtml(idea.category)}</span>
      <span class="badge badge-cost">${escapeHtml(idea.cost)}</span>
    </div>
    <div class="card-credit">via <span>${escapeHtml(idea.found)}</span></div>

    <div class="card-section">
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

    <div class="card-source">
      Source: <a href="${escapeAttr(idea.url)}" target="_blank" rel="noopener">${escapeHtml(idea.url)}</a>
    </div>
  `;
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
