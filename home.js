// Home page script (index.html). app.js is kept for review.html.
//
// How the page narrows the list:
// - Situation chips ("About me" / "I want"). Every chip narrows: a gig shows
//   only if it carries every selected chip's tag in its `filters` array
//   (tags live in ideas.json, one array per idea).
// - Search. Only gigs that match the search words show, best match first.
// - The big "N gigs found" count always reflects the current list.

// ---------- Situation chips ----------
// id = the tag code stored in each idea's `filters` array.
const ABOUT = [
  { id: 'older', label: '50+ or retired' },
  { id: 'parent', label: 'Stay-at-home parent' },
  { id: 'health', label: 'Health limits' },
  { id: 'outside', label: 'Outside the US' }
];
const WANT = [
  { id: 'lowcost', label: 'Low startup cost' },
  { id: 'nosales', label: 'No sales or cold calling' },
  { id: 'nocamera', label: 'No camera' },
  { id: 'noinventory', label: 'No inventory or shipping' },
  { id: 'novisits', label: 'No client visits' },
  { id: 'noai', label: 'No AI needed' }
];
const CHIP_LABEL = Object.fromEntries([...ABOUT, ...WANT].map(c => [c.id, c.label]));

// ---------- Search weights (same as app.js) ----------
const WEIGHT_NAME = 4;
const WEIGHT_TAG = 3;
const WEIGHT_CATEGORY_OR_SOURCE = 2;
const WEIGHT_BODY = 1;
const WEIGHT_CREATOR_NAME = 1000;

const SAVED_KEY = 'shi_saved_gigs'; // same key as before, so visitors keep their saved gigs
const PAGE = 30;

// ---------- State ----------
let ALL_IDEAS = [];
let SHUFFLED = [];
let pageIds = new Set();
const st = { q: '', chips: new Set(), sort: 'shuffle', savedOnly: false, shown: PAGE, open: new Set(), pin: null };
let saved = new Set(loadSaved());
let lastMatched = null; // genuine search matches, for the same-creator note

const $ = id => document.getElementById(id);

// ---------- Analytics ----------
function track(eventName, params) {
  try { if (typeof window.gtag === 'function') window.gtag('event', eventName, params || {}); } catch (e) {}
}
function ideaParams(idea) {
  return { idea_id: idea.id, idea_name: toTitleCase(idea.name || ''), creator: idea.found || '', idea_category: idea.category || '' };
}

// ---------- Saved gigs ----------
function loadSaved() {
  try { const raw = localStorage.getItem(SAVED_KEY); return raw ? JSON.parse(raw) : []; } catch (e) { return []; }
}
function persistSaved() {
  try { localStorage.setItem(SAVED_KEY, JSON.stringify([...saved])); } catch (e) {}
}

// ---------- Daily shuffle (same order for everyone all day, changes at midnight UTC) ----------
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function dailySeed() {
  const d = new Date();
  const s = `${d.getUTCFullYear()}${d.getUTCMonth()}${d.getUTCDate()}`;
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}
function shuffleWithSeed(arr, seed) {
  const rand = mulberry32(seed);
  const c = arr.slice();
  for (let i = c.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [c[i], c[j]] = [c[j], c[i]]; }
  return c;
}

// ---------- Source video grouping ("One of N ideas covered in this video") ----------
const videoCounts = new Map();
function videoKey(url) {
  const m = (url || '').match(/(?:[?&]v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : (url || '');
}
function videoIdeaCount(idea) { return videoCounts.get(videoKey(idea.url)) || 1; }

// ---------- Search scoring (ported from app.js) ----------
function tokenize(str) { return (str || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
function stem(w) {
  if (w.length > 4 && w.endsWith('ies')) return w.slice(0, -3) + 'y';
  if (w.length > 4 && w.endsWith('es')) return w.slice(0, -2);
  if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) return w.slice(0, -1);
  return w;
}
function sharedPrefixLength(a, b) { const n = Math.min(a.length, b.length); let i = 0; while (i < n && a[i] === b[i]) i++; return i; }
function wordMatchesToken(word, token) {
  if (token === word) return true;
  if (stem(token) === stem(word)) return true;
  if (token.length >= 3 && word.length >= 3 && (token.startsWith(word) || word.startsWith(token))) return true;
  const shorter = Math.min(word.length, token.length);
  return shorter >= 5 && sharedPrefixLength(word, token) >= Math.ceil(shorter * 0.75);
}
function fieldMatches(tokens, word) { return tokens.some(t => wordMatchesToken(word, t)); }

let TOPIC_VOCAB = null;
function topicVocab() {
  if (TOPIC_VOCAB) return TOPIC_VOCAB;
  TOPIC_VOCAB = new Set();
  ALL_IDEAS.forEach(idea => {
    const own = new Set(tokenize(idea.found || ''));
    tokenize([idea.name, idea.category, idea.what, idea.pitch, idea.best, idea.truth,
      ...(idea.tags || []), ...(idea.situation_tags || []), ...(idea.search_terms || [])].join(' '))
      .forEach(t => { if (!own.has(t)) TOPIC_VOCAB.add(t); });
  });
  return TOPIC_VOCAB;
}
function creatorNameMatch(idea, words) {
  const src = tokenize(idea.found || '');
  const q = words.flatMap(tokenize);
  if (!src.length || !q.length) return false;
  if (!q.every(t => src.includes(t))) return false;
  if (q.length >= 2) return true;
  if (src.every(t => q.includes(t))) return true;
  return q[0].length >= 4 && !topicVocab().has(q[0]);
}
function scoreIdea(idea, words) {
  const nameT = tokenize(idea.name), catT = tokenize(idea.category), srcT = tokenize(idea.found || '');
  const tagT = (idea.tags || []).flatMap(tokenize);
  const sitT = (idea.situation_tags || []).flatMap(tokenize);
  const termT = (idea.search_terms || []).flatMap(tokenize);
  const bodyT = tokenize([idea.what, idea.pitch, idea.best, idea.truth].join(' '));
  let score = 0;
  words.forEach(w => {
    if (fieldMatches(nameT, w)) score += WEIGHT_NAME;
    if (fieldMatches(tagT, w) || fieldMatches(sitT, w) || fieldMatches(termT, w)) score += WEIGHT_TAG;
    if (fieldMatches(catT, w) || fieldMatches(srcT, w)) score += WEIGHT_CATEGORY_OR_SOURCE;
    if (fieldMatches(bodyT, w)) score += WEIGHT_BODY;
  });
  if (creatorNameMatch(idea, words)) score += WEIGHT_CREATOR_NAME;
  return score;
}
function compareByDate(a, b, sortBy) {
  const da = a.published || '', db = b.published || '';
  if (!da && !db) return 0;
  if (!da) return 1;
  if (!db) return -1;
  return sortBy === 'oldest' ? da.localeCompare(db) : db.localeCompare(da);
}

// ---------- The list ----------
function results() {
  let list = SHUFFLED;
  if (st.savedOnly) list = list.filter(i => saved.has(i.id));
  if (st.chips.size) {
    const need = [...st.chips];
    list = list.filter(i => { const f = i.filters || []; return need.every(c => f.includes(c)); });
  }
  const words = st.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  lastMatched = null;
  if (words.length) {
    let scored = list.map(i => ({ i, s: scoreIdea(i, words) })).filter(x => x.s > 0);
    // A creator-name search shows only that creator's gigs.
    const creatorHits = scored.filter(x => x.s >= WEIGHT_CREATOR_NAME);
    if (creatorHits.length) scored = creatorHits;
    if (st.sort === 'shuffle') scored.sort((a, b) => b.s - a.s);
    else scored.sort((a, b) => compareByDate(a.i, b.i, st.sort));
    list = scored.map(x => x.i);
    lastMatched = list;
  } else if (st.sort !== 'shuffle') {
    list = list.slice().sort((a, b) => compareByDate(a, b, st.sort));
  }
  // A gig opened from a link (?open=<id>) stays first until the visitor changes anything.
  if (st.pin) {
    const k = list.findIndex(i => i.id === st.pin);
    if (k > 0) list = [list[k], ...list.slice(0, k), ...list.slice(k + 1)];
  }
  return list;
}

// ---------- Card ----------
const HEART = '<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 7.9 3.6 4.5 7 4.5c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.4 0 5.6 3.4 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
const CHEV = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function slugifyProducer(name) { return (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60); }
function toTitleCase(str) {
  const minor = new Set(['a','an','the','and','but','or','nor','for','so','yet','at','by','in','of','on','to','up','as','is','it','vs']);
  const words = str.split(' ');
  return words.map((w, i) => {
    if (!w) return w;
    if (/^[A-Z0-9$]/.test(w) && w === w.toUpperCase() && /[A-Z]/.test(w)) return w;
    const lower = w.toLowerCase();
    if (i !== 0 && i !== words.length - 1 && minor.has(lower)) return lower;
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }).join(' ');
}
// First sentence of "What it is", shown as a one-line summary (the line is cut with … if long).
function oneLine(text) {
  const t = String(text || '').trim();
  const m = t.match(/^.+?[.!?](?=\s|$)/);
  return m ? m[0] : t;
}
function fmtDate(d) {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00Z');
  return isNaN(dt) ? '' : dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

function cardHtml(i) {
  const isSaved = saved.has(i.id), isOpen = st.open.has(i.id);
  const initials = (i.found || '?').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const date = fmtDate(i.published);
  const n = videoIdeaCount(i);
  const srcLabel = i.video_title || (/youtu/.test(i.url || '') ? 'Watch the video' : 'View the source');
  return `<article class="card" data-id="${esc(i.id)}">
    <div class="card-top">
      <img class="avatar card-toggle" data-act="details" src="assets/avatars/avatar-${esc(slugifyProducer(i.found))}.jpg" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">
      <div class="avatar-ph" aria-hidden="true" hidden>${esc(initials)}</div>
      <div class="card-body card-toggle" data-act="details" role="button" tabindex="0" aria-expanded="${isOpen}">
        <h3 class="card-title">${esc(toTitleCase(i.name || ''))}</h3>
        ${isOpen ? '' : `<p class="card-desc">${esc(oneLine(i.what))}</p>`}
        <p class="card-meta"><span class="cat">${esc(i.category)}</span> · ${esc(i.cost)}</p>
        <p class="card-src">${esc(i.found)}${date ? ' · ' + esc(date) : ''}</p>
      </div>
      <div class="card-actions">
        <button type="button" class="icon-btn save" data-act="save" aria-pressed="${isSaved}" aria-label="${isSaved ? 'Remove from saved' : 'Save this gig'}" title="${isSaved ? 'Saved' : 'Save'}">${HEART}</button>
        <button type="button" class="details-btn" data-act="details" aria-expanded="${isOpen}"><span class="lbl">Details</span>${CHEV}</button>
      </div>
    </div>
    ${isOpen ? `<div class="details">
      <div><h4>What it is</h4><p>${esc(i.what)}</p></div>
      <div><h4>The pitch</h4><p>${esc(i.pitch)}</p></div>
      <div><h4>Best for</h4><p>${esc(i.best)}</p></div>
      <div><h4>The truth</h4><p>${esc(i.truth)}</p></div>
      <div><h4>Source</h4><p>${esc(i.found)} · <a class="source-link" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(srcLabel)}&nbsp;&#8599;</a></p>${n > 1 ? `<p class="source-note">One of ${n} ideas covered in this video</p>` : ''}</div>
      <div class="details-foot"><button type="button" class="small-btn" data-act="copy">Copy this entire gig</button>${pageIds.has(i.id) ? `<a href="ideas/${encodeURIComponent(i.id)}/">Open on its own page to share or bookmark &rarr;</a>` : ''}</div>
    </div>` : ''}
    <div class="card-foot"><button type="button" class="expand-link" data-act="details" aria-expanded="${isOpen}">${isOpen ? 'Show less <span aria-hidden="true">▴</span>' : 'Show full details <span aria-hidden="true">▾</span>'}</button></div>
  </article>`;
}

// ---------- Render ----------
function render() {
  const list = results();
  const n = list.length.toLocaleString();
  const plural = list.length === 1 ? '' : 's';
  $('found').innerHTML = st.savedOnly ? `${n} <small>saved gig${plural}</small>` : `${n} <small>gig${plural} found</small>`;

  let line = '';
  if (st.savedOnly) line = `Showing your saved gigs<button type="button" class="linkish" id="back-all">Back to all gigs</button>`;
  else if (st.q.trim() || st.chips.size) line = `Filters on<button type="button" class="linkish" id="clear-all">Clear all</button>`;
  $('count').innerHTML = line;

  $('list').innerHTML = list.slice(0, st.shown).map(cardHtml).join('');
  $('empty').hidden = list.length > 0;
  $('empty').textContent = st.savedOnly ? 'No saved gigs yet. Tap the heart on any gig to save it.' : 'No gigs match.';
  $('more').hidden = list.length <= st.shown;
  $('q-clear').hidden = !$('q').value;
  updateSavedUI();
  updateSameProducerNote();

  const back = $('back-all'); if (back) back.onclick = () => { st.savedOnly = false; reset(); };
  const clr = $('clear-all'); if (clr) clr.onclick = () => { st.q = ''; $('q').value = ''; st.chips.clear(); syncChips(); reset(); };
}
// Links from creator pages and outreach emails can open the tool with a
// search already run (?q=Adam%20Enfroy) and one gig opened first (&open=<id>).
function applyLinkParams() {
  let p;
  try { p = new URLSearchParams(location.search); } catch (e) { return; }
  const q = (p.get('q') || '').trim();
  const open = p.get('open');
  if (q) { st.q = q; $('q').value = q; }
  if (open && ALL_IDEAS.some(i => i.id === open)) { st.open.add(open); st.pin = open; }
  if (q || open) track('link_landing', { search_term: q, idea_id: open || '' });
}

function reset() { st.pin = null; st.shown = PAGE; render(); }

// A reminder that a creator search shows our sample, not their whole channel.
function updateSameProducerNote() {
  const note = $('same-producer-note');
  const basis = lastMatched;
  if (!basis || !basis.length) { note.hidden = true; return; }
  const who = basis[0].found;
  if (who && basis.every(i => i.found === who)) {
    note.hidden = false;
    note.textContent = `${basis.length} entr${basis.length === 1 ? 'y' : 'ies'} from ${who} in our database — not their full upload history.`;
  } else note.hidden = true;
}

function updateSavedUI() {
  $('saved-n').textContent = saved.size;
  const none = saved.size === 0;
  $('s-view').disabled = $('s-download').disabled = $('s-clear').disabled = none;
  $('s-view').textContent = st.savedOnly ? 'Showing saved' : 'Show saved';
}

function buildChips(target, defs) {
  $(target).innerHTML = defs.map(c => `<button type="button" class="chip" data-chip="${c.id}" aria-pressed="false">${esc(c.label)}<span class="x" aria-hidden="true">×</span></button>`).join('');
}
function syncChips() { document.querySelectorAll('.chip').forEach(b => b.setAttribute('aria-pressed', String(st.chips.has(b.dataset.chip)))); }

function toast(msg) {
  const t = $('toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 2600);
}

function gigText(i) {
  const n = videoIdeaCount(i);
  return `${toTitleCase(i.name)}\n${i.category} | ${i.cost}\nSource: ${i.found}${i.video_title ? ` · "${i.video_title}"` : ''} — ${i.url}${n > 1 ? ` (one of ${n} ideas in this video)` : ''}\n\nWhat It Is\n${i.what}\n\nThe Pitch\n${i.pitch}\n\nBest For\n${i.best}\n\nThe Truth\n${i.truth}\n`;
}

function downloadSaved() {
  const list = ALL_IDEAS.filter(i => saved.has(i.id));
  if (!list.length) return;
  track('download_saved', { saved_count: list.length });
  const body = list.map(gigText).join('\n' + '-'.repeat(40) + '\n\n');
  const header = `Side Hustle Intel — Saved Gigs\nExported ${new Date().toLocaleString()}\n\n${'='.repeat(40)}\n\n`;
  const url = URL.createObjectURL(new Blob([header + body], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `side-hustle-intel-saved-gigs-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.txt`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- Wiring ----------
let searchTrackTimer;
function applySearch(value, fromSubmit) {
  st.q = value; st.savedOnly = false; reset();
  clearTimeout(searchTrackTimer);
  const q = value.trim().toLowerCase();
  if (!q) return;
  const send = () => track('search', { search_term: q, results_found: lastMatched && lastMatched.length ? 'yes' : 'no', match_count: lastMatched ? lastMatched.length : 0 });
  if (fromSubmit) send(); else searchTrackTimer = setTimeout(send, 1500); // only log a typed search once typing pauses
}

function wire() {
  buildChips('chips-me', ABOUT);
  buildChips('chips-want', WANT);

  document.querySelector('.finder').addEventListener('click', e => {
    const b = e.target.closest('.chip'); if (!b) return;
    const id = b.dataset.chip;
    const on = !st.chips.has(id);
    on ? st.chips.add(id) : st.chips.delete(id);
    st.savedOnly = false; syncChips(); reset();
    if (on) track('filter_chip', { chip: CHIP_LABEL[id], chips_on: st.chips.size, gigs_found: results().length });
  });

  let deb;
  $('q').addEventListener('input', () => { clearTimeout(deb); $('q-clear').hidden = !$('q').value; deb = setTimeout(() => applySearch($('q').value, false), 250); });
  $('search-form').addEventListener('submit', e => { e.preventDefault(); clearTimeout(deb); applySearch($('q').value, true); $('q').blur(); });
  $('q-clear').onclick = () => { $('q').value = ''; st.q = ''; reset(); $('q').focus(); };
  $('sort').onchange = e => { st.sort = e.target.value; reset(); };
  $('more-btn').onclick = () => { st.shown += PAGE; render(); };

  $('list').addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) {
      const link = e.target.closest('.source-link');
      if (link) { const idea = ALL_IDEAS.find(x => x.id === link.closest('.card').dataset.id); if (idea) track('source_click', Object.assign(ideaParams(idea), { link_url: idea.url })); }
      return;
    }
    const card = btn.closest('.card');
    const id = card.dataset.id;
    const idea = ALL_IDEAS.find(x => x.id === id);
    if (!idea) return;
    const act = btn.dataset.act;
    if (act === 'save') {
      if (saved.has(id)) saved.delete(id); else { saved.add(id); track('save_idea', ideaParams(idea)); }
      persistSaved();
      if (st.savedOnly) { render(); return; }
      card.outerHTML = cardHtml(idea);
      updateSavedUI();
    } else if (act === 'details') {
      const opening = !st.open.has(id);
      opening ? st.open.add(id) : st.open.delete(id);
      card.outerHTML = cardHtml(idea);
      if (opening) track('view_idea', ideaParams(idea));
    } else if (act === 'copy') {
      track('copy_idea', ideaParams(idea));
      try { navigator.clipboard.writeText(gigText(idea)).then(() => toast('Gig copied to clipboard'), () => toast('Your browser blocked copying')); }
      catch (err) { toast('Your browser blocked copying'); }
    }
  });

  $('s-view').onclick = () => { st.savedOnly = true; reset(); window.scrollTo({ top: 0 }); };
  $('s-download').onclick = downloadSaved;
  $('s-clear').onclick = () => { $('s-confirm').hidden = false; $('s-clear').hidden = true; };
  $('s-no').onclick = () => { $('s-confirm').hidden = true; $('s-clear').hidden = false; };
  $('s-yes').onclick = () => { saved.clear(); persistSaved(); $('s-confirm').hidden = true; $('s-clear').hidden = false; render(); toast('All saved gigs deselected'); };
  // Enter/Space on a focused card title opens it, like a click.
  $('list').addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.card-body[data-act]')) { e.preventDefault(); e.target.click(); }
  });
}

wire();

fetch('ideas.json')
  .then(r => r.json())
  .then(data => {
    ALL_IDEAS = data;
    data.forEach(i => { const k = videoKey(i.url); videoCounts.set(k, (videoCounts.get(k) || 0) + 1); });
    SHUFFLED = shuffleWithSeed(data, dailySeed());
    applyLinkParams();
    render();
  })
  .catch(err => { $('found').textContent = 'Couldn\'t load the gigs. Try refreshing.'; console.error(err); });

fetch('page-index.json')
  .then(r => (r.ok ? r.json() : { ideas: [] }))
  .then(d => { pageIds = new Set(d.ideas || []); if (ALL_IDEAS.length) render(); })
  .catch(() => {});
