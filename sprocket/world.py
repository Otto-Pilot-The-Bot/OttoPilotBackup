"""Geometry, places, targets and 'hidden tastes'. Pure logic, no I/O."""
import hashlib
import math
import re
from . import config

PLACES = {
    "home":           {"label": "home pad",       "x": -10.0, "z": -10.0, "aliases": ["home", "pad", "bed", "charging", "cabin"],
                      "enter": True, "inside": [-10.0, -10.4]},
    "fuel_station":   {"label": "fuel station",   "x": 10.0,  "z": -12.0, "aliases": ["fuel", "food", "station", "battery"]},
    "clothing_store": {"label": "clothing store", "x": 14.0,  "z": 8.0,   "aliases": ["clothing", "store", "clothes", "boutique"],
                      "enter": True, "inside": [14.0, 6.2]},
    "gallery":        {"label": "gallery",        "x": 0.0,   "z": -18.0,  "aliases": ["gallery", "art", "museum", "wall"],
                      "enter": True, "inside": [0.0, -16.6]},
    "workshop":       {"label": "workshop",       "x": -14.0, "z": 9.0,   "aliases": ["workshop", "print", "printer", "build"],
                      "enter": True, "inside": [-14.4, 10.6]},
}

KINDS = ["tree", "rock", "flower", "ball", "box", "lamp", "house", "fountain", "statue", "bench", "creature", "other"]
KIND_VERB = {"tree": "touched the bark of", "rock": "knocked on", "flower": "sniffed", "ball": "kicked", "box": "peeked inside",
             "lamp": "studied the glow of", "house": "knocked on the door of", "fountain": "dipped a hand into",
             "statue": "inspected", "bench": "sat on", "creature": "said hello to", "other": "poked", "creation": "admired"}

COLORS = {"red": "#e53935", "orange": "#fb8c00", "yellow": "#fdd835", "green": "#43a047", "teal": "#00897b",
          "blue": "#1e88e5", "navy": "#1a237e", "purple": "#8e24aa", "pink": "#ec407a", "white": "#f5f5f5",
          "black": "#212121", "grey": "#9e9e9e", "brown": "#6d4c41", "gold": "#ffc107", "silver": "#b0bec5",
          # the soft palette of the city kit
          "cream": "#f4e8cc", "tan": "#e8caa4", "sage": "#dbe5d1", "ivory": "#f1eee2", "terracotta": "#c4604b", "brick": "#b5694f",
          "slate": "#6e8da3", "plum": "#7d6c92", "forest": "#5f8159", "olive": "#8a9a4a", "sky": "#8fb9cd", "rose": "#eaa0b4",
          "charcoal": "#3b3a3f", "stone": "#c9c2b2", "sand": "#e6d3a0", "wood": "#8a6240"}

FEELINGS = {"happy": 1.0, "excited": 1.0, "proud": 0.9, "content": 0.5, "curious": 0.4, "surprised": 0.1,
            "tired": -0.3, "bored": -0.4, "scared": -0.7, "sad": -0.8, "angry": -0.8}


_half = float(config.WORLD_HALF)      # the buildable area can grow (see layout.py); this is the current half-size


def half():
    return _half


def set_half(v):
    global _half
    _half = float(v)


def clamp(v, lim=None):
    lim = _half if lim is None else lim
    return max(-lim, min(lim, v))


def dist(ax, az, bx, bz):
    return math.hypot(ax - bx, az - bz)


def step_toward(x, z, tx, tz, step=config.MAX_STEP, stop=config.REACH * 0.6):
    """Walk toward a target but stop `stop` short of it. Returns (nx, nz, arrived)."""
    d = dist(x, z, tx, tz)
    if d <= config.REACH:
        return x, z, True
    goal = max(d - stop, 0)
    move = min(step, goal)
    nx, nz = x + (tx - x) * move / d, z + (tz - z) * move / d
    return round(nx, 2), round(nz, 2), dist(nx, nz, tx, tz) <= config.REACH


_COORD = re.compile(r"^\(?\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*\)?$")


def resolve_target(text, x, z, objects):
    """Return dict(label, kind, x, z, key, id) or None. Accepts places, objects, ids, 'x,z'."""
    t = (text or "").strip().lower().lstrip("#")
    if not t:
        return None
    m = _COORD.match(t)
    if m:
        return {"label": f"({clamp(float(m[1])):.0f},{clamp(float(m[2])):.0f})", "kind": "point",
                "x": clamp(float(m[1])), "z": clamp(float(m[2])), "key": None, "id": None}
    for key, p in PLACES.items():
        if t == key or t.replace(" ", "_") == key or t == p["label"] or t in p["aliases"]:
            return {"label": p["label"], "kind": "place", "x": p["x"], "z": p["z"], "key": key, "id": None}
    if t.isdigit():
        for o in objects:
            if o["id"] == int(t):
                return _obj(o)
    cands = [o for o in objects if t == o["name"].lower()] or \
            [o for o in objects if t in o["name"].lower() or o["name"].lower() in t or t == o["kind"]]
    if cands:
        return _obj(min(cands, key=lambda o: dist(x, z, o["x"], o["z"])))
    for key, p in PLACES.items():
        if t in p["label"] or any(a in t for a in p["aliases"]):
            return {"label": p["label"], "kind": "place", "x": p["x"], "z": p["z"], "key": key, "id": None}
    return None


def _obj(o):
    return {"label": o["name"], "kind": o["kind"], "x": o["x"], "z": o["z"], "key": None, "id": o["id"], "color": o.get("color")}


def affinity(seed, key):
    """Deterministic hidden taste in [-1, 1] — differs per robot instance, so personality diverges."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return (int.from_bytes(h[:4], "big") / 0xFFFFFFFF) * 2 - 1


# Words that mean "making things". Negative feelings about these are never allowed to turn into avoidance.
MAKER_RE = re.compile(r"\b(build\w*|assembl\w*|calibrat\w*|creat\w*|making|maker|workshop|print\w*|arts?|sculpt\w*|draw\w*|paint\w*|"
                      r"construct\w*|project\w*|blueprint\w*|craft\w*|gallery|pixel|sketch\w*)\b", re.I)


def color_name(hexv):
    """Nearest named colour for a #rrggbb value."""
    try:
        h = hexv.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return "grey"

    def d(c):
        c = c.lstrip("#")
        return (int(c[0:2], 16) - r) ** 2 + (int(c[2:4], 16) - g) ** 2 + (int(c[4:6], 16) - b) ** 2
    return min(COLORS, key=lambda k: d(COLORS[k]))


def to_hex(c):
    """Colour name or #rrggbb -> '#rrggbb' (or None)."""
    c = str(c or "").strip().lower()
    if c in COLORS:
        return COLORS[c]
    if re.fullmatch(r"#?[0-9a-f]{6}", c):
        return "#" + c.lstrip("#")
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        return "#" + "".join(ch * 2 for ch in c[1:])
    return None


def world_time(tick, frac=0.0):
    """World clock: starts 08:00, each tick is 10 world minutes (a day is 144 ticks)."""
    mins = 8 * 60 + (tick + max(0.0, min(1.0, frac))) * 10
    day, hour = int(mins // 1440) + 1, (mins % 1440) / 60
    phase = "dawn" if 5 <= hour < 7.5 else "day" if 7.5 <= hour < 18 else "dusk" if 18 <= hour < 20 else "night"
    return {"day": day, "hour": round(hour, 3), "label": f"{int(hour):02d}:{int((hour % 1) * 60):02d}", "phase": phase}


def free_spot(objects, cx, cz, gap=3.6, place_gap=5.5, skip_id=None):
    """First free position on a spiral around (cx, cz): not near any object or place, inside the world."""
    taken = [(o["x"], o["z"]) for o in objects if o["id"] != skip_id]
    centers = [(p["x"], p["z"]) for p in PLACES.values()]
    best = None
    for i in range(0, 400):
        r = 0 if i == 0 else 2.2 + 0.55 * (i ** 0.5) * 2.2
        a = i * 2.399963                                   # golden angle: even spread
        x, z = clamp(cx + r * math.cos(a), config.WORLD_HALF - 2), clamp(cz + r * math.sin(a), config.WORLD_HALF - 2)
        if any(dist(x, z, tx, tz) < gap for tx, tz in taken) or any(dist(x, z, px, pz) < place_gap for px, pz in centers):
            continue
        return round(x, 2), round(z, 2)
    return round(cx, 2), round(cz, 2)


def build_yard():
    """Open ground east of the workshop where projects and creations are set down."""
    ws = PLACES["workshop"]
    return ws["x"] + 9.0, ws["z"] - 4.0
