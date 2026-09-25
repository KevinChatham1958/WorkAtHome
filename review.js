// ==========================================================
// REVIEW MODE — private layer on top of app.js.
// Only loaded by review.html. The public site never loads this file.
//
// Simple version: every card gets a "Delete" checkbox. The
// "Submit all tagged" button copies the tagged list so it can be
// pasted to Claude, who removes those ideas from the live site.
//
// app.js does all the normal work (loading ideas.json, search, sort,
// building cards). This file wraps getRankedIdeas, render and
// buildCard, so changes to the public site show up here too.
// Tags are saved only in this browser (localStorage).
// ==========================================================

const DELETE_TAGS_KEY = 'shi_delete_tags';
const OLD_FLAGS_KEY = 'shi_review_flags'; // from the first version of this page

let reviewState = {
  taggedOnly: false,
  groupBy: 'none',  // none | guru | video
  guru: ''
};

let deleteTags = rLoad(DELETE_TAGS_KEY, null);
if (deleteTags === null) {
  // Carry over anything already flagged for removal in the old version.
  deleteTags = {};
  const old = rLoad(OLD_FLAGS_KEY, {});
  Object.entries(old).forEach(([id, f]) => {
    if (f && f.status === 'remove') deleteTags[id] = { name: f.name, found: f.found, url: f.url };
  });
  rSave(DELETE_TAGS_KEY, deleteTags);
}
let reviewInitDone = false;

function rLoad(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (e) { return fallback; }
}
function rSave(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); }
  catch (e) { console.error('Review: could not save', e); }
}
function saveTags() { rSave(DELETE_TAGS_KEY, deleteTags); }
function tagCount() { return Object.keys(deleteTags).length; }

function tag(idea) { deleteTags[idea.id] = { name: idea.name, found: idea.found, url: idea.url }; }
function untag(idea) { delete deleteTags[idea.id]; }

// ---------- Wrap app.js: filtering ----------

const _publicGetRankedIdeas = getRankedIdeas;
getRankedIdeas = function () {
  let list = _publicGetRankedIdeas();
  if (reviewState.guru) list = list.filter(i => i.found === reviewState.guru);
  if (reviewState.taggedOnly) list = list.filter(i => deleteTags[i.id]);
  return list;
};

// ---------- Wrap app.js: rendering (adds grouping) ----------

const _publicRender = render;
render = function () {
  if (!reviewInitDone && ALL_IDEAS.length > 0) reviewInit();
  updateTagCount();

  if (reviewState.groupBy === 'none') {
    _publicRender();
    showReviewEmpty();
    return;
  }

  const grid = document.getElementById('gig-grid');
  const ranked = getRankedIdeas();
  updateSavedUI();
  updateSameProducerNote(ranked);
  document.getElementById('empty-state').hidden = true;
  grid.innerHTML = '';

  const keyOf = reviewState.groupBy === 'guru' ? (i => i.found || '(unknown)') : (i => i.url || '(no link)');
  const groups = new Map();
  ranked.forEach(idea => {
    const k = keyOf(idea);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(idea);
  });

  const keys = [...groups.keys()];
  if (reviewState.groupBy === 'guru') {
    keys.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  } else {
    keys.sort((a, b) => {
      const ia = groups.get(a)[0], ib = groups.get(b)[0];
      const g = (ia.found || '').localeCompare(ib.found || '', undefined, { sensitivity: 'base' });
      if (g !== 0) return g;
      return (ib.published || '').localeCompare(ia.published || '');
    });
  }

  keys.forEach(k => {
    const items = groups.get(k);
    grid.appendChild(buildGroupHead(k, items));
    items.forEach(idea => grid.appendChild(buildCard(idea)));
  });

  showReviewEmpty(ranked.length === 0);
};

function showReviewEmpty(forceEmpty) {
  const grid = document.getElementById('gig-grid');
  const msg = document.getElementById('review-empty');
  const empty = forceEmpty !== undefined ? forceEmpty : grid.children.length === 0;
  msg.hidden = !(empty && !state.savedOnly);
}

function buildGroupHead(key, items) {
  const head = document.createElement('div');
  head.className = 'review-group-head';
  const n = items.length;
  const taggedN = items.filter(i => deleteTags[i.id]).length;
  const tagNote = taggedN ? ` · ${taggedN} tagged` : '';

  if (reviewState.groupBy === 'guru') {
    head.innerHTML = `<span>${escapeHtml(key)}</span>
      <span class="rg-meta">${n} idea${n === 1 ? '' : 's'}${tagNote}</span>`;
  } else {
    const first = items[0];
    const date = formatPublished(first.published);
    const allTagged = taggedN === n;
    head.innerHTML = `<span>${escapeHtml(first.found || '')}${date ? ' — ' + escapeHtml(date) : ''}</span>
      <span class="rg-meta">${n} idea${n === 1 ? '' : 's'}${tagNote} ·
        <a href="${escapeAttr(first.url)}" target="_blank" rel="noopener">watch video</a>
        <button type="button" class="rg-flagall">${allTagged ? 'Untag all from this video' : 'Delete all from this video'}</button></span>`;
    head.querySelector('.rg-flagall').addEventListener('click', () => {
      items.forEach(i => allTagged ? untag(i) : tag(i));
      saveTags();
      render();
    });
  }
  return head;
}

// ---------- Wrap app.js: cards (adds the Delete checkbox) ----------

const _publicBuildCard = buildCard;
buildCard = function (idea) {
  const card = _publicBuildCard(idea);
  card.dataset.id = idea.id;

  const box = document.createElement('label');
  box.className = 'delete-toggle';
  box.innerHTML = `<input type="checkbox" class="delete-checkbox"><span>Delete</span>`;
  card.querySelector('.card-actions').prepend(box);

  const input = box.querySelector('input');
  const paint = () => {
    const on = !!deleteTags[idea.id];
    input.checked = on;
    box.classList.toggle('on', on);
    card.classList.toggle('review-flagged', on);
  };
  input.addEventListener('change', () => {
    if (input.checked) tag(idea); else untag(idea);
    saveTags(); paint(); updateTagCount();
  });

  paint();
  return card;
};

// ---------- Panel ----------

function reviewInit() {
  reviewInitDone = true;

  // Clear tags for ideas already gone from the database (already deleted).
  const liveIds = new Set(ALL_IDEAS.map(i => i.id));
  let pruned = false;
  Object.keys(deleteTags).forEach(id => {
    if (!liveIds.has(id)) { delete deleteTags[id]; pruned = true; }
  });
  if (pruned) saveTags();

  const counts = new Map();
  ALL_IDEAS.forEach(i => { const g = i.found || '(unknown)'; counts.set(g, (counts.get(g) || 0) + 1); });
  const sel = document.getElementById('review-guru');
  [...counts.keys()]
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .forEach(g => {
      const opt = document.createElement('option');
      opt.value = g;
      opt.textContent = `${g} (${counts.get(g)})`;
      sel.appendChild(opt);
    });
}

function updateTagCount() {
  const n = tagCount();
  document.querySelectorAll('.submit-tagged-btn').forEach(btn => {
    btn.disabled = n === 0;
    btn.textContent = `Submit all tagged (${n})`;
  });
}

document.getElementById('review-tagged-only').addEventListener('change', e => {
  reviewState.taggedOnly = e.target.checked; expandedId = null; render();
});
document.getElementById('review-group').addEventListener('change', e => {
  reviewState.groupBy = e.target.value; expandedId = null; render();
});
document.getElementById('review-guru').addEventListener('change', e => {
  reviewState.guru = e.target.value; expandedId = null; render();
});

// ---------- Submit all tagged ----------

function buildDeleteList() {
  const entries = Object.entries(deleteTags);
  const d = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  let out = `SIDE HUSTLE INTEL — DELETE LIST (${d})\n${entries.length} idea${entries.length === 1 ? '' : 's'} to delete\n\n`;
  out += entries.map(([id, f]) =>
    `- ${toTitleCase(f.name || id)} — ${f.found || ''}\n  id: ${id}${f.url ? `\n  video: ${f.url}` : ''}`
  ).join('\n') + '\n';
  return out;
}

const modal = document.getElementById('review-modal');
const modalText = document.getElementById('review-modal-text');
const modalCopyBtn = document.getElementById('review-modal-copy');

function submitTagged() {
  modalText.value = buildDeleteList();
  modal.hidden = false;
  doCopy();
}
function doCopy() {
  const done = () => { modalCopyBtn.textContent = 'Copied ✓'; setTimeout(() => { modalCopyBtn.textContent = 'Copy again'; }, 1800); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(modalText.value).then(done, () => { modalText.select(); });
  } else {
    modalText.select();
  }
}
document.querySelectorAll('.submit-tagged-btn').forEach(btn => btn.addEventListener('click', submitTagged));
modalCopyBtn.addEventListener('click', doCopy);
document.getElementById('review-modal-close').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', e => { if (e.target === modal) modal.hidden = true; });
