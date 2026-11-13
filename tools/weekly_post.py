"""Weekly social post: the newest gigs added to the database (Kevin, Nov 12, 2026).

Lists gigs added to ideas.json in the last DAYS days (read from git history, like
tools/weekly_email.py), newest first, at most 2 per creator so one big batch doesn't
fill the list, up to 15. Prints one JSON object per line: added date, title, creator,
YouTube video date, one-line description, id. Claude then writes the post text
(adding a short plain-language explanation to any title that doesn't explain itself).

Needs git history for the period: `git fetch --shallow-since="10 days ago" origin main`.
Usage: python3 tools/weekly_post.py [DAYS] [LIMIT]
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(rev):
    out = subprocess.run(['git', 'show', f'{rev}:ideas.json'], cwd=ROOT, capture_output=True, text=True)
    if out.returncode:
        return None
    d = json.loads(out.stdout)
    return d if isinstance(d, list) else d.get('ideas', [])


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    log = subprocess.run(['git', 'log', '--format=%H %cs', f'--since={days} days ago', '--', 'ideas.json'],
                         cwd=ROOT, capture_output=True, text=True).stdout.split('\n')
    added = {}
    for line in filter(None, log):  # newest commit first
        sha, date = line.split()
        cur, prev = load(sha), load(sha + '^')
        if cur is None or prev is None:
            sys.exit('Missing git history; run: git fetch --shallow-since="10 days ago" origin main')
        before = {i['id'] for i in prev}
        for i in cur:
            if i['id'] not in before and i['id'] not in added:
                added[i['id']] = (date, i)
    live = {i['id'] for i in load('HEAD')}
    items = sorted((v for k, v in added.items() if k in live), key=lambda x: x[0], reverse=True)
    per = collections.Counter()
    shown = 0
    for date, i in items:
        if per[i['found']] >= 2:
            continue
        per[i['found']] += 1
        print(json.dumps({'added': date, 'title': i.get('title') or i['name'], 'creator': i['found'],
                          'video_date': i.get('published', ''), 'one_line': i['name'], 'id': i['id']},
                         ensure_ascii=False))
        shown += 1
        if shown == limit:
            break
    print(json.dumps({'total_added_this_period': len(items), 'total_gigs': len(live)}))


if __name__ == '__main__':
    main()
