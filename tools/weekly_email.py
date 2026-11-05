"""Build the weekly email (Gig of the Week in full, then 7 more new gigs by name) and hand it to Kit (kit.com).

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
MORE = 7  # new gigs listed by name under the Gig of the Week


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


def link_for(i, pages):
    if i['id'] in pages:
        return f"{SITE}/ideas/{i['id']}/"
    return f"{SITE}/tool/?open={i['id']}"


FONT = 'font-family:Arial,Helvetica,sans-serif'
LABEL = 'font-size:12px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#C2410C;margin:0 0 4px'
SECTION = 'font-size:13px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#0F3D57;margin:18px 0 6px;padding-top:10px;border-top:1px solid #E3EAEE'
TEXT = 'font-size:16px;line-height:1.55;color:#16202e;margin:0'


def paras(t):
    """Full text, keeping any paragraph breaks."""
    return ''.join(f'<p style="{TEXT};margin:0 0 10px">{html.escape(x.strip())}</p>'
                   for x in re.split(r'\n\s*\n', (t or '').strip()) if x.strip())


def gig_of_week_html(i, pages, views):
    """The Gig of the Week, shown in full with the same four sections as the site."""
    v = views.get(video_key(i.get('url')), -1)
    meta = f"From <strong>{html.escape(i['found'])}</strong>'s YouTube video" + (f" &middot; {fmt_views(v)}" if v >= 0 else '')
    link = link_for(i, pages)
    sections = ''.join(f'<p style="{SECTION}">{label}</p>{paras(i.get(key))}'
                       for label, key in (('What It Is', 'what'), ('The Pitch', 'pitch'),
                                          ("Who It's Best For", 'best'), ('The Truth (as we see it)', 'truth')))
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;border:2px solid #E3EAEE;border-radius:12px;background:#FFFFFF">
<tr><td style="padding:18px 20px 20px;{FONT}">
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 10px"><tr><td style="background:#FFF4ED;border:1.5px solid #F6D3BF;border-radius:999px;padding:4px 12px;{FONT};font-size:12px;font-weight:bold;letter-spacing:1.5px;color:#C2410C">GIG OF THE WEEK</td></tr></table>
  <a href="{link}" style="font-size:24px;line-height:1.25;font-weight:bold;color:#0F3D57;text-decoration:none">{html.escape(i.get("title") or i["name"])}</a>
  <p style="font-size:13px;color:#6b7280;margin:4px 0 4px">{html.escape(i.get('category', ''))} &middot; {html.escape(i.get('cost', ''))}</p>
  <p style="font-size:13px;color:#6b7280;margin:0 0 6px">{meta}</p>
  {sections}
  <p style="margin:14px 0 0;font-size:16px"><a href="{link}" style="color:#1A56DB;text-decoration:underline">See it in the database &rarr;</a></p>
</td></tr></table>"""


SIGNOFF = ("<p style=\"font-size:16px;margin:24px 0 4px\">Thanks for reading,</p>"
           "<p style=\"font-size:16px;margin:0 0 10px\">Kevin<br><span style=\"color:#6b7280\">Side Hustle Intel</span></p>"
           "<p style=\"margin:0 0 16px\"><a href=\"https://sidehustleintel.org/\"><img src=\"https://sidehustleintel.org/assets/logo-horizontal.png\" width=\"170\" alt=\"Side Hustle Intel\" style=\"display:block;width:170px;height:auto;border:0\"></a></p>"
           "<p style=\"font-size:15px;color:#3C5260\">P.S. Hit reply and tell me what kind of gigs you'd like to see more of. I read every reply.</p>")


def by_views(pool, views):
    """Most-viewed first, one gig per video."""
    out, seen = [], set()
    for i in sorted(pool, key=lambda i: views.get(video_key(i.get('url')), -1), reverse=True):
        k = video_key(i.get('url')) or i['id']
        if k not in seen:
            out.append(i); seen.add(k)
    return out


def build(days):
    ideas = json.load(open(os.path.join(ROOT, 'ideas.json'), encoding='utf-8'))
    before = {i['id'] for i in old_ideas(days)}
    if not before:
        fail('Could not read ideas.json from git history (checkout needs full history).')
    new = [i for i in ideas if i['id'] not in before]
    if not new:
        return None
    try:
        views = json.load(open(os.path.join(ROOT, 'views.json'))).get('views', {})
    except FileNotFoundError:
        views = {}
    try:
        pages = set(json.load(open(os.path.join(ROOT, 'page-index.json'))).get('ideas', []))
    except FileNotFoundError:
        pages = set()

    # Gig of the Week: the week's most-watched new gig (Kevin can swap it in the Kit draft).
    # The other 7: the next most-watched new gigs, one per video, creators varied where possible.
    ranked = by_views(new, views)
    gotw = ranked[0]
    rest = ranked[1:]
    more, creators = [], {gotw['found']}
    for i in rest:                      # first pass: a different creator each
        if i['found'] not in creators:
            more.append(i); creators.add(i['found'])
        if len(more) == MORE:
            break
    for i in rest:                      # top up if the week had few creators
        if len(more) == MORE:
            break
        if i not in more:
            more.append(i)
    if len(more) < MORE:                # top up from the week's other gigs (same video)
        for i in sorted(new, key=lambda i: views.get(video_key(i.get('url')), -1), reverse=True):
            if len(more) == MORE:
                break
            if i is not gotw and i not in more:
                more.append(i)

    n, total = len(new), len(ideas)
    title = gotw.get('title') or gotw['name']
    subject = f'Gig of the Week: {title}'
    preview = f'Plus {len(more)} more of the newest work-at-home gigs.' if more else 'This week\'s newest work-at-home gig.'
    card = gig_of_week_html(gotw, pages, views)
    more_rows = ''.join(
        f'<tr><td style="padding:9px 0;border-bottom:1px solid #E3EAEE;{FONT}">'
        f'<a href="{link_for(i, pages)}" style="font-size:17px;font-weight:bold;color:#0F3D57;text-decoration:none">{html.escape(i.get("title") or i["name"])}</a></td></tr>'
        for i in more)
    more_html = (f'<tr><td style="padding:6px 0 18px"><p style="{LABEL};font-size:13px">{len(more)} more new gigs</p>'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{more_rows}</table></td></tr>') if more else ''
    count_line = f"the Gig of the Week, then {len(more)} more of the newest gigs from the database" if more else "the Gig of the Week"

    # Personal matches (Nov 3, 2026, Production Process §17): quiz-takers who gave their email have
    # their filtered gig-browser link (newest first) saved in the Kit custom field "quiz_link".
    # Kit's Liquid shows them a personal button; everyone else gets an invitation to take the quiz.
    QUIZ_BLOCK = (
        '{% if subscriber.quiz_link and subscriber.quiz_link != "" %}'
        '<tr><td align="center" style="padding:6px 0 20px">'
        '<a href="{{ subscriber.quiz_link }}" style="display:inline-block;background:#C2410C;color:#FFFFFF;'
        'font-size:17px;font-weight:bold;text-decoration:none;padding:13px 24px;border-radius:8px">'
        'See this week&#39;s new gigs that match your quiz answers &rarr;</a></td></tr>'
        '{% else %}'
        '<tr><td align="center" style="padding:6px 0 20px">'
        f'<p style="font-size:15px;color:#3C5260;margin:0">Want your own list? <a href="{SITE}/quiz/?from=email" '
        'style="color:#9A3412;font-weight:bold">Take the 60-second quiz</a> and every email will include a link to the new gigs that fit you.</p>'
        '</td></tr>'
        '{% endif %}')
    body = f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF"><tr><td align="center" style="padding:8px 12px 20px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;{FONT};color:#16202e">
<tr><td style="padding:4px 4px 18px">
  <p style="font-size:16px;line-height:1.55;margin:0">Hi, it's Kevin from <a href="{SITE}/" style="color:#0F3D57;font-weight:bold">SideHustleIntel.org</a>, the free database of work-at-home gigs you signed up for. Every Saturday I send {count_line}.</p>
</td></tr>
<tr><td>{card}</td></tr>
{more_html}
{QUIZ_BLOCK}
<tr><td align="center" style="padding:4px 0 22px">
  <a href="{SITE}/tool/" style="font-size:16px;font-weight:bold;color:#0F3D57">Browse every gig &rarr;</a>
  <p style="font-size:14px;color:#6b7280;margin:8px 0 0">{n} gig{'s were' if n != 1 else ' was'} added this week. There are now {total:,} in the free database.</p>
</td></tr>
<tr><td style="border-top:1px solid #E3EAEE;padding:18px 4px 0">{SIGNOFF}
  <p style="font-size:15px;color:#3C5260;line-height:1.5;margin:0 0 14px"><strong>Your subscriber bonus:</strong> the <a href="{SITE}/creator-directory/" style="color:#1A56DB">Creator Directory</a>, every creator in our database plus their videos from the last two years, searchable by subject.</p>
  <p style="font-size:13px;color:#6b7280;line-height:1.5">You're getting this because you signed up for the weekly email at <a href="{SITE}/" style="color:#6b7280">SideHustleIntel.org</a>. Side Hustle Intel is free and independent: I don't sell courses, and creators don't pay to be included.</p>
  <p style="font-size:14px;color:#6b7280;margin:0">(Not for you anymore? <a href="{{{{ unsubscribe_url }}}}" style="color:#6b7280">Unsubscribe here</a>.)</p>
</td></tr>
</table></td></tr></table>"""
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
        open(os.path.join(ROOT, 'weekly-email-preview.html'), 'w').write(body.replace('{{ unsubscribe_url }}', '#'))
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
