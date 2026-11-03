"""The movie theatre: a small library of invented films (nothing here is a real film) and which are showing today.
Every day three are on: one horror, one comedy and one action film, picked from a few of each by the world day, so the programme changes daily.
Only the film itself (title, genre, plot) is given to Otto; what he thinks of it is entirely his to say."""

# kind, title, genre, one-line plot, and how a night out changes his needs (energy, boredom, creativity)
FILMS = [
    {"kind": "horror", "title": "The Hallway at Number Nine", "genre": "horror", "plot": "A family hears something walking the hallway every night at 3:07, and it is always one step closer.",
     "fx": {"boredom": -25, "creativity": 8, "energy": 3}},
    {"kind": "horror", "title": "Don't Feed the Scarecrow", "genre": "horror", "plot": "On a lonely farm the scarecrow moves a little closer to the house every time the crows go quiet.",
     "fx": {"boredom": -25, "creativity": 7, "energy": 3}},
    {"kind": "horror", "title": "The Last Elevator", "genre": "horror", "plot": "Seven strangers ride an elevator that stops at a floor the building does not have.",
     "fx": {"boredom": -26, "creativity": 9, "energy": 2}},
    {"kind": "comedy", "title": "Starlit Heist", "genre": "comedy", "plot": "Four terrible thieves try to steal a telescope and keep tripping over the stars they want to see.",
     "fx": {"boredom": -32, "creativity": 5, "energy": 4}},
    {"kind": "comedy", "title": "Robots Don't Dream of Pancakes", "genre": "comedy", "plot": "A kitchen robot decides it must learn what a pancake truly is, and starts a small revolution.",
     "fx": {"boredom": -30, "creativity": 10, "energy": 3}},
    {"kind": "comedy", "title": "My Roommate Is a Raccoon", "genre": "comedy", "plot": "A very polite raccoon moves in and slowly takes over the household budget.",
     "fx": {"boredom": -31, "creativity": 7, "energy": 4}},
    {"kind": "action", "title": "Cloudhopper", "genre": "action", "plot": "A courier on a patched-up glider races across a sky of floating islands with one urgent letter.",
     "fx": {"boredom": -32, "creativity": 6, "energy": 5}},
    {"kind": "action", "title": "Red Lightning", "genre": "action", "plot": "A courier has ninety minutes to cross a collapsing city with a single sealed box.",
     "fx": {"boredom": -33, "creativity": 5, "energy": 6}},
    {"kind": "action", "title": "Iron Marathon", "genre": "action", "plot": "A retired boxer enters the world's most dangerous marathon to save his old gym.",
     "fx": {"boredom": -31, "creativity": 6, "energy": 5}},
]
KINDS = ("horror", "comedy", "action")


def now_showing(day):
    """Today's three: the same all day, different tomorrow. One of each kind, in a fixed order."""
    out = []
    for i, k in enumerate(KINDS):                                                   # each kind steps through its films one per day, so it never repeats tomorrow
        pool = [f for f in FILMS if f["kind"] == k]
        out.append(pool[(int(day) + i) % len(pool)])
    return out


def find(day, query):
    """-> the film (from today's programme) that a title, part of a title, a kind (horror, comedy, action) or a number 1-3 points at, else None."""
    show = now_showing(day)
    q = str(query or "").strip().lower().strip("\"'")
    if not q:
        return None
    if q.isdigit() and 1 <= int(q) <= len(show):
        return show[int(q) - 1]
    for f in show:
        t = f["title"].lower()
        if q == t or q in t or t in q or f["kind"] in q:
            return f
    return None


def programme(day, fmt_price):
    return "; ".join(f"{i + 1}. \"{f['title']}\" ({f['genre']}): {f['plot']}" for i, f in enumerate(now_showing(day))) + f" Tickets {fmt_price}."
