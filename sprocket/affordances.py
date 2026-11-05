"""Affordances: what Otto can DO with the things you placed, decided by each object's TAGS (not by special cases).

Each entry in ACTIONS says which tags it applies to, what it costs or gives (needs, mood), a plain caption with the reason, and what is written to
his journal and memory. The registry only reads the live map; it can never place, move or remove anything (only the human can, in the Plan editor).
"""
import re
import math
import time

from . import config, maps, world

NEAR = 14.0              # objects farther than this are not offered in his prompt
COOLDOWN = 25            # ticks before the same thing can be done with the same object again

# id, label, tags (any of), required tags (all of), where, why (plain reason), effects, valence, anim, verb (journal/memory, past tense), importance
ACTIONS = [
    dict(id="knock", label="knock on the door", tags={"building", "shop", "home"}, where="outside", needs_door=True, why="to see if anyone answers",
         fx={"boredom": -3}, v=0.3, anim="Wave", verb="knocked on the door of the {name}", imp=1),
    dict(id="enter", label="go inside", tags={"building", "shop", "home", "gallery"}, where="outside", needs_place=True, why="to have a look around in there",
         fx={"boredom": -3}, v=0.4, anim="Walking", verb="went inside the {name}", imp=1, special="enter"),
    dict(id="look_around", label="look around inside", tags={"building", "shop", "home", "gallery"}, where="inside", why="to see what is in here",
         fx={"boredom": -8, "creativity": 2}, v=0.6, anim="Yes", verb="looked around inside the {name}", imp=1),
    dict(id="rest_inside", label="rest inside", tags={"home", "rest", "bed"}, where="inside", why="to recharge in comfort",
         fx={"energy": config.REST_RESTORE_HOME, "battery": config.REST_BATTERY_TRICKLE_HOME, "boredom": 3}, v=1.0, anim="Sitting", verb="rested inside the {name}", imp=2,
         needs_low="energy"),
    dict(id="browse", label="browse the wares", tags={"shop"}, where="any", why="to see what is for sale",
         fx={"boredom": -6}, v=0.5, anim="Yes", verb="browsed the wares at the {name}", imp=1),
    dict(id="look_at", label="look at it", tags={"vehicle", "ride", "machine", "rocket"}, where="outside", why="because it looks interesting",
         fx={"boredom": -3}, v=0.2, anim="Idle", verb="looked at the {name}", imp=1),
    dict(id="sit_in", label="sit in it for a while", tags={"vehicle"}, where="outside", why="to rest your legs",
         fx={"energy": 8, "boredom": -2}, v=0.3, anim="Sitting", verb="sat in the {name}", imp=1),
    dict(id="honk", label="honk the horn", tags={"vehicle"}, where="outside", why="just for fun",
         fx={"boredom": -4}, v=0.6, anim="Jump", verb="honked the horn of the {name}", imp=1, special="honk"),
    dict(id="ride", label="ride along the road to another place", tags={"vehicle"}, where="outside", why="to travel without walking",
         fx={"energy": -2, "boredom": -10}, v=1.0, anim="Sitting", verb="rode in the {name} to the {dest}", imp=2, special="ride", needs_args=("to",)),
    dict(id="sit", label="sit down", tags={"bench", "seat", "stool", "chair"}, where="outside", why="to rest your legs",
         fx={"energy": 10, "boredom": -1}, v=0.3, anim="Sitting", verb="sat on the {name}", imp=1),
    dict(id="watch", label="sit and watch the world go by", tags={"bench", "seat", "pond", "ride"}, where="outside", why="to watch and relax",
         fx={"boredom": -8, "energy": 4}, v=0.4, anim="Sitting", verb="sat and watched the world from the {name}", imp=1),
    dict(id="recharge", label="recharge", tags={"charger", "power", "recharge"}, where="outside", why="because your battery is low",
         fx={"battery": config.EAT_RESTORE}, v=0.6, anim="ThumbsUp", verb="recharged at the {name}", imp=1, needs_low="battery"),
    dict(id="look_art", label="look at the art", tags={"gallery", "art"}, where="any", why="to enjoy the pictures",
         fx={"creativity": 8, "boredom": -6}, v=0.7, anim="ThumbsUp", verb="looked at the art at the {name}", imp=2),
    dict(id="ride_watch", label="watch it", tags={"ride"}, where="outside", why="to watch it go round",
         fx={"boredom": -8}, v=0.5, anim="Idle", verb="watched the {name}", imp=1),
    dict(id="look_plant", label="look at it closely", tags={"tree", "plant", "flower", "rock", "nature"}, where="outside", why="because it is nice to look at",
         fx={"boredom": -3}, v=0.25, anim="Idle", verb="looked closely at the {name}", imp=1),
    dict(id="tend", label="tend to it", tags={"plant", "flower", "garden", "tree"}, where="outside", why="to help it grow",
         fx={"creativity": 4, "boredom": -4}, v=0.5, anim="Yes", verb="tended to the {name}", imp=1),
    dict(id="use_computer", label="use the computer", tags={"computer", "screen", "terminal"}, where="outside", why="to look things up or write something",
         fx={"boredom": -8, "creativity": 6}, v=0.5, anim="Yes", verb="used the {name}", imp=1),
    dict(id="take", label="pick it up and carry it", tags={"holdable"}, where="outside", why="to carry it with you", fx={"boredom": -2}, v=0.4, anim="ThumbsUp",
         verb="picked up the {name}", imp=1, special="take"),
    dict(id="photo", label="take a photo of it", tags={"*"}, where="outside", why="to keep a picture of it", fx={"creativity": 6, "boredom": -6}, v=0.6, anim="Yes",
         verb="took a photo of the {name}", imp=2, special="photo"),
    dict(id="pet", label="say hello and pet it", tags={"animal", "pet", "cat", "dog"}, where="outside", why="because it is friendly",
         fx={"boredom": -6}, v=0.8, anim="Wave", verb="said hello to the {name}", imp=2),
]
BY_ID = {a["id"]: a for a in ACTIONS}


# ---------------------------------------------------------------- the live map
def objects():
    doc = maps.ACTIVE["doc"]
    return doc["objects"] if doc else []


def find(ref):
    ref = str(ref or "").strip().lower().lstrip("#")
    if not ref:
        return None
    objs = objects()
    m = re.match(r"^(\d+)(?:\s|$)", ref)                    # his prompt lists things as "#38 Cafe": the whole label works, not just the number or the name
    if m:
        hit = next((o for o in objs if o["id"] == int(m.group(1))), None)
        if hit:
            return hit
        ref = ref[m.end():].strip() or ref
    if ref.isdigit():
        return next((o for o in objs if o["id"] == int(ref)), None)
    exact = [o for o in objs if o["name"].lower() == ref]
    cands = exact or [o for o in objs if ref in o["name"].lower() or ref in (o.get("tags") or [])]
    return cands[0] if cands else None


def edge_dist(o, x, z):
    """Distance from a point to the nearest solid rectangle of an object (0 when on it)."""
    best = 1e9
    for r in maps.world_rects(o):
        c, s = math.cos(r["rot"]), math.sin(r["rot"]); dx, dz = x - r["x"], z - r["z"]
        lx, lz = dx * c - dz * s, dx * s + dz * c
        best = min(best, math.hypot(max(abs(lx) - r["hw"], 0), max(abs(lz) - r["hd"], 0)))
    return best


def dist_to(o, x, z):
    if o.get("door"):
        d = maps.door_world(o, 1.2)
        if d:
            return min(math.hypot(d[0] - x, d[1] - z), edge_dist(o, x, z))
    return edge_dist(o, x, z)


def _place_of(o):
    k = place_key_for(o)
    return k


def describe(o, full=False):
    """What this thing IS, in plain words, for Otto. Your own note (the 'About it' box in the Plan editor) always wins;
    otherwise it comes from the object's place and tags. `full` adds what he can do with it."""
    about = (o.get("about") or "").strip()
    t = tags_of(o); name = label(o).lower(); k = _place_of(o)
    if about:
        text = about
    elif k == "home":
        text = "your home: go inside to rest and recover your energy"
    elif k == "fuel_station" or t & {"charger", "recharge"}:
        text = "your charging station: recharge your battery here"
    elif "atm" in t:
        text = "a cash machine: deposit or withdraw your money with the bank tool"
    elif "casino" in t:
        text = "a casino: go inside and play slots, roulette, blackjack or dice with the gamble tool (play money)"
    elif "bank" in t:
        text = "the bank: go inside to deposit or withdraw your money (bank tool)"
    elif t & {"computer", "screen", "terminal"}:
        text = "a computer: use it to look things up or write"
    elif "camera" in t:
        text = "a camera: pick it up, then take photos of things"
    elif "desk" in t:
        text = "a desk to work at"
    elif t & {"structure", "wall", "roof", "corridor"}:
        text = "part of a building's walls or roof, just scenery"
    elif t & {"vehicle", "ride"}:
        text = "a vehicle: look at it, honk, or ride it to another place"
    elif t & {"bench", "seat", "stool", "chair"}:
        text = "somewhere to sit and rest"
    elif t & {"planter", "plant", "flower", "tree", "nature"}:
        text = "a plant to look at or tend"
    elif t & {"gallery", "art"}:
        text = "art to look at"
    elif t & {"shop"}:
        text = "a shop to browse"
    elif t & {"building", "home"}:
        text = "a building: knock on its door or go inside"
    elif t & {"road", "sign", "light"}:
        text = "street furniture, just scenery"
    else:
        text = f"a {name} your human placed"
    if full:
        acts = applicable({"tick": 10 ** 9, "inside": None, "x": 0, "z": 0, "holding": None, "energy": 0, "battery": 0}, o)
        ids = [a["label"] for a in acts if a["id"] not in ("photo",)]
        if ids:
            text += ". You could: " + "; ".join(ids[:4])
    return text


def label(o):
    n = o["name"]
    return n.replace("-", " ").replace("_", " ").strip()


def place_key_for(o):
    for k, p in world.PLACES.items():
        if p.get("object") == o["id"]:
            return k
    return None


def inside_obj(state):
    k = state.get("inside")
    p = world.PLACES.get(k) if k else None
    return p.get("object") if p else None


def tags_of(o):
    return set(o.get("tags") or [])


def applicable(state, o):
    """Actions that make sense for this object right now (tags decide; needs and location refine)."""
    t = tags_of(o); ins = inside_obj(state); out = []
    held = (state.get("holding") or {}).get("tags") or []
    for a in ACTIONS:
        if "*" in a["tags"]:
            if a["id"] == "photo" and "camera" not in held:
                continue
        elif not (t & a["tags"]):
            continue
        if a["id"] == "take" and state.get("holding"):
            continue
        if a.get("needs_door") and not o.get("door"):
            continue
        if a.get("needs_place") and not (place_key_for(o) and world.PLACES[place_key_for(o)].get("enter")):
            continue
        here = ins == o["id"]
        if a["where"] == "inside" and not here:
            continue
        if a["where"] == "outside" and (here or (ins and ins != o["id"] and False)):
            continue
        if a.get("needs_low") and state.get(a["needs_low"], 100) >= config.FULL_THRESHOLD - (25 if a["needs_low"] == "energy" else 0):
            continue
        if state["tick"] - state.get("aff_cd", {}).get(f"{o['id']}:{a['id']}", -999) < COOLDOWN:
            continue
        out.append(a)
    return out


def offers(state, limit=4):
    """Nearby placed objects that can be used, nearest first: [(obj, distance, [actions])]."""
    res = []
    for o in objects():
        d = dist_to(o, state["x"], state["z"])
        if d > NEAR:
            continue
        acts = applicable(state, o)
        if "structure" in (o.get("tags") or []) and not o.get("door"):
            acts = [a for a in acts if a["id"] != "photo"]            # walls and roofs are not worth a photo
        if acts:
            res.append((o, d, acts))
    # things with a real use (take, sit, recharge...) come before things that only offer a photo
    res.sort(key=lambda r: (all(a["id"] == "photo" for a in r[2]), r[1]))
    return res[:limit]


def prompt_line(state):
    if not maps.ACTIVE["doc"]:
        return None
    rows = offers(state)
    h = state.get("holding")
    hold = f" YOU ARE HOLDING: {h['name']} (put it away with the put_away tool when you are done)." if h else ""
    if not rows:
        return ("YOU CAN DO HERE:" + hold) if hold else None
    parts = []
    for o, d, acts in rows:
        parts.append(f"#{o['id']} {label(o)} ({d:.0f} m): " + "; ".join(f"{a['id']} = {a['label']}, {a['why']}" for a in acts[:3]))
    return "YOU CAN DO HERE (things your human placed; use the use tool with object and action): " + " | ".join(parts) + hold


# ---------------------------------------------------------------- the tool
def _log(ctx, a, o, text, v, extra=""):
    s, db = ctx.state, ctx.db
    full = (text[0].upper() + text[1:] + ".") + extra
    db.x("INSERT INTO journal(ts,tick,kind,text,mood) VALUES(?,?,?,?,?)", time.time(), s["tick"], "interaction", full[:300], s["mood"])
    db.x("INSERT INTO memories(ts,tick,text,importance) VALUES(?,?,?,?)", time.time(), s["tick"], f"I {text}."[:240] + (" It felt good." if v > 0.5 else ""), a["imp"] + (1 if v > 0.7 else 0))


def walk_to(ctx, o, reach, what):
    """Take one step toward a placed object until he is within `reach` of it. Returns None when he is there, else the tool result to hand back."""
    from . import tools
    s = ctx.state
    if dist_to(o, s["x"], s["z"]) <= reach:
        return None
    ins = inside_obj(s)
    if ins and ins != o["id"]:
        tools._exit(ctx)
    spot = maps.door_world(o, 1.2) if o.get("door") else None
    spot = spot or maps.nearest_walkable(o["x"], o["z"]) or (o["x"], o["z"])
    if not o.get("door"):
        ang = math.atan2(s["z"] - o["z"], s["x"] - o["x"]); r = max(abs(o["fw"]), abs(o["fd"])) * o["scale"] / 2 + 1.0
        spot = maps.nearest_walkable(o["x"] + math.cos(ang) * r, o["z"] + math.sin(ang) * r) or spot
    ox_, oz_ = s["x"], s["z"]
    nx, nz, arrived = world.step_toward(s["x"], s["z"], spot[0], spot[1])
    s["x"], s["z"] = nx, nz
    s["path"] = [[round(p, 1), round(q, 1)] for p, q in world.LAST_PATH][:40]
    left = dist_to(o, nx, nz)
    if left > reach and abs(nx - ox_) + abs(nz - oz_) < 0.05 and left <= reach + 2.0:
        return None                                              # boxed in by other things: this is as close as he can get, which is close enough
    if left > reach:
        return tools.out(True, f"You walked toward the {label(o)} to {what}; {left:.0f} m left. Keep going.", 0.0, "Walking", moved=True,
                         caption=f"Walking to the {label(o).lower()} to {what}")
    return None


def use(ctx, args):
    from . import tools
    out = tools.out
    s = ctx.state
    if not maps.ACTIVE["doc"]:
        return out(False, "There is nothing here to use yet.")
    o = find(args.get("object"))
    if not o:
        near = ", ".join(f"#{x['id']} {label(x)}" for x, _, _ in offers(s, 6)) or "nothing close by"
        return out(False, f"No such object '{args.get('object')}'. Things you can use near you: {near}.")
    acts = {a["id"]: a for a in applicable(s, o)}
    act = acts.get(str(args.get("action", "")).strip().lower().replace(" ", "_"))
    if not act:
        if o["id"] and s["tick"] - max([s.get("aff_cd", {}).get(f"{o['id']}:{a['id']}", -999) for a in ACTIONS] + [-999]) < COOLDOWN:
            return out(False, f"You just did something with the {label(o)}; give it a little while. You could do something else.")
        return out(False, f"You can't do that with the {label(o)} right now. Options: " + (", ".join(f"{a['id']} ({a['label']})" for a in acts.values()) or "nothing") + ".")
    # --- get there (walk the path) unless already inside the right building
    ins = inside_obj(s)
    if act["where"] == "inside" and ins != o["id"]:
        return out(False, f"You need to be inside the {label(o)} for that.")
    if act["where"] != "inside" and ins and ins != o["id"]:
        tools._exit(ctx)
    if dist_to(o, s["x"], s["z"]) > config.REACH and ins != o["id"]:
        spot = maps.door_world(o, 1.2) if o.get("door") else None
        spot = spot or maps.nearest_walkable(o["x"], o["z"]) or (o["x"], o["z"])
        if not o.get("door"):                                     # stand just outside the edge, on the side nearest to him
            ang = math.atan2(s["z"] - o["z"], s["x"] - o["x"]); r = max(abs(o["fw"]), abs(o["fd"])) * o["scale"] / 2 + 1.0
            spot = maps.nearest_walkable(o["x"] + math.cos(ang) * r, o["z"] + math.sin(ang) * r) or spot
        tgt = {"label": label(o).lower(), "kind": "object", "x": spot[0], "z": spot[1], "key": None, "id": None}
        px, pz = s["x"], s["z"]
        nx, nz, arrived = world.step_toward(s["x"], s["z"], tgt["x"], tgt["z"])
        s["x"], s["z"] = nx, nz
        s["path"] = [[round(p, 1), round(q, 1)] for p, q in world.LAST_PATH][:40]
        boxed_in = (arrived or (nx, nz) == (px, pz)) and dist_to(o, nx, nz) <= config.REACH_BOXED_IN     # it stands somewhere he cannot walk to (e.g. inside a building's footprint): as close as he can get is close enough
        if dist_to(o, nx, nz) > config.REACH and not boxed_in:
            return out(True, f"You walked toward the {label(o)} to {act['label']}; {dist_to(o, nx, nz):.0f} m left. Keep going.", 0.0, "Walking", moved=True,
                       caption=f"Walking to the {label(o).lower()} {act['why']}")
    # --- do it
    extra, v, anim = "", act["v"], act["anim"]
    cd = s.setdefault("aff_cd", {})
    if act.get("special") == "enter":
        key = place_key_for(o)
        tools._enter(ctx, key)
    elif act.get("special") == "ride":
        dest = tools.world.resolve_target(str(args.get("to", "")), s["x"], s["z"], [])
        if not dest or dest["kind"] != "place" or world.dist(s["x"], s["z"], dest["x"], dest["z"]) < 10:
            names = ", ".join(p["label"] for p in world.PLACES.values())
            return out(False, f"Where to? Give a place at least 10 m away with to=<place>. Places: {names}.")
        path = maps.find_path(o["x"], o["z"], dest["x"], dest["z"]) or [(o["x"], o["z"]), (dest["x"], dest["z"])]
        s["ride"] = {"obj": o["id"], "path": [[round(p, 1), round(q, 1)] for p, q in path][:60], "tick": s["tick"]}
        s["x"], s["z"] = dest["x"], dest["z"]; s["inside"] = None
        args = dict(args, dest=dest["label"])
        extra = f" The ride took you to the {dest['label']}."
    elif act.get("special") == "take":
        row = ctx.db.one("SELECT id,fit FROM assets WHERE file=? AND usable=1", o.get("asset") or "")
        if not row:
            return out(False, "You can't pick that up.")
        s["holding"] = {"name": label(o), "aid": row["id"], "fit": row["fit"], "scale": o.get("scale", 1.0), "tags": list(o.get("tags") or []), "from": o["id"]}
        extra = " It stays on the shelf for others; you carry your own copy."
    elif act.get("special") == "photo":
        extra = " You will remember how it looked."
    elif act.get("special") == "honk":
        s["honk"] = {"obj": o["id"], "tick": s["tick"]}
    for k, d in act["fx"].items():
        s[k] = max(0.0, min(100.0, s.get(k, 50) + d))
    cd[f"{o['id']}:{act['id']}"] = s["tick"]
    for k in [k for k, t in cd.items() if s["tick"] - t > 400]:
        cd.pop(k)
    text = act["verb"].format(name=label(o).lower(), dest=args.get("dest", ""))
    _log(ctx, act, o, text, v)
    feel = tools._feel_text(v)
    return out(True, f"You {text}. {feel}{extra}", v, anim, subject=label(o).lower(), caption=f"{text[0].upper() + text[1:]}", cat="rest" if act["fx"].get("energy", 0) > 0 else None)
