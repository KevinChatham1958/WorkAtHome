"""Keep creator names ("found" in ideas.json) clean and consistent (Kevin, Nov 5, 2026).

Rules:
  - One name per real creator: Chris Koerner's podcast, highlights channel and guest
    appearances are all "Chris Koerner"; hosts' shows keep the host/channel name.
  - No guest or show notes in the name: "X (guest: Y)", "X (interviewed by Y)",
    "X (summarizing Y)", "X and Y" combinations → the presenter / channel.
  - No channel taglines: "Name | tagline" → "Name".
  - No ALL-CAPS names: "SUCCESSFUL ENTREPRENEUR" → "Successful Entrepreneur"
    (short acronyms like AI, TV, KDP stay capitalised).

build_pages.py calls clean_ideas() before every build, so any gig added with an old-style
name is fixed automatically and ideas.json is saved with the clean name. Add new
one-off renames to ALIASES.
"""
import re

ALIASES = {
    "Chris Koerner on The Koerner Office Podcast": "Chris Koerner",
    "The Koerner Office Highlights": "Chris Koerner",
    "Chris Koerner (guest on Marketing Against the Grain)": "Chris Koerner",
    "Mark Tilbury and Iman Gadzhi (covered independently by both)": "Mark Tilbury",
    "Balint Adorjan (interviewed by ItsKeaton)": "Balint Adorjan",
    "Kai Stone and Michael, Stone Systems": "Kai Stone",
    "Udo Onyekwere (summarizing Iman Gadzhi)": "Udo Onyekwere",
    "AutoDS - Build Your Online Income": "AutoDS",
    "Olly Richards - Business": "Olly Richards",
    "The Savvy Couple - Kelan & Brittany": "The Savvy Couple",
    "How Much (Idan)": "How Much?",
    "Jeff (5 TINY but Profitable KDP Niches)": "JeffSetLife",
    "Cam (Camlife)": "Camlife",
    "Ac Hampton (SupremeEcom)": "Ac Hampton",
    "affiliatemarketingdude (Marcus)": "affiliatemarketingdude",
    "Jo | Digital Product Designer": "Jo, Digital Product Designer",
    "Mr. AI CASH": "Mr. AI Cash",
    "BRAD LEA TV": "Brad Lea TV",
}
ACRONYMS = {'AI', 'TV', 'KDP', 'SEO', 'POD', 'UGC', 'USA', 'US', 'UK', 'DIY', 'CEO', 'VA', 'PR', 'ROI', 'DoD'}


def clean_name(name):
    n = ' '.join(str(name or '').replace('™', '').replace('®', '').split())
    if n in ALIASES:
        return ALIASES[n]
    if n.startswith('Chris Koerner'):
        return 'Chris Koerner'
    n = re.sub(r'\s*\((?:guest|interviewed|summari[sz]ing|with)\b[^)]*\)\s*$', '', n, flags=re.I)
    if ' | ' in n:
        n = n.split(' | ')[0].strip()
    # "Host Show and Guest" combinations: keep the first name when it's a known show/host pattern
    m = re.match(r'^(.*?(?:Show|Podcast|AI))\s+and\s+.+$', n)
    if m:
        n = m.group(1)
    if n in ALIASES:
        return ALIASES[n]
    words = n.split(' ')
    if any(len(w) >= 4 and w.isupper() for w in words):
        n = ' '.join(w if (w in ACRONYMS or not w.isupper() or len(w) <= 2) else w.capitalize() for w in words)
    return n


def clean_ideas(ideas):
    """Fix names in place; returns {old: new} for anything changed."""
    changed = {}
    for i in ideas:
        new = clean_name(i.get('found'))
        if new and new != i.get('found'):
            changed[i['found']] = new
            i['found'] = new
    return changed
