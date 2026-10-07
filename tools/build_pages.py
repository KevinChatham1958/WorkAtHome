"""Build static, crawlable pages from ideas.json.

What it makes (all generated; never edit these by hand):
  ideas/<idea-id>/index.html      one page per released idea
  category/<slug>/index.html      one page per category
  creator/<slug>/index.html       one page per creator with a released idea
  sitemap.xml, robots.txt         the page list for search engines
  page-index.json                 tells the homepage which ideas have a page
  idea-page.css                   styles for the pages above

Which ideas get pages is set in pages-release.json:
  {"release_all": false, "released": ["idea-id", ...]}
Pages go live in batches by adding ids to "released". Once every idea is
out, set "release_all" to true and every idea (including new ones) gets a
page automatically.

Each run rebuilds the ideas/, category/ and creator/ folders from scratch, so
an idea deleted from ideas.json loses its page on the next run.

Usage:
  python3 tools/build_pages.py                  # build everything
  python3 tools/build_pages.py --preview-idea <id> out.html
  python3 tools/build_pages.py --preview-category "<name>" out.html
  python3 tools/build_pages.py --preview-creator "<name>" out.html
      # self-contained single page (CSS inlined, images embedded) for review
"""
import argparse
from urllib.parse import quote
import base64
import datetime
import html
import json
import os
import re
import shutil

SITE = "https://sidehustleintel.org"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_VERSION = "20261003a"
PAGE_CSS_VERSION = "4"
CATEGORY_ORDER = [
    "AI & automation", "Local & professional services", "E-commerce",
    "Marketing & content", "Physical & print products",
    "Digital & subscription products", "Content & personal brand",
]
MINOR = {'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'so', 'yet', 'at',
         'by', 'in', 'of', 'on', 'to', 'up', 'as', 'is', 'it', 'vs'}


# ---------- small helpers ----------

def title_case(s):
    """Like toTitleCase() in app.js, but keeps words the source already
    capitalized on purpose (AI, PNG, YouTube, PDFs, AI-generated)."""
    words = s.split(' ')
    out = []
    for i, w in enumerate(words):
        if not w:
            out.append(w)
            continue
        if re.search(r'[A-Z]', w[1:]):
            out.append(w)
            continue
        low = w.lower()
        if i != 0 and i != len(words) - 1 and low in MINOR:
            out.append(low)
        else:
            out.append(low[:1].upper() + low[1:])
    return ' '.join(out)


def slugify(name):
    """Same as slugifyProducer() in app.js."""
    s = re.sub(r'[^a-z0-9]+', '-', (name or '').lower())
    return s.strip('-')[:60]


def fmt_date(d):
    try:
        dt = datetime.date.fromisoformat(d)
    except (TypeError, ValueError):
        return None
    return dt.strftime('%b ') + str(dt.day) + dt.strftime(', %Y')


def esc(s):
    return html.escape(s or '', quote=True)


def trim(s, n):
    s = ' '.join((s or '').split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(' ', 1)[0].rstrip(',;:.') + '…'


def data_uri(path, mime):
    with open(path, 'rb') as f:
        return f'data:{mime};base64,' + base64.b64encode(f.read()).decode()


def avatar_file(creator):
    rel = f"assets/avatars/avatar-{slugify(creator)}.jpg"
    return rel if os.path.exists(os.path.join(ROOT, rel)) else None


def by_date_desc(items):
    return sorted(items, key=lambda x: (x.get('published') or '', x['id']), reverse=True)


# ---------- site model ----------

def video_key(url):
    """Same video can appear as watch?v=, youtu.be/, with &t= or &list= tails;
    reduce each to the 11-character video ID (non-YouTube links as-is).
    Mirrors videoKey() in app.js."""
    m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else (url or '')


class Site:
    def __init__(self, ideas, release):
        self.all = ideas
        if release.get('release_all'):
            self.pages = list(ideas)
        else:
            wanted = set(release.get('released', []))
            self.pages = [x for x in ideas if x['id'] in wanted]
        self.page_ids = {x['id'] for x in self.pages}
        self.intros = json.load(open(os.path.join(ROOT, 'tools', 'category_intros.json')))
        pf = os.path.join(ROOT, 'tools', 'creator_profiles.json')
        self.profiles = {k: v for k, v in json.load(open(pf)).items() if not k.startswith('_')} if os.path.exists(pf) else {}
        # A creator gets a page once they have at least two released ideas;
        # a one-item creator page would just repeat that idea's summary.
        counts = {}
        for x in self.pages:
            counts[x['found']] = counts.get(x['found'], 0) + 1
        # Featured creators (outreach targets, listed in pages-release.json)
        # always get a page, and it covers ALL their ideas, not just released ones.
        all_names = {x['found'] for x in ideas}
        self.featured = {c for c in release.get('featured_creators', []) if c in all_names}
        missing = set(release.get('featured_creators', [])) - all_names
        if missing:
            raise SystemExit(f'featured_creators not found in ideas.json: {sorted(missing)}')
        self.creators = sorted({c for c, n in counts.items() if c and n >= 2} | self.featured)
        self.creator_set = set(self.creators)
        # Ideas per source video (counted across ALL ideas, released or not),
        # so list-style videos can say "One of N ideas covered in this video".
        self.video_counts = {}
        for x in ideas:
            k = video_key(x.get('url'))
            self.video_counts[k] = self.video_counts.get(k, 0) + 1

    def video_count(self, idea):
        return self.video_counts.get(video_key(idea.get('url')), 1)

    def total(self):
        return len(self.all)

    def in_category(self, cat, released_only=True):
        pool = self.pages if released_only else self.all
        return [x for x in pool if x['category'] == cat]

    def by_creator(self, name):
        return [x for x in self.pages if x['found'] == name]

    def by_creator_all(self, name):
        return [x for x in self.all if x['found'] == name]

    def related(self, idea, k=5):
        """Other released ideas in the same category, most shared topic tags
        first, one per creator so the list shows a spread of sources."""
        mine = {t.lower() for t in idea.get('tags', [])}
        pool = [x for x in self.pages if x['category'] == idea['category'] and x['id'] != idea['id']]
        pool.sort(key=lambda x: (-len(mine & {t.lower() for t in x.get('tags', [])}), x['id']))
        picked, seen = [], {idea['found']}
        for x in pool:
            if x['found'] not in seen:
                picked.append(x)
                seen.add(x['found'])
            if len(picked) == k:
                break
        return picked


# ---------- shared page shell ----------

PAGE_CSS = """
.idea-page { max-width: 820px; margin: 0 auto; padding: 20px 24px 64px; }
.crumbs { font-size: 0.85rem; color: var(--text-muted); margin: 0 0 18px; }
.crumbs a { color: var(--link); text-decoration: none; }
.crumbs a:hover { text-decoration: underline; }
.crumbs span[aria-hidden] { margin: 0 6px; color: var(--text-faint); }
.idea-head { display: flex; gap: 16px; align-items: center; border-top: 3px solid var(--text-primary); padding-top: 18px; }
.idea-head h1, .list-head h1 { font-family: var(--font-display); font-weight: 700; font-size: clamp(1.35rem, 3.4vw, 1.75rem); line-height: 1.2; letter-spacing: -0.01em; margin: 0; text-wrap: balance; }
.idea-actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0 6px; }
.btn { display: inline-flex; align-items: center; gap: 7px; font-family: var(--font-body); font-weight: 600; font-size: 0.88rem; padding: 9px 16px; border-radius: 8px; border: 1.5px solid var(--accent); background: var(--bg-card); color: var(--accent); text-decoration: none; cursor: pointer; }
.btn:hover { background: var(--accent-bg); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-dim); }
.idea-body { margin-top: 14px; }
.idea-body .card-section { margin-top: 14px; padding-top: 10px; }
.idea-body .card-text { font-size: 1rem; line-height: 1.6; max-width: 68ch; }
.truth-box { background: var(--accent-bg); border-left: 4px solid var(--accent); border-top: none !important; padding: 12px 16px !important; margin-top: 18px !important; }
.more { margin-top: 40px; border-top: 5px double var(--text-primary); padding-top: 14px; }
.more h2, .list-page h2 { font-family: var(--font-display); font-size: 0.95rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; margin: 0 0 10px; }
.link-list { list-style: none; margin: 0 0 28px; padding: 0; }
.link-list li { border-bottom: 1px solid var(--border); padding: 10px 0; }
.link-list li a { color: var(--text-primary); text-decoration: none; font-weight: 600; }
.link-list li a:hover { color: var(--link); text-decoration: underline; }
.link-list li small { display: block; color: var(--text-faint); font-size: 0.8rem; margin-top: 2px; }
.link-list li p { margin: 4px 0 0; color: var(--text-muted); font-size: 0.92rem; line-height: 1.5; max-width: 68ch; }
.see-all { color: var(--link); font-weight: 600; text-decoration: none; font-size: 0.9rem; }
.see-all:hover { text-decoration: underline; }
.browse-all { text-align: center; margin: 12px 0 0; padding: 22px 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; }
.browse-all p { margin: 0 0 12px; color: var(--text-muted); }
.list-head { display: flex; gap: 16px; align-items: center; border-top: 3px solid var(--text-primary); padding-top: 18px; }
.list-intro { font-size: 1rem; line-height: 1.6; max-width: 68ch; margin: 14px 0 6px; }
.list-count { color: var(--text-faint); font-size: 0.85rem; margin: 0 0 22px; }
.cat-nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 28px; padding: 0; list-style: none; }
.cat-nav a { display: inline-block; font-size: 0.82rem; padding: 5px 11px; border: 1px solid var(--border-strong); border-radius: 999px; text-decoration: none; color: var(--text-muted); background: var(--bg-card); }
.cat-nav a:hover, .cat-nav a[aria-current] { border-color: var(--accent); color: var(--accent); }
.site-bar { background: #0d0d0d; }
.site-bar-inner { max-width: 1200px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.site-bar img { height: 30px; width: auto; display: block; }
.site-bar nav { display: flex; gap: 10px; flex-wrap: wrap; }
.copied { font-size: 0.85rem; color: var(--cat-digital); align-self: center; }
.footer-cats { margin-top: 10px; font-size: 0.8rem; line-height: 1.9; }
.footer-cats a { color: var(--text-muted); text-decoration: none; margin: 0 6px; white-space: nowrap; }
.footer-cats a:hover { text-decoration: underline; }
.fc-stats { display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0 8px; }
.fc-stats div { flex: 1 1 140px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.fc-stats strong { display: block; font-family: var(--font-display); font-size: 2rem; line-height: 1; color: var(--text-primary); }
.fc-stats span { display: block; margin-top: 4px; color: var(--text-muted); font-size: 0.88rem; }
.fc-cta { margin: 18px 0 30px; }
.btn-big { font-size: 1rem; padding: 12px 22px; }
.fc-cats { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; margin: 0 0 28px; padding: 0; }
.fc-cats li { font-size: 0.88rem; padding: 5px 12px; border: 1px solid var(--border-strong); border-radius: 999px; background: var(--bg-card); }
.fc-cats a { color: var(--text-primary); text-decoration: none; }
.fc-cats a:hover { color: var(--link); text-decoration: underline; }
.fc-cats span { color: var(--text-muted); font-weight: 600; margin-left: 4px; }
.fc-about { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin: 4px 0 8px; }
.fc-about h2 { margin: 0 0 6px !important; }
.fc-facts { margin: 0; color: var(--text-muted); font-size: 0.92rem; }
.fc-facts a { color: var(--link); font-weight: 600; text-decoration: none; }
.fc-facts a:hover { text-decoration: underline; }
.fc-quote { margin: 12px 0 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--accent); }
.fc-quote p { margin: 0; font-size: 1rem; line-height: 1.55; font-style: italic; color: var(--text-primary); }
.fc-quote cite { display: block; margin-top: 4px; font-size: 0.82rem; font-style: normal; color: var(--text-faint); }
.fc-asof { margin: 10px 0 0; font-size: 0.78rem; color: var(--text-faint); }
.fc-note { color: var(--text-muted); font-size: 0.9rem; margin: -4px 0 6px; }
.featured-creator h2 { margin-top: 8px; }
@media (max-width: 560px) { .idea-page { padding: 16px 16px 48px; } .site-bar-inner { padding: 12px 16px; } }
"""

COPY_SCRIPT = """<script>
(function () {
  var b = document.getElementById('copy-link-btn'), m = document.getElementById('copied-msg');
  if (!b) return;
  b.addEventListener('click', function () {
    var u = b.getAttribute('data-url');
    function done() { m.hidden = false; setTimeout(function () { m.hidden = true; }, 2500); }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(u).then(done, function () { window.prompt('Copy this link:', u); });
    } else { window.prompt('Copy this link:', u); }
  });
})();
</script>"""


class Ctx:
    """Link and asset paths. Real pages use site-relative paths; a preview
    points at the live site and embeds images so it works on its own."""
    def __init__(self, preview):
        self.preview = preview
        self.base = SITE if preview else ''

    def home(self):
        return f"{self.base}/"

    def idea(self, i):
        return f"{self.base}/ideas/{i['id']}/"

    def cat(self, name):
        return f"{self.base}/category/{slugify(name)}/"

    def creator(self, name):
        return f"{self.base}/creator/{slugify(name)}/"

    def tool(self, query, open_id=None):
        """Link into the home-page search tool with a search already run
        (and optionally one gig opened and placed first)."""
        q = f"?q={quote(query)}"
        if open_id:
            q += f"&open={quote(open_id)}"
        return f"{self.base}/{q}"

    def img(self, rel, mime):
        if self.preview:
            return data_uri(os.path.join(ROOT, rel), mime)
        return '/' + rel


def footer_html(ctx):
    cats = ' '.join(f'<a href="{ctx.cat(c)}">{esc(c)}</a>' for c in CATEGORY_ORDER)
    return f"""<footer class="site-footer">
  <div class="footer-inner">
    <span>Side Hustle Intel — every idea here is sourced from a real creator video, linked in the Source section of each entry.</span>
    <div class="footer-cats">Browse by category: {cats}</div>
  </div>
</footer>"""


def shell(ctx, site, *, title, desc, canonical, og_type, schema, main, extra_script=''):
    if ctx.preview:
        with open(os.path.join(ROOT, 'styles.css')) as f:
            site_css = f.read()
        css = (f"<style>{site_css}\n{PAGE_CSS}\nbody{{background:var(--bg)}}\n"
               ".preview-note{background:#fff7d6;border-bottom:1px solid #e8d48a;color:#5c4a00;"
               "font-size:0.85rem;padding:8px 16px;text-align:center}</style>")
        head_start = ''
        analytics = ''
        note = ('<div class="preview-note">Preview of one page. Links to other new pages will work '
                'once the pages are published on sidehustleintel.org.</div>')
    else:
        css = (f'<link rel="stylesheet" href="/styles.css?v={STYLE_VERSION}">\n'
               f'<link rel="stylesheet" href="/idea-page.css?v={PAGE_CSS_VERSION}">')
        head_start = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                      '<meta charset="UTF-8">\n'
                      '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
        analytics = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-DP5LDLD5VR"></script>\n'
                     "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                     "gtag('js',new Date());gtag('config','G-DP5LDLD5VR');</script>\n")
        note = ''
    logo = ctx.img('assets/logo-horizontal-white.png', 'image/png')
    doc = f"""{head_start}{analytics}<title>{esc(title)} — Side Hustle Intel</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Side Hustle Intel">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/assets/logo.png">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Archivo+Black&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
{css}
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
{'' if ctx.preview else '</head>' + chr(10) + '<body>'}
{note}
<header class="site-bar">
  <div class="site-bar-inner">
    <a href="{ctx.home()}"><img src="{logo}" alt="SideHustleIntel.org"></a>
    <nav>
      <a class="about-link" href="{ctx.home()}">Search all {site.total()} ideas</a>
      <a class="about-link" href="{ctx.base}/about.html">About Us</a>
    </nav>
  </div>
</header>

{main}

{footer_html(ctx)}
{extra_script}
{'' if ctx.preview else '</body>' + chr(10) + '</html>'}
"""
    return doc


def browse_all_box(ctx, site, text='Search, filter and save from every idea in the database.'):
    return f"""<div class="browse-all">
      <p>{esc(text)}</p>
      <a class="btn btn-primary" href="{ctx.home()}">Browse all {site.total()} work-at-home ideas</a>
    </div>"""


def crumbs(ctx, *parts):
    items = [f'<a href="{ctx.home()}">Home</a>']
    for label, href in parts:
        items.append(f'<a href="{href}">{esc(label)}</a>' if href else f'<span>{esc(label)}</span>')
    return '<nav class="crumbs" aria-label="Breadcrumb">' + '<span aria-hidden="true">›</span>'.join(items) + '</nav>'


def breadcrumb_schema(parts):
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": n + 1, "name": name, "item": url}
            for n, (name, url) in enumerate(parts)],
    }


# ---------- idea page ----------

def idea_page(idea, site, ctx):
    t = title_case(idea['name'])
    url = f"{SITE}/ideas/{idea['id']}/"
    desc = trim(idea['what'], 155)
    date_txt = fmt_date(idea.get('published'))
    others = [x for x in site.by_creator(idea['found']) if x['id'] != idea['id']]
    rel = site.related(idea)
    av = avatar_file(idea['found'])
    avatar = (f'<img class="card-avatar" src="{ctx.img(av, "image/jpeg")}" alt="{esc(idea["found"])}">'
              if av else '')

    schema = [
        {
            "@context": "https://schema.org", "@type": "Article",
            "headline": t, "description": desc, "url": url,
            "datePublished": idea.get('published'),
            "articleSection": idea['category'],
            "keywords": ', '.join(idea.get('tags', [])),
            "isBasedOn": {"@type": "VideoObject", "url": idea['url'],
                          "creator": {"@type": "Person", "name": idea['found']}},
            "publisher": {"@type": "Organization", "name": "Side Hustle Intel", "url": SITE + "/"},
        },
        breadcrumb_schema([("Home", SITE + "/"),
                           (idea['category'], f"{SITE}/category/{slugify(idea['category'])}/"),
                           (t, url)]),
    ]

    rel_items = ''.join(
        f'<li><a href="{ctx.idea(x)}">{esc(title_case(x["name"]))}</a>'
        f'<small>{esc(x["found"])} &middot; {esc(x["cost"])}</small></li>' for x in rel)
    rel_block = ''
    if rel:
        rel_block = f"""<h2>More in {esc(idea['category'])}</h2>
    <ul class="link-list">{rel_items}</ul>
    <p><a class="see-all" href="{ctx.cat(idea['category'])}">All {esc(idea['category'])} ideas &rarr;</a></p>
    <br>"""
    creator_block = ''
    if others:
        items = ''.join(
            f'<li><a href="{ctx.idea(x)}">{esc(title_case(x["name"]))}</a>'
            f'<small>{esc(x["category"])}</small></li>' for x in others[:5])
        creator_block = f"""<h2>More from {esc(idea['found'])}</h2>
    <ul class="link-list">{items}</ul>"""
    has_cp = idea['found'] in site.creator_set
    creator_link = (f'<p><a class="see-all" href="{ctx.creator(idea["found"])}">'
                    f'All ideas from {esc(idea["found"])} &rarr;</a></p><br>') if has_cp else ''
    creator_name = (f'<a href="{ctx.creator(idea["found"])}" style="color:inherit">{esc(idea["found"])}</a>'
                    if has_cp else esc(idea['found']))

    if idea.get('video_title'):
        source_label = esc(idea['video_title'])
    else:
        source_label = 'Watch the video' if 'youtu' in (idea.get('url') or '') else 'View the source'
    n_in_video = site.video_count(idea)
    source_note = (f'\n        <p class="source-note">One of {n_in_video} ideas covered in this video</p>'
                   if n_in_video > 1 else '')

    fb = 'https://www.facebook.com/sharer/sharer.php?u=' + url
    main = f"""<main class="idea-page">
  {crumbs(ctx, (idea['category'], ctx.cat(idea['category'])))}

  <article>
    <div class="idea-head">
      {avatar}
      <div class="card-title-text">
        <h1>{esc(t)}</h1>
        <p class="card-meta">{esc(idea['category'])} &middot; {esc(idea['cost'])}</p>
        <p class="card-date">{f'Originally published {esc(date_txt)} &mdash; ' if date_txt else ''}{creator_name}</p>
      </div>
    </div>

    <div class="idea-actions">
      <button type="button" class="btn" id="copy-link-btn" data-url="{url}">Copy link to this idea</button>
      <a class="btn" href="{esc(fb)}" target="_blank" rel="noopener">Share on Facebook</a>
      <span class="copied" id="copied-msg" hidden>Link copied</span>
    </div>

    <div class="idea-body">
      <div class="card-section">
        <div class="card-section-label">Source</div>
        <p class="card-text">{esc(idea['found'])} &middot; <a class="source-link" href="{esc(idea['url'])}" target="_blank" rel="noopener">{source_label}&nbsp;&#8599;</a></p>{source_note}
      </div>
      <div class="card-section">
        <div class="card-section-label">What It Is</div>
        <p class="card-text">{esc(idea['what'])}</p>
      </div>
      <div class="card-section">
        <div class="card-section-label">The Pitch</div>
        <p class="card-text">{esc(idea['pitch'])}</p>
      </div>
      <div class="card-section">
        <div class="card-section-label">Best For</div>
        <p class="card-text">{esc(idea['best'])}</p>
      </div>
      <div class="card-section truth-box">
        <div class="card-section-label">The Truth</div>
        <p class="card-text">{esc(idea['truth'])}</p>
      </div>
    </div>
  </article>

  <section class="more">
    {rel_block}
    {creator_block}
    {creator_link}
    {browse_all_box(ctx, site)}
  </section>
</main>"""
    return shell(ctx, site, title=t, desc=desc, canonical=url, og_type='article',
                 schema=schema, main=main, extra_script=COPY_SCRIPT)


# ---------- list items used on category and creator pages ----------

def list_item(x, ctx, show):
    meta = x['found'] if show == 'creator' else x['category']
    return (f'<li><a href="{ctx.idea(x)}">{esc(title_case(x["name"]))}</a>'
            f'<small>{esc(meta)} &middot; {esc(x["cost"])}</small>'
            f'<p>{esc(trim(x["what"], 180))}</p></li>')


def item_list_schema(items, name, url):
    return {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": name, "url": url,
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(items),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": f"{SITE}/ideas/{x['id']}/", "name": title_case(x['name'])}
                for n, x in enumerate(items)],
        },
    }


# ---------- category page ----------

def category_page(cat, site, ctx):
    items = by_date_desc(site.in_category(cat))
    total_in_cat = len(site.in_category(cat, released_only=False))
    url = f"{SITE}/category/{slugify(cat)}/"
    intro = site.intros.get(cat, '')
    title = f"{cat} work-at-home ideas"
    desc = trim(intro, 155)
    current = ' aria-current="page"'
    nav = ''.join(
        f'<li><a href="{ctx.cat(c)}"{current if c == cat else ""}>{esc(c)}</a></li>'
        for c in CATEGORY_ORDER)
    if len(items) < total_in_cat:
        count = (f"{len(items)} of the {total_in_cat} ideas in this category have their own page so far. "
                 f"The full database has all of them.")
    else:
        count = f"{len(items)} ideas, newest first."
    schema = [item_list_schema(items, title, url),
              breadcrumb_schema([("Home", SITE + "/"), (cat, url)])]
    main = f"""<main class="idea-page list-page">
  {crumbs(ctx, (cat, None))}
  <div class="list-head"><h1>{esc(cat)}</h1></div>
  <p class="list-intro">{esc(intro)}</p>
  <p class="list-count">{esc(count)}</p>
  <ul class="cat-nav" aria-label="Categories">{nav}</ul>
  <ul class="link-list">{''.join(list_item(x, ctx, 'creator') for x in items)}</ul>
  {browse_all_box(ctx, site, 'Search every idea in the database by keyword, category or creator.')}
</main>"""
    return shell(ctx, site, title=title, desc=desc, canonical=url, og_type='website',
                 schema=schema, main=main)


# ---------- creator page ----------

def featured_creator_page(name, site, ctx):
    """Full page for an outreach target: every idea of theirs in the database,
    the videos they came from, and a way into the search tool."""
    items = by_date_desc(site.by_creator_all(name))
    url = f"{SITE}/creator/{slugify(name)}/"
    n = len(items)
    videos = {}
    for x in items:
        k = video_key(x.get('url'))
        v = videos.setdefault(k, {'url': x['url'], 'title': x.get('video_title') or '', 'date': x.get('published') or '', 'n': 0})
        v['n'] += 1
    vids = sorted(videos.values(), key=lambda v: (v['date'], v['title']), reverse=True)
    nv = len(vids)
    cats = {}
    for x in items:
        cats[x['category']] = cats.get(x['category'], 0) + 1
    cat_list = sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))
    idea_w = 'idea' if n == 1 else 'ideas'
    vid_w = 'video' if nv == 1 else 'videos'
    title = f"Work-at-home ideas from {name}"
    prof = site.profiles.get(name, {})
    short = prof.get('short') or name
    cv = prof.get('channel_videos')
    his = prof.get('possessive', 'their')
    if cv and cv >= nv:
        has = f"{name} has {nv} of {his} {cv} YouTube videos in Side Hustle Intel"
    else:
        has = f"{name} has {nv} {vid_w} in Side Hustle Intel"
    top = [c.lower() for c, _ in cat_list[:2]]
    focus = (", mostly in " + " and ".join(top)) if top else ''
    bio = (f"{has}. Together they cover {n} different work-from-home {idea_w}{focus}. "
           f"We pull out each idea on its own and write it up in plain language: what the gig is, how {short} "
           f"pitches it, who it suits, and our honest take. Every entry links back to the video it came from, "
           f"so you can always hear it from {short} directly.")
    intro = bio
    about = ''
    if prof:
        facts = []
        if prof.get('subscribers'): facts.append(f"{esc(prof['subscribers'])} subscribers")
        if cv: facts.append(f"{cv} videos")
        if prof.get('joined_year'): facts.append(f"on YouTube since {prof['joined_year']}")
        if prof.get('country'): facts.append(esc(prof['country']))
        link = (f' &middot; <a href="{esc(prof["channel_url"])}" target="_blank" rel="noopener">Visit the channel&nbsp;&#8599;</a>'
                if prof.get('channel_url') else '')
        quote = (f'<blockquote class="fc-quote"><p>&ldquo;{esc(prof["quote"])}&rdquo;</p>'
                 f'<cite>{esc(name)}, on {his} YouTube channel</cite></blockquote>' if prof.get('quote') else '')
        about = (f'<div class="fc-about"><h2>About {esc(name)}</h2>'
                 f'<p class="fc-facts">{" &middot; ".join(facts)}{link}</p>{quote}'
                 f'<p class="fc-asof">Channel figures as of {esc(fmt_date(prof["checked"]))}.</p></div>' if prof.get('checked') else '</div>')
    av = avatar_file(name)
    avatar = f'<img class="card-avatar" src="{ctx.img(av, "image/jpeg")}" alt="{esc(name)}">' if av else ''
    tool_all = ctx.tool(name)

    def idea_href(x):
        return ctx.idea(x) if x['id'] in site.page_ids else ctx.tool(name, x['id'])

    def vid_li(v):
        label = esc(v['title']) if v['title'] else ('Watch the video' if 'youtu' in v['url'] else 'View the source')
        meta = ' &middot; '.join(p for p in [esc(fmt_date(v['date'])) if v['date'] else '',
                                             f"{v['n']} {'idea' if v['n'] == 1 else 'ideas'}"] if p)
        return (f'<li><a href="{esc(v["url"])}" target="_blank" rel="noopener">{label}&nbsp;&#8599;</a>'
                f'<small>{meta}</small></li>')

    def idea_li(x):
        return (f'<li><a href="{idea_href(x)}">{esc(title_case(x["name"]))}</a>'
                f'<small>{esc(x["category"])} &middot; {esc(x["cost"])}</small>'
                f'<p>{esc(trim(x["what"], 180))}</p></li>')

    stats = (f'<div class="fc-stats">'
             f'<div><strong>{n}</strong><span>{idea_w} featured</span></div>'
             f'<div><strong>{nv}</strong><span>{vid_w} covered</span></div>'
             f'<div><strong>{len(cats)}</strong><span>{"category" if len(cats) == 1 else "categories"}</span></div>'
             f'</div>')
    cat_html = ''.join(f'<li><a href="{ctx.cat(c)}">{esc(c)}</a> <span>{k}</span></li>' for c, k in cat_list)
    schema = [{
        "@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": url,
        "mainEntity": {"@type": "ItemList", "numberOfItems": n, "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "url": (SITE + idea_href(x)) if not ctx.preview else idea_href(x), "name": title_case(x['name'])}
            for i, x in enumerate(items)]},
    }, breadcrumb_schema([("Home", SITE + "/"), (name, url)])]
    main = f"""<main class="idea-page list-page featured-creator">
  {crumbs(ctx, (name, None))}
  <div class="list-head">{avatar}<h1>{esc(name)}</h1></div>
  <p class="list-intro">{esc(intro)}</p>
  {stats}
  {about}
  <p class="fc-cta"><a class="btn btn-primary btn-big" href="{tool_all}">See all {n} in the searchable tool &rarr;</a></p>
  <h2>Where these ideas fall</h2>
  <ul class="fc-cats">{cat_html}</ul>
  <h2>Videos featured ({nv})</h2>
  <p class="fc-note">Every idea on Side Hustle Intel links viewers to the video it came from.</p>
  <ul class="link-list fc-videos">{''.join(vid_li(v) for v in vids)}</ul>
  <h2>All {n} {idea_w}</h2>
  <ul class="link-list">{''.join(idea_li(x) for x in items)}</ul>
  {browse_all_box(ctx, site)}
</main>"""
    return shell(ctx, site, title=title, desc=trim(intro, 155), canonical=url,
                 og_type='profile', schema=schema, main=main)


def creator_page(name, site, ctx):
    if name in site.featured:
        return featured_creator_page(name, site, ctx)
    items = by_date_desc(site.by_creator(name))
    url = f"{SITE}/creator/{slugify(name)}/"
    n = len(items)
    noun = 'idea' if n == 1 else 'ideas'
    intro = (f"{n} work-at-home {noun} from {name}'s videos. Each entry sums up the idea as the "
             f"video presents it and adds our own assessment in The Truth, with a link to the original video.")
    title = f"Work-at-home ideas from {name}"
    av = avatar_file(name)
    avatar = f'<img class="card-avatar" src="{ctx.img(av, "image/jpeg")}" alt="{esc(name)}">' if av else ''
    schema = [item_list_schema(items, title, url),
              breadcrumb_schema([("Home", SITE + "/"), (name, url)])]
    videos = sorted({x['url'] for x in items})
    vid_word = 'video' if len(videos) == 1 else 'videos'
    main = f"""<main class="idea-page list-page">
  {crumbs(ctx, (name, None))}
  <div class="list-head">{avatar}<h1>{esc(name)}</h1></div>
  <p class="list-intro">{esc(intro)}</p>
  <p class="list-count">Drawn from {len(videos)} {vid_word}.</p>
  <ul class="link-list">{''.join(list_item(x, ctx, 'category') for x in items)}</ul>
  {browse_all_box(ctx, site)}
</main>"""
    return shell(ctx, site, title=title, desc=trim(intro, 155), canonical=url,
                 og_type='profile', schema=schema, main=main)


# ---------- sitemap, robots, homepage index ----------

def sitemap(site):
    urls = [SITE + '/', SITE + '/about.html']
    urls += [f"{SITE}/category/{slugify(c)}/" for c in CATEGORY_ORDER]
    urls += [f"{SITE}/creator/{slugify(c)}/" for c in site.creators]
    urls += [f"{SITE}/ideas/{x['id']}/" for x in site.pages]
    body = ''.join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'{body}</urlset>\n'), len(urls)


ROBOTS = f"""User-agent: *
Allow: /
Disallow: /review.html

Sitemap: {SITE}/sitemap.xml
"""


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w') as f:
        f.write(text)


def build_all(site):
    for d in ('ideas', 'category', 'creator'):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    ctx = Ctx(preview=False)
    for idea in site.pages:
        write(f"ideas/{idea['id']}/index.html", idea_page(idea, site, ctx))
    for cat in CATEGORY_ORDER:
        write(f"category/{slugify(cat)}/index.html", category_page(cat, site, ctx))
    slugs = {}
    for name in site.creators:
        s = slugify(name)
        if s in slugs:
            raise SystemExit(f'Two creators share the address /creator/{s}/: {slugs[s]!r} and {name!r}')
        slugs[s] = name
        write(f"creator/{s}/index.html", creator_page(name, site, ctx))
    sm, n_urls = sitemap(site)
    write('sitemap.xml', sm)
    write('robots.txt', ROBOTS)
    write('idea-page.css', PAGE_CSS.lstrip())
    write('page-index.json', json.dumps({"ideas": sorted(site.page_ids)}, separators=(',', ':')) + '\n')
    print(f"Built {len(site.pages)} idea pages, {len(CATEGORY_ORDER)} category pages, "
          f"{len(site.creators)} creator pages; sitemap lists {n_urls} addresses.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-idea', nargs=2, metavar=('ID', 'OUT'))
    ap.add_argument('--preview-category', nargs=2, metavar=('NAME', 'OUT'))
    ap.add_argument('--preview-creator', nargs=2, metavar=('NAME', 'OUT'))
    a = ap.parse_args()
    ideas = json.load(open(os.path.join(ROOT, 'ideas.json')))
    release = json.load(open(os.path.join(ROOT, 'pages-release.json')))
    site = Site(ideas, release)
    ctx = Ctx(preview=True)
    if a.preview_idea:
        idea = next(x for x in ideas if x['id'] == a.preview_idea[0])
        open(a.preview_idea[1], 'w').write(idea_page(idea, site, ctx))
    elif a.preview_category:
        open(a.preview_category[1], 'w').write(category_page(a.preview_category[0], site, ctx))
    elif a.preview_creator:
        open(a.preview_creator[1], 'w').write(creator_page(a.preview_creator[0], site, ctx))
    else:
        build_all(site)


if __name__ == '__main__':
    main()
