"""Data-driven maps: ground tiles, roads and objects as JSON (data/maps/<name>.json), plus the walkable grid Otto paths over.

Only the human edits maps (the Plan editor in the page sends map_* messages; no model tool can reach this module's writers).
Everything that comes from the page is validated and clamped here before it is saved.
"""
import heapq
import json
import math
import re
import time
from pathlib import Path

from . import config

MAPS_DIR = config.ROOT / "data" / "maps"
NAV = 1.0                                   # walkable-grid resolution in meters
TILES = {"g": "grass", "p": "plaza", "r": "road", "t": "path", "w": "water", "s": "sand", "d": "dirt"}
TILE_COST = {"grass": 3.0, "plaza": 1.0, "road": 1.0, "path": 1.0, "sand": 2.0, "dirt": 2.0, "water": None}   # None = cannot walk
MAX_OBJECTS, MAX_CELLS = 900, 40
NAME_RX = re.compile(r"^[A-Za-z0-9 _-]{1,40}$")
TAG_RX = re.compile(r"^[a-z0-9_-]{1,24}$")
ACTIVE = {"doc": None, "blocked": None, "cost": None, "n": 0, "half": 0.0, "colliders": []}


# ---------------------------------------------------------------- documents
def blank(name="new map", n=20, cell=None):
    cell = cell or config.WORLD_CELL
    return {"version": 1, "name": name, "cell": cell, "n": n, "ground": ["g" * n for _ in range(n)], "objects": [], "places": {}}


def _num(v, lo, hi, d=0.0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return d
    return d if math.isnan(v) else max(lo, min(hi, v))


def asset_defaults(row):
    """Starting values for an object made from an asset row: footprint, door guess, tags, walkable flag. All editable afterwards."""
    tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else list(row["tags"])
    cat = row["cat"] or "prop"
    fw, fd = float(row["fw"] or 1), float(row["fd"] or 1)
    if cat == "tree" or "plant" in tags and "building" not in tags:
        fw, fd = max(0.5, fw * 0.3), max(0.5, fd * 0.3)               # you can walk under the leaves; the trunk is what blocks
    walk = cat in ("road",) or fw * fd < 0.04 or (row["sy"] * row["fit"] < 0.25 and cat not in ("building", "shop"))
    door = None
    if row["door_x"] is not None and row["door_z"] is not None and cat in ("building", "shop"):
        door = [float(row["door_x"]), float(row["door_z"])]
    out = {"fw": round(fw, 2), "fd": round(fd, 2), "tags": [t for t in tags if TAG_RX.match(t)][:10], "door": door, "walkable": bool(walk)}
    sol = tunnel_solids(row["name"], fw, fd)
    if sol:
        out["solids"] = sol
    return out


def tunnel_solids(name, fw, fd):
    """Space Kit / Modular Space corridors are tunnels you walk THROUGH: only their two side walls (and the back of an 'end' piece) are solid."""
    n = name.lower()
    if not re.match(r"^(corridor|gate)[ -]?(detailed|window|windowclosed|open|end|split|)$", n.strip()):
        return None
    t = 0.8
    sol = [{"x": round(-fw / 2 + t / 2, 2), "z": 0, "w": t, "d": round(fd, 2)}, {"x": round(fw / 2 - t / 2, 2), "z": 0, "w": t, "d": round(fd, 2)}]
    if n.strip().endswith("end"):
        sol.append({"x": 0, "z": round(-fd / 2 + t / 2, 2), "w": round(fw, 2), "d": t})
    return sol


def clean(doc, db):
    """Validate a map document from the page. Raises ValueError with a plain message."""
    if not isinstance(doc, dict):
        raise ValueError("not a map")
    name = str(doc.get("name", "")).strip()
    if not NAME_RX.match(name):
        raise ValueError("Map names are 1-40 letters, numbers, spaces, - or _.")
    n = int(_num(doc.get("n"), 4, MAX_CELLS, 20)); cell = _num(doc.get("cell"), 1, 8, config.WORLD_CELL)
    if n * cell / 2 > config.WORLD_HALF_MAX:
        raise ValueError(f"That map is too big (limit {config.WORLD_HALF_MAX * 2:.0f} m across).")
    rows = doc.get("ground") or []
    ground = []
    for z in range(n):
        r = str(rows[z]) if z < len(rows) else ""
        ground.append("".join(c if c in TILES else "g" for c in (r + "g" * n)[:n]))
    objs, seen = [], set()
    for o in (doc.get("objects") or [])[:MAX_OBJECTS]:
        if not isinstance(o, dict):
            continue
        asset = o.get("asset")
        row = None
        if asset:
            row = db.one("SELECT * FROM assets WHERE file=? AND usable=1", str(asset))
            if not row:
                continue                                              # unknown model: drop it, never trust a path from the page
        elif not isinstance(o.get("panel"), dict):
            continue
        oid = int(_num(o.get("id"), 1, 10**9, len(objs) + 1))
        while oid in seen:
            oid += 1
        seen.add(oid)
        half = n * cell / 2
        d = asset_defaults(row) if row else {"fw": 2.0, "fd": 0.2, "tags": ["art"], "door": None, "walkable": True}
        out = {"id": oid, "asset": str(asset) if row else None, "kit": row["pack"] if row else "flat", "name": str(o.get("name") or (row["name"] if row else "Art panel"))[:60],
               "x": round(_num(o.get("x"), -half, half), 2), "z": round(_num(o.get("z"), -half, half), 2), "rot": round(_num(o.get("rot"), -360, 360) % 360, 1),
               "scale": round(_num(o.get("scale"), 0.2, 6, 1.0), 3),
               "fw": round(_num(o.get("fw"), 0.1, 60, d["fw"]), 2), "fd": round(_num(o.get("fd"), 0.1, 60, d["fd"]), 2),
               "tags": [t for t in (o.get("tags") if isinstance(o.get("tags"), list) else d["tags"]) if isinstance(t, str) and TAG_RX.match(t)][:12],
               "walkable": bool(o.get("walkable", d["walkable"]))}
        about = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", str(o.get("about") or ""))).strip()[:160]
        if about:
            out["about"] = about
        dr = o.get("door")
        out["door"] = [round(_num(dr[0], -30, 30), 2), round(_num(dr[1], -30, 30), 2)] if isinstance(dr, list) and len(dr) == 2 else None
        if o.get("y") is not None:
            out["y"] = round(_num(o.get("y"), -5, 30), 2)
        if isinstance(o.get("solids"), list):                          # optional: only these parts of the footprint are solid (walls of a room you can walk into)
            sol = []
            for r in o["solids"][:8]:
                if isinstance(r, dict):
                    sol.append({"x": round(_num(r.get("x"), -40, 40), 2), "z": round(_num(r.get("z"), -40, 40), 2),
                                "w": round(_num(r.get("w"), 0.1, 60, 1), 2), "d": round(_num(r.get("d"), 0.1, 60, 1), 2)})
            if sol:
                out["solids"] = sol
        elif row and "solids" not in o:
            ts = tunnel_solids(row["name"], out["fw"], out["fd"])        # walk-through corridor pieces keep a way through by default
            if ts:
                out["solids"] = ts
        if not row:
            p = o["panel"]
            out["panel"] = {"w": round(_num(p.get("w"), 0.3, 6, 1.4), 2), "h": round(_num(p.get("h"), 0.3, 6, 1.0), 2), "art_id": int(_num(p.get("art_id"), 0, 10**9, 0)) or None, "gift_id": int(_num(p.get("gift_id"), 0, 10**9, 0)) or None,
                            "caption": str(p.get("caption", ""))[:80]}
            out["y"] = round(_num(o.get("y"), 0, 6, 1.2), 2)
        objs.append(out)
    places = {}
    for k, p in (doc.get("places") or {}).items():
        if isinstance(p, dict) and re.match(r"^[a-z_]{2,20}$", str(k)):
            at = p.get("at")
            places[k] = {"label": str(p.get("label", k))[:30], "object": int(_num(p.get("object"), 0, 10**9, 0)) or None,
                         "aliases": [str(a)[:20] for a in (p.get("aliases") or [])][:8], "enter": bool(p.get("enter", False))}
            if isinstance(at, list) and len(at) == 2:
                places[k]["at"] = [round(_num(at[0], -config.WORLD_HALF_MAX, config.WORLD_HALF_MAX), 2), round(_num(at[1], -config.WORLD_HALF_MAX, config.WORLD_HALF_MAX), 2)]
    return {"version": 1, "name": name, "cell": cell, "n": n, "ground": ground, "objects": objs, "places": places}


def path_for(name):
    return MAPS_DIR / (re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()) + ".json")


def list_maps():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem.replace("_", " ") if False else json.loads(p.read_text())["name"] for p in MAPS_DIR.glob("*.json") if p.is_file())


def save(doc, db):
    d = clean(doc, db)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    p = path_for(d["name"])
    tmp = p.with_suffix(".part"); tmp.write_text(json.dumps(d, indent=1)); tmp.replace(p)
    return d


def load(name):
    p = path_for(name)
    if not p.is_file():
        raise ValueError("No map with that name.")
    return json.loads(p.read_text())


# ---------------------------------------------------------------- derived data: places, colliders, walkable grid
def tile_at(doc, x, z):
    n, c = doc["n"], doc["cell"]
    i, j = int((x + n * c / 2) // c), int((z + n * c / 2) // c)
    if 0 <= i < n and 0 <= j < n:
        return TILES.get(doc["ground"][j][i], "grass")
    return None


def obj_corners(o, pad=0.0):
    c, s = math.cos(math.radians(o["rot"])), math.sin(math.radians(o["rot"]))
    hw, hd = o["fw"] * o["scale"] / 2 + pad, o["fd"] * o["scale"] / 2 + pad
    return [(o["x"] + lx * c + lz * s, o["z"] - lx * s + lz * c) for lx, lz in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]


def rects_of(o):
    """Solid rectangles of an object as (cx, cz, half_w, half_d) in the object's own axes, relative to its centre, plus the object's turn."""
    sc = o["scale"]
    if o.get("solids"):
        return [(r["x"] * sc, r["z"] * sc, r["w"] * sc / 2, r["d"] * sc / 2) for r in o["solids"]]
    return [(0.0, 0.0, o["fw"] * sc / 2, o["fd"] * sc / 2)]


def world_rects(o):
    c, s = math.cos(math.radians(o["rot"])), math.sin(math.radians(o["rot"]))
    return [{"x": o["x"] + lx * c + lz * s, "z": o["z"] - lx * s + lz * c, "hw": hw, "hd": hd, "rot": math.radians(o["rot"]), "id": o["id"]} for lx, lz, hw, hd in rects_of(o)]


def door_world(o, out=1.8):
    """The spot just OUTSIDE an object's door (where a visitor stands to knock)."""
    if not o.get("door"):
        return None
    dx, dz = o["door"]; c, s = math.cos(math.radians(o["rot"])), math.sin(math.radians(o["rot"]))
    L = math.hypot(dx, dz) or 1
    ox, oz = dx + dx / L * out, dz + dz / L * out
    return o["x"] + ox * c + oz * s, o["z"] - ox * s + oz * c


def activate(doc, db=None):
    """Make `doc` the live map: builds the walkable grid and the place table the agent uses."""
    from . import world
    n, cell = doc["n"], doc["cell"]
    half = n * cell / 2
    W = int(round(2 * half / NAV))
    blocked = [[False] * W for _ in range(W)]
    cost = [[1.0] * W for _ in range(W)]
    for j in range(W):
        for i in range(W):
            t = tile_at(doc, -half + (i + 0.5) * NAV, -half + (j + 0.5) * NAV)
            tc = TILE_COST.get(t, 3.0)
            if tc is None:
                blocked[j][i] = True
            else:
                cost[j][i] = tc
    colliders = []
    for o in doc["objects"]:
        if o.get("walkable") or o.get("panel") or (o.get("y") or 0) >= 1.8:      # a roof or anything raised overhead never blocks the ground below
            continue
        for r in world_rects(o):
            colliders.append(r)
            ca, sa = math.cos(r["rot"]), math.sin(r["rot"])
            hw, hd = r["hw"] + 0.3, r["hd"] + 0.3
            ext = math.hypot(hw, hd)
            for j in range(max(0, int((r["z"] - ext + half) // NAV)), min(W, int((r["z"] + ext + half) // NAV) + 1)):
                for i in range(max(0, int((r["x"] - ext + half) // NAV)), min(W, int((r["x"] + ext + half) // NAV) + 1)):
                    px, pz = -half + (i + 0.5) * NAV - r["x"], -half + (j + 0.5) * NAV - r["z"]
                    lx, lz = px * ca - pz * sa, px * sa + pz * ca
                    if abs(lx) <= hw and abs(lz) <= hd:
                        blocked[j][i] = True
    ACTIVE.update(doc=doc, blocked=blocked, cost=cost, n=W, half=half, colliders=colliders)
    world.set_half(half)
    # places the agent knows by name: derived from the map, never hand-coded
    world.PLACES.clear()
    by_id = {o["id"]: o for o in doc["objects"]}
    for key, p in doc.get("places", {}).items():
        o = by_id.get(p.get("object"))
        if not o and p.get("at"):
            spot = nearest_walkable(*p["at"]) or tuple(p["at"])
            world.PLACES[key] = {"label": p["label"], "x": round(spot[0], 2), "z": round(spot[1], 2), "aliases": p.get("aliases", [])}
            continue
        if not o:
            continue
        dw = door_world(o) or (o["x"], o["z"] + o["fd"] * o["scale"] / 2 + 1.8)
        spot = nearest_walkable(*dw) or dw
        pl = {"label": p["label"], "x": round(spot[0], 2), "z": round(spot[1], 2), "aliases": p.get("aliases", []), "object": o["id"]}
        if p.get("enter") and o.get("door"):
            ins = (o["x"], o["z"])
            pl.update(enter=True, inside=[round(ins[0], 2), round(ins[1], 2)])
        world.PLACES[key] = pl
    taken = {p.get("object") for p in world.PLACES.values() if p.get("object")}
    for o in doc["objects"]:                                          # any building with a door can be entered, even if you did not mark it as a place
        if o["id"] in taken or o.get("panel") or not o.get("door") or "building" not in (o.get("tags") or []):
            continue
        dw = door_world(o) or (o["x"], o["z"] + o["fd"] * o["scale"] / 2 + 1.8)
        spot = nearest_walkable(*dw) or dw
        nm = re.sub(r"[-_]", " ", o["name"]).strip()
        world.PLACES[f"b{o['id']}"] = {"label": nm, "x": round(spot[0], 2), "z": round(spot[1], 2), "aliases": [nm.lower()], "object": o["id"],
                                       "enter": True, "inside": [round(o["x"], 2), round(o["z"], 2)]}
    FALL = {"home": ("home spot", ["home", "pad", "bed"]), "fuel_station": ("charging spot", ["charging", "station", "fuel", "battery", "food"]),
            "clothing_store": ("shop spot", ["shop", "store", "clothing"]), "gallery": ("gallery spot", ["gallery", "art"])}
    for i, (key, (label, al)) in enumerate(FALL.items()):            # a map without these still works: plain named spots near the middle until you mark real buildings
        if key not in world.PLACES:
            spot = nearest_walkable(-3 + 2 * i, 3) or (0.0, 0.0)
            world.PLACES[key] = {"label": label, "x": round(spot[0], 2), "z": round(spot[1], 2), "aliases": al}
    ACTIVE["warnings"] = reachability(doc)
    return doc


def reachability(doc):
    """Places Otto cannot walk to from the middle of the map (a closed room, a wall of buildings...): reported to the editor and the control log."""
    W, blocked = ACTIVE["n"], ACTIVE["blocked"]
    s = nearest_walkable(0.0, 0.0)
    if not s:
        return []
    from collections import deque
    seen = {_cell(*s)}; q = deque(seen)
    while q:
        i, j = q.popleft()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + a, j + b)
            if 0 <= n[0] < W and 0 <= n[1] < W and n not in seen and not blocked[n[1]][n[0]]:
                seen.add(n); q.append(n)
    from . import world
    return [f"Otto cannot walk to the {p['label']} (blocked in or walled off)." for k, p in world.PLACES.items() if "spot" not in p["label"] and _cell(p["x"], p["z"]) not in seen]


def _cell(x, z):
    h = ACTIVE["half"]
    return int((x + h) // NAV), int((z + h) // NAV)


def walkable(x, z):
    if ACTIVE["doc"] is None:
        return True
    i, j = _cell(x, z)
    W = ACTIVE["n"]
    return 0 <= i < W and 0 <= j < W and not ACTIVE["blocked"][j][i]


def nearest_walkable(x, z, maxr=12):
    if ACTIVE["doc"] is None or walkable(x, z):
        return (x, z)
    h, W = ACTIVE["half"], ACTIVE["n"]
    i0, j0 = _cell(x, z)
    best = None
    for r in range(1, maxr + 1):
        for j in range(j0 - r, j0 + r + 1):
            for i in range(i0 - r, i0 + r + 1):
                if max(abs(i - i0), abs(j - j0)) != r or not (0 <= i < W and 0 <= j < W) or ACTIVE["blocked"][j][i]:
                    continue
                px, pz = -h + (i + 0.5) * NAV, -h + (j + 0.5) * NAV
                d = (px - x) ** 2 + (pz - z) ** 2
                if best is None or d < best[0]:
                    best = (d, px, pz)
        if best:
            return best[1], best[2]
    return None


def find_path(x0, z0, x1, z1):
    """A* over the walkable grid; roads and paths are cheaper than grass so he follows them. -> [(x,z), ...] or None."""
    if ACTIVE["doc"] is None:
        return [(x0, z0), (x1, z1)]
    h, W, blocked, cost = ACTIVE["half"], ACTIVE["n"], ACTIVE["blocked"], ACTIVE["cost"]
    s = nearest_walkable(x0, z0); g = nearest_walkable(x1, z1)
    if not s or not g:
        return None
    si, sj = _cell(*s); gi, gj = _cell(*g)
    openh = [(0.0, 0.0, si, sj)]; came = {}; best = {(si, sj): 0.0}
    while openh:
        _, gc, i, j = heapq.heappop(openh)
        if (i, j) == (gi, gj):
            break
        if gc > best.get((i, j), 1e9):
            continue
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            a, b = i + di, j + dj
            if not (0 <= a < W and 0 <= b < W) or blocked[b][a]:
                continue
            if di and dj and (blocked[j][a] or blocked[b][i]):
                continue                                              # no cutting corners through walls
            ng = gc + (1.414 if di and dj else 1.0) * cost[b][a]
            if ng < best.get((a, b), 1e9):
                best[(a, b)] = ng; came[(a, b)] = (i, j)
                hh = max(abs(a - gi), abs(b - gj)) + 0.414 * min(abs(a - gi), abs(b - gj))
                heapq.heappush(openh, (ng + hh, ng, a, b))
    if (gi, gj) not in best:
        return None
    cells = [(gi, gj)]
    while cells[-1] != (si, sj):
        cells.append(came[cells[-1]])
    cells.reverse()
    pts = [(x0, z0)] + [(-h + (i + 0.5) * NAV, -h + (j + 0.5) * NAV) for i, j in cells] + [(x1, z1) if walkable(x1, z1) else g]
    return _simplify(pts)


def _simplify(pts, tol=0.45):
    """Drop points that lie (almost) on the straight line between their neighbours."""
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[k], pts[k + 1]
        cross = abs((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / (math.hypot(c[0] - a[0], c[1] - a[1]) or 1)
        if cross > tol:
            out.append(b)
    out.append(pts[-1])
    return out


def walk(x, z, tx, tz, step):
    """Walk up to `step` meters along the best path. -> (nx, nz, waypoints_walked, arrived)."""
    p = find_path(x, z, tx, tz)
    if not p:
        return x, z, [], False
    left, way, cx, cz = step, [(x, z)], x, z
    for (px, pz) in p[1:]:
        d = math.hypot(px - cx, pz - cz)
        if d >= left:
            f = left / d if d else 0
            cx, cz = cx + (px - cx) * f, cz + (pz - cz) * f
            way.append((cx, cz)); return cx, cz, way, False
        left -= d; cx, cz = px, pz; way.append((cx, cz))
    return cx, cz, way, True


def approach_spot(o, fx, fz):
    """Where to stand to use an object: just outside its door, or just outside its edge on the side nearest (fx, fz)."""
    d = door_world(o, 1.2) if o.get("door") else None
    if d:
        return nearest_walkable(*d) or d
    ang = math.atan2(fz - o["z"], fx - o["x"]); r = max(abs(o["fw"]), abs(o["fd"])) * o["scale"] / 2 + 1.0
    return nearest_walkable(o["x"] + math.cos(ang) * r, o["z"] + math.sin(ang) * r) or nearest_walkable(o["x"], o["z"]) or (o["x"], o["z"])


def find_object(text):
    """Map object by '#id' / id / name (exact, then contained). Roads and lights are ignored for name matches."""
    doc = ACTIVE["doc"]
    if not doc:
        return None
    t = str(text or "").strip().lower().lstrip("#")
    if not t:
        return None
    objs = doc["objects"]
    if t.isdigit():
        return next((o for o in objs if o["id"] == int(t)), None)
    t = re.sub(r"^#\d+\s*", "", t)
    c = [o for o in objs if o["name"].lower() == t] or [o for o in objs if t in o["name"].lower() or o["name"].lower().replace("-", " ") in t.replace("-", " ")]
    return c[0] if c else None
