"""Placement is the ENGINE's job. The model may suggest an area ("near the workshop", "garden", "next to Old Oak", "x,z")
but never a coordinate that matters: the engine resolves it, avoids every footprint, and grows the world when crowded."""
import math
import random
import re

from . import config, world
from .world import dist

# ---- zones: where things naturally go --------------------------------------------------------------
ZONES = {
    "workshop_yard": {"label": "workshop yard", "c": (-5.0, 4.0), "r": 10.0, "aliases": ["workshop", "yard", "workbench", "build area"]},
    "garden":        {"label": "garden", "c": (-18.0, -3.0), "r": 8.0, "aliases": ["garden", "park", "plants", "nature", "flower bed"]},
    "gallery_front": {"label": "gallery front", "c": (0.0, -10.5), "r": 6.5, "aliases": ["gallery", "art area", "sculpture garden", "exhibit"]},
    "open_field":    {"label": "open field", "c": (5.0, 4.0), "r": 10.0, "aliases": ["field", "meadow", "open", "middle", "center", "centre", "plaza"]},
    "meadow":        {"label": "east meadow", "c": (17.0, -3.0), "r": 7.0, "aliases": ["east", "east meadow", "grassland"]},
    "lakeside":      {"label": "lakeside", "c": (-4.0, 16.0), "r": 7.0, "aliases": ["lake", "lakeside", "pond area", "waterside"]},
    "village":       {"label": "village", "c": (10.0, 16.0), "r": 7.5, "aliases": ["village", "town", "street", "neighbourhood", "neighborhood"]},
    "orchard":       {"label": "orchard", "c": (-18.0, -15.0), "r": 6.0, "aliases": ["orchard", "grove", "woods", "forest"]},
}
# "near <place>" -> where that means
NEAR_PLACE = {"home": (-5.5, -6.0), "fuel_station": (6.0, -7.5), "clothing_store": (9.0, 12.5), "workshop": None, "gallery": None}
PLACE_ZONE = {"workshop": "workshop_yard", "gallery": "gallery_front"}

# ---- footprints --------------------------------------------------------------------------------------
KIND_RADIUS = {"landscape": 1.2, "ground": 0.05, "tree": 1.5, "rock": 1.1, "flower": 0.6, "ball": 0.7, "box": 1.0, "lamp": 0.6, "house": 2.6, "fountain": 2.3,
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


def is_free(objects, x, z, r, margin=config.SPACING_MARGIN, skip_id=None, half=None, skip_ids=None):
    half = half or world.half()
    if abs(x) > half - r - 0.8 or abs(z) > half - r - 0.8:
        return False
    if _hit_obstacle(x, z, r, margin):
        return False
    return all(dist(x, z, o["x"], o["z"]) >= radius_of(o) + r + margin for o in objects
               if o["id"] != skip_id and o.get("kind") != "ground" and not (skip_ids and o["id"] in skip_ids))


def find_spot(objects, cx, cz, r, rng=None, skip_id=None, max_tries=900, max_radius=None):
    """Spiral outward (golden angle + random jitter) from (cx,cz) until a free spot is found. None if the world is full."""
    rng = rng or random
    step = 0.9 + r * 0.7
    for i in range(max_tries):
        rad = 0.0 if i == 0 else step * math.sqrt(i) * rng.uniform(0.85, 1.15)
        ang = i * 2.399963 + rng.uniform(-0.45, 0.45)
        if max_radius and rad > max_radius:
            return None
        x, z = cx + rad * math.cos(ang) + (rng.uniform(-0.4, 0.4) if i == 0 else 0), cz + rad * math.sin(ang)
        if is_free(objects, x, z, r, skip_id=skip_id):
            return round(x, 2), round(z, 2)
    return None


def group_of(name):
    """Things of the same kind belong together: 'Pine Tree' and 'Blossom Tree' -> 'tree'."""
    w = [x for x in re.findall(r"[a-z]+", str(name).lower())]
    return (w[-1][:-1] if w and len(w[-1]) > 3 and w[-1].endswith("s") else (w[-1] if w else "thing"))


def lattice_spot(objects, ax, az, r, rng=None, skip_ids=None, max_radius=12.0):
    """A tidy position: the nearest free point of a grid (step = footprint + margin) around (ax, az), so like things line up."""
    step = round(2 * r + config.SPACING_MARGIN + 0.2, 1)
    step = max(1.5, step)
    pts = sorted(((i, j) for i in range(-7, 8) for j in range(-7, 8)), key=lambda p: (p[0] ** 2 + p[1] ** 2, abs(p[1])))
    for i, j in pts:
        x, z = round(ax + i * step, 2), round(az + j * step, 2)
        if dist(x, z, ax, az) > max_radius:
            break
        if is_free(objects, x, z, r, skip_ids=skip_ids):
            return x, z
    return None


def crowding(objects):
    area = (2 * world.half()) ** 2
    return sum(math.pi * radius_of(o) ** 2 for o in objects if o.get("kind") != "ground") / area


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


def place(state, objects, cx, cz, r, rng=None, log=None, skip_id=None, group=None):
    """Find a spot near (cx,cz). Order: inside its own zone -> the closest other zones that still have room -> anywhere (growing the world if needed)."""
    maybe_grow(state, objects, log)
    if group:                                                                 # neat: next to the same kind of thing, on a grid
        like = [o for o in objects if group_of(o.get("name", "")) == group and o["id"] != skip_id and dist(o["x"], o["z"], cx, cz) <= 14]
        ax, az = (sum(o["x"] for o in like) / len(like), sum(o["z"] for o in like) / len(like)) if like else (cx, cz)
        spot = lattice_spot(objects, ax, az, r, skip_ids={skip_id} if skip_id else None, max_radius=9.0 if like else 6.0)
        if spot:
            return spot, False
    home = zone_at(cx, cz)
    order = ([home] if home else []) + sorted((k for k in ZONES if k != home), key=lambda k: dist(cx, cz, *ZONES[k]["c"]))
    for k in order:
        zn = ZONES[k]
        if k != home and zone_used(objects, k) > 0.55:
            continue
        centre = (cx, cz) if k == home else zn["c"]
        spot = find_spot(objects, centre[0], centre[1], r, rng, skip_id=skip_id, max_radius=zn["r"] * 1.25)
        if spot:
            return spot, False
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


GEN_ZONE = {"house": "village", "cottage": "village", "tower": "village", "shop": "village", "sign": "village", "car": "village", "workshop_building": "workshop_yard",
            "tree": "garden", "bush": "garden", "flower_bed": "garden", "rock": "garden", "pond": "lakeside", "path": "village", "fence": "garden", "lamp": "village"}


def default_zone_for(tags=(), kind=None):
    t = set(tags or ())
    for g, z in GEN_ZONE.items():
        if g in t:
            return z
    if t & {"plant", "tree", "nature", "flower", "cactus", "camp", "fire", "garden", "stone"} or kind in ("tree", "flower", "rock", "fountain", "bench"):
        return "garden"
    if t & {"animal", "creature", "space", "celestial", "vehicle"} or kind in ("creature", "ball"):
        return "open_field"
    if t & {"wall", "door", "roof", "building", "structure", "stairs"}:
        return "village"
    if kind == "sculpture":
        return "gallery_front"
    return "workshop_yard"


def zone_at(x, z):
    """The zone a point belongs to (or None)."""
    best = None
    for k, zn in ZONES.items():
        d = dist(x, z, *zn["c"])
        if d <= zn["r"] * 1.15 and (best is None or d < best[0]):
            best = (d, k)
    return best[1] if best else None


def zone_used(objects, key):
    zn = ZONES[key]
    inside = [o for o in objects if dist(o["x"], o["z"], *zn["c"]) <= zn["r"] and o.get("kind") != "ground"]
    return sum(math.pi * radius_of(o) ** 2 for o in inside) / (math.pi * zn["r"] ** 2)


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
    for k, z in ZONES.items():
        n = len([o for o in objects if dist(o["x"], o["z"], *z["c"]) <= z["r"] and o.get("kind") != "ground"])
        used = zone_used(objects, k)
        out.append(f"{z['label']} ({n}, {'roomy' if used < 0.2 else 'filling up' if used < 0.45 else 'crowded'})")
    return "; ".join(out)


# ---- arranging existing objects ----------------------------------------------------------------------
def _fits(others, x, z, r, taken):
    return is_free(others, x, z, r) and all(dist(x, z, tx, tz) >= tr + r + config.SPACING_MARGIN for tx, tz, tr in taken)


def arrange_positions(objects, sel, pattern, cx, cz):
    """New positions for the selected objects (list of dicts) in a pattern, avoiding everything else. -> {id: (x, z)} or None if it cannot fit."""
    ids = {o["id"] for o in sel}
    others = [o for o in objects if o["id"] not in ids]
    sel = sorted(sel, key=lambda o: (group_of(o["name"]), o["name"]))
    n = len(sel)
    rs = [radius_of(o) for o in sel]
    gap = config.SPACING_MARGIN + 0.3

    def try_layout(offsets_fn):
        # slide the whole arrangement around the anchor until every member fits
        for k in range(0, 40):
            ang = k * 2.399963
            rad = 0 if k == 0 else 1.6 * (k ** 0.5)
            ox, oz = cx + rad * math.cos(ang), cz + rad * math.sin(ang)
            pos, taken = {}, []
            for o, r, (dx, dz) in zip(sel, rs, offsets_fn()):
                x, z = round(ox + dx, 2), round(oz + dz, 2)
                if not _fits(others, x, z, r, taken):
                    break
                pos[o["id"]] = (x, z); taken.append((x, z, r))
            else:
                return pos
        return None
    if pattern in ("row", "line"):
        total = sum(2 * r + gap for r in rs) - gap
        def off():
            x, out = -total / 2, []
            for r in rs:
                out.append((x + r, 0)); x += 2 * r + gap
            return out
        return try_layout(off)
    if pattern == "column":
        total = sum(2 * r + gap for r in rs) - gap
        def off():
            z, out = -total / 2, []
            for r in rs:
                out.append((0, z + r)); z += 2 * r + gap
            return out
        return try_layout(off)
    if pattern == "circle":
        R = max(2.0, sum(2 * r + gap for r in rs) / (2 * math.pi))
        return try_layout(lambda: [(R * math.cos(2 * math.pi * i / n), R * math.sin(2 * math.pi * i / n)) for i in range(n)])
    if pattern == "grid":
        cols = math.ceil(math.sqrt(n)); cell = 2 * max(rs) + gap
        rows = math.ceil(n / cols)
        return try_layout(lambda: [((i % cols - (cols - 1) / 2) * cell, (i // cols - (rows - 1) / 2) * cell) for i in range(n)])
    # cluster / move: pack tightly around the anchor, largest first
    order = sorted(range(n), key=lambda i: -rs[i])
    pos, taken = {}, []
    for i in order:
        spot = None
        for k in range(0, 300):
            rad = 0 if k == 0 else 0.9 + 0.5 * math.sqrt(k) * (1 + rs[i] * 0.3)
            ang = k * 2.399963
            x, z = round(cx + rad * math.cos(ang), 2), round(cz + rad * math.sin(ang), 2)
            if _fits(others, x, z, rs[i], taken):
                spot = (x, z); break
        if not spot:
            return None
        pos[sel[i]["id"]] = spot; taken.append((spot[0], spot[1], rs[i]))
    return pos
