"""Fetch top YouTube comments for the "What Viewers Say" section (Kevin, Nov 19, 2026).

Runs in GitHub Actions (.github/workflows/fetch-comments.yml) with the YOUTUBE_API_KEY
secret. It does NOT write any summaries; it gathers material for the weekly
"Viewer comments" run, where Claude reads the comments and writes our 2-3 sentence
summaries into data/viewers.json.

What it does:
 1. Checks every source video in ideas.json (videos.list, 50 per call): flags videos
    that are now private or deleted, and videos whose title has changed.
 2. Picks videos that need a summary: no entry in data/viewers.json yet and at least
    21 days old (gigs with no date count as old), most-viewed first, up to --limit.
    Videos marked "few" more than 90 days ago get one re-check (marked recheck: true).
    --videos id1,id2 picks exactly those instead.
 3. For each pick, reads the top comments (commentThreads.list, order=relevance, one
    page of up to 100, with a few replies each). Comment authors are reduced to a
    single flag: is it the video's own creator? No usernames are kept.

Output: a working file (default /tmp/comments-batch.json). The workflow puts it on
the branch "comments-work", which holds only the latest batch (each run replaces it;
it can be deleted any time from the repo's Branches page). Comments are never kept in main (YouTube API rules: see
claude/YouTube API Rules.md in the Project).

Quota: about 30 units for the video check plus 1 unit per video read, of the free
10,000 a day.

Usage: python3 tools/fetch_comments.py [--limit 40] [--videos ID,ID] [--out FILE]
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = 'https://www.googleapis.com/youtube/v3/'
WAIT_DAYS = 21
RECHECK_DAYS = 90
MAX_COMMENTS = 80


def video_key(url):
    m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def call(endpoint, key, **params):
    q = urllib.parse.urlencode(dict(params, key=key))
    try:
        with urllib.request.urlopen(f'{API}{endpoint}?{q}', timeout=30) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            reason = json.load(e)['error']['errors'][0]['reason']
        except Exception:
            reason = f'http {e.code}'
        return None, reason


def clip(t, n):
    t = re.sub(r'\s+', ' ', t or '').strip()
    return t if len(t) <= n else t[:n].rstrip() + '…'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=40)
    ap.add_argument('--videos', default='')
    ap.add_argument('--out', default='/tmp/comments-batch.json')
    a = ap.parse_args()
    key = os.environ.get('YOUTUBE_API_KEY') or sys.exit('YOUTUBE_API_KEY is not set')

    ideas = json.load(open(os.path.join(ROOT, 'ideas.json'), encoding='utf-8'))
    vf = os.path.join(ROOT, 'data', 'viewers.json')
    done = json.load(open(vf, encoding='utf-8')).get('videos', {}) if os.path.exists(vf) else {}
    views = {}
    if os.path.exists(os.path.join(ROOT, 'views.json')):
        views = json.load(open(os.path.join(ROOT, 'views.json'), encoding='utf-8')).get('views', {})

    gigs = {}
    for i in ideas:
        k = video_key(i.get('url'))
        if k:
            gigs.setdefault(k, []).append(i)

    # 1. Check every video.
    info, ids = {}, sorted(gigs)
    for n in range(0, len(ids), 50):
        data, err = call('videos', key, part='snippet,status,statistics', id=','.join(ids[n:n + 50]))
        if err:
            sys.exit(f'videos.list failed: {err}')
        for it in data.get('items', []):
            info[it['id']] = it
    unavailable, title_changes = [], []
    for v in ids:
        it = info.get(v)
        if not it or it.get('status', {}).get('privacyStatus') == 'private':
            unavailable.append({'video': v, 'reason': 'private or deleted' if not it else 'private',
                                'gigs': [{'id': g['id'], 'title': g.get('title') or g['name']} for g in gigs[v]]})
            continue
        new_t = it['snippet'].get('title', '')
        for g in gigs[v]:
            if g.get('video_title') and new_t and g['video_title'].strip() != new_t.strip():
                title_changes.append({'video': v, 'gig': g['id'], 'old': g['video_title'], 'new': new_t})

    # 2. Pick videos.
    today = datetime.date.today()
    def age(v):
        try:
            return (today - datetime.date.fromisoformat(min(g.get('published') or '9999' for g in gigs[v]))).days
        except ValueError:
            return 9999
    gone = {u['video'] for u in unavailable}
    if a.videos:
        picks = [v.strip() for v in a.videos.split(',') if v.strip() in gigs and v.strip() not in gone]
        recheck = set()
    else:
        fresh = [v for v in ids if v not in done and v not in gone and age(v) >= WAIT_DAYS]
        recheck = set()
        for v, e in done.items():
            if v in gigs and v not in gone and e.get('status') == 'few' and not e.get('rechecked'):
                try:
                    if (today - datetime.date.fromisoformat(e.get('date', '')[:7] + '-01')).days >= RECHECK_DAYS:
                        recheck.add(v)
                except ValueError:
                    pass
        pool = sorted(set(fresh) | recheck, key=lambda v: -views.get(v, -1))
        picks = pool[:a.limit]
        backlog_left = len(pool) - len(picks)

    # 3. Read comments.
    out_videos = []
    for v in picks:
        it = info[v]
        chan = it['snippet'].get('channelId')
        entry = {
            'video': v, 'title': it['snippet'].get('title'), 'channel': it['snippet'].get('channelTitle'),
            'published': it['snippet'].get('publishedAt', '')[:10],
            'comment_total': int(it.get('statistics', {}).get('commentCount', 0) or 0),
            'recheck': v in recheck,
            'gigs': [{'id': g['id'], 'title': g.get('title'), 'name': g['name']} for g in gigs[v]],
            'comments': [], 'comments_off': False,
        }
        data, err = call('commentThreads', key, part='snippet,replies', videoId=v, order='relevance',
                         maxResults=100, textFormat='plainText')
        if err == 'commentsDisabled':
            entry['comments_off'] = True
        elif err:
            entry['error'] = err
        else:
            for th in data.get('items', [])[:MAX_COMMENTS]:
                top = th['snippet']['topLevelComment']['snippet']
                c = {'t': clip(top.get('textDisplay'), 500), 'likes': top.get('likeCount', 0),
                     'replies': th['snippet'].get('totalReplyCount', 0)}
                if top.get('authorChannelId', {}).get('value') == chan:
                    c['creator'] = True
                cr = [clip(r['snippet'].get('textDisplay'), 220) for r in th.get('replies', {}).get('comments', [])
                      if r['snippet'].get('authorChannelId', {}).get('value') == chan]
                if cr:
                    c['creator_reply'] = cr[0]
                entry['comments'].append(c)
        out_videos.append(entry)

    out = {'fetched': today.isoformat(), 'videos': out_videos,
           'backlog_left': 0 if a.videos else backlog_left,
           'unavailable': unavailable, 'title_changes': title_changes}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'{len(out_videos)} videos read, {len(unavailable)} unavailable, '
          f'{len(title_changes)} title changes, {out["backlog_left"]} still waiting')


if __name__ == '__main__':
    main()
