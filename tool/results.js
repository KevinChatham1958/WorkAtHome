// The gig browser (/tool/): gigs first, filters in a column on the left.
//
// Gigs show first; filters sit in a column on the left (a "Filters" button on phones).
// - What interests you?: popular topics plus the 7 types, one choice at a time (none = all).
//   Homepage ?kind= links can still preset a group of types.
// - Your situation: every ticked box narrows the list (same tags as the live tool).
// - Popular topics: one-tap topic buttons, one at a time; they add to the Type of gig choices.
// - Search: only gigs matching the words show, best match first. The search box stands
//   alone: searching clears the filters, and ticking a filter clears the search.
// Links can preset everything: ?kind=products|services|audience, ?cat=slug[,slug],
// ?topic=thrift[,etsy], ?f=lowcost,nocamera, ?q=words, ?open=<gig id>, ?sort=newest.

const SITUATIONS = [
  { id: 'older', label: '50+ or retired' },
  { id: 'parent', label: 'Stay-at-home mom' },
  { id: 'health', label: 'Health limits' },
  { id: 'outside', label: 'Outside the US' },
  { id: 'lowcost', label: 'Under $100 to start' },
  { id: 'nosales', label: 'No sales or cold calling' },
  { id: 'nocamera', label: 'Stay off camera' },
  { id: 'noinventory', label: 'No inventory or shipping' },
  { id: 'novisits', label: 'No client visits' },
  { id: 'noai', label: 'No AI needed' }
];
const SIT_LABEL = Object.fromEntries(SITUATIONS.map(s => [s.id, s.label]));

// Popular topics (Nov 9, 2026, Kevin): one-tap buttons for the topics creators cover most.
// A gig belongs to a topic when its short title, full name or tags match `re` (thrift uses
// title + tags only) and don't match `not` (unless they match `keep`). This keeps software
// "reseller" gigs out of Thrift & flipping, for example. New gigs are sorted in automatically.
// To add a topic: add a line here; ?topic=<id> links work straight away.
const TOPICS = [
  { id: 'thrift', label: 'Thrift & flipping', tagsOnly: true,
    re: /thrift|goodwill|garage[- ]sale|yard[- ]sale|flea market|estate sale|liquidation|pallet|retail arbitrage|reselling|resale|resell|flipping|used (?:book|media|phone|parts|goods|electronics)|ebay|poshmark|depop|mercari|vinted|whatnot|secondhand|second-hand|sports card|sell stuff|declutter/,
    not: /saas|software|receptionist|voice agent|white[- ]label|domain|brand deal|affiliate|freelance|ppc|digital product|cleaning|ai video|private label|wholesale|authorization|blank apparel|food resale|upcycl|print on demand|woodworking/,
    keep: /used book|used media|book flipping|liquidation/ },
  { id: 'etsy', label: 'Etsy & crafts', re: /etsy|handmade|crochet|knit|candle|jewelry|sewing|woodwork|resin|\bcrafts?\b|crafting|upcycl|soap/ },
  { id: 'kdp', label: 'Amazon KDP', re: /\bkdp\b|kindle|low[- ]content|coloring book|activity book|puzzle book|self[- ]publish|amazon book|children'?s book|kids'? book|journal publishing|publishing on amazon/, not: /book funnel|lead magnet/ },
  { id: 'pod', label: 'Print-on-demand', re: /print[- ]on[- ]demand|\bpod\b|printify|printful|merch by amazon|redbubble|teespring|spreadshirt|t-?shirt|custom mug|tote bag|apparel design/, not: /\bkdp\b|kindle|coloring book|low[- ]content|blank apparel/ },
  { id: 'faceless', label: 'Faceless YouTube', re: /faceless (?:youtube|channel|video)|youtube automation|cash cow|faceless.*youtube|youtube.*faceless/ },
  { id: 'affiliate', label: 'Affiliate marketing', re: /affiliate/ },
  { id: 'coaching', label: 'Coaching & courses', re: /coach|online course|course creat|udemy|cohort|teach(?:ing)? online|membership|skool/ },
  { id: 'dropship', label: 'Dropshipping', re: /dropship|drop[- ]ship/ }
];
const TOPIC_BY_ID = Object.fromEntries(TOPICS.map(t => [t.id, t]));
function inTopic(i, id) {
  if (!i._t) {
    const full = [i.title, i.name, (i.tags || []).join(' | ')].join(' | ').toLowerCase();
    const short = [i.title, (i.tags || []).join(' | ')].join(' | ').toLowerCase();
    i._t = new Set(TOPICS.filter(t => { const x = t.tagsOnly ? short : full; return t.re.test(x) && (!t.not || !t.not.test(x) || (t.keep && t.keep.test(x))); }).map(t => t.id));
  }
  return i._t.has(id);
}
const PAGE = 30;

let ALL = [], SHUFFLED = [], pageIds = new Set(), LAST_N = 0;
// YouTube view counts by video ID, from /views.json (refreshed weekly by a GitHub Action).
let VIEWS = {}, VIEWS_DATE = '';
const st = { cats: new Set(), topics: new Set(), chips: new Set(), q: '', sort: 'shuffle', savedOnly: false, shown: PAGE, open: new Set(), pin: null, kind: '' };
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

// ---------- Search (rebuilt Nov 5, 2026 after the CRO review) ----------
// Every meaningful word must appear somewhere in the gig (falls back to "any word" only
// when that finds nothing). Filler words are ignored. Whole words and stems match; a
// search word of 4+ letters also matches longer words starting with it ("edit" → "editing"),
// but never the other way ("bookkeeping" does not match "book"). Gigs whose title or name
// contain the words rank first.
const STOP = new Set(['a','an','the','and','or','to','for','on','in','of','with','no','my','i','me','from','at','by','is','it','as','be','you','your','how','what','that','this','do','can','gig','gigs','idea','ideas','side','hustle','hustles','job','jobs','work','home','online','make','money']);
function tokenize(s) { return (s || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
function stem(w) { if (w.length > 4 && w.endsWith('ies')) return w.slice(0, -3) + 'y'; if (w.length > 4 && w.endsWith('es')) return w.slice(0, -2); if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) return w.slice(0, -1); return w; }
function prefixLen(a, b) { const n = Math.min(a.length, b.length); let i = 0; while (i < n && a[i] === b[i]) i++; return i; }
function wordMatches(word, tok) {
  if (tok === word || stem(tok) === stem(word)) return true;
  if (word.length >= 4 && tok.startsWith(word)) return true;
  // Word-family endings ("retired" ~ "retirees", "bookkeeping" ~ "bookkeeper"), never short roots.
  const p = prefixLen(word, tok);
  return p >= 6 && p >= 0.8 * Math.min(word.length, tok.length);
}
// Budget searches ("no money", "free", "cheap", "low budget"...) mean gigs that cost little to start.
const BUDGET_Q = /^(?:(?:no|low|little|zero|without|small|tiny|minimal|cheap)\s+(?:money|cost|costs|budget|investment|capital|startup|start ?up)|free|cheap|\$0|no investment needed|with no money)$/;
const BUDGET_COST = /^(?:free|\$0|zero|none|no |near[- ]zero|very low|minimal|almost nothing)/i;
function fieldHas(toks, w) { return toks.some(t => wordMatches(w, t)); }
function queryWords(q) {
  const all = tokenize(q);
  const kept = all.filter(w => !STOP.has(w));
  return kept.length ? kept : all; // a search made only of filler words still searches them
}
function fields(i) {
  if (!i._f) i._f = {
    title: tokenize(i.title || ''), name: tokenize(i.name), cat: tokenize(i.category + ' ' + ((CAT_BY_NAME[i.category] || {}).name || '')),
    src: tokenize(i.found || ''), tags: [...(i.tags || []), ...(i.situation_tags || []), ...(i.search_terms || [])].flatMap(tokenize),
    body: tokenize([i.what, i.pitch, i.best, i.truth].join(' ')),
    text: ((i.title || '') + ' ' + i.name).toLowerCase()
  };
  return i._f;
}
function scoreIdea(i, words, phrase, needAll) {
  const f = fields(i);
  let s = 0, hits = 0;
  words.forEach(w => {
    let h = 0;
    if (fieldHas(f.title, w)) h += 10;
    if (fieldHas(f.name, w)) h += 6;
    if (fieldHas(f.tags, w)) h += 4;
    if (fieldHas(f.cat, w) || fieldHas(f.src, w)) h += 3;
    if (fieldHas(f.body, w)) h += 1;
    if (h) hits++;
    s += h;
  });
  if (needAll && hits < words.length) return 0;
  if (phrase && words.length > 1 && f.text.includes(phrase)) s += 40;
  else if (phrase && words.length > 1 && [i.what, i.pitch, i.best].join(' ').toLowerCase().includes(phrase)) s += 15;
  // Searching a creator's name shows that creator's gigs.
  if (f.src.length && words.length && words.every(t => f.src.includes(t)) && (words.length >= 2 || f.src.every(t => words.includes(t)))) s += 1000;
  return s;
}

// ---------- Filtering ----------
function baseFiltered(skipCats) {
  let list = SHUFFLED;
  // Saved view shows every saved gig, whatever filters or search are on (Nov 5, 2026 fix).
  if (st.savedOnly) return list.filter(i => saved.has(i.id));
  // Popular topics and Type of gig add together ("what interests you?"); Your situation narrows.
  if (!skipCats && (st.cats.size || st.topics.size)) { const tp = [...st.topics]; list = list.filter(i => st.cats.has(i.category) || tp.some(t => inTopic(i, t))); }
  if (st.chips.size) { const need = [...st.chips]; list = list.filter(i => need.every(c => hasTag(i, c))); }
  return list;
}
function results() {
  let list = baseFiltered(false);
  const q = st.savedOnly ? '' : st.q.trim().toLowerCase();
  st.loose = false; st.budget = BUDGET_Q.test(q);
  if (st.budget) return list.filter(i => i.cost_level ? i.cost_level === 'Under $100' : BUDGET_COST.test(String(i.cost || '').trim()));
  const words = queryWords(q);
  if (words.length) {
    const phrase = words.join(' ');
    let scored = list.map(i => ({ i, s: scoreIdea(i, words, phrase, true) })).filter(x => x.s > 0);
    if (!scored.length && words.length > 1) { scored = list.map(i => ({ i, s: scoreIdea(i, words, phrase, false) })).filter(x => x.s > 0); st.loose = scored.length > 0; }
    const creatorHits = scored.filter(x => x.s >= 1000);
    if (creatorHits.length) scored = creatorHits;
    // Best match first whatever the sort; the sort only breaks ties.
    const tie = st.sort === 'views' ? (a, b) => viewsOf(b.i) - viewsOf(a.i) : (st.sort === 'newest' || st.sort === 'oldest') ? (a, b) => byDate(a.i, b.i) : () => 0;
    scored.sort((a, b) => (b.s - a.s) || tie(a, b));
    list = scored.map(x => x.i);
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
  return `<article class="gig${isOpen ? ' is-open' : ''}" data-id="${esc(i.id)}">
    <div class="gig-top">
      ${avatarHtml(i.found, 'av')}
      <div class="gig-body" data-act="toggle" role="button" tabindex="0" aria-expanded="${isOpen}">
        <h3>${esc(shortTitle(i))}</h3>
        <p class="one">${esc(subLine(i))}</p>
        <p class="meta">${esc(friendly)} · ${esc(costLabel(i))} · ${esc(i.found)}${date ? ' · ' + esc(date) : ''}${views ? ` · <span title="YouTube views of the source video${VIEWS_DATE ? ', as of ' + esc(fmtDate(VIEWS_DATE)) : ''}">${esc(views)}</span>` : ''}</p>
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
      <div class="truth-box"><h4>The Truth (as we see it)</h4><p>${esc(i.truth)}</p><p class="truth-note">Our assessment, based on the video and what&rsquo;s typical across similar videos. We don&rsquo;t independently verify income claims or prices.</p></div>
      <div class="foot">
        <p class="source-line"><span class="source-label">${/youtu/.test(i.url || '') ? 'Watch the source video on YouTube:' : 'Watch the source video:'}</span> <a class="source-link" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.video_title || 'Watch on YouTube')} ↗</a></p>
        <button type="button" class="small-btn" data-act="copy">Copy this entire gig</button>
        ${pageIds.has(i.id) ? `<p class="own-page" style="flex-basis:100%;margin:0"><a href="/ideas/${encodeURIComponent(i.id)}/" target="_blank" rel="noopener">Open this gig on its own page ↗</a></p>` : ''}
      </div>
    </div>` : ''}
  </article>`;
}

function renderFilters() {
  const base = baseFiltered(true);
  $('topic-btns').innerHTML = TOPICS.map(t => {
    const n = base.filter(i => inTopic(i, t.id)).length;
    return `<button type="button" class="topic-btn" data-topic="${t.id}" aria-pressed="${st.topics.has(t.id)}">${esc(t.label)}<span class="n">${n}</span></button>`;
  }).join('');
  $('cat-boxes').innerHTML = CATS.map(c => {
    const n = base.filter(i => i.category === c.cat).length;
    return `<button type="button" class="topic-btn" data-cat="${esc(c.cat)}" aria-pressed="${st.cats.has(c.cat)}">${esc(c.name)}<span class="n">${n}</span></button>`;
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
  if (st.q.trim()) return `Gigs matching “${st.q.trim()}”`;
  if (st.topics.size === 1 && !st.cats.size) return TOPIC_BY_ID[[...st.topics][0]].label + ' gigs';
  if (st.topics.size) return 'Work-at-home gigs';
  if (st.cats.size === 1) return CAT_BY_NAME[[...st.cats][0]].name + ' gigs';
  if (kindActive()) return KINDS[st.kind].name + ' gigs';
  return 'Work-at-home gigs';
}

function render() {
  const list = results();
  const n = list.length;
  $('heading').textContent = heading();
  const prev = $('count').dataset.n;
  // Oct 30, 2026 (Kevin): make an active search or filter impossible to miss, with a one-click way out.
  const gigsTxt = `<strong>${n.toLocaleString()} gig${n === 1 ? '' : 's'}</strong>`;
  const narrowed = st.cats.size || st.topics.size || st.chips.size;
  if (st.savedOnly) $('count').innerHTML = `${gigsTxt} saved · <button type="button" class="count-clear" data-clear="saved">Back to all gigs</button>`;
  else if (st.q.trim() && st.budget) $('count').innerHTML = `Showing ${gigsTxt} that cost under $100 to start${narrowed ? ', with your filters' : ''} · <button type="button" class="count-clear" data-clear="q">Clear search</button>`;
  else if (st.q.trim() && st.loose) $('count').innerHTML = `No gig mentions every word of “${esc(st.q.trim())}”. Showing ${gigsTxt} that match some of them · <button type="button" class="count-clear" data-clear="q">Clear search</button>`;
  else if (st.q.trim()) $('count').innerHTML = `Showing ${gigsTxt} for “${esc(st.q.trim())}”${narrowed ? ' with your filters' : ''} (of ${ALL.length.toLocaleString()}) · <button type="button" class="count-clear" data-clear="q">Clear search</button>`;
  else if (narrowed) $('count').innerHTML = `Showing ${gigsTxt} that ${n === 1 ? 'matches' : 'match'} your choices (of ${ALL.length.toLocaleString()}) · <button type="button" class="count-clear" data-clear="all">Clear all</button>`;
  else $('count').innerHTML = `${gigsTxt} · tap any gig for the full write-up`;
  $('count').dataset.n = n;
  if (prev !== undefined && String(prev) !== String(n)) { const c = $('count'); c.classList.remove('flash'); void c.offsetWidth; c.classList.add('flash'); setTimeout(() => c.classList.remove('flash'), 50); }
  $('apply').textContent = n ? `Show ${n.toLocaleString()} gig${n === 1 ? '' : 's'}` : 'No gigs match';

  const act = [];
  if (st.savedOnly) {
    act.push(`<button type="button" class="chip-x" data-x="saved">Saved only ×</button>`);
    if (saved.size) act.push(`<button type="button" class="small-btn" data-x="download">Download my saved gigs</button>`);
  }
  if (st.q.trim()) act.push(`<button type="button" class="chip-x" data-x="q">“${esc(st.q.trim())}” ×</button>`);
  st.topics.forEach(t => act.push(`<button type="button" class="chip-x" data-x="topic" data-v="${t}">${esc(TOPIC_BY_ID[t].label)} ×</button>`));
  if (kindActive()) act.push(`<button type="button" class="chip-x" data-x="kind">${esc(KINDS[st.kind].name)} gigs ×</button>`);
  else st.cats.forEach(c => act.push(`<button type="button" class="chip-x" data-x="cat" data-v="${esc(c)}">${esc(CAT_BY_NAME[c].name)} ×</button>`));
  st.chips.forEach(c => act.push(`<button type="button" class="chip-x" data-x="chip" data-v="${c}">${esc(SIT_LABEL[c])} ×</button>`));
  // "Clear all" here only when the count line above doesn't already offer it.
  if (act.length > 1 && st.q.trim() && !st.savedOnly) act.push(`<button type="button" class="clear" data-x="all">Clear all</button>`);
  $('active').innerHTML = act.join('');

  if (SIGNUP && SIGNUP.parentNode === $('list')) SIGNUP.remove();
  $('list').innerHTML = list.slice(0, st.shown).map(gigHtml).join('');
  $('empty').hidden = n > 0;
  $('empty').innerHTML = st.savedOnly ? 'No saved gigs yet. Tap the heart on any gig to save it.'
    : st.q.trim() ? `No gigs mention “${esc(st.q.trim())}”. Try a broader word like “writing”, “Etsy” or “assistant”, or <a href="/quiz/">take the quiz</a>.`
    : 'No gigs match all of these choices. Try removing one.';
  placeSignup(n);
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
  if (st.topics.size) p.set('topic', [...st.topics].join(','));
  if (st.chips.size) p.set('f', [...st.chips].join(','));
  if (st.q.trim()) p.set('q', st.q.trim());
  const s = p.toString();
  try { history.replaceState(null, '', location.pathname + (s ? '?' + s : '')); } catch (e) {}
}

// The weekly-email box sits after the 5th gig (Nov 5, 2026: before, it pushed every gig
// below the first screen on phones). With fewer gigs it goes after the last one.
const SIGNUP = document.querySelector('form.signup[data-src="tool"]');
function placeSignup(n) {
  if (!SIGNUP) return;
  const cards = $('list').querySelectorAll(':scope > .gig');
  SIGNUP.hidden = st.savedOnly || n === 0;
  if (cards.length >= 5) cards[4].after(SIGNUP); else $('list').appendChild(SIGNUP);
}

function changed() { st.pin = null; st.shown = PAGE; render(); }

// ---------- Events ----------
// Nov 9, 2026 (Kevin): the search box stands alone. Ticking any filter clears the search,
// and running a search clears every filter, so the two never quietly narrow each other.
function clearSearch() { st.q = ''; $('q').value = ''; }
function clearBoxes() { st.cats.clear(); st.topics.clear(); st.chips.clear(); st.kind = ''; }
// "What interests you?" (Kevin, Nov 10): topics and types are one section, one choice at a time.
// Picking any button replaces the current topic or type; tapping it again turns it off.
$('filters').addEventListener('click', e => {
  const b = e.target.closest('button[data-topic], button[data-cat]'); if (!b) return;
  const id = b.dataset.topic, cat = b.dataset.cat;
  const on = id ? !st.topics.has(id) : !(st.cats.size === 1 && st.cats.has(cat) && !st.kind);
  st.topics.clear(); st.cats.clear(); st.kind = '';
  if (on) id ? st.topics.add(id) : st.cats.add(cat);
  st.savedOnly = false; clearSearch(); changed();
  if (on && id) track('filter_topic', { topic: TOPIC_BY_ID[id].label, gigs_found: results().length });
  if (on && cat) track('filter_category', { idea_category: cat, gigs_found: results().length });
});
$('filters').addEventListener('change', e => {
  const t = e.target;
  st.savedOnly = false; clearSearch();
  if (t.dataset.chip) t.checked ? st.chips.add(t.dataset.chip) : st.chips.delete(t.dataset.chip);
  changed();
  if (t.checked && t.dataset.chip) track('filter_chip', { chip: SIT_LABEL[t.dataset.chip], chips_on: st.chips.size, gigs_found: results().length });
});
$('count').addEventListener('click', e => {
  const b = e.target.closest('[data-clear]'); if (!b) return;
  if (b.dataset.clear === 'q') { st.q = ''; $('q').value = ''; }
  else if (b.dataset.clear === 'saved') st.savedOnly = false;
  else { st.savedOnly = false; clearSearch(); clearBoxes(); syncBoxesSafe(); }
  changed();
});
function syncBoxesSafe() { try { renderFilters(); } catch (e) {} }
$('active').addEventListener('click', e => {
  const b = e.target.closest('[data-x]'); if (!b) return;
  const x = b.dataset.x;
  if (x === 'download') { downloadSaved(); return; }
  if (x === 'saved') st.savedOnly = false;
  if (x === 'q') { st.q = ''; $('q').value = ''; }
  if (x === 'cat') { st.cats.delete(b.dataset.v); st.kind = ''; }
  if (x === 'chip') st.chips.delete(b.dataset.v);
  if (x === 'topic') st.topics.delete(b.dataset.v);
  if (x === 'kind') { st.cats.clear(); st.kind = ''; }
  if (x === 'all') { st.savedOnly = false; clearSearch(); clearBoxes(); }
  changed();
});
$('search-form').addEventListener('submit', e => {
  e.preventDefault(); st.q = $('q').value; st.savedOnly = false;
  if (st.q.trim()) clearBoxes();
  changed(); $('q').blur();
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
  { const t = (p.get('topic') || '').toLowerCase().split(',').map(x => x.trim()).find(x => TOPIC_BY_ID[x]); if (t) st.topics.add(t); }
  // A search link wins over any filters in the same link (the search box stands alone).
  const q = (p.get('q') || '').trim(); if (q) { clearBoxes(); st.q = q; $('q').value = q; }
  const open = p.get('open'); if (open && ALL.some(i => i.id === open)) { st.open.add(open); st.pin = open; }
  // ?sort=newest|oldest|views (the quiz's saved link uses newest, for the Saturday email's "new matches" button)
  const so = p.get('sort'); if (['newest', 'oldest', 'views', 'shuffle'].includes(so)) { st.sort = so; $('sort').value = so; }
  if (q || open || st.cats.size || st.topics.size || st.chips.size) track('link_landing', { search_term: q, idea_id: open || '', idea_category: [...st.cats].join(','), topics: [...st.topics].join(','), chips: [...st.chips].join(',') });
}

loadIdeas().then(data => {
  ALL = data;
  SHUFFLED = shuffleWithSeed(data, dailySeed());
  applyParams();
  render();
}).catch(() => { $('count').textContent = "Couldn't load the gigs. Try refreshing."; });

fetch('/views.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : {}).then(d => { VIEWS = d.views || {}; VIEWS_DATE = d.updated || ''; if (ALL.length) render(); }).catch(() => {});

fetch('/page-index.json').then(r => r.ok ? r.json() : { ideas: [] }).then(d => { pageIds = new Set(d.ideas || []); if (ALL.length) render(); }).catch(() => {});
