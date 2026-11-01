"""The starter map: a small cozy sci-fi town on a 20 x 20 grid (4 m cells). Built only from models that exist in assets/kenney.
Run again any time to regenerate (it never overwrites a map you saved under another name). Everything in it is editable in the Plan editor."""
import math

from . import config, maps

N = 20
C = config.WORLD_CELL


def cx(i): return round((i - N / 2 + 0.5) * C, 2)        # world coordinate of the middle of grid column/row i


def build(db):
    g = [["g"] * N for _ in range(N)]
    def fill(i0, j0, i1, j1, t):
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                g[j][i] = t
    fill(8, 8, 11, 11, "p")                                            # plaza
    for i in range(4, 16):
        g[4][i] = g[15][i] = "r"
    for j in range(4, 16):
        g[j][4] = g[j][15] = "r"                                       # the road loop
    for j in (5, 6, 7): g[j][9] = "t"                                  # footpaths from the plaza out to the loop
    for j in (12, 13, 14): g[j][10] = "t"
    for i in (5, 6, 7): g[9][i] = "t"
    for i in (12, 13, 14): g[10][i] = "t"
    fill(16, 7, 19, 12, "s"); fill(17, 8, 18, 11, "w")                 # pond with a sandy shore, east of the loop
    fill(1, 16, 8, 18, "t")                                            # little park paths, south-west
    ground = ["".join(r) for r in g]
    objs, nid = [], [0]

    def A(kit, name):
        r = db.one("SELECT * FROM assets WHERE pack=? AND lower(name)=lower(?) AND usable=1", kit, name)
        if not r:
            print(f"  (starter map: '{kit} / {name}' not found, skipped)")
        return r

    ROOM = [{"x": 0, "z": -5.1, "w": 11.0, "d": 0.9}, {"x": -5.1, "z": 0, "w": 0.9, "d": 11.0}, {"x": 5.1, "z": 0, "w": 0.9, "d": 11.0},
                                                                  {"x": -3.7, "z": 5.1, "w": 3.6, "d": 0.9}, {"x": 3.7, "z": 5.1, "w": 3.6, "d": 0.9}]     # the curved walls of a Modular Space Kit room, with a doorway on its front (+z) side

    def put(kit, name, x, z, rot=0, scale=1.0, tags=None, door="keep", walkable=None, fp=None, y=None, solids=None, title=None):
        r = A(kit, name)
        if not r:
            return None
        d = maps.asset_defaults(r); nid[0] += 1
        o = {"id": nid[0], "asset": r["file"], "kit": kit, "name": title or r["name"], "x": x, "z": z, "rot": rot, "scale": scale,
             "fw": fp[0] if fp else d["fw"], "fd": fp[1] if fp else d["fd"], "tags": list(dict.fromkeys((tags or []) + d["tags"][:4]))[:12],
             "door": d["door"] if door == "keep" else door, "walkable": d["walkable"] if walkable is None else walkable}
        if y is not None:
            o["y"] = y
        if solids:
            o["solids"] = solids
        objs.append(o); return o

    # --- road pieces on the loop (corner bends + straights)
    for i in range(5, 15):
        put("City Kit - Roads", "road-straight", cx(i), cx(4), 90, tags=["road"], walkable=True)
        put("City Kit - Roads", "road-straight", cx(i), cx(15), 90, tags=["road"], walkable=True)
    for j in range(5, 15):
        put("City Kit - Roads", "road-straight", cx(4), cx(j), 0, tags=["road"], walkable=True)
        put("City Kit - Roads", "road-straight", cx(15), cx(j), 0, tags=["road"], walkable=True)
    for (i, j, rot) in ((4, 4, 0), (15, 4, 270), (15, 15, 180), (4, 15, 90)):
        put("City Kit - Roads", "road-bend", cx(i), cx(j), rot, tags=["road"], walkable=True)

    # --- buildings, one per corner of the plaza (each is a 3x3 block of cells = 12 m)
    home = put("Modular Space Kit", "room-small", cx(6), cx(6), 0, title="Home", tags=["building", "home", "house", "rest"], door=[0, 5.0], fp=(11.0, 11.0), solids=ROOM)
    shop = put("City Kit - Commercial", "building-e", cx(13), cx(6), 0, title="Shop", tags=["building", "shop"], door=[0, 2.4], fp=(6.6, 4.8))
    gallery = put("Modular Space Kit", "room-small-variation", cx(13), cx(13), 180, title="Gallery", tags=["building", "gallery", "art"], door=[0, 5.0], fp=(11.0, 11.0), solids=ROOM)
    charger = put("Space Kit", "hangar smallA", cx(6), cx(13), 0, title="Charging hall", tags=["building", "charger", "power"], door=[0, 4.0], fp=(7.5, 7.5))
    put("Space Kit", "machine generatorLarge", cx(8) - 1, cx(13) + 3.4, 0, title="Charging station", tags=["charger", "power", "recharge"], walkable=False)
    if home:                                                      # a homey corner inside (all Kenney Space Station furniture)
        hx, hz = home["x"], home["z"]
        put("Space Station Kit", "bed-single", hx - 3.6, hz - 2.6, 90, title="Bed", tags=["bed", "rest", "furniture"], walkable=False, fp=(2.4, 4.0))
        put("Space Station Kit", "table", hx + 1.5, hz - 3.8, 0, title="Table", tags=["table", "furniture"], walkable=False, fp=(2.2, 1.2))
        put("Space Station Kit", "chair", hx + 1.5, hz - 2.4, 180, title="Chair", tags=["chair", "seat", "furniture"], walkable=False, fp=(0.8, 0.8))
        put("Space Station Kit", "computer", hx + 3.8, hz - 3.4, 0, title="Computer", tags=["computer", "furniture"], walkable=False, fp=(1.2, 0.8))
    if shop:                                                      # awning and a couple of crates by the shop
        put("City Kit - Commercial", "detail-awning-wide", shop["x"], shop["z"] + 2.9, 0, title="Awning", tags=["decor"], walkable=True)
    if gallery:
        gx, gz = gallery["x"], gallery["z"]
        put("Furniture Kit", "bench", gx, gz - 1.0, 0, title="Gallery bench", scale=1.8, tags=["bench", "seat", "gallery"], fp=(1.6, 0.8))
        for k, dx in enumerate((-3.4, 0.0, 3.4)):                 # flat art panels on the back wall: they show Otto's newest pictures (empty frames until he has some)
            nid[0] += 1
            objs.append({"id": nid[0], "asset": None, "kit": "flat", "name": f"Art panel {k + 1}", "x": round(gx + dx, 2), "z": round(gz + 4.7, 2), "rot": 180,
                         "scale": 1.0, "fw": 2.4, "fd": 0.2, "tags": ["art", "gallery"], "door": None, "walkable": True, "y": 1.9,
                         "panel": {"w": 2.2, "h": 1.6, "art_id": None, "caption": ""}})

    # --- park (south-west, outside the loop): benches, trees, flowers
    put("Furniture Kit", "bench", cx(3) + 1, cx(17), 0, title="Park bench", scale=1.8, tags=["bench", "seat", "park"], fp=(1.6, 0.8))
    put("Furniture Kit", "bench", cx(7), cx(17) - 1, 180, title="Garden bench", scale=1.8, tags=["bench", "seat", "park"], fp=(1.6, 0.8))
    for (dx, dz, nm) in ((-12.5, 1.5, "tree default"), (-9, 4, "tree oak"), (-1, 5.5, "tree pineRoundA"), (3, 0, "tree default fall"), (-14, 5, "tree fat")):
        put("Nature Kit", nm, round(cx(3) + dx + 2, 2), round(cx(18) + dz - 2, 2), (dx * 37) % 360, tags=["tree", "plant", "park"], title="Tree")
    for k, (fx, fz) in enumerate(((-12, 15), (-10.2, 16.5), (-8.5, 15.6), (-5, 17), (-2.4, 15.5))):
        put("Nature Kit", ("flower redA", "flower yellowA", "flower purpleA", "flower yellowB", "flower redB")[k], fx, fz, k * 50, scale=1.0, tags=["flower", "plant", "garden"])
    # --- trees on the margins, a few rocks by the pond
    for (x, z, nm) in ((-35, -33, "tree default"), (33, -34, "tree oak"), (-36, -5, "tree pineRoundA"), (-34, 12, "tree fat"), (35, 22, "tree default fall"), (20, 34, "tree oak"), (-26, -35, "tree pineTallA")):
        put("Nature Kit", nm, x, z, (x * 13) % 360, tags=["tree", "plant"])
    for k, (x, z) in enumerate(((cx(16) + 0.5, cx(7) - 0.5), (cx(19) - 0.5, cx(12) + 1), (cx(16) + 0.5, cx(12) + 0.5))):
        put("Nature Kit", ("rock smallA", "rock smallC", "rock smallG")[k], x, z, k * 70, scale=2.0, tags=["rock"])
    # --- street furniture and a few parked cars on the loop
    for (i, rot) in ((6, 0), (9, 0), (12, 0)):
        put("City Kit - Roads", "light-square", cx(i), cx(4) - 1.6, 0, tags=["light", "lamp", "prop"], walkable=True)
    put("Car Kit", "sedan", cx(8) - 1, cx(3) + 0.4, 90, title="Sedan", tags=["vehicle", "car", "sit", "honk"], walkable=True)
    put("Car Kit", "taxi", cx(16) + 0.2, cx(5), 0, title="Taxi", tags=["vehicle", "car", "sit", "honk"], walkable=True)
    put("Car Kit", "van", cx(11), cx(16) + 0.2, 90, title="Van", tags=["vehicle", "car", "sit", "honk"], walkable=True)
    put("Space Kit", "rover", cx(2) + 1, cx(10), 90, scale=2.2, title="Rover", tags=["vehicle", "rover", "sit"], walkable=False)
    # --- a few props (cat by the home, planters)
    put("Cube Pets", "animal-cat", cx(7) + 0.5, cx(8) + 2.2, 200, title="Cat", scale=0.8, tags=["animal", "cat", "pet"], walkable=False, fp=(0.5, 0.6))
    put("Furniture Kit", "plantSmall1", cx(8), cx(5) + 6.4, 0, scale=3.0, title="Potted plant", tags=["plant", "decor"])
    put("Furniture Kit", "lampRoundFloor", cx(10) - 0.5, cx(9), 0, scale=2.4, title="Plaza lamp", tags=["light", "lamp"], walkable=True)

    places = {}
    def place(key, label, o, aliases, enter=False):
        if o:
            places[key] = {"label": label, "object": o["id"], "aliases": aliases, "enter": enter}
    place("home", "home", home, ["home", "pad", "bed", "house", "cabin"], True)
    place("clothing_store", "shop", shop, ["shop", "store", "market", "clothing", "clothes"], True)
    place("gallery", "gallery", gallery, ["gallery", "art", "museum"], True)
    place("fuel_station", "charging station", charger, ["charging", "charger", "station", "fuel", "battery", "food"])
    places["plaza"] = {"label": "plaza", "at": [0.0, 0.0], "aliases": ["plaza", "square", "center", "centre"]}
    places["park"] = {"label": "park", "at": [cx(5), cx(17)], "aliases": ["park", "garden", "benches"]}
    places["pond"] = {"label": "pond", "at": [cx(16) - 0.6, cx(9.5)], "aliases": ["pond", "water", "lake"]}
    return {"version": 1, "name": "starter", "cell": C, "n": N, "ground": ground, "objects": objs, "places": places}


def ensure(db, force=False):
    p = maps.path_for("starter")
    if force or not p.is_file():
        maps.save(build(db), db)
    return maps.load("starter")
