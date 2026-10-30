// The gig browser (/tool/): gigs first, filters in a column on the left.
//
// Gigs show first; filters sit in a column on the left (a "Filters" button on phones).
// - Type of gig: tick one or more categories (none ticked = all).
// - Your situation: every ticked box narrows the list (same tags as the live tool).
// - Search: only gigs matching the words show, best match first.
// Links can preset everything: ?kind=products|services|audience, ?cat=slug[,slug],
// ?f=lowcost,nocamera, ?q=words, ?open=<gig id>.

const SITUATIONS = [
  { id: 'older', label: '50+ or retired' },
  { id: 'parent', label: 'Stay-at-home mom' },
  { id: 'health', label: 'Health limits' },
  { id: 'outside', label: 'Outside the US' },
  { id: 'lowcost', label: 'Low startup cost' },
  { id: 'nosales', label: 'No sales or cold calling' },
  { id: 'nocamera', label: 'Stay off camera' },
  { id: 'noinventory', label: 'No inventory or shipping' },
  { id: 'novisits', label: 'No client visits' },
  { id: 'noai', label: 'No AI needed' }
];
const SIT_LABEL = Object.fromEntries(SITUATIONS.map(s => [s.id, s.label]));
const PAGE = 30;

let ALL = [], SHUFFLED = [], pageIds = new Set(), LAST_N = 0;
// YouTube view counts by video ID, from /views.json (refreshed weekly by a GitHub Action).
let VIEWS = {}, VIEWS_DATE = '';
const st = { cats: new Set(), chips: new Set(), q: '', sort: 'shuffle', savedOnly: false, shown: PAGE, open: new Set(), pin: null, kind: '' };
let saved = new Set(loadSaved());
const $ = id => document.getElementById(id);

// ---------- Analytics (Google Analytics 4 events, same names as the old tool) ----------
function track(eventName, params) { try { if (typeof window.gtag === 'function') window.gtag('event', eventName, params || {}); } catch (e) {} }
function ideaParams(i) { return { idea_id: i.id, idea_name: shortTitle(i), creator: i.found || '', idea_category: i.category || '' }; }

function loadSaved() { try { return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]'); } catch (e) { return []; } }
function persistSaved() { try { localStorage.setItem(SAVED_KEY, JSON.stringify([...saved])); } catch (e) {} }

// ---------- Daily shuffle (same order all day, like the live tool) ----------
function mulberry32(seed) { return function () { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function dailySeed() { const d = new Date(); const s = `${d.getUTCFullYear()}${d.getUTCMonth()}${d.getUTCDate()}`; let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h; }
function shuffleWithSeed(arr, seed) { const r = mulberry32(seed), c = arr.slice(); for (let i = c.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [c[i], c[j]] = [c[j], c[i]]; } return c; }

// ---------- Search scoring (same as the live tool) ----------
function tokenize(s) { return (s || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
function stem(w) { if (w.length > 4 && w.endsWith('ies')) return w.slice(0, -3) + 'y'; if (w.length > 4 && w.endsWith('es')) return w.slice(0, -2); if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) return w.slice(0, -1); return w; }
function prefixLen(a, b) { const n = Math.min(a.length, b.length); let i = 0; while (i < n && a[i] === b[i]) i++; return i; }
function wordMatches(word, tok) { if (tok === word || stem(tok) === stem(word)) return true; if (tok.length >= 3 && word.length >= 3 && (tok.startsWith(word) || word.startsWith(tok))) return true; const s = Math.min(word.length, tok.length); return s >= 5 && prefixLen(word, tok) >= Math.ceil(s * 0.75); }
function fieldHas(toks, w) { return toks.some(t => wordMatches(w, t)); }
function scoreIdea(i, words) {
  const name = tokenize((i.title || '') + ' ' + i.name), cat = tokenize(i.category), src = tokenize(i.found || '');
  const tags = [...(i.tags || []), ...(i.situation_tags || []), ...(i.search_terms || [])].flatMap(tokenize);
  const body = tokenize([i.what, i.pitch, i.best, i.truth].join(' '));
  let s = 0;
  words.forEach(w => { if (fieldHas(name, w)) s += 4; if (fieldHas(tags, w)) s += 3; if (fieldHas(cat, w) || fieldHas(src, w)) s += 2; if (fieldHas(body, w)) s += 1; });
  const q = words.flatMap(tokenize);
  if (src.length && q.length && q.every(t => src.includes(t)) && (q.length >= 2 || src.every(t => q.includes(t)))) s += 1000;
  return s;
}

// ---------- Filtering ----------
function baseFiltered(skipCats) {
  let list = SHUFFLED;
  if (st.savedOnly) list = list.filter(i => saved.has(i.id));
  if (!skipCats && st.cats.size) list = list.filter(i => st.cats.has(i.category));
  if (st.chips.size) { const need = [...st.chips]; list = list.filter(i => need.every(c => hasTag(i, c))); }
  return list;
}
function results() {
  let list = baseFiltered(false);
  const words = st.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length) {
    let scored = list.map(i => ({ i, s: scoreIdea(i, words) })).filter(x => x.s > 0);
    const creatorHits = scored.filter(x => x.s >= 1000);
    if (creatorHits.length) scored = creatorHits;
    if (st.sort === 'shuffle' || st.sort === 'views') scored.sort((a, b) => b.s - a.s);
    else scored.sort((a, b) => byDate(a.i, b.i));
    list = scored.map(x => x.i);
    if (st.sort === 'views') list = byViews(list);
  } else if (st.sort === 'views') list = byViews(list);
  else if (st.sort !== 'shuffle') list = list.slice().sort(byDate);
  if (st.pin) { const k = list.findIndex(i => i.id === st.pin); if (k > 0) list = [list[k], ...list.slice(0, k), ...list.slice(k + 1)]; }
  return list;
}
// "Most viewed": highest view count first. One video can give several gigs (a
// "10 ideas" video gives up to 10), so they'd all share its count and fill the
// top of the list together. To spread them out, a video's 2nd gig ranks as if it
// had 1/2 the views, its 3rd 1/3, and so on. Gigs without a count go last.
function videoId(url) { const m = String(url || '').match(/(?:[?&]v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/); return m ? m[1] : ''; }
function viewsOf(i) { const v = VIEWS[videoId(i.url)]; return typeof v === 'number' ? v : -1; }
function byViews(list) {
  const seen = {};
  return list.map(i => { const id = videoId(i.url), k = (seen[id] = (seen[id] || 0) + 1), v = viewsOf(i); return { i, r: v < 0 ? -1 : v / k }; })
    .sort((a, b) => b.r - a.r).map(x => x.i);
}
function fmtViews(n) {
  if (n < 0) return '';
  const t = n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M'
    : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K' : String(n);
  return t + ' views';
}
function byDate(a, b) { const da = a.published || '', db = b.published || ''; if (!da && !db) return 0; if (!da) return 1; if (!db) return -1; return st.sort === 'oldest' ? da.localeCompare(db) : db.localeCompare(da); }

// ---------- Download saved gigs as a text file ----------
function gigText(i) {
  return `${shortTitle(i)}\n${sentenceCase(i.name)}\n${i.category} | ${i.cost}\nSource: ${i.found}${i.video_title ? ` · "${i.video_title}"` : ''} — ${i.url}\n\nWhat It Is\n${i.what}\n\nThe Pitch\n${i.pitch}\n\nWho It's Best For\n${i.best}\n\nThe Truth (as we see it)\n${i.truth}\n`;
}
function downloadSaved() {
  const list = ALL.filter(i => saved.has(i.id));
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

// ---------- Rendering ----------
function fmtDate(d) { if (!d) return ''; const dt = new Date(d + 'T00:00:00Z'); return isNaN(dt) ? '' : dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }); }
function sentenceCase(s) { s = String(s || '').trim(); return s.charAt(0).toUpperCase() + s.slice(1); }
// Line under the short title: the full name, unless it's already short (then it would just
// repeat the title), in which case the first sentence of "What it is".
function subLine(i) { return i.name.split(/\s+/).length > 6 ? sentenceCase(i.name) : oneLine(i.what); }
function oneLine(t) { const s = String(t || '').trim(); const m = s.match(/^.+?[.!?](?=\s|$)/); return m ? m[0] : s; }

function gigHtml(i) {
  const isOpen = st.open.has(i.id), isSaved = saved.has(i.id);
  const labels = [];
  if (!hasTag(i, 'nocamera')) labels.push('On camera');
  if (!hasTag(i, 'nosales')) labels.push('Sales or cold calling');
  const date = fmtDate(i.published);
  const views = fmtViews(viewsOf(i));
  const friendly = (CAT_BY_NAME[i.category] || {}).name || i.category;
  return `<article class="gig" data-id="${esc(i.id)}">
    <div class="gig-top">
      ${avatarHtml(i.found, 'av')}
      <div class="gig-body" data-act="toggle" role="button" tabindex="0" aria-expanded="${isOpen}">
        <h3>${esc(shortTitle(i))}</h3>
        <p class="one">${esc(subLine(i))}</p>
        <p class="meta">${esc(friendly)} · ${esc(shortCost(i.cost))} · ${esc(i.found)}${date ? ' · ' + esc(date) : ''}${views ? ` · <span title="YouTube views of the source video${VIEWS_DATE ? ', as of ' + esc(fmtDate(VIEWS_DATE)) : ''}">${esc(views)}</span>` : ''}</p>
        ${labels.length ? `<div class="labels">${labels.map(l => `<span class="label">${l}</span>`).join('')}</div>` : ''}
      </div>
      <div class="gig-actions">
        <button type="button" class="heart" data-act="save" aria-pressed="${isSaved}" aria-label="${isSaved ? 'Remove from saved' : 'Save this gig'}">${isSaved ? '♥' : '♡'}</button>
        <button type="button" class="more-btn" data-act="toggle" aria-expanded="${isOpen}">${isOpen ? 'Less ▴' : 'Details ▾'}</button>
      </div>
    </div>
    ${isOpen ? `<div class="details">
      <div><h4>What it is</h4><p>${esc(i.what)}</p></div>
      <div><h4>The pitch</h4><p>${esc(i.pitch)}</p></div>
      <div><h4>Who it's best for</h4><p>${esc(i.best)}</p></div>
      <div><h4>The Truth (as we see it)</h4><p>${esc(i.truth)}</p></div>
      <div class="foot">
        <a class="source-link" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.video_title || 'Watch the source video')} ↗</a>
        <button type="button" class="small-btn" data-act="copy">Copy this entire gig</button>
        ${pageIds.has(i.id) ? `<a href="/ideas/${encodeURIComponent(i.id)}/">Open on its own page →</a>` : ''}
      </div>
    </div>` : ''}
  </article>`;
}

function renderFilters() {
  const base = baseFiltered(true);
  $('cat-boxes').innerHTML = CATS.map(c => {
    const n = base.filter(i => i.category === c.cat).length;
    return `<label><input type="checkbox" data-cat="${esc(c.cat)}" ${st.cats.has(c.cat) ? 'checked' : ''}>${esc(c.name)}<span class="n">${n}</span></label>`;
  }).join('');
  $('sit-boxes').innerHTML = SITUATIONS.map(s =>
    `<label><input type="checkbox" data-chip="${s.id}" ${st.chips.has(s.id) ? 'checked' : ''}>${esc(s.label)}</label>`).join('');
}

function kindActive() {
  if (!st.kind || !KINDS[st.kind]) return false;
  const want = new Set(KINDS[st.kind].cats.map(s => CAT_BY_SLUG[s].cat));
  return want.size === st.cats.size && [...want].every(c => st.cats.has(c));
}
function heading() {
  if (st.savedOnly) return 'Your saved gigs';
  if (st.cats.size === 1) return CAT_BY_NAME[[...st.cats][0]].name + ' gigs';
  if (kindActive()) return KINDS[st.kind].name + ' gigs';
  return 'Work-at-home gigs';
}

function render() {
  const list = results();
  const n = list.length;
  $('heading').textContent = heading();
  const prev = $('count').dataset.n;
  $('count').innerHTML = `<strong>${n.toLocaleString()} gig${n === 1 ? '' : 's'}</strong> · tap any gig for the full write-up`;
  $('count').dataset.n = n;
  if (prev !== undefined && String(prev) !== String(n)) { const c = $('count'); c.classList.remove('flash'); void c.offsetWidth; c.classList.add('flash'); setTimeout(() => c.classList.remove('flash'), 50); }
  $('apply').textContent = n ? `Show ${n.toLocaleString()} gig${n === 1 ? '' : 's'}` : 'No gigs match';

  const act = [];
  if (st.savedOnly) {
    act.push(`<button type="button" class="chip-x" data-x="saved">Saved only ×</button>`);
    if (saved.size) act.push(`<button type="button" class="small-btn" data-x="download">Download my saved gigs</button>`);
  }
  if (st.q.trim()) act.push(`<button type="button" class="chip-x" data-x="q">“${esc(st.q.trim())}” ×</button>`);
  if (kindActive()) act.push(`<button type="button" class="chip-x" data-x="kind">${esc(KINDS[st.kind].name)} gigs ×</button>`);
  else st.cats.forEach(c => act.push(`<button type="button" class="chip-x" data-x="cat" data-v="${esc(c)}">${esc(CAT_BY_NAME[c].name)} ×</button>`));
  st.chips.forEach(c => act.push(`<button type="button" class="chip-x" data-x="chip" data-v="${c}">${esc(SIT_LABEL[c])} ×</button>`));
  if (act.length > 1) act.push(`<button type="button" class="clear" data-x="all">Clear all</button>`);
  $('active').innerHTML = act.join('');

  $('list').innerHTML = list.slice(0, st.shown).map(gigHtml).join('');
  $('empty').hidden = n > 0;
  $('empty').textContent = st.savedOnly ? 'No saved gigs yet. Tap the heart on any gig to save it.' : 'No gigs match all of these choices. Try removing one.';
  LAST_N = n;
  $('more').hidden = AUTO || n <= st.shown;
  $('saved-n').textContent = saved.size;
  renderFilters();
  syncUrl();
}

function syncUrl() {
  const p = new URLSearchParams();
  if (kindActive()) p.set('kind', st.kind);
  else if (st.cats.size) p.set('cat', [...st.cats].map(c => CAT_BY_NAME[c].slug).join(','));
  if (st.chips.size) p.set('f', [...st.chips].join(','));
  if (st.q.trim()) p.set('q', st.q.trim());
  const s = p.toString();
  try { history.replaceState(null, '', location.pathname + (s ? '?' + s : '')); } catch (e) {}
}

function changed() { st.pin = null; st.shown = PAGE; render(); }

// ---------- Events ----------
$('filters').addEventListener('change', e => {
  const t = e.target;
  if (t.dataset.cat) { t.checked ? st.cats.add(t.dataset.cat) : st.cats.delete(t.dataset.cat); st.kind = ''; }
  if (t.dataset.chip) t.checked ? st.chips.add(t.dataset.chip) : st.chips.delete(t.dataset.chip);
  changed();
  if (t.checked && t.dataset.cat) track('filter_category', { idea_category: t.dataset.cat, gigs_found: results().length });
  if (t.checked && t.dataset.chip) track('filter_chip', { chip: SIT_LABEL[t.dataset.chip], chips_on: st.chips.size, gigs_found: results().length });
});
$('active').addEventListener('click', e => {
  const b = e.target.closest('[data-x]'); if (!b) return;
  const x = b.dataset.x;
  if (x === 'download') { downloadSaved(); return; }
  if (x === 'saved') st.savedOnly = false;
  if (x === 'q') { st.q = ''; $('q').value = ''; }
  if (x === 'cat') { st.cats.delete(b.dataset.v); st.kind = ''; }
  if (x === 'chip') st.chips.delete(b.dataset.v);
  if (x === 'kind') { st.cats.clear(); st.kind = ''; }
  if (x === 'all') { st.savedOnly = false; st.q = ''; $('q').value = ''; st.cats.clear(); st.chips.clear(); st.kind = ''; }
  changed();
});
$('search-form').addEventListener('submit', e => {
  e.preventDefault(); st.q = $('q').value; st.savedOnly = false; changed(); $('q').blur();
  const q = st.q.trim().toLowerCase();
  if (q) { const n = results().length; track('search', { search_term: q, results_found: n ? 'yes' : 'no', match_count: n }); }
});
// Emptying the search box clears the search right away (no Enter needed), so a refresh doesn't bring it back.
$('q').addEventListener('input', () => {
  if (!$('q').value.trim() && st.q) { st.q = ''; changed(); }
});
$('sort').addEventListener('change', e => { st.sort = e.target.value; changed(); });
$('more').addEventListener('click', () => { st.shown += PAGE; render(); });
// Load the next 30 automatically as the visitor nears the bottom of the list (like the live tool).
// The button stays only as a fallback for very old browsers.
let AUTO = false;
if ('IntersectionObserver' in window) {
  AUTO = true;
  const io = new IntersectionObserver(entries => {
    if (!entries.some(e => e.isIntersecting) || !hasMore()) return;
    st.shown += PAGE; render();
    io.unobserve($('more-zone')); io.observe($('more-zone')); // re-check in case the screen still isn't full
  }, { rootMargin: '0px 0px 800px 0px' });
  io.observe($('more-zone'));
}
function hasMore() { return LAST_N > st.shown; }
$('saved-link').addEventListener('click', e => { e.preventDefault(); st.savedOnly = !st.savedOnly; changed(); window.scrollTo(0, 0); });
$('apply').addEventListener('click', () => {
  $('filters').classList.remove('open');
  $('filters-toggle').setAttribute('aria-expanded', 'false');
  $('filters-toggle').textContent = 'Filters';
  document.querySelector('.main').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
// Height of the locked top row, so the count bar and filters line up just below it.
function setHeaderHeight() { document.documentElement.style.setProperty('--hdr', document.querySelector('.results-head').offsetHeight + 'px'); }
// The filter column is only as tall as the screen space below where it currently sits,
// so its last boxes can always be scrolled into view (at the top of the page it sits lower).
function fitFilters() {
  const f = $('filters');
  if (window.innerWidth <= 860) { f.style.removeProperty('--fmax'); return; }
  const top = Math.max(f.getBoundingClientRect().top, 0);
  f.style.setProperty('--fmax', Math.max(window.innerHeight - top - 12, 240) + 'px');
}
setHeaderHeight();
fitFilters();
window.addEventListener('resize', () => { setHeaderHeight(); fitFilters(); });
window.addEventListener('scroll', fitFilters, { passive: true });
// A soft shadow under the count bar once it sticks to the top.
window.addEventListener('scroll', () => {
  const s = document.querySelector('.sticky-top');
  const hdr = window.innerWidth > 860 ? document.querySelector('.results-head').offsetHeight : 0;
  s.classList.toggle('stuck', s.getBoundingClientRect().top <= hdr + 1 && window.scrollY > 120);
}, { passive: true });
$('filters-toggle').addEventListener('click', () => {
  const open = $('filters').classList.toggle('open');
  $('filters-toggle').setAttribute('aria-expanded', String(open));
  $('filters-toggle').textContent = open ? 'Hide filters' : 'Filters';
});
$('list').addEventListener('click', e => {
  const b = e.target.closest('[data-act]');
  if (!b) {
    const link = e.target.closest('.source-link');
    if (link) { const i = ALL.find(x => x.id === link.closest('.gig').dataset.id); if (i) track('source_click', Object.assign(ideaParams(i), { link_url: i.url })); }
    return;
  }
  const id = b.closest('.gig').dataset.id;
  const idea = ALL.find(x => x.id === id);
  const act = b.dataset.act;
  if (act === 'toggle') { const opening = !st.open.has(id); opening ? st.open.add(id) : st.open.delete(id); render(); if (opening) track('view_idea', ideaParams(idea)); }
  if (act === 'save') { if (saved.has(id)) saved.delete(id); else { saved.add(id); track('save_idea', ideaParams(idea)); } persistSaved(); render(); }
  if (act === 'copy') {
    const i = ALL.find(x => x.id === id);
    const text = gigText(i);
    track('copy_idea', ideaParams(i));
    navigator.clipboard && navigator.clipboard.writeText(text).then(() => { b.textContent = 'Copied ✓'; setTimeout(() => { b.textContent = 'Copy this entire gig'; }, 1800); });
  }
});
$('list').addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.gig-body')) { e.preventDefault(); e.target.click(); }
});

// ---------- Start ----------
function applyParams() {
  let p; try { p = new URLSearchParams(location.search); } catch (e) { return; }
  const kind = (p.get('kind') || '').toLowerCase();
  if (KINDS[kind]) { st.kind = kind; KINDS[kind].cats.forEach(s => st.cats.add(CAT_BY_SLUG[s].cat)); }
  (p.get('cat') || '').toLowerCase().split(',').forEach(s => { if (CAT_BY_SLUG[s.trim()]) st.cats.add(CAT_BY_SLUG[s.trim()].cat); });
  (p.get('f') || '').split(',').forEach(f => { if (SIT_LABEL[f.trim()]) st.chips.add(f.trim()); });
  const q = (p.get('q') || '').trim(); if (q) { st.q = q; $('q').value = q; }
  const open = p.get('open'); if (open && ALL.some(i => i.id === open)) { st.open.add(open); st.pin = open; }
  if (q || open || st.cats.size || st.chips.size) track('link_landing', { search_term: q, idea_id: open || '', idea_category: [...st.cats].join(','), chips: [...st.chips].join(',') });
}

loadIdeas().then(data => {
  ALL = data;
  SHUFFLED = shuffleWithSeed(data, dailySeed());
  applyParams();
  render();
}).catch(() => { $('count').textContent = "Couldn't load the gigs. Try refreshing."; });

fetch('/views.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : {}).then(d => { VIEWS = d.views || {}; VIEWS_DATE = d.updated || ''; if (ALL.length) render(); }).catch(() => {});

fetch('/page-index.json').then(r => r.ok ? r.json() : { ideas: [] }).then(d => { pageIds = new Set(d.ideas || []); if (ALL.length) render(); }).catch(() => {});
