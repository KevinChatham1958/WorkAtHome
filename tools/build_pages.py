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
SITE_CSS_VERSION = "20261105d"   # site.css (shared with the homepage, Gig Finder and quiz)
PAGE_CSS_VERSION = "5"
# Friendly category names shown to visitors (same as CATS in site.js). The data and the
# /category/<slug>/ addresses keep the internal names.
FRIENDLY = {
    "Local & professional services": "Services from home",
    "Digital & subscription products": "Digital products",
    "Marketing & content": "Marketing for businesses",
    "Physical & print products": "Things you make",
    "Content & personal brand": "YouTube & blogging",
    "AI & automation": "AI & automation",
    "E-commerce": "Online stores",
}
# Display order for category links (same as the homepage footer).
DISPLAY_ORDER = ["Local & professional services", "Digital & subscription products",
                 "Marketing & content", "Physical & print products", "Content & personal brand",
                 "AI & automation", "E-commerce"]


def cat_name(c):
    return FRIENDLY.get(c, c)


def rounded(n):
    """Rounded-down count for visible text ("1,000+"), so pages don't go stale."""
    step = 100 if n >= 1000 else 50
    return f"{(n // step) * step:,}+"
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


def short_title(x):
    """The gig's short headline (2-6 words); falls back to the full name."""
    return x.get('title') or title_case(x['name'])


def sentence(s):
    s = (s or '').strip()
    return s[:1].upper() + s[1:]


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
        # Same creator written two ways ("Sabrina Ramonov" / "Sabrina Ramonov 🍄",
        # "Tiger Insight" / "Tiger Insight™") would make two pages at one address and stop
        # the build, leaving new gigs without pages (Nov 5, 2026). Use the most common
        # spelling for every gig of that creator (pages only; ideas.json is not changed).
        spellings = {}
        for x in ideas:
            spellings.setdefault(slugify(x['found']), []).append(x['found'])
        best = {s: max(set(v), key=lambda n: (v.count(n), -len(n))) for s, v in spellings.items()}
        ideas = [dict(x, found=best[slugify(x['found'])]) for x in ideas]
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
/* Gig, category and creator pages (built by tools/build_pages.py).
   Since Nov 5, 2026 these use the main site look: site.css (header, menu, footer,
   colors, fonts) plus the styles below. No more styles.css on these pages. */
.page { max-width: 860px; margin: 0 auto; padding: 28px 24px 56px; }
.crumbs { font-size: 15px; color: var(--muted); margin: 0 0 22px; }
.crumbs a { color: #0F4C68; text-decoration: none; font-weight: 600; }
.crumbs a:hover { text-decoration: underline; }
.crumbs span[aria-hidden] { margin: 0 8px; color: var(--field); }
.gig-head { display: flex; gap: 20px; align-items: center; }
.gig-av { width: 88px; height: 88px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: #DCE8EE; }
.gig-head h1, .list-head h1 { font-size: 40px; font-weight: 800; line-height: 1.1; letter-spacing: -0.01em; text-wrap: balance; }
.gig-dek { margin: 8px 0 0; font-size: 19px; line-height: 1.45; color: var(--body); }
.gig-meta { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0; padding: 0; list-style: none; }
.gig-meta li { font-size: 14px; font-weight: 600; background: var(--tint2); color: var(--navy); border-radius: 999px; padding: 5px 12px; }
.gig-meta li.cat { background: var(--accent-tint); color: var(--accent-dark); }
.gig-meta a { color: inherit; text-decoration: none; }
.gig-meta a:hover { text-decoration: underline; }
.gig-date { margin: 10px 0 0; font-size: 15px; color: var(--muted); }
.gig-date a { color: var(--body); font-weight: 600; }
.share-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 22px 0 0; }
.pbtn { display: inline-flex; align-items: center; gap: 7px; font: inherit; font-size: 15px; font-weight: 600; padding: 9px 16px; border-radius: 8px; border: 1.5px solid var(--navy); background: #FFFFFF; color: var(--navy); text-decoration: none; cursor: pointer; }
.pbtn:hover, .pbtn:focus-visible { background: var(--navy); color: #FFFFFF; }
.copied { font-size: 15px; font-weight: 600; color: #15803D; }
.source-box { margin: 26px 0 0; background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 16px 20px; }
.source-box .lab { font-family: Outfit, system-ui, sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 4px; }
.source-box p { margin: 0; font-size: 17px; line-height: 1.5; color: var(--ink); }
.source-box a { color: #1A56DB; font-weight: 600; }
.source-box .note { margin-top: 4px; font-size: 14px; color: var(--muted); font-style: italic; }
.gig-sec { margin: 30px 0 0; }
.gig-sec h2 { font-size: 22px; font-weight: 700; color: var(--navy); margin: 0 0 8px; }
.gig-sec p { margin: 0; font-size: 18px; line-height: 1.65; color: var(--body); max-width: 68ch; }
.more { margin-top: 52px; padding-top: 32px; border-top: 2px solid var(--line); }
.more h2, .list-page h2 { font-size: 24px; font-weight: 700; margin: 0 0 12px; }
.link-list { list-style: none; margin: 0 0 14px; padding: 0; }
.link-list li { border-bottom: 1px solid var(--line); padding: 12px 0; }
.link-list li a { font-family: Outfit, system-ui, sans-serif; font-size: 18px; font-weight: 600; color: var(--navy); text-decoration: none; }
.link-list li a:hover { color: var(--accent-dark); text-decoration: underline; }
.link-list li small { display: block; color: var(--muted); font-size: 14px; margin-top: 3px; }
.link-list li p { margin: 5px 0 0; color: var(--body); font-size: 16px; line-height: 1.5; max-width: 68ch; }
.see-all { display: inline-block; margin: 0 0 34px; color: var(--accent-dark); font-weight: 700; text-decoration: none; font-size: 16px; }
.see-all:hover { text-decoration: underline; }
.cta-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin: 18px 0 0; }
.cta-card { text-decoration: none; color: var(--ink); background: #FFFFFF; border: 2.5px solid var(--accent); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; gap: 8px; text-align: center; }
.cta-card.quiz { border-color: var(--navy); }
.cta-card b { font-family: Outfit, system-ui, sans-serif; font-size: 22px; font-weight: 700; color: var(--navy); }
.cta-card span { font-size: 16px; line-height: 1.45; color: var(--body); flex-grow: 1; }
.cta-card em { font-style: normal; margin-top: 6px; display: block; background: var(--accent); color: #FFFFFF; font-weight: 700; font-size: 17px; border-radius: 8px; padding: 12px 16px; }
.cta-card.quiz em { background: var(--navy); }
.cta-card:hover { box-shadow: 0 10px 26px rgba(15,61,87,0.14); color: var(--ink); }
.list-head { display: flex; gap: 18px; align-items: center; }
.list-intro { font-size: 18px; line-height: 1.6; color: var(--body); max-width: 68ch; margin: 16px 0 6px; }
.list-count { color: var(--muted); font-size: 15px; margin: 0 0 22px; }
.cat-nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 28px; padding: 0; list-style: none; }
.cat-nav a { display: inline-block; font-size: 15px; font-weight: 600; padding: 6px 14px; border: 1.5px solid var(--line); border-radius: 999px; text-decoration: none; color: var(--navy); background: #FFFFFF; }
.cat-nav a:hover, .cat-nav a[aria-current] { border-color: var(--accent); color: var(--accent-dark); background: var(--accent-tint); }
.fc-stats { display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0 8px; }
.fc-stats div { flex: 1 1 140px; background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
.fc-stats strong { display: block; font-family: Outfit, system-ui, sans-serif; font-size: 34px; font-weight: 800; line-height: 1; color: var(--navy); }
.fc-stats span { display: block; margin-top: 4px; color: var(--muted); font-size: 15px; }
.fc-cta { margin: 18px 0 30px; }
.fc-cta .btn { font-size: 18px; padding: 14px 24px; }
.fc-cats { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; margin: 0 0 28px; padding: 0; }
.fc-cats li { font-size: 15px; padding: 6px 13px; border: 1.5px solid var(--line); border-radius: 999px; background: #FFFFFF; }
.fc-cats a { color: var(--navy); font-weight: 600; text-decoration: none; }
.fc-cats a:hover { text-decoration: underline; }
.fc-cats span { color: var(--muted); font-weight: 600; margin-left: 4px; }
.fc-about { background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; margin: 6px 0 10px; }
.fc-about h2 { margin: 0 0 6px !important; }
.fc-facts { margin: 0; color: var(--body); font-size: 16px; }
.fc-facts a { color: #1A56DB; font-weight: 600; }
.fc-quote { margin: 12px 0 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--accent); }
.fc-quote p { margin: 0; font-size: 17px; line-height: 1.55; font-style: italic; color: var(--ink); }
.fc-quote cite { display: block; margin-top: 4px; font-size: 14px; font-style: normal; color: var(--muted); }
.fc-asof { margin: 10px 0 0; font-size: 13px; color: var(--muted); }
.fc-note { color: var(--muted); font-size: 15px; margin: -4px 0 6px; }
.page .signup-wrap { margin: 48px 0 0; }
.page .signup { background: var(--accent-tint); border: 2px solid #F6D3BF; border-radius: 14px; padding: 22px 24px; margin: 0; }
.page .signup-kicker { margin: 0 0 4px; }
.page .signup .signup-head { font-size: 24px; font-weight: 700; }
.page .signup p { font-size: 16px; }
.page .signup-row input { border: 2px solid #8FA5B2; border-radius: 10px; padding: 12px 14px; }
.page .signup-row button { padding: 12px 20px; font-weight: 700; }
@media (max-width: 760px) {
  .page { padding: 20px 16px 44px; }
  .gig-head { align-items: flex-start; gap: 14px; }
  .gig-av { width: 64px; height: 64px; }
  .gig-head h1, .list-head h1 { font-size: 30px; }
  .gig-dek { font-size: 17px; }
  .gig-sec p { font-size: 17px; }
  .cta-pair { grid-template-columns: 1fr; }
  .page .signup-row button { width: 100%; }
}
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
        """Link into the search tool (/tool/) with a search already run
        (and optionally one gig opened and placed first)."""
        q = f"?q={quote(query)}"
        if open_id:
            q += f"&open={quote(open_id)}"
        return f"{self.base}/tool/{q}"

    def img(self, rel, mime):
        if self.preview:
            return data_uri(os.path.join(ROOT, rel), mime)
        return '/' + rel


# Bottom of every built page (idea, category and creator pages): the two paths (Gig Finder,
# quiz) and the weekly email signup (Kit form 10117206, Production Process §17). Matches the
# homepage since Nov 5, 2026.
def bottom_html(ctx):
    return f"""<section class="signup-wrap">
    <div class="cta-pair">
      <a class="cta-card" href="{ctx.base}/tool/" data-cta="page-browse"><b>Browse the Database</b><span>Search by keyword, filter by gig type, or search by Presenter.</span><em>Explore the Gig Database</em></a>
      <a class="cta-card quiz" href="{ctx.base}/quiz/?from=gig-page" data-cta="page-quiz"><b>Take the 60-Second Quiz</b><span>Checkmark your preferences and we&rsquo;ll find your gigs for you.</span><em>Find My Gigs</em></a>
    </div>
  </section>
  <section class="signup-wrap">
    <form class="signup shi-signup" action="https://app.kit.com/forms/10117206/subscriptions" method="post" data-src="gig-page">
      <p class="signup-kicker">Free Newsletter</p>
      <h2 class="signup-head">New gigs in your inbox every week</h2>
      <p>One short email a week: the Gig of the Week, with our honest take, plus 7 more of the newest work-from-home gigs. Unsubscribe anytime. <a href="{ctx.base}/privacy/">Privacy</a></p>
      <div class="signup-row"><label class="sr" for="shi-email">Your email address</label><input id="shi-email" type="email" name="email_address" placeholder="Your email address" autocomplete="email" required><button type="submit">Subscribe Free</button></div>
    </form>
  </section>"""


PAGE_SCRIPT = """<script>
document.querySelectorAll('form.shi-signup').forEach(f => f.addEventListener('submit', () => { try { if (typeof gtag === 'function') gtag('event', 'email_signup', { form: f.dataset.src, transport_type: 'beacon' }); } catch (e) {} }));
document.addEventListener('click', e => { const a = e.target.closest('[data-cta]'); if (a) { try { gtag('event', 'cta_click', { cta: a.dataset.cta }); } catch (err) {} } });
(function () { const b = document.getElementById('menu-btn'), n = document.getElementById('home-nav'); if (!b) return;
  b.addEventListener('click', () => { const o = b.getAttribute('aria-expanded') !== 'true'; b.setAttribute('aria-expanded', String(o)); n.classList.toggle('open', o); }); })();
</script>"""


def footer_html(ctx):
    cats = ' · '.join(f'<a href="{ctx.cat(c)}">{esc(cat_name(c))}</a>' for c in DISPLAY_ORDER)
    return f"""<footer class="site-footer h-footer">
  <div class="wrap">
    <nav class="h-foot-links" aria-label="Footer">
      <a href="{ctx.base}/tool/">Browse Database</a>
      <a href="{ctx.base}/quiz/">Take the Quiz</a>
      <a href="{ctx.base}/subscribe/">Subscribe</a>
      <a href="{ctx.base}/about.html">About</a>
      <a href="mailto:website@sidehustleintel.org">Contact</a>
      <a href="{ctx.base}/privacy/">Privacy</a>
    </nav>
    <p class="h-foot-cats">Browse by type: {cats}</p>
    <p>© 2026 SideHustleIntel.org · Each gig is a summary of an idea from a creator&rsquo;s YouTube video, linked in its Source box. Creator names are shown for reference only and imply no endorsement. No income is promised or guaranteed.</p>
  </div>
</footer>"""


def shell(ctx, site, *, title, desc, canonical, og_type, schema, main, extra_script=''):
    if ctx.preview:
        with open(os.path.join(ROOT, 'site.css')) as f:
            site_css = f.read()
        css = f"<style>{site_css}\n{PAGE_CSS}</style>"
        head_start = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        analytics = ''
    else:
        css = (f'<link rel="stylesheet" href="/site.css?v={SITE_CSS_VERSION}">\n'
               f'<link rel="stylesheet" href="/idea-page.css?v={PAGE_CSS_VERSION}">')
        head_start = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                      '<meta charset="UTF-8">\n'
                      '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
        analytics = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-DP5LDLD5VR"></script>\n'
                     "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                     "gtag('js',new Date());gtag('config','G-DP5LDLD5VR');</script>\n")
    logo = ctx.img('assets/logo-horizontal.png', 'image/png')
    b = ctx.base
    doc = f"""{head_start}{analytics}<title>{esc(title)} — Side Hustle Intel</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Side Hustle Intel">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/assets/og-share.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
{css}
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
</head>
<body class="gig-site">

<header class="site-header home-header">
  <div class="wrap">
    <a href="{ctx.home()}" class="home-logo"><img class="logo" src="{logo}" alt="Side Hustle Intel home" width="1782" height="169"></a>
    <button type="button" class="menu-btn" id="menu-btn" aria-expanded="false" aria-controls="home-nav">
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
      Menu
    </button>
    <nav class="nav home-nav" id="home-nav" aria-label="Main">
      <a href="{b}/tool/" data-cta="page-header">Browse Database</a>
      <a href="{b}/quiz/" data-cta="page-header-quiz">Take the Quiz</a>
      <a href="{b}/subscribe/" data-cta="page-header-subscribe">Subscribe</a>
      <a href="{b}/about.html">About</a>
    </nav>
  </div>
</header>

<div class="page">
{main}
{bottom_html(ctx)}
</div>

{footer_html(ctx)}
{PAGE_SCRIPT}
{extra_script}
</body>
</html>
"""
    return doc


def browse_all_box(ctx, site, text=''):
    """Replaced on Nov 5, 2026 by the two-path cards at the bottom of every page."""
    return ''


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
    t = title_case(idea['name'])          # full name: page title and search snippets
    short = short_title(idea)             # short headline shown on the page
    url = f"{SITE}/ideas/{idea['id']}/"
    desc = trim(idea['what'], 155)
    date_txt = fmt_date(idea.get('published'))
    others = [x for x in site.by_creator(idea['found']) if x['id'] != idea['id']]
    rel = site.related(idea)
    av = avatar_file(idea['found'])
    avatar = (f'<img class="gig-av" src="{ctx.img(av, "image/jpeg")}" alt="{esc(idea["found"])}">'
              if av else f'<img class="gig-av" src="{ctx.img("assets/avatars/silhouette.svg", "image/svg+xml")}" alt="">')

    schema = [
        {
            "@context": "https://schema.org", "@type": "Article",
            "headline": t, "description": desc, "url": url,
            "datePublished": idea.get('published'),
            "articleSection": cat_name(idea['category']),
            "keywords": ', '.join(idea.get('tags', [])),
            "isBasedOn": {"@type": "VideoObject", "url": idea['url'],
                          "creator": {"@type": "Person", "name": idea['found']}},
            "publisher": {"@type": "Organization", "name": "Side Hustle Intel", "url": SITE + "/"},
        },
        breadcrumb_schema([("Home", SITE + "/"),
                           (cat_name(idea['category']), f"{SITE}/category/{slugify(idea['category'])}/"),
                           (t, url)]),
    ]

    rel_items = ''.join(
        f'<li><a href="{ctx.idea(x)}">{esc(short_title(x))}</a>'
        f'<small>{esc(x["found"])} &middot; {esc(x["cost"].split(" (")[0])}</small></li>' for x in rel)
    rel_block = ''
    if rel:
        rel_block = f"""<h2>More in {esc(cat_name(idea['category']))}</h2>
    <ul class="link-list">{rel_items}</ul>
    <a class="see-all" href="{ctx.cat(idea['category'])}">All {esc(cat_name(idea['category']))} gigs &rarr;</a>"""
    creator_block = ''
    if others:
        items = ''.join(
            f'<li><a href="{ctx.idea(x)}">{esc(short_title(x))}</a>'
            f'<small>{esc(cat_name(x["category"]))}</small></li>' for x in others[:5])
        creator_block = f"""<h2>More from {esc(idea['found'])}</h2>
    <ul class="link-list">{items}</ul>"""
    has_cp = idea['found'] in site.creator_set
    creator_link = (f'<a class="see-all" href="{ctx.creator(idea["found"])}">'
                    f'All gigs from {esc(idea["found"])} &rarr;</a>') if has_cp else ''
    creator_name = (f'<a href="{ctx.creator(idea["found"])}">{esc(idea["found"])}</a>'
                    if has_cp else esc(idea['found']))

    if idea.get('video_title'):
        source_label = esc(idea['video_title'])
    else:
        source_label = 'Watch the video' if 'youtu' in (idea.get('url') or '') else 'View the source'
    n_in_video = site.video_count(idea)
    source_note = (f'<p class="note">One of {n_in_video} gigs covered in this video</p>'
                   if n_in_video > 1 else '')

    fb = 'https://www.facebook.com/sharer/sharer.php?u=' + url
    dek = (f'<p class="gig-dek">{esc(sentence(idea["name"]))}</p>' if len(idea['name'].split()) > 6 else '')
    main = f"""<main class="idea-page">
  {crumbs(ctx, (cat_name(idea['category']), ctx.cat(idea['category'])))}

  <article>
    <div class="gig-head">
      {avatar}
      <div>
        <h1>{esc(short)}</h1>
        {dek}
      </div>
    </div>
    <ul class="gig-meta">
      <li class="cat"><a href="{ctx.cat(idea['category'])}">{esc(cat_name(idea['category']))}</a></li>
      <li>{esc(idea['cost'].split(' (')[0])}</li>
    </ul>
    <p class="gig-date">{f'Video published {esc(date_txt)} by ' if date_txt else 'From '}{creator_name}</p>

    <div class="share-actions">
      <button type="button" class="pbtn" id="copy-link-btn" data-url="{url}">Copy link to this gig</button>
      <a class="pbtn" href="{esc(fb)}" target="_blank" rel="noopener">Share on Facebook</a>
      <span class="copied" id="copied-msg" hidden>Link copied</span>
    </div>

    <div class="source-box">
      <p class="lab">Source video</p>
      <p>{esc(idea['found'])} &middot; <a href="{esc(idea['url'])}" target="_blank" rel="noopener" data-cta="page-source">{source_label}&nbsp;&#8599;</a></p>{source_note}
    </div>
    <section class="gig-sec"><h2>What It Is</h2><p>{esc(idea['what'])}</p></section>
    <section class="gig-sec"><h2>The Pitch</h2><p>{esc(idea['pitch'])}</p></section>
    <section class="gig-sec"><h2>Who It&rsquo;s Best For</h2><p>{esc(idea['best'])}</p></section>
    <section class="gig-sec"><h2>The Truth <span style="font-weight:600">(as we see it)</span></h2><p>{esc(idea['truth'])}</p></section>
  </article>

  <section class="more">
    {rel_block}
    {creator_block}
    {creator_link}
  </section>
</main>"""
    return shell(ctx, site, title=t, desc=desc, canonical=url, og_type='article',
                 schema=schema, main=main, extra_script=COPY_SCRIPT)


# ---------- list items used on category and creator pages ----------

def list_item(x, ctx, show):
    meta = x['found'] if show == 'creator' else cat_name(x['category'])
    return (f'<li><a href="{ctx.idea(x)}">{esc(short_title(x))}</a>'
            f'<small>{esc(meta)} &middot; {esc(x["cost"].split(" (")[0])}</small>'
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
    title = f"{cat_name(cat)}: work-at-home gigs"
    desc = trim(intro, 155)
    current = ' aria-current="page"'
    nav = ''.join(
        f'<li><a href="{ctx.cat(c)}"{current if c == cat else ""}>{esc(cat_name(c))}</a></li>'
        for c in DISPLAY_ORDER)
    if len(items) < total_in_cat:
        count = (f"{len(items)} of the {total_in_cat} gigs of this type have their own page so far. "
                 f"The Gig Finder has all of them.")
    else:
        count = f"{len(items)} gigs, newest first."
    schema = [item_list_schema(items, title, url),
              breadcrumb_schema([("Home", SITE + "/"), (cat_name(cat), url)])]
    main = f"""<main class="idea-page list-page">
  {crumbs(ctx, (cat_name(cat), None))}
  <div class="list-head"><h1>{esc(cat_name(cat))}</h1></div>
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
    idea_w = 'gig' if n == 1 else 'gigs'
    vid_w = 'video' if nv == 1 else 'videos'
    title = f"Work-at-home gigs from {name}"
    prof = site.profiles.get(name, {})
    short = prof.get('short') or name
    cv = prof.get('channel_videos')
    his = prof.get('possessive', 'their')
    # "27 of his 67 videos" reads well; "18 of his 668" undersells, so only show the share when it's sizable.
    if cv and cv >= nv and nv / cv >= 0.25:
        has = f"{name} has {nv} of {his} {cv} YouTube videos in Side Hustle Intel"
    elif nv == 1:
        has = f"{name} has one video in Side Hustle Intel"
    else:
        has = f"{name} has {nv} of {his} {vid_w} in Side Hustle Intel"
    top = [cat_name(c) if c.startswith("AI") else cat_name(c)[0].lower() + cat_name(c)[1:] for c, _ in cat_list[:2]]
    focus = (", mostly in " + " and ".join(top)) if top else ''
    bio = (f"{has}. {'It covers' if nv == 1 else 'Together they cover'} {n} different work-from-home {idea_w}{focus}. "
           f"We pull out each gig on its own and write it up in plain language: what the gig is, how {short} "
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
    avatar = f'<img class="gig-av" src="{ctx.img(av, "image/jpeg")}" alt="{esc(name)}">' if av else ''
    tool_all = ctx.tool(name)

    def idea_href(x):
        return ctx.idea(x) if x['id'] in site.page_ids else ctx.tool(name, x['id'])

    def vid_li(v):
        label = esc(v['title']) if v['title'] else ('Watch the video' if 'youtu' in v['url'] else 'View the source')
        meta = ' &middot; '.join(p for p in [esc(fmt_date(v['date'])) if v['date'] else '',
                                             f"{v['n']} {'gig' if v['n'] == 1 else 'gigs'}"] if p)
        return (f'<li><a href="{esc(v["url"])}" target="_blank" rel="noopener">{label}&nbsp;&#8599;</a>'
                f'<small>{meta}</small></li>')

    def idea_li(x):
        return (f'<li><a href="{idea_href(x)}">{esc(title_case(x["name"]))}</a>'
                f'<small>{esc(cat_name(x["category"]))} &middot; {esc(x["cost"].split(" (")[0])}</small>'
                f'<p>{esc(trim(x["what"], 180))}</p></li>')

    stats = (f'<div class="fc-stats">'
             f'<div><strong>{n}</strong><span>{idea_w} featured</span></div>'
             f'<div><strong>{nv}</strong><span>{vid_w} covered</span></div>'
             f'<div><strong>{len(cats)}</strong><span>{"category" if len(cats) == 1 else "categories"}</span></div>'
             f'</div>')
    cat_html = ''.join(f'<li><a href="{ctx.cat(c)}">{esc(cat_name(c))}</a> <span>{k}</span></li>' for c, k in cat_list)
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
  <p class="fc-cta"><a class="btn" href="{tool_all}">See all {n} in the Gig Finder &rarr;</a></p>
  <h2>Types of gigs</h2>
  <ul class="fc-cats">{cat_html}</ul>
  <h2>Videos featured ({nv})</h2>
  <p class="fc-note">Every gig on Side Hustle Intel links viewers to the video it came from.</p>
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
    noun = 'gig' if n == 1 else 'gigs'
    intro = (f"{n} work-at-home {noun} from {name}'s videos. Each entry sums up the gig as the "
             f"video presents it and adds our own assessment in The Truth, with a link to the original video.")
    title = f"Work-at-home gigs from {name}"
    av = avatar_file(name)
    avatar = f'<img class="gig-av" src="{ctx.img(av, "image/jpeg")}" alt="{esc(name)}">' if av else ''
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
    urls = [SITE + '/', SITE + '/tool/', SITE + '/quiz/', SITE + '/about.html']
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
