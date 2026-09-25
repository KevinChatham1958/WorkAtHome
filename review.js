// ==========================================================
// REVIEW MODE — private layer on top of app.js.
// Only loaded by review.html. The public site never loads this file.
//
// app.js does all the normal work (loading ideas.json, search, sort,
// building cards). This file wraps three of its functions —
// getRankedIdeas, render and buildCard — to add the review tools,
// so any change to the public site shows up here automatically.
//
// Flags live only in this browser (localStorage). Nothing on this
// page changes the live site; flags reach the site only when the
// copied list is pasted to Claude and processed.
// ==========================================================

const REVIEW_FLAGS_KEY = 'shi_review_flags';
const REVIEW_SEEN_KEY = 'shi_review_seen';
const REVIEW_SEEN_AT_KEY = 'shi_review_seen_at';

const REMOVE_REASONS = [
  'Not work-at-home',
  'Duplicate',
  'Too thin / vague',
  'Other'
];

let reviewState = {
  show: 'all',      // all | new | remove | fix | unflagged
  groupBy: 'none',  // none | guru | video
  guru: ''          // '' = all gurus
};

let reviewFlags = rLoad(REVIEW_FLAGS_KEY, {});          // id -> {status, reason, note, name, found, url, at}
let reviewSeen = new Set(rLoad(REVIEW_SEEN_KEY, []));   // ids already reviewed
let reviewSeenAt = rLoad(REVIEW_SEEN_AT_KEY, null);
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
function saveFlags() { rSave(REVIEW_FLAGS_KEY, reviewFlags); }

function isNew(idea) { return !reviewSeen.has(idea.id); }

// ---------- Wrap app.js: filtering ----------

const _publicGetRankedIdeas = getRankedIdeas;
getRankedIdeas = function () {
  let list = _publicGetRankedIdeas();
  if (reviewState.guru) list = list.filter(i => i.found === reviewState.guru);
  switch (reviewState.show) {
    case 'new':       list = list.filter(isNew); break;
    case 'remove':    list = list.filter(i => reviewFlags[i.id]?.status === 'remove'); break;
    case 'fix':       list = list.filter(i => reviewFlags[i.id]?.status === 'fix'); break;
    case 'unflagged': list = list.filter(i => !reviewFlags[i.id]); break;
  }
  return list;
};

// ---------- Wrap app.js: rendering (adds grouping) ----------

const _publicRender = render;
render = function () {
  if (!reviewInitDone && ALL_IDEAS.length > 0) reviewInit();
  updateReviewStats();

  if (reviewState.groupBy === 'none') {
    _publicRender();
    showReviewEmpty();
    return;
  }

  const grid = document.getElementById('gig-grid');
  const emptyState = document.getElementById('empty-state');
  const ranked = getRankedIdeas();
  updateSavedUI();
  updateSameProducerNote(ranked);
  emptyState.hidden = true;
  grid.innerHTML = '';

  const keyOf = reviewState.groupBy === 'guru' ? (i => i.found || '(unknown)') : (i => i.url || '(no link)');
  const groups = new Map();
  ranked.forEach(idea => {
    const k = keyOf(idea);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(idea);
  });

  let keys = [...groups.keys()];
  if (reviewState.groupBy === 'guru') {
    keys.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  } else {
    // videos: by guru, then newest video first
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
  let msg = document.getElementById('review-empty');
  const empty = forceEmpty !== undefined ? forceEmpty : grid.children.length === 0;
  if (empty && !state.savedOnly) {
    msg.hidden = false;
  } else {
    msg.hidden = true;
  }
}

function buildGroupHead(key, items) {
  const head = document.createElement('div');
  head.className = 'review-group-head';
  const flaggedN = items.filter(i => reviewFlags[i.id]?.status === 'remove').length;
  const flagNote = flaggedN ? ` · ${flaggedN} flagged` : '';

  if (reviewState.groupBy === 'guru') {
    head.innerHTML = `<span>${escapeHtml(key)}</span>
      <span class="rg-meta">${items.length} idea${items.length === 1 ? '' : 's'}${flagNote}</span>`;
  } else {
    const first = items[0];
    const date = formatPublished(first.published);
    head.innerHTML = `<span>${escapeHtml(first.found || '')}${date ? ' — ' + escapeHtml(date) : ''}</span>
      <span class="rg-meta">${items.length} idea${items.length === 1 ? '' : 's'}${flagNote} ·
        <a href="${escapeAttr(first.url)}" target="_blank" rel="noopener">watch video</a>
        <button type="button" class="rg-flagall">Flag all from this video</button></span>`;
    head.querySelector('.rg-flagall').addEventListener('click', () => {
      const allFlagged = items.every(i => reviewFlags[i.id]?.status === 'remove');
      items.forEach(i => {
        if (allFlagged) delete reviewFlags[i.id];
        else setFlag(i, 'remove', REMOVE_REASONS[0], reviewFlags[i.id]?.note || '');
      });
      saveFlags();
      render();
    });
    if (items.every(i => reviewFlags[i.id]?.status === 'remove')) {
      head.querySelector('.rg-flagall').textContent = 'Unflag all from this video';
    }
  }
  return head;
}

// ---------- Wrap app.js: cards (adds the review bar) ----------

const _publicBuildCard = buildCard;
buildCard = function (idea) {
  const card = _publicBuildCard(idea);
  card.dataset.id = idea.id;
  if (isNew(idea)) card.classList.add('review-new');

  const bar = document.createElement('div');
  bar.className = 'review-bar';
  bar.innerHTML = `
    <span class="review-bar-label">Review</span>
    <button type="button" class="rb-flag">Flag for removal</button>
    <select class="rb-reason" hidden>
      ${REMOVE_REASONS.map(r => `<option value="${escapeAttr(r)}">${escapeHtml(r)}</option>`).join('')}
    </select>
    <button type="button" class="rb-fix">Needs a fix</button>
    <input type="text" class="rb-note" placeholder="Note (optional)" hidden>
    <span class="rb-status"></span>
  `;
  card.appendChild(bar);

  const flagBtn = bar.querySelector('.rb-flag');
  const fixBtn = bar.querySelector('.rb-fix');
  const reasonSel = bar.querySelector('.rb-reason');
  const noteInput = bar.querySelector('.rb-note');

  const paint = () => {
    const f = reviewFlags[idea.id];
    const status = f ? f.status : null;
    card.classList.toggle('review-flagged', status === 'remove');
    card.classList.toggle('review-fix', status === 'fix');
    flagBtn.classList.toggle('on', status === 'remove');
    fixBtn.classList.toggle('on', status === 'fix');
    flagBtn.textContent = status === 'remove' ? 'Flagged ✕ undo' : 'Flag for removal';
    fixBtn.textContent = status === 'fix' ? 'Fix noted ✕ undo' : 'Needs a fix';
    reasonSel.hidden = status !== 'remove';
    noteInput.hidden = !status;
    noteInput.placeholder = status === 'fix' ? 'What needs fixing? (e.g. should be E-commerce)' : 'Note (optional)';
    if (f) {
      reasonSel.value = f.reason || REMOVE_REASONS[0];
      if (document.activeElement !== noteInput) noteInput.value = f.note || '';
    }
  };

  flagBtn.addEventListener('click', () => {
    if (reviewFlags[idea.id]?.status === 'remove') delete reviewFlags[idea.id];
    else setFlag(idea, 'remove', REMOVE_REASONS[0], reviewFlags[idea.id]?.note || '');
    saveFlags(); paint(); updateReviewStats();
  });
  fixBtn.addEventListener('click', () => {
    if (reviewFlags[idea.id]?.status === 'fix') delete reviewFlags[idea.id];
    else { setFlag(idea, 'fix', '', reviewFlags[idea.id]?.note || ''); setTimeout(() => noteInput.focus(), 0); }
    saveFlags(); paint(); updateReviewStats();
  });
  reasonSel.addEventListener('change', () => {
    if (reviewFlags[idea.id]) { reviewFlags[idea.id].reason = reasonSel.value; saveFlags(); }
  });
  noteInput.addEventListener('input', () => {
    if (reviewFlags[idea.id]) { reviewFlags[idea.id].note = noteInput.value; saveFlags(); }
  });

  paint();
  return card;
};

function setFlag(idea, status, reason, note) {
  reviewFlags[idea.id] = {
    status, reason, note,
    name: idea.name, found: idea.found, url: idea.url,
    at: new Date().toISOString()
  };
}

// ---------- Panel ----------

function reviewInit() {
  reviewInitDone = true;

  // Drop removal flags for ideas that are no longer in the database —
  // those have already been processed and taken off the site.
  const liveIds = new Set(ALL_IDEAS.map(i => i.id));
  let pruned = false;
  Object.keys(reviewFlags).forEach(id => {
    if (!liveIds.has(id)) { delete reviewFlags[id]; pruned = true; }
  });
  if (pruned) saveFlags();

  // Guru dropdown
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

function updateReviewStats() {
  const el = document.getElementById('review-stats');
  if (!el || ALL_IDEAS.length === 0) return;
  const newN = ALL_IDEAS.filter(isNew).length;
  const removeN = Object.values(reviewFlags).filter(f => f.status === 'remove').length;
  const fixN = Object.values(reviewFlags).filter(f => f.status === 'fix').length;
  el.innerHTML = `<span class="n-new">${newN} new</span> · <span class="n-flag">${removeN} flagged for removal</span> · <span class="n-fix">${fixN} need a fix</span>`;

  document.getElementById('review-copy-btn').disabled = (removeN + fixN) === 0;
  const bannerBtn = document.getElementById('review-banner-copy');
  bannerBtn.disabled = (removeN + fixN) === 0;
  bannerBtn.textContent = `Copy flagged list (${removeN + fixN})`;

  const seenEl = document.getElementById('review-seen-at');
  if (reviewSeenAt) {
    const d = new Date(reviewSeenAt);
    seenEl.textContent = `Last marked reviewed: ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
  } else {
    seenEl.textContent = 'Not marked reviewed yet — everything counts as new';
  }
}

document.getElementById('review-show').addEventListener('change', e => {
  reviewState.show = e.target.value; expandedId = null; render();
});
document.getElementById('review-group').addEventListener('change', e => {
  reviewState.groupBy = e.target.value; expandedId = null; render();
});
document.getElementById('review-guru').addEventListener('change', e => {
  reviewState.guru = e.target.value; expandedId = null; render();
});

// Two-click confirm (no browser pop-ups)
function confirmButton(btn, label, confirmLabel, action) {
  let armed = false, timer = null;
  btn.addEventListener('click', () => {
    if (!armed) {
      armed = true; btn.textContent = confirmLabel;
      timer = setTimeout(() => { armed = false; btn.textContent = label; }, 4000);
      return;
    }
    clearTimeout(timer); armed = false; btn.textContent = label;
    action();
  });
}

confirmButton(
  document.getElementById('review-mark-seen-btn'),
  'Mark all as reviewed', 'Click again to confirm',
  () => {
    reviewSeen = new Set(ALL_IDEAS.map(i => i.id));
    reviewSeenAt = new Date().toISOString();
    rSave(REVIEW_SEEN_KEY, [...reviewSeen]);
    rSave(REVIEW_SEEN_AT_KEY, reviewSeenAt);
    render();
  }
);

// ---------- Copy flagged list ----------

function buildFlagList() {
  const entries = Object.entries(reviewFlags);
  const removes = entries.filter(([, f]) => f.status === 'remove');
  const fixes = entries.filter(([, f]) => f.status === 'fix');
  const d = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const line = ([id, f]) => {
    let s = `- ${toTitleCase(f.name || id)} — ${f.found || ''}\n  id: ${id}`;
    if (f.url) s += `\n  video: ${f.url}`;
    if (f.note) s += `\n  note: ${f.note}`;
    return s;
  };

  let out = `SIDE HUSTLE INTEL — REVIEW LIST (${d})\n`;
  out += `${removes.length} to remove, ${fixes.length} to fix\n`;

  if (removes.length) {
    const byReason = new Map();
    removes.forEach(e => {
      const r = e[1].reason || 'Other';
      if (!byReason.has(r)) byReason.set(r, []);
      byReason.get(r).push(e);
    });
    REMOVE_REASONS.forEach(r => {
      if (!byReason.has(r)) return;
      const list = byReason.get(r);
      out += `\nREMOVE — ${r} (${list.length})\n` + list.map(line).join('\n') + '\n';
    });
  }
  if (fixes.length) {
    out += `\nFIX (${fixes.length})\n` + fixes.map(line).join('\n') + '\n';
  }
  return out;
}

const modal = document.getElementById('review-modal');
const modalText = document.getElementById('review-modal-text');
const modalCopyBtn = document.getElementById('review-modal-copy');

function openFlagList() {
  modalText.value = buildFlagList();
  modal.hidden = false;
  doCopy();
}
document.getElementById('review-copy-btn').addEventListener('click', openFlagList);
document.getElementById('review-banner-copy').addEventListener('click', openFlagList);
function doCopy() {
  const done = () => { modalCopyBtn.textContent = 'Copied ✓'; setTimeout(() => { modalCopyBtn.textContent = 'Copy again'; }, 1800); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(modalText.value).then(done, () => { modalText.select(); });
  } else {
    modalText.select();
  }
}
modalCopyBtn.addEventListener('click', doCopy);
document.getElementById('review-modal-close').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', e => { if (e.target === modal) modal.hidden = true; });

confirmButton(
  document.getElementById('review-modal-clear'),
  'Clear all flags', 'Click again to clear everything',
  () => {
    reviewFlags = {};
    saveFlags();
    modal.hidden = true;
    render();
  }
);
