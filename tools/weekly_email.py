"""Build the weekly email (3 gigs on a rotating theme) and hand it to Kit (kit.com).

Runs in GitHub Actions (.github/workflows/weekly-email.yml) with the secret
KIT_API_KEY. Gigs "added this week" are the ids in ideas.json now that were
not in ideas.json 7 days ago (read from git history), so nothing has to be
recorded by hand when gigs are published.

MODE (env):
  draft   create the email in Kit as a draft; Kevin sends it from Kit > Broadcasts
  send    schedule it to go out a few minutes from now, to all subscribers
  preview only write weekly-email-preview.html (no Kit call); for testing
DAYS (env, default 7): how far back "new" reaches.
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request


def fail(msg):
    # ::error:: shows up as an annotation on the GitHub run, readable without the log.
    print('::error::' + msg.replace('\n', ' '))
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://sidehustleintel.org'
API = 'https://api.kit.com/v4/broadcasts'
PICKS = 3  # gigs per email


def video_key(url):
    m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else ''


def old_ideas(days):
    sha = subprocess.run(['git', 'rev-list', '-1', f'--before={days} days ago', 'HEAD'],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not sha:
        return []
    out = subprocess.run(['git', 'show', f'{sha}:ideas.json'], cwd=ROOT, capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else []


def fmt_views(n):
    if n >= 1e6:
        s = f'{n / 1e6:.1f}'.rstrip('0').rstrip('.') + 'M'
    elif n >= 1e3:
        s = f'{n / 1e3:.0f}K' if n >= 1e4 else f'{n / 1e3:.1f}'.rstrip('0').rstrip('.') + 'K'
    else:
        s = str(n)
    return s + ' views'


def first_sentence(t):
    t = (t or '').strip()
    m = re.match(r'^.+?[.!?](?=\s|$)', t)
    return m.group(0) if m else t


def link_for(i, pages):
    if i['id'] in pages:
        return f"{SITE}/ideas/{i['id']}/"
    return f"{SITE}/tool/?open={i['id']}"


def sentences(t, n):
    parts = re.findall(r'.+?[.!?](?=\s|$)', (t or '').strip())
    return ' '.join(parts[:n]) if parts else (t or '').strip()


def gig_html(i, pages, views):
    v = views.get(video_key(i.get('url')), -1)
    meta = f"{html.escape(i['found'])}" + (f" · {fmt_views(v)} on YouTube" if v >= 0 else '')
    return (f'<div style="padding:16px 0;border-bottom:1px solid #e3e6ea">'
            f'<a href="{link_for(i, pages)}" style="font-size:19px;font-weight:bold;color:#0F3D57;text-decoration:none">'
            f'{html.escape(i.get("title") or i["name"])}</a>'
            f'<div style="font-size:13px;color:#6b7280;margin:2px 0 8px">{meta}</div>'
            f'<div style="font-size:16px;color:#16202e;margin:0 0 8px">{html.escape(sentences(i.get("what"), 2))}</div>'
            f'<div style="font-size:15px;color:#3C5260;margin:0 0 8px"><strong>Our opinion:</strong> {html.escape(sentences(i.get("truth"), 1))}</div>'
            f'<a href="{link_for(i, pages)}" style="font-size:15px;color:#C2410C;font-weight:bold">Read the full write-up &rarr;</a></div>')


# Themes rotate week by week: most watched overall, then a category, then a
# situation (the site's filter boxes), then most watched again with the next
# category, and so on. THEME env (views / cat:<slug> / sit:<code>) forces one.
CATS = [  # (category in ideas.json, friendly name, /category/ slug)
    ('Local & professional services', 'Services from home', 'local-professional-services'),
    ('Digital & subscription products', 'Digital products', 'digital-subscription-products'),
    ('Marketing & content', 'Marketing for businesses', 'marketing-content'),
    ('Physical & print products', 'Things you make', 'physical-print-products'),
    ('Content & personal brand', 'YouTube & blogging', 'content-personal-brand'),
    ('AI & automation', 'AI & automation', 'ai-automation'),
    ('E-commerce', 'Online stores', 'e-commerce'),
]
# Opening paragraph for each theme (after "Hi there,"). {when} = "this week" / "this month".
INTRO_VIEWS = ("Every week we read through new work-from-home ideas from YouTube creators and add the real ones "
               "to Side Hustle Intel. Here are the three new gigs whose videos people have watched the most. "
               "Popular isn't the same as good, so each comes with our honest take.")
INTRO_CAT = ("This week's theme is <strong>{name}</strong>: {sub}. Here are the three new ones {when} "
             "whose videos people have watched the most, with our honest take on each.")
CAT_SUB = {
    'local-professional-services': 'services you sell to clients and do from home, like bookkeeping, dispatching or virtual assistance',
    'digital-subscription-products': 'things you make once and sell many times, like printables, templates and e-books',
    'marketing-content': 'helping businesses with social media, ads and websites',
    'physical-print-products': 'things you make or design, from crafts to print-on-demand and books',
    'content-personal-brand': 'building an audience with a YouTube channel, a blog or social media',
    'ai-automation': 'using AI tools to build products or offer services',
    'e-commerce': 'selling online through Etsy, Amazon, Shopify and similar stores',
}
SIT_INTRO = {
    'parent': "If you're home with kids, you need work you can do in short stretches and put down whenever they need you. These three new gigs fit that, and they're the ones whose videos people have watched the most {when}.",
    'nocamera': "Plenty of people like the idea of earning online but would rather not be on camera. None of these three needs you to show your face. They're the most-watched new ones {when}.",
    'lowcost': "Not everyone has money to put into a new idea. These three can be started for about $100 or less, beyond a computer and internet. They're the most-watched new ones {when}.",
    'older': "These three suit people who are 50+ or retired: no heavy lifting or on-site labor, and room to use the experience you already have. They're the most-watched new ones {when}.",
    'nosales': "If cold calling and pitching strangers isn't for you, these three are worth a look: none of them depends on selling by phone or chasing clients. They're the most-watched new ones {when}.",
    'noinventory': "No boxes in the garage: none of these three needs you to buy, store or ship products. They're the most-watched new ones {when}.",
}
SIGNOFF = ("<p style=\"font-size:16px;margin:24px 0 4px\">Thanks for reading,</p>"
           "<p style=\"font-size:16px;margin:0 0 16px\">Kevin<br><span style=\"color:#6b7280\">Side Hustle Intel</span></p>"
           "<p style=\"font-size:15px;color:#3C5260\">P.S. Hit reply and tell me what kind of gigs you'd like to see more of. I read every reply.</p>")

SITS = [  # (filter code, phrase finishing "3 new gigs ...")
    ('parent', 'that fit around kids'),
    ('nocamera', 'you can do without ever appearing on camera'),
    ('lowcost', 'you can start for about $100 or less'),
    ('older', 'that suit people 50+ or retired'),
    ('nosales', 'with no cold calling or sales pitches'),
    ('noinventory', 'with no inventory or shipping'),
]


def pick_theme(week):
    forced = os.environ.get('THEME', '').strip()
    if forced:
        return forced
    kind, rnd = week % 3, week // 3
    if kind == 0:
        return 'views'
    if kind == 1:
        return 'cat:' + CATS[rnd % len(CATS)][2]
    return 'sit:' + SITS[rnd % len(SITS)][0]


def top3(pool, views):
    """Most-viewed first, one gig per video."""
    out, seen = [], set()
    for i in sorted(pool, key=lambda i: views.get(video_key(i.get('url')), -1), reverse=True):
        k = video_key(i.get('url')) or i['id']
        if k not in seen:
            out.append(i); seen.add(k)
        if len(out) == PICKS:
            break
    return out


def build(days):
    ideas = json.load(open(os.path.join(ROOT, 'ideas.json'), encoding='utf-8'))
    before = {i['id'] for i in old_ideas(days)}
    if not before:
        fail('Could not read ideas.json from git history (checkout needs full history).')
    new = [i for i in ideas if i['id'] not in before]
    if not new:
        return None
    month_ids = {i['id'] for i in old_ideas(30)}
    month = [i for i in ideas if i['id'] not in month_ids] if month_ids else new
    try:
        views = json.load(open(os.path.join(ROOT, 'views.json'))).get('views', {})
    except FileNotFoundError:
        views = {}
    try:
        pages = set(json.load(open(os.path.join(ROOT, 'page-index.json'))).get('ideas', []))
    except FileNotFoundError:
        pages = set()

    theme = pick_theme(datetime.date.today().isocalendar()[1])
    picks, when = [], 'this week'
    if theme.startswith('cat:'):
        cat = next((c for c in CATS if c[2] == theme[4:]), None)
        if cat:
            for pool, w in ((new, 'this week'), (month, 'this month')):
                picks = top3([i for i in pool if i['category'] == cat[0]], views)
                when = w
                if len(picks) >= 2:
                    break
            heading = f'The most-watched new {cat[1]} gigs {when}'
            intro = INTRO_CAT.format(name=html.escape(cat[1]), sub=CAT_SUB[cat[2]], when=when)
            subject = f'{cat[1]}: the most-watched new gigs {when}'
            more_link, more_text = f'{SITE}/category/{cat[2]}/', f'See every {cat[1]} gig'
    elif theme.startswith('sit:'):
        sit = next((x for x in SITS if x[0] == theme[4:]), None)
        if sit:
            for pool, w in ((new, 'this week'), (month, 'this month')):
                picks = top3([i for i in pool if sit[0] in (i.get('filters') or [])], views)
                when = w
                if len(picks) >= 2:
                    break
            heading = f'{len(picks)} new gigs {sit[1]}'
            intro = SIT_INTRO[sit[0]].format(when=when)
            subject = f'{len(picks)} new work-from-home gigs {sit[1]}'
            more_link, more_text = f'{SITE}/tool/?f={sit[0]}', 'See them all in the gig browser'
    if len(picks) < 2:  # theme 'views', or a theme with too few gigs
        picks, when = top3(new, views), 'this week'
        heading = f'The {len(picks)} most-watched new gigs this week'
        intro = INTRO_VIEWS
        subject = f'The {len(picks)} most-watched new work-from-home gigs this week'
        more_link, more_text = f'{SITE}/tool/', 'Browse every gig'
    n, total = len(new), len(ideas)
    preview = re.sub(r'<[^>]+>', '', intro).split('. ')[0][:140]
    cards = ''.join(gig_html(i, pages, views) for i in picks)
    body = f'''<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#16202e">
<p style="font-size:16px;margin:0 0 12px">Hi there,</p>
<p style="font-size:16px;margin:0 0 18px">{intro}</p>
<h1 style="font-size:22px;color:#0F3D57;margin:0 0 2px">{html.escape(heading)}</h1>
{cards}
<p style="font-size:16px;margin:22px 0 6px"><a href="{more_link}" style="color:#0F3D57;font-weight:bold">{more_text} &rarr;</a></p>
<p style="font-size:15px;color:#3C5260;margin:0 0 20px">We added {n} gig{'s' if n != 1 else ''} this week; there are now {total:,} in the free database at <a href="{SITE}/" style="color:#3C5260">sidehustleintel.org</a>, each with the same plain-English write-up and honest opinion.</p>
{SIGNOFF}
<p style="font-size:13px;color:#6b7280">You're getting this because you signed up for the weekly email at sidehustleintel.org. Side Hustle Intel is free and independent: we don't sell courses, and creators don't pay to be included.</p>
</div>'''
    return subject, preview, body, n


def main():
    mode = os.environ.get('MODE', 'draft')
    days = int(os.environ.get('DAYS', '7'))
    built = build(days)
    if not built:
        print('No new gigs this week; no email.')
        return
    subject, preview, body, n = built
    if mode == 'preview':
        open(os.path.join(ROOT, 'weekly-email-preview.html'), 'w').write(f'<h3>{html.escape(subject)}</h3><p><i>{html.escape(preview)}</i></p>{body}')
        print(subject)
        return
    key = os.environ.get('KIT_API_KEY')
    if not key:
        fail('KIT_API_KEY is not set')
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        'subject': subject,
        'preview_text': preview,
        'description': f'Weekly new gigs {now.date().isoformat()} ({n})',
        'content': body,
        'public': False,
        'published_at': now.isoformat(timespec='seconds'),
        'send_at': (now + datetime.timedelta(minutes=10)).isoformat(timespec='seconds') if mode == 'send' else None,
    }
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), method='POST',
                                 headers={'X-Kit-Api-Key': key, 'Content-Type': 'application/json',
                                          'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        fail(f'Kit refused the broadcast: HTTP {e.code} {e.read().decode()[:500]}')
    b = res.get('broadcast', res)
    print(f"::notice::Kit broadcast {b.get('id')} created ({mode}): {subject}")


if __name__ == '__main__':
    main()
