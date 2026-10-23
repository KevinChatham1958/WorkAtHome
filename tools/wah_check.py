"""Work-from-home check. Run before publishing new gigs:
    python3 tools/wah_check.py <pending.json or ideas.json>
Lists gigs that may fail the WAH Scope Rule (Extraction Spec): no `novisits`
filter, an on-site situation tag, or on-site/route/rental/factory wording.
Flagged gigs are held for Kevin's decision, not published."""
import json, re, sys
ONSITE_TAGS = {"Local travel required", "Needs a truck or cargo vehicle", "Weekend/event-based schedule",
               "Requires travel to source or inspect goods"}
WORDS = re.compile(r"\b(on-site|on site|route|rent(?:al|s)? out|rentals?|kiosk|vending|install(?:ation|s)?|"
                   r"pressure wash|mobile service|job site|courier|deliver(?:y|ies)|crush|shred|baler|pellet|"
                   r"briquette|manufactur\w*|weld\w*|injection mold\w*|factory|industrial)\b", re.I)
data = json.load(open(sys.argv[1]))
items = data if isinstance(data, list) else data.get("entries", data.get("ideas", []))
flagged = 0
for i in items:
    why = []
    if "novisits" not in (i.get("filters") or []): why.append("no novisits filter")
    tags = set(i.get("situation_tags") or []) & ONSITE_TAGS
    if tags: why.append("tags: " + ", ".join(sorted(tags)))
    m = WORDS.search(" ".join([i.get("title", ""), i.get("name", ""), i.get("what", "")]))
    if m: why.append(f"wording: '{m.group(0)}'")
    if why:
        flagged += 1
        print(f"{i['id']} | {i.get('title', i.get('name'))} | {i.get('found')} | {'; '.join(why)}")
print(f"\n{flagged} of {len(items)} flagged for a WAH check.")
