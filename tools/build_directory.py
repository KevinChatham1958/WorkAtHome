"""Build the data for the unlisted creator directory (/creator-directory/).

Runs in GitHub Actions (.github/workflows/build-directory.yml) with the secret
YOUTUBE_API_KEY (YouTube Data API v3; free quota 10,000 units/day; a full run
uses roughly 1,000-2,000 units).

Steps:
1. Every YouTube video in ideas.json -> its channel (videos.list, snippet).
2. Those channels, minus removed creators (data/directory_exclude.json)
   -> channel facts (channels.list: name, handle, photo, country, start year,
   subscribers, video count, total views, uploads playlist).
3. Each channel's uploads from the last 2 years (playlistItems.list), then
   durations and views (videos.list); Shorts (3 minutes or less) are dropped.
   Videos that are in our database are always kept.
4. Our own data per channel and per video (gig count, topics, gig links).

Writes (served with the site):
  creator-directory/creators.json  one row per creator
  creator-directory/videos.json    compact list of videos for the search
  data/video_channels.json         videoId -> [channelId, channel title]
                                   (used to clean up creator names in ideas.json)
"""
import collections
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
YEARS = 2
SHORT_MAX = 180  # seconds; YouTube Shorts can be up to 3 minutes
KEY = os.environ.get('YOUTUBE_API_KEY', '')
calls = 0


def fail(msg):
    print('::error::' + msg.replace('\n', ' '))
    sys.exit(1)


def api(endpoint, **params):
    global calls
    params['key'] = KEY
    url = API + endpoint + '?' + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                calls += 1
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code == 404:
                return {'items': []}
            if attempt == 2 or e.code in (400, 403):
                fail(f'YouTube API {endpoint} HTTP {e.code}: {body}')
        except Exception as e:  # network hiccup
            if attempt == 2:
                fail(f'YouTube API {endpoint}: {e}')


def chunks(seq, n=50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def video_key(url):
    m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def seconds(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def main():
    if not KEY:
        fail('YOUTUBE_API_KEY is not set')
    ideas = json.load(open(os.path.join(ROOT, 'ideas.json'), encoding='utf-8'))
    try:
        pages = set(json.load(open(os.path.join(ROOT, 'page-index.json'))).get('ideas', []))
    except FileNotFoundError:
        pages = set()
    try:
        exclude = set(json.load(open(os.path.join(ROOT, 'data', 'directory_exclude.json'))).get('channel_ids', []))
    except FileNotFoundError:
        exclude = set()

    gigs_by_video = collections.defaultdict(list)
    for i in ideas:
        v = video_key(i.get('url'))
        if v:
            gigs_by_video[v].append(i)

    # 1. our videos -> channels
    vid_channel = {}
    for chunk in chunks(sorted(gigs_by_video)):
        for it in api('videos', part='snippet', id=','.join(chunk), maxResults=50).get('items', []):
            vid_channel[it['id']] = [it['snippet']['channelId'], it['snippet']['channelTitle']]
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'data', 'video_channels.json'), 'w') as f:
        json.dump(dict(sorted(vid_channel.items())), f, indent=0, ensure_ascii=False)
        f.write('\n')

    channel_ids = sorted({c for c, _ in vid_channel.values()} - exclude)

    # 2. channel facts
    chans = {}
    for chunk in chunks(channel_ids):
        for it in api('channels', part='snippet,statistics,contentDetails', id=','.join(chunk), maxResults=50).get('items', []):
            sn, stt = it['snippet'], it.get('statistics', {})
            thumbs = sn.get('thumbnails', {})
            chans[it['id']] = {
                'id': it['id'],
                'name': sn.get('title', ''),
                'handle': sn.get('customUrl', ''),
                'photo': (thumbs.get('medium') or thumbs.get('default') or {}).get('url', ''),
                'country': sn.get('country', ''),
                'since': (sn.get('publishedAt') or '')[:4],
                'subs': None if stt.get('hiddenSubscriberCount') else int(stt.get('subscriberCount', 0)),
                'videos': int(stt.get('videoCount', 0)),
                'views': int(stt.get('viewCount', 0)),
                'uploads': it.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads', ''),
            }

    # 3. recent uploads per channel
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=365 * YEARS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    uploads = {}  # videoId -> [channelId, title, date]
    for cid, ch in chans.items():
        token, done = None, False
        while ch['uploads'] and not done:
            params = dict(part='snippet,contentDetails', playlistId=ch['uploads'], maxResults=50)
            if token:
                params['pageToken'] = token
            res = api('playlistItems', **params)
            for it in res.get('items', []):
                when = it.get('contentDetails', {}).get('videoPublishedAt') or it['snippet'].get('publishedAt', '')
                if when and when < cutoff:
                    done = True
                    continue
                vid = it['contentDetails']['videoId']
                uploads[vid] = [cid, it['snippet'].get('title', ''), when[:10]]
            token = res.get('nextPageToken')
            if not token:
                done = True
    # always include our own videos, even if older or short
    missing = [v for v in vid_channel if v not in uploads and vid_channel[v][0] in chans]

    # durations + views (and details for our older videos)
    stats = {}
    for chunk in chunks(sorted(set(uploads) | set(missing))):
        for it in api('videos', part='contentDetails,statistics,snippet', id=','.join(chunk), maxResults=50).get('items', []):
            stats[it['id']] = (seconds(it['contentDetails'].get('duration')),
                               int(it.get('statistics', {}).get('viewCount', 0) or 0),
                               it['snippet'].get('title', ''),
                               (it['snippet'].get('publishedAt') or '')[:10])
    for v in missing:
        if v in stats:
            uploads[v] = [vid_channel[v][0], stats[v][2], stats[v][3]]

    # 4. assemble
    cidx = {cid: n for n, cid in enumerate(sorted(chans, key=lambda c: -(chans[c]['subs'] or 0)))}
    gig_ids_for = lambda v: [g['id'] for g in gigs_by_video.get(v, [])]
    videos = []
    for v, (cid, title, date) in uploads.items():
        dur, views = stats.get(v, (0, 0))[:2]
        ours = gig_ids_for(v)
        if not ours and (v not in stats or dur <= SHORT_MAX):
            continue  # Shorts, live placeholders, removed videos
        videos.append([v, cidx[cid], title, date, views, ours])
    videos.sort(key=lambda r: r[3], reverse=True)

    gig_titles = {}
    per_channel = collections.defaultdict(lambda: {'gigs': 0, 'vids': set(), 'cats': collections.Counter(), 'found': collections.Counter()})
    for v, gl in gigs_by_video.items():
        if v not in vid_channel:
            continue
        cid = vid_channel[v][0]
        for g in gl:
            gig_titles[g['id']] = [g.get('title') or g['name'], 1 if g['id'] in pages else 0]
            pc = per_channel[cid]
            pc['gigs'] += 1
            pc['vids'].add(v)
            pc['cats'][g['category']] += 1
            pc['found'][g['found']] += 1

    creators = []
    for cid in sorted(chans, key=lambda c: cidx[c]):
        ch, pc = chans[cid], per_channel[cid]
        creators.append({**{k: ch[k] for k in ('id', 'name', 'handle', 'photo', 'country', 'since', 'subs', 'videos', 'views')},
                         'our_gigs': pc['gigs'], 'our_videos': len(pc['vids']),
                         'topics': [c for c, _ in pc['cats'].most_common(2)],
                         'found': pc['found'].most_common(1)[0][0] if pc['found'] else ''})

    out_dir = os.path.join(ROOT, 'creator-directory')
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    with open(os.path.join(out_dir, 'creators.json'), 'w', encoding='utf-8') as f:
        json.dump({'updated': today, 'creators': creators}, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(out_dir, 'videos.json'), 'w', encoding='utf-8') as f:
        json.dump({'updated': today, 'years': YEARS, 'gigs': gig_titles, 'videos': videos}, f,
                  ensure_ascii=False, separators=(',', ':'))
    print(f'::notice::{len(creators)} creators, {len(videos)} videos '
          f'({sum(1 for r in videos if r[5])} in our database), {calls} API calls')


if __name__ == '__main__':
    main()
