"""Refresh YouTube view counts for every source video in ideas.json.

Writes views.json: {"updated": "YYYY-MM-DD", "views": {"<videoId>": <count>, ...}}
The gig browser (/tool/) reads it to show "1.2M views" on each card and to
offer the "Most viewed" sort.

Runs in GitHub Actions (.github/workflows/update-views.yml) with the secret
YOUTUBE_API_KEY, a YouTube Data API v3 key in Kevin's Google Cloud project
"Side Hustle Intel". Each request covers up to 50 videos and costs 1 unit of
the free 10,000-units-a-day allowance, so a full refresh costs about 12 units.

Videos that are deleted or private come back without a count; the previous
count is kept so a gig doesn't suddenly drop to the bottom of the sort.
"""
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDEAS = os.path.join(ROOT, 'ideas.json')
OUT = os.path.join(ROOT, 'views.json')
API = 'https://www.googleapis.com/youtube/v3/videos'


def video_key(url):
    m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def main():
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key:
        sys.exit('YOUTUBE_API_KEY is not set')
    ideas = json.load(open(IDEAS, encoding='utf-8'))
    ids = sorted({k for k in (video_key(i.get('url')) for i in ideas) if k})

    old = {}
    if os.path.exists(OUT):
        old = json.load(open(OUT, encoding='utf-8')).get('views', {})

    views, missing = {}, []
    for n in range(0, len(ids), 50):
        chunk = ids[n:n + 50]
        q = urllib.parse.urlencode({'part': 'statistics', 'id': ','.join(chunk), 'key': key})
        with urllib.request.urlopen(f'{API}?{q}', timeout=30) as r:
            data = json.load(r)
        got = {it['id']: int(it['statistics']['viewCount'])
               for it in data.get('items', []) if 'viewCount' in it.get('statistics', {})}
        views.update(got)
        missing += [v for v in chunk if v not in got]

    for v in missing:
        if v in old:
            views[v] = old[v]

    out = {'updated': datetime.date.today().isoformat(),
           'views': dict(sorted(views.items()))}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
        f.write('\n')
    print(f'{len(ids)} videos, {len(views)} with counts, '
          f'{len(missing)} not returned by YouTube (deleted/private){": " + ", ".join(missing) if missing else ""}')


if __name__ == '__main__':
    main()
