#!/usr/bin/env python3
"""Release the next batch of idea pages (Production Process: static pages rollout).

Adds up to N not-yet-released ideas to pages-release.json, spread across
categories in proportion to how many unreleased ideas each category has
(newest ideas first within a category). When nothing is left to release,
sets "release_all": true so every future idea gets a page automatically.

Usage:  python3 tools/release_batch.py [N]      (default 150)
Then:   python3 tools/build_pages.py, commit, push.
Prints one summary line: "released X, Y left" or "release_all now on".
"""
import json, sys, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150

ideas = json.loads((ROOT / 'ideas.json').read_text(encoding='utf-8'))
rel_path = ROOT / 'pages-release.json'
rel = json.loads(rel_path.read_text(encoding='utf-8'))

if rel.get('release_all'):
    print('release_all already on; nothing to do')
    sys.exit(0)

live_ids = {i['id'] for i in ideas}
released = [x for x in rel.get('released', []) if x in live_ids]  # drop deleted ideas
done = set(released)
pending = [i for i in ideas if i['id'] not in done]

if not pending:
    rel['release_all'] = True
    rel['released'] = released
    rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('release_all now on (every idea has a page)')
    sys.exit(0)

by_cat = defaultdict(list)
for i in pending:
    by_cat[i.get('category', '')].append(i)
for lst in by_cat.values():
    lst.sort(key=lambda i: i.get('published', ''), reverse=True)

take = min(N, len(pending))
# proportional quota per category, then fill any remainder round-robin
quota = {c: math.floor(take * len(l) / len(pending)) for c, l in by_cat.items()}
left = take - sum(quota.values())
for c in sorted(by_cat, key=lambda c: -len(by_cat[c])):
    if left <= 0:
        break
    if quota[c] < len(by_cat[c]):
        quota[c] += 1
        left -= 1

new = [i['id'] for c, l in by_cat.items() for i in l[:quota[c]]]
rel['released'] = released + new
if len(pending) == len(new):
    rel['release_all'] = True
rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
remaining = len(pending) - len(new)
print(f"released {len(new)}, {remaining} left" + (' (release_all now on)' if rel.get('release_all') else ''))
