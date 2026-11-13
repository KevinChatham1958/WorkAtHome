"""Weekly social post: the newest work-at-home gigs on YouTube (Kevin, Nov 12, 2026).

Picks the gigs in ideas.json whose source videos are the newest on YouTube (by the
`published` field, the video's date), ONE PER CREATOR, up to LIMIT (default 10).
Prints one JSON object per line: title, creator, video_date, one-line description,
video URL, id; the last line gives the total gig count. Claude then writes the post
(adding a short plain-language explanation to any title that doesn't explain itself).

Usage: python3 tools/weekly_post.py [LIMIT]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    d = json.loads((ROOT / 'ideas.json').read_text())
    ideas = d if isinstance(d, list) else d.get('ideas', [])
    seen, shown = set(), 0
    for i in sorted(ideas, key=lambda i: i.get('published', ''), reverse=True):
        if i['found'] in seen:
            continue
        seen.add(i['found'])
        print(json.dumps({'title': i.get('title') or i['name'], 'creator': i['found'],
                          'video_date': i.get('published', ''), 'one_line': i['name'],
                          'url': i['url'], 'id': i['id']}, ensure_ascii=False))
        shown += 1
        if shown == limit:
            break
    print(json.dumps({'total_gigs': len(ideas)}))


if __name__ == '__main__':
    main()
