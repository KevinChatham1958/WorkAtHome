"""Build the weekly "new gigs" email and hand it to Kit (kit.com).

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
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://sidehustleintel.org'
API = 'https://api.kit.com/v4/broadcasts'
MAX_REST = 25  # longest "Also new" list; a bigger week links to the rest


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


def gig_html(i, pages, views):
    v = views.get(video_key(i.get('url')), -1)
    meta = f"{html.escape(i['found'])}" + (f" · {fmt_views(v)} on YouTube" if v >= 0 else '')
    return (f'<tr><td style="padding:12px 0;border-bottom:1px solid #e3e6ea">'
            f'<a href="{link_for(i, pages)}" style="font-size:17px;font-weight:bold;color:#1f3a5f;text-decoration:none">'
            f'{html.escape(i.get("title") or i["name"])}</a>'
            f'<div style="font-size:15px;color:#16202e;margin:4px 0">{html.escape(first_sentence(i.get("what")))}</div>'
            f'<div style="font-size:13px;color:#6b7280">{meta}</div></td></tr>')


def build(days):
    ideas = json.load(open(os.path.join(ROOT, 'ideas.json'), encoding='utf-8'))
    before = {i['id'] for i in old_ideas(days)}
    if not before:
        sys.exit('Could not read ideas.json from git history (checkout needs full history).')
    new = [i for i in ideas if i['id'] not in before]
    try:
        views = json.load(open(os.path.join(ROOT, 'views.json'))).get('views', {})
    except FileNotFoundError:
        views = {}
    try:
        pages = set(json.load(open(os.path.join(ROOT, 'page-index.json'))).get('ideas', []))
    except FileNotFoundError:
        pages = set()
    if not new:
        return None
    vw = lambda i: views.get(video_key(i.get('url')), -1)
    new.sort(key=vw, reverse=True)
    # Most watched: one gig per video, so a "10 ideas" video can't fill the list.
    top, seen = [], set()
    for i in new:
        k = video_key(i.get('url')) or i['id']
        if k not in seen and len(top) < 5:
            top.append(i); seen.add(k)
    rest = [i for i in new if i not in top]
    more = max(0, len(rest) - MAX_REST)
    rest = sorted(rest[:MAX_REST], key=lambda i: (i['category'], (i.get('title') or i['name']).lower()))
    n, total = len(new), len(ideas)
    subject = f"{n} new work-from-home gig{'s' if n != 1 else ''} this week"
    preview = f"Most watched: {top[0].get('title') or top[0]['name']} ({top[0]['found']})"
    rows_top = ''.join(gig_html(i, pages, views) for i in top)
    rows_rest = ''.join(gig_html(i, pages, views) for i in rest)
    body = f'''<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#16202e">
<p style="font-size:16px">This week we added <strong>{n}</strong> work-from-home gig{'s' if n != 1 else ''} to Side Hustle Intel, taken from YouTube creators' videos. Each one is explained in plain English, with our honest opinion and a link to the source video. There are now {total:,} in the database.</p>
<h2 style="font-size:20px;color:#1f3a5f;margin:24px 0 4px">Most watched this week</h2>
<p style="font-size:13px;color:#6b7280;margin:0">Ranked by the source video's YouTube views. Popular isn't the same as good; read our opinion on each.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_top}</table>
{f'<h2 style="font-size:20px;color:#1f3a5f;margin:28px 0 4px">Also new</h2><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_rest}</table>' if rest else ''}
{f'<p style="font-size:15px">...and {more} more new this week, all in the gig browser (sort by Newest first).</p>' if more else ''}
<p style="font-size:16px;margin-top:28px"><a href="{SITE}/tool/" style="color:#1f3a5f;font-weight:bold">Browse all {total:,} gigs &rarr;</a></p>
<p style="font-size:13px;color:#6b7280">You're getting this because you signed up for weekly gig updates at sidehustleintel.org. Side Hustle Intel is free and independent: we don't sell courses and creators don't pay to be included.</p>
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
        sys.exit('KIT_API_KEY is not set')
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
        sys.exit(f'Kit refused the broadcast: HTTP {e.code} {e.read().decode()[:500]}')
    b = res.get('broadcast', res)
    print(f"Kit broadcast {b.get('id')} created ({mode}): {subject}")


if __name__ == '__main__':
    main()
