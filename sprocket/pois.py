"""Points of interest: places in the world that each offer something to do. Some exist from the start, others turn up (and sometimes
leave) over time, with variants (a different cat, a different train, different wares). When he is within TRIGGER of one, it appears
in his prompt as an option. Visuals are ordinary validated designs (kit generators + primitive parts); behaviour lives in tools.py."""
import json
import random
import time

from . import config, design, layout, world

TRIGGER = 5.0
MAX_POIS = 8

CAT_NAMES = ["Biscuit", "Pepper", "Marmalade", "Juniper", "Pickle", "Mochi"]
CAT_COLORS = {"ginger": "#d9822b", "grey": "#9e9e9e", "black": "#2b2b30", "cream": "#f1e0b8", "tabby": "#a07a55"}
TRAINS = ["a slow red freight train with twelve cars", "a quiet silver passenger train", "a little steam engine puffing white smoke", "a long grain train, rumbling for a full minute",
          "a yellow maintenance cart that waves to you"]
WARES = {"hats": "rows of knitted and straw hats", "fruit": "baskets of apples and plums", "pottery": "blue and cream clay bowls", "flowers": "buckets of cut flowers",
         "kites": "paper kites in every colour", "honey": "jars of golden honey"}
NEWS = [("bake sale", "baking", "A pie sale is planned at the bakery; all are welcome."), ("star walk", "stars", "Night-sky walk this evening. Bring warm clothes."),
        ("lost glove", "gloves", "Found: one blue woollen glove. Ask at the shop."), ("bird count", "birds", "Help count the birds in the garden this week."),
        ("train timetable", "trains", "New train times: the freight rolls through in the afternoon."), ("art wanted", "art", "The gallery wall has space for new pieces."),
        ("seed swap", "gardening", "Bring spare seeds and swap them by the pond."), ("quiet hour", "music", "Quiet hour at noon: soft tunes only.")]

# kind -> definition
CATALOG = {
    "bench": dict(label="Bench", anchor=(-5.5, -6.5), r=1.3, start=True, offers=["rest|sit and rest a little (a small recharge)"]),
    "noticeboard": dict(label="Noticeboard", anchor=(6.0, -8.0), r=1.0, start=True, offers=["read|read the notices"]),
    "snack_machine": dict(label="Snack machine", anchor=(6.5, -8.5), r=1.0, start=True, offers=["eat|buy a snack (refuels the battery a bit)"]),
    "bird_feeder": dict(label="Bird feeder", zone="garden", r=0.9, chance=0.05, offers=["watch|watch the birds"]),
    "cat_spot": dict(label="Cat spot", zone="village", r=1.1, chance=0.05, lifetime=(260, 420), offers=["watch|watch the cat", "pet|pet the cat"]),
    "train_line": dict(label="Train line", zone="meadow", r=4.2, chance=0.03, offers=["watch|wait and spot trains"]),
    "market_stall": dict(label="Market stall", zone="village", r=1.9, chance=0.05, lifetime=(180, 300), offers=["browse|browse the wares"]),
}


def _design(db, kind, v):
    P = lambda **k: k
    if kind == "bench":
        parts = [P(s="box", size=[1.8, .12, .6], c="wood", y=.5), P(s="box", size=[1.8, .5, .1], c="wood", y=.85, z=-.25), P(s="box", size=[.1, .5, .5], c="charcoal", x=.8, y=.25), P(s="box", size=[.1, .5, .5], c="charcoal", x=-.8, y=.25)]
    elif kind == "snack_machine":
        parts = [P(s="box", size=[.9, 1.8, .7], c="terracotta", y=.9), P(s="box", size=[.62, 1.0, .05], c="sky", y=1.15, z=.36, mat="glass"), P(s="box", size=[.5, .18, .05], c="gold", y=.45, z=.36, mat="glow")]
    elif kind == "noticeboard":
        parts = [P(gen="sign", text="NOTICES", scale=1.3)]
    elif kind == "bird_feeder":
        parts = [P(s="cylinder", size=[.1, 1.6, .1], c="wood", y=.8), P(s="box", size=[.7, .08, .7], c="wood", y=1.6), P(s="pyramid", size=[.95, .4, .95], c=v.get("roof", "terracotta"), y=2.0), P(s="sphere", size=[.1, .05, .1], c="gold", y=1.68, x=.15)]
    elif kind == "cat_spot":
        col = CAT_COLORS[v["color"]]
        parts = [P(s="cylinder", size=[1.0, .18, 1.0], c="plum", y=.09), P(s="sphere", size=[.5, .4, .7], c=col, y=.38), P(s="sphere", size=[.34, .3, .32], c=col, y=.55, z=.38), P(s="cone", size=[.1, .16, .1], c=col, y=.78, z=.36, x=.1),
                 P(s="cone", size=[.1, .16, .1], c=col, y=.78, z=.36, x=-.1), P(s="sphere", size=[.14, .14, .4], c=col, y=.3, z=-.45)]
    elif kind == "train_line":
        parts = [P(s="box", size=[8, .08, .1], c="charcoal", y=.12, z=.35), P(s="box", size=[8, .08, .1], c="charcoal", y=.12, z=-.35)] + \
                [P(s="box", size=[.18, .06, 1.1], c="wood", x=-3.2 + i * 1.6, y=.05) for i in range(5)] + \
                [P(s="box", size=[3, .3, 1.0], c="stone", y=.15, z=1.8, x=1.5), P(gen="lamp", x=2.8, z=1.8, y=.3, style="lantern")]
    elif kind == "market_stall":
        parts = [P(s="box", size=[2.4, .9, 1.0], c="wood", y=.45), P(s="prism", size=[2.8, .7, 1.6], c=v.get("awning", "rose"), y=2.1), P(s="box", size=[.1, 1.7, .1], c="wood", x=-1.2, y=.9, z=.7), P(s="box", size=[.1, 1.7, .1], c="wood", x=1.2, y=.9, z=.7),
                 P(s="box", size=[.6, .4, .5], c="sage", y=.9, x=-.6), P(s="box", size=[.6, .5, .5], c=v.get("ware_color", "gold"), y=.9, x=.5), P(gen="sign", text=v.get("sign", "MARKET"), x=0, z=1.5, scale=.7)]
    return design.clean_design(db, parts=parts, max_parts=24)


def _variant(kind, tick):
    r = random.Random(tick * 7919 + hash(kind) % 1000)
    if kind == "cat_spot":
        return {"name": r.choice(CAT_NAMES), "color": r.choice(list(CAT_COLORS))}
    if kind == "train_line":
        return {"train": r.choice(TRAINS)}
    if kind == "market_stall":
        w = r.choice(list(WARES))
        return {"wares": w, "awning": r.choice(["rose", "terracotta", "sky", "sage", "gold"]), "ware_color": r.choice(["gold", "rose", "sky", "plum", "forest"]), "sign": w.upper()[:10]}
    if kind == "bird_feeder":
        return {"roof": r.choice(["terracotta", "slate", "forest"])}
    return {}


def label_for(kind, v):
    if kind == "cat_spot": return f"{v['name']}'s spot"
    if kind == "market_stall": return f"{v['wares'].title()} stall"
    return CATALOG[kind]["label"]


def news_for(day):
    return NEWS[day % len(NEWS)], NEWS[(day * 3 + 1) % len(NEWS)]


def add(agent, kind, announce=True):
    """Create one POI (engine-placed). Returns the object id."""
    c, db, s = CATALOG[kind], agent.db, agent.state
    v = _variant(kind, s["tick"])
    d = _design(db, kind, v)
    cx, cz = c.get("anchor") or layout.ZONES[c["zone"]]["c"]
    (x, z), _ = agent.place_near(cx, cz, c["r"] + 0.3)
    exp = None
    if c.get("lifetime"):
        exp = s["tick"] + random.randint(*c["lifetime"])
    offers = [o.split("|")[1] for o in c["offers"]]
    meta = {"stage": "finished", "description": "Here you can: " + "; ".join(offers), "design": d, "poi": kind, "variant": v, "expires": exp,
            "offers": [o.split("|")[0] for o in c["offers"]]}
    name = label_for(kind, v)
    oid = db.x("INSERT INTO objects(ts,kind,name,x,z,color,source,meta,radius) VALUES(?,?,?,?,?,?,?,?,?)", time.time(), "poi", name, x, z, "#c9a97c", "poi", json.dumps(meta), c["r"] + 0.3)
    if announce:
        db.thought(s["tick"], "system", f"Something new in the world: {name.lower()}.")
        db.control(f"poi appeared: {name}")
    return oid


def ensure(agent):
    """Called every tick: seed the starting POIs, let new ones turn up, and retire the ones whose time is up."""
    db, s = agent.db, agent.state
    have = {}
    for o in db.q("SELECT id,name,meta FROM objects WHERE kind='poi'"):
        m = json.loads(o["meta"] or "{}")
        if m.get("expires") and m["expires"] <= s["tick"]:
            db.x("DELETE FROM objects WHERE id=?", o["id"])
            db.thought(s["tick"], "system", f"The {o['name'].lower()} is gone: it packed up and left.")
            db.control(f"poi left: {o['name']}")
            continue
        have[m.get("poi")] = have.get(m.get("poi"), 0) + 1
    for kind, c in CATALOG.items():
        if c.get("start") and kind not in have:
            add(agent, kind, announce=False)
            have[kind] = 1
    if sum(have.values()) >= MAX_POIS:
        return
    for kind, c in CATALOG.items():
        if not c.get("start") and kind not in have and random.random() < c["chance"] * 0.5:
            add(agent, kind)
            have[kind] = 1
            break                                   # at most one new arrival per tick


def near(objs, x, z, radius=TRIGGER):
    out = []
    for o in objs:
        if o["kind"] == "poi" and world.dist(x, z, o["x"], o["z"]) <= radius + (o.get("radius") or 1.0) * (0.0 if o.get("radius", 1) < 2 else 0.6):
            out.append(o)
    return sorted(out, key=lambda o: world.dist(x, z, o["x"], o["z"]))
