"""Placement is the ENGINE's job. The model may suggest an area ("near the workshop", "garden", "next to Old Oak", "x,z")
but never a coordinate that matters: the engine resolves it, avoids every footprint, and grows the world when crowded."""
import math
import random
import re

from . import config, world
from .world import dist

# ---- zones: where things naturally go --------------------------------------------------------------
ZONES = {
    "workshop_yard": {"label": "workshop yard", "c": (-5.0, 4.0), "r": 9.0, "aliases": ["workshop", "yard", "workbench", "build area"]},
    "garden":        {"label": "garden", "c": (-18.0, -2.0), "r": 6.5, "aliases": ["garden", "park", "plants", "nature", "flower bed"]},
    "gallery_front": {"label": "gallery front", "c": (0.0, -10.5), "r": 6.5, "aliases": ["gallery", "art area", "sculpture garden", "exhibit"]},
    "open_field":    {"label": "open field", "c": (5.0, 4.0), "r": 10.0, "aliases": ["field", "meadow", "open", "middle", "center", "centre", "plaza"]},
}
# "near <place>" -> where that means
NEAR_PLACE = {"home": (-5.5, -6.0), "fuel_station": (6.0, -7.5), "clothing_store": (9.0, 12.5), "workshop": None, "gallery": None}
PLACE_ZONE = {"workshop": "workshop_yard", "gallery": "gallery_front"}

# ---- footprints --------------------------------------------------------------------------------------
KIND_RADIUS = {"tree": 1.5, "rock": 1.1, "flower": 0.6, "ball": 0.7, "box": 1.0, "lamp": 0.6, "house": 2.6, "fountain": 2.3,
               "statue": 1.2, "bench": 1.5, "creature": 1.0, "other": 1.0, "creation": 1.6, "project": 2.3, "sculpture": 1.7}


def radius_of(o):
    r = o.get("radius")
    return float(r) if r else KIND_RADIUS.get(o.get("kind"), 1.2)


# Buildings are obstacles too. ("c", x, z, r) circle or ("r", cx, cz, half_w, half_d) rectangle
OBSTACLES = [("c", -10.0, -10.0, 4.4), ("c", 10.0, -12.0, 3.6), ("r", 14.0, 6.4, 3.1, 3.3), ("r", -14.0, 10.5, 3.3, 2.6),
             ("r", 0.0, -17.7, 8.6, 4.4)]


def _hit_obstacle(x, z, r, margin):
    for ob in OBSTACLES:
        if ob[0] == "c":
            if dist(x, z, ob[1], ob[2]) < ob[3] + r + margin:
                return True
        else:
            dx, dz = max(abs(x - ob[1]) - ob[3], 0), max(abs(z - ob[2]) - ob[4], 0)
            if math.hypot(dx, dz) < r + margin:
                return True
    return False


def is_free(objects, x, z, r, margin=config.SPACING_MARGIN, skip_id=None, half=None):
    half = half or world.half()
    if abs(x) > half - r - 0.8 or abs(z) > half - r - 0.8:
        return False
    if _hit_obstacle(x, z, r, margin):
        return False
    return all(dist(x, z, o["x"], o["z"]) >= radius_of(o) + r + margin for o in objects if o["id"] != skip_id)


def find_spot(objects, cx, cz, r, rng=None, skip_id=None, max_tries=900):
    """Spiral outward (golden angle + random jitter) from (cx,cz) until a free spot is found. None if the world is full."""
    rng = rng or random
    step = 0.9 + r * 0.7
    for i in range(max_tries):
        rad = 0.0 if i == 0 else step * math.sqrt(i) * rng.uniform(0.85, 1.15)
        ang = i * 2.399963 + rng.uniform(-0.45, 0.45)
        x, z = cx + rad * math.cos(ang) + (rng.uniform(-0.4, 0.4) if i == 0 else 0), cz + rad * math.sin(ang)
        if is_free(objects, x, z, r, skip_id=skip_id):
            return round(x, 2), round(z, 2)
    return None


def crowding(objects):
    area = (2 * world.half()) ** 2
    return sum(math.pi * radius_of(o) ** 2 for o in objects) / area


def maybe_grow(state, objects, log=None):
    """Expand the buildable area when it gets crowded. Returns True if it grew."""
    h = world.half()
    if crowding(objects) > config.CROWD_LIMIT and h < config.WORLD_HALF_MAX:
        return grow(state, log)
    return False


def grow(state, log=None):
    h = world.half()
    if h >= config.WORLD_HALF_MAX:
        return False
    nh = min(config.WORLD_HALF_MAX, h + config.WORLD_GROW_STEP)
    world.set_half(nh)
    state["world_half"] = nh
    if log:
        log(f"  the buildable area grew to {2 * nh:.0f} x {2 * nh:.0f}")
    return True


def place(state, objects, cx, cz, r, rng=None, log=None, skip_id=None):
    """Find a spot near (cx,cz); grow the world if needed. Always returns a position (last resort: far corner of a bigger world)."""
    maybe_grow(state, objects, log)
    for _ in range(4):
        spot = find_spot(objects, cx, cz, r, rng, skip_id=skip_id)
        if spot:
            return spot, False
        if not grow(state, log):
            break
    spot = find_spot(objects, 0, 0, r, rng, skip_id=skip_id)          # last resort: search from the middle
    return (spot or (round(world.clamp(cx, world.half() - r - 1), 2), round(world.clamp(cz, world.half() - r - 1), 2))), True


# ---- suggested areas ---------------------------------------------------------------------------------
_FILLER = re.compile(r"\b(near|next to|beside|by|in|at|around|the|a|an|my|on|to|close to|front of|in front of)\b", re.I)
_COORD = re.compile(r"^\(?\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*\)?$")


def default_zone_for(tags=(), kind=None):
    t = set(tags or ())
    if t & {"plant", "tree", "nature", "flower", "cactus", "camp", "fire", "garden", "stone"} or kind in ("tree", "flower", "rock", "fountain", "bench"):
        return "garden"
    if t & {"animal", "creature", "space", "celestial", "vehicle"} or kind in ("creature", "ball"):
        return "open_field"
    if kind == "sculpture":
        return "gallery_front"
    return "workshop_yard"


def resolve_area(text, state, objects, default_zone="workshop_yard"):
    """-> (cx, cz, label). Understands zones, places, object names, 'here', and 'x,z'."""
    raw = str(text or "").strip()
    t = _FILLER.sub(" ", raw.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        z = ZONES[default_zone]
        return z["c"][0], z["c"][1], z["label"]
    m = _COORD.match(raw.strip().lower())
    if m:
        return world.clamp(float(m[1])), world.clamp(float(m[2])), "that spot"
    if t in ("here", "me", "myself", "current", "this spot", "where i am", "where i stand"):
        return state["x"], state["z"], "here"
    for key, z in ZONES.items():
        if t == key or t == z["label"] or any(a == t or (len(a) > 3 and a in t) for a in z["aliases"]):
            return z["c"][0], z["c"][1], z["label"]
    for key, p in world.PLACES.items():
        if t == key or t == p["label"] or any(a == t for a in p["aliases"]):
            if key in PLACE_ZONE:
                z = ZONES[PLACE_ZONE[key]]
                return z["c"][0], z["c"][1], z["label"]
            c = NEAR_PLACE.get(key)
            if c:
                return c[0], c[1], f"near the {p['label']}"
    cands = [o for o in objects if o["name"].lower() == t] or [o for o in objects if t in o["name"].lower() or o["kind"] == t]
    if cands:
        o = min(cands, key=lambda o: dist(state["x"], state["z"], o["x"], o["z"]))
        return o["x"], o["z"], f"near {o['name']}"
    z = ZONES[default_zone]
    return z["c"][0], z["c"][1], z["label"]


def zone_report(objects):
    """Compact list of zones and how filled they are, for his prompt."""
    out = []
    for z in ZONES.values():
        inside = [o for o in objects if dist(o["x"], o["z"], *z["c"]) <= z["r"]]
        used = sum(math.pi * radius_of(o) ** 2 for o in inside) / (math.pi * z["r"] ** 2)
        out.append(f"{z['label']} ({len(inside)} things, {'roomy' if used < 0.2 else 'filling up' if used < 0.45 else 'crowded'})")
    return "; ".join(out)
