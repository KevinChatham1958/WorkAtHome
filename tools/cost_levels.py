"""Startup cost levels (CRO To-Do item 11, Nov 5, 2026).

Every gig keeps its free-text `cost` (shown in full on its own page) and gets a
`cost_level`, one of LEVELS, shown on every card and used by the "Under $100 to start"
filter, "no money" searches and the quiz.

Meaning: roughly what it takes to get started (first month or two), beyond a computer and
internet. Ongoing ad spend counts. Optional or "later, when scaling" costs don't.

How it's decided:
  1. OVERRIDES (by gig id) — hand decisions, always win.
  2. Dollar figures in the cost text: the first relevant amount (the lower end of a range;
     monthly fees x2; daily ad budgets x30; "under $X" only if nothing else is given;
     amounts about income, fees charged to clients, optional, later or course spending ignored).
  3. Otherwise the wording: near-zero / free / very low -> Under $100; "low" -> Under $100
     if the gig carried the old low-cost tag, else $100-$500; low-to-moderate -> $100-$500;
     moderate / ad budget -> $500-$2,000; high -> Over $2,000.
  When the text has dollar figures, they decide; otherwise the wording does.

build_pages.py calls set_levels() before every build, so new gigs get a level
automatically and the low-cost filter always matches the level.
"""
import re

LEVELS = ["Under $100", "$100–$500", "$500–$2,000", "Over $2,000"]
OVERRIDES = {
    # Hand decisions (Nov 5, 2026) where the cost text alone misleads
    "expired-domain-niche-directory-flat-fee": "$500–$2,000",   # one premium domain cost $18k; cheaper ones exist
    "ai-guided-nonfiction-kdp-book-coauthor-software-krrd": "$100–$500",     # $49/month tool + $150 book credit
    "aged-domain-first-strategy": "$100–$500",
    "rock-tumbler-polished-stone-gift-bags": "$100–$500",     # $90 tumbler + $35-40 supplies
    "amazon-fba-brand-direct-wholesale-beginner-setup": "$500–$2,000",   # needs wholesale order capital
    "chatgpt-digital-product-live-launch-challenge": "$100–$500",     # tools plus an ad budget
    "claude-shopify-dropshipping-50-dollar-ai-ugc-ads": "$100–$500",
    "pin-back-button-maker-custom-orders": "$100–$500",
    "ai-social-video-package-for-businesses-kok2": "$100–$500",
    "2x4-christmas-tree-advent-countdown-woodcraft-etsy": "$100–$500",     # needs basic power tools
    "wholesale-3d-printed-toy-company": "$100–$500",     # needs a 3D printer
    "simple-2x4-furniture-local-marketplace-sales": "$100–$500",
    "multi-site-seo-content-network-ad-revenue": "$100–$500",     # $7k/month is the presenter's 20-site portfolio
    "ai-coded-niche-hobby-software-subscription-collector-community": "$500–$2,000",   # ~$500 in build credits per app
    "free-reviews-local-seo-agency-upsell": "$500–$2,000",   # $297/month GoHighLevel plus per-client tool fees
    "ai-agent-local-service-matchmaking-agency": "Under $100",    # agent plans start free
    "simple-printable-planner-gumroad-pinterest-wril": "Under $100",    # free listing; the $100 plan was the creator's choice
}

_SKIP = re.compile(r'optional|later|when scal|at scale|brand-level|per client|client fee|charge|'
                   r'earn|income|revenue|profit|commission|retainer|payout|price[sd]? at|sell[s]? for|'
                   r'per sale|per order|per pallet|per batch|per lot|course|spent|once you have', re.I)
_AMT = re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k|K)?(?:\s*(?:-|–|to)\s*\$?\s?(\d[\d,]*(?:\.\d+)?)\s*(k|K)?)?'
                  r'(\s*(?:/|per|a)\s*(?:mo\b|month|year|yr|day))?')


def _num(s, k):
    v = float(s.replace(',', ''))
    return v * 1000 if k else v


def from_dollars(text):
    """Best estimate of the starting cost from $ figures, or None."""
    first = under = None
    for m in _AMT.finditer(text):
        # judge each amount by its own clause (between ; , ( ) and similar breaks), nearby words only
        a = max(text.rfind(c, 0, m.start()) for c in ';,()—') + 1
        ends = [i for i in (text.find(c, m.end()) for c in ';,()—') if i != -1]
        ctx = text[max(a, m.start() - 40):min(min(ends) if ends else len(text), m.end() + 50)]
        if _SKIP.search(ctx):
            continue
        low = _num(m.group(1), m.group(2))
        per = (m.group(5) or '').lower()
        if 'day' in per:
            low *= 30
        elif 'year' in per or 'yr' in per:
            pass
        elif per:
            low *= 2
        if re.search(r'under\s*(about\s*)?$', text[max(0, m.start() - 12):m.start()], re.I):
            under = low * 0.99 if under is None else under
            continue
        if first is None:
            first = low
    return first if first is not None else under


def _band(v):
    return 0 if v <= 100 else 1 if v < 500 else 2 if v < 2000 else 3


def from_words(text, had_lowcost):
    t = text.lower().strip()
    if re.match(r'(high|moderate to high|medium to high)', t):
        return 3
    if re.match(r'(moderate|medium|needs (ongoing )?ad budget|a few hundred to a few thousand)', t) or 'ad budget' in t[:40]:
        return 2
    if re.match(r'(low[- ]to[- ](moderate|medium)|low-moderate)', t):
        return 0 if had_lowcost else 1
    if re.match(r'(near[- ]zero|free|no |none|zero|very low|minimal|almost nothing|\$0)', t):
        return 0
    if re.match(r'low', t):
        return 0 if had_lowcost else 1
    return 0 if had_lowcost else 1


def level_index(gig):
    if gig.get('id') in OVERRIDES:
        return LEVELS.index(OVERRIDES[gig['id']])
    text = str(gig.get('cost') or '')
    had = 'lowcost' in (gig.get('filters') or [])
    w = from_words(text, had)
    d = from_dollars(text)
    return _band(d) if d is not None else w


def set_levels(ideas, keep_existing=True):
    """Give every gig a cost_level and make the 'lowcost' filter match it. Returns count changed."""
    n = 0
    for g in ideas:
        if not (keep_existing and g.get('cost_level') in LEVELS):
            g['cost_level'] = LEVELS[level_index(g)]
            n += 1
        f = list(g.get('filters') or [])
        want = g['cost_level'] == LEVELS[0]
        if want and 'lowcost' not in f:
            f.append('lowcost'); g['filters'] = f; n += 1
        elif not want and 'lowcost' in f:
            f.remove('lowcost'); g['filters'] = f; n += 1
    return n


def is_estimate(gig):
    """True when the cost text gives no dollar figures, so the level is our own estimate."""
    return from_dollars(str(gig.get('cost') or '')) is None and gig.get('id') not in OVERRIDES
