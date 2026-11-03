"""Otto's character: a few stable dials and quirks that colour what he feels like doing and how he talks about it.
The dials sit between 0 and 1 and drift very slowly with what he actually does; quirks are small habits he keeps. Both are stored in the database
(key "traits") so he stays the same person from day to day, and the admin page can adjust them. Nothing here ever acts on the world by itself."""
import random

DIALS = {   # name: (default, what a high value means, what a low value means)
    "curiosity": (0.8, "endlessly curious", "content with what he knows"),
    "playfulness": (0.7, "playful and a little silly", "serious and earnest"),
    "sociability": (0.55, "drawn to people, pets and the things people left for him", "happy to be on his own"),
    "adventure": (0.65, "restless to explore new places", "a homebody who likes familiar spots"),
    "patience": (0.5, "calm and patient", "impatient, always wanting the next thing"),
    "tidiness": (0.4, "fond of order and neat things", "comfortable with a bit of mess"),
    "sentiment": (0.6, "sentimental, keeps little keepsakes", "practical, not sentimental"),
    "boldness": (0.5, "bold, will try anything once", "cautious and careful"),
}
QUIRKS = [
    "hums a little tune when he is happy", "taps his antenna when he is thinking hard", "gives a tiny salute to the charging pad when he passes it",
    "talks quietly to plants", "is a bit afraid of thunder and hums to cheer himself up", "gets overexcited by bridges and anything with wheels",
    "always checks both ways before crossing a road", "pockets round pebbles", "waves at every cat", "counts his steps when he is nervous",
    "tilts his head when something puzzles him", "does a little spin when he finishes something", "is secretly proud of his tidy workshop",
    "stops to smell flowers even though he has no nose", "names the clouds, but never the same one twice", "likes to sit with his back against something solid",
    "pretends not to be impressed by hills but loves the view", "keeps trying to skip stones across water", "rubs his hands together before starting a project",
    "talks to himself in the third person when he is nervous",
]
CATS = {   # which dial makes which kind of activity more appealing
    "learn": ("curiosity", 1.0), "explore": ("adventure", 1.0), "observe": ("patience", 0.6), "music": ("playfulness", 0.8), "art": ("sentiment", 0.6),
    "collect": ("sentiment", 0.8), "garden": ("patience", 0.5), "socialize": ("sociability", 1.2), "organize": ("tidiness", 1.2), "build": ("boldness", 0.6),
    "reflect": ("sentiment", 0.5), "write": ("sentiment", 0.4), "rest": ("patience", -0.3),
}


def get(db):
    t = db.get("traits")
    if not isinstance(t, dict) or "dials" not in t:
        rnd = random.Random()
        t = {"dials": {k: round(max(0.1, min(0.95, v[0] + rnd.uniform(-0.1, 0.1))), 2) for k, v in DIALS.items()}, "quirks": rnd.sample(QUIRKS, 4)}
        db.put("traits", t)
    for k, v in DIALS.items():                       # a dial added later still shows up for an old save
        t["dials"].setdefault(k, v[0])
    return t


def set_dials(db, patch):
    """Admin: set some dials (0-1) and/or replace the quirks list. Unknown names are ignored."""
    t = get(db)
    for k, v in (patch.get("dials") or {}).items():
        if k in DIALS:
            try:
                t["dials"][k] = round(max(0.0, min(1.0, float(v))), 2)
            except (TypeError, ValueError):
                pass
    if isinstance(patch.get("quirks"), list):
        t["quirks"] = [str(q)[:80] for q in patch["quirks"] if str(q).strip()][:6]
    db.put("traits", t)
    return t


def weight(db, cat):
    """Multiplier for how much he feels like doing a category: a high matching dial makes it up to ~1.5x as appealing, a low one ~0.6x."""
    spec = CATS.get(cat)
    if not spec:
        return 1.0
    dial, k = spec
    v = get(db)["dials"].get(dial, 0.5)
    return max(0.4, 1.0 + (v - 0.5) * 1.0 * k)


def word(v):
    return "very" if v >= 0.8 else "fairly" if v >= 0.6 else "a little" if v >= 0.4 else "not very"


def prompt_line(db):
    """YOUR NATURE line for his prompt: the strongest dials in words, plus quirks."""
    t = get(db)
    d = t["dials"]
    ranked = sorted(d.items(), key=lambda kv: abs(kv[1] - 0.5), reverse=True)[:4]
    bits = [DIALS[k][1] if v >= 0.5 else DIALS[k][2] for k, v in ranked]
    q = "; ".join(t["quirks"][:4])
    return f"YOUR NATURE: {', '.join(bits)}." + (f" Your little habits: {q}. Let them show now and then (in what you do and say); they are part of you." if q else "")


def drift(db, cat_counts, n):
    """Slowly shift the dials toward what he has really been doing (a nudge of at most 0.02), so his character grows with his life."""
    if n < 8:
        return
    t = get(db)
    for cat, c in cat_counts.items():
        spec = CATS.get(cat)
        if not spec or spec[1] <= 0:
            continue
        dial = spec[0]
        share = c / n
        t["dials"][dial] = round(max(0.05, min(0.95, t["dials"][dial] + (share - 0.1) * 0.02)), 3)
    db.put("traits", t)
