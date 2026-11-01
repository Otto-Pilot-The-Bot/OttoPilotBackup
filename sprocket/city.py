"""The 'city' map: a bigger, more city-like version of the starter town (24 x 24 cells of 4 m). Roads are placed automatically from the road tiles:
straights, bends, T-junctions, crossroads and road ends (City Kit - Roads). Buildings come from the City Kit - Commercial / Suburban kits and the space kits.
Run via the Plan editor's 'Regenerate city' or `maps.save(city.build(db), db)`; it never overwrites other maps."""
from . import config, maps, starter

N, C = 24, config.WORLD_CELL
def cx(i): return round((i - N / 2 + 0.5) * C, 2)

# road piece rotation tables (turn in degrees); straight runs along x at 90
BEND = {frozenset("ES"): 0, frozenset("WS"): 270, frozenset("WN"): 180, frozenset("EN"): 90}
TEE = {"N": 180, "E": 90, "S": 0, "W": 270}        # keyed by the MISSING side


def build(db):
    g = [["g"] * N for _ in range(N)]
    def fill(i0, j0, i1, j1, t):
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                g[j][i] = t
    fill(10, 10, 13, 13, "p")                                           # plaza in the middle
    for a, b in ((6, 17), (2, 21)):                                     # inner and outer ring roads
        for k in range(a, b + 1):
            g[a][k] = g[b][k] = g[k][a] = g[k][b] = "r"
    for k in list(range(3, 6)) + list(range(18, 21)) + list(range(7, 10)) + list(range(14, 17)):   # streets joining the rings and the plaza
        g[k][11] = g[k][12] = g[11][k] = g[12][k] = "r"
    fill(18, 3, 20, 5, "s"); fill(19, 3, 20, 4, "w")                    # pond, north-east
    fill(3, 18, 5, 20, "t")                                             # park paths, south-west
    ground = ["".join(r) for r in g]
    objs, nid = [], [0]

    def A(kit, name):
        return db.one("SELECT * FROM assets WHERE pack=? AND lower(name)=lower(?) AND usable=1", kit, name)

    def put(kit, name, x, z, rot=0, scale=1.0, tags=None, door="keep", walkable=None, fp=None, solids=None, title=None):
        r = A(kit, name)
        if not r:
            print(f"  (city map: '{kit} / {name}' not found, skipped)"); return None
        d = maps.asset_defaults(r); nid[0] += 1
        o = {"id": nid[0], "asset": r["file"], "kit": kit, "name": title or r["name"], "x": x, "z": z, "rot": rot % 360, "scale": scale,
             "fw": fp[0] if fp else d["fw"], "fd": fp[1] if fp else d["fd"], "tags": list(dict.fromkeys((tags or []) + d["tags"][:4]))[:12],
             "door": d["door"] if door == "keep" else door, "walkable": d["walkable"] if walkable is None else walkable}
        if solids:
            o["solids"] = solids
        objs.append(o); return o

    # ---- roads from tiles
    isroad = lambda i, j: 0 <= i < N and 0 <= j < N and g[j][i] in "rp"
    for j in range(N):
        for i in range(N):
            if g[j][i] != "r":
                continue
            n = {"N": isroad(i, j - 1), "S": isroad(i, j + 1), "E": isroad(i + 1, j), "W": isroad(i - 1, j)}
            on = [k for k, v in n.items() if v]; x, z = cx(i), cx(j)
            if len(on) == 4: name, rot = "road-crossroad", 0
            elif len(on) == 3: name, rot = "road-intersection", TEE[[k for k in "NESW" if not n[k]][0]]
            elif len(on) == 2 and set(on) in ({"N", "S"}, {"E", "W"}): name, rot = "road-straight", 0 if "N" in on else 90
            elif len(on) == 2: name, rot = "road-bend", BEND[frozenset(on)]
            else: name, rot = "road-end", {"N": 0, "E": 270, "S": 180, "W": 90}.get(on[0], 0) if on else 0
            put("City Kit - Roads", name, x, z, rot, tags=["road"], walkable=True, title="Road")

    ROOM = starter_room()
    # ---- the four places around the plaza
    home = put("Modular Space Kit", "room-small", cx(8), cx(8), 0, tags=["building", "home", "house", "rest"], door=[0, 5.0], fp=(11.0, 11.0), solids=ROOM, title="Home")
    shop = put("City Kit - Commercial", "building-e", cx(15), cx(8), 0, tags=["building", "shop"], door=[0, 2.4], fp=(6.6, 4.8), title="Shop")
    charger = put("Space Kit", "hangar smallA", cx(8), cx(15), 0, tags=["building", "charger", "power"], door=[0, 4.0], fp=(7.5, 7.5), title="Charging hall")
    gallery = put("Modular Space Kit", "room-small-variation", cx(15), cx(15), 180, tags=["building", "gallery", "art"], door=[0, 5.0], fp=(11.0, 11.0), solids=ROOM, title="Gallery")
    put("Space Kit", "machine generatorLarge", cx(10) - 1, cx(15) + 3.4, 0, tags=["charger", "power", "recharge"], walkable=False, title="Charging station")
    if home:
        hx, hz = home["x"], home["z"]
        put("Space Station Kit", "bed-single", hx - 3.6, hz - 2.6, 90, tags=["bed", "rest", "furniture"], walkable=False, fp=(2.4, 4.0), title="Bed")
        put("Space Station Kit", "table", hx + 1.5, hz - 3.8, 0, tags=["table", "furniture"], walkable=False, fp=(2.2, 1.2), title="Table")
        put("Space Station Kit", "chair", hx + 1.5, hz - 2.4, 180, tags=["chair", "seat", "furniture"], walkable=False, fp=(0.8, 0.8), title="Chair")
    if shop:
        put("City Kit - Commercial", "detail-awning-wide", shop["x"], shop["z"] + 2.9, 0, tags=["decor"], walkable=True, title="Awning")
    if gallery:
        gx, gz = gallery["x"], gallery["z"]
        put("Furniture Kit", "bench", gx, gz - 1.0, 0, scale=1.8, tags=["bench", "seat", "gallery"], fp=(1.6, 0.8), title="Gallery bench")
        for k, dx in enumerate((-3.4, 0.0, 3.4)):
            nid[0] += 1
            objs.append({"id": nid[0], "asset": None, "kit": "flat", "name": f"Art panel {k + 1}", "x": round(gx + dx, 2), "z": round(gz + 4.7, 2), "rot": 180, "scale": 1.0,
                         "fw": 2.4, "fd": 0.2, "tags": ["art", "gallery"], "door": None, "walkable": True, "y": 1.9, "panel": {"w": 2.2, "h": 1.6, "art_id": None, "caption": ""}})

    # ---- city bands between the rings: commercial buildings north and south, houses west and east. Doors face the outer street.
    COM = ["building-a", "building-b", "building-d", "building-f", "building-h", "building-skyscraper-a", "building-c", "building-g", "building-m", "building-skyscraper-c", "building-i", "building-k"]
    SUB = ["building-type-a", "building-type-c", "building-type-e", "building-type-g", "building-type-i", "building-type-k", "building-type-m", "building-type-o"]
    for k, i in enumerate(range(3, 21, 3)):                          # north band (faces north = outer street at row 2): rot 180
        if 16 <= i <= 20: continue                                    # pond corner
        put("City Kit - Commercial", COM[k % len(COM)], cx(i) + 1.0, cx(4), 180, tags=["building", "city"], title="Office")
    for k, i in enumerate(range(3, 21, 3)):                          # south band faces south (outer street at row 21): rot 0
        if i <= 6: continue                                           # park corner
        put("City Kit - Commercial", COM[(k + 4) % len(COM)], cx(i) + 1.0, cx(19), 0, tags=["building", "city"], title="Office")
    for k, j in enumerate(range(8, 21, 3)):                          # west band, face west: rot 270
        if j >= 17: continue
        put("City Kit - Suburban", SUB[k % len(SUB)], cx(4), cx(j) + 1.0, 270, tags=["building", "house"], title="House")
    for k, j in enumerate(range(8, 21, 3)):                          # east band, face east: rot 90
        put("City Kit - Suburban", SUB[(k + 3) % len(SUB)], cx(19), cx(j) + 1.0, 90, tags=["building", "house"], title="House")
    # ---- street lights along the inner ring, trees on the margins, parked cars
    for i in (8, 11, 12, 15):
        put("City Kit - Roads", "light-square", cx(i), cx(6) - 1.8, 0, tags=["light", "lamp"], walkable=True, title="Street light")
        put("City Kit - Roads", "light-square", cx(i), cx(17) + 1.8, 180, tags=["light", "lamp"], walkable=True, title="Street light")
    for j in (8, 11, 12, 15):
        put("City Kit - Roads", "light-square", cx(6) - 1.8, cx(j), 90, tags=["light", "lamp"], walkable=True, title="Street light")
        put("City Kit - Roads", "light-square", cx(17) + 1.8, cx(j), 270, tags=["light", "lamp"], walkable=True, title="Street light")
    for k, (i, j, nm) in enumerate(((0, 4, "tree default"), (0, 10, "tree oak"), (0, 16, "tree fat"), (23, 6, "tree default fall"), (23, 14, "tree oak"), (4, 23, "tree pineRoundA"),
                                    (12, 0, "tree default"), (8, 0, "tree fat"), (17, 23, "tree oak"), (12, 23, "tree default fall"))):
        put("Nature Kit", nm, cx(i), cx(j), k * 41, tags=["tree", "plant"], title="Tree")
    put("Furniture Kit", "bench", cx(3), cx(19) - 1, 0, scale=1.8, tags=["bench", "seat", "park"], fp=(1.6, 0.8), title="Park bench")
    put("Furniture Kit", "bench", cx(5), cx(19) + 1, 180, scale=1.8, tags=["bench", "seat", "park"], fp=(1.6, 0.8), title="Park bench")
    for k, (fx, fz) in enumerate(((3, 18), (5, 18), (4, 20), (5, 20))):
        put("Nature Kit", ("flower redA", "flower yellowA", "flower purpleA", "flower yellowB")[k], cx(fx), cx(fz), k * 50, scale=1.0, tags=["flower", "plant", "garden"], title="Flowers")
    put("Nature Kit", "tree oak", cx(4), cx(20) - 1, 20, tags=["tree", "plant", "park"], title="Tree")
    put("Car Kit", "sedan", cx(9) - 1, cx(2) - 2.6, 90, tags=["vehicle", "car", "sit", "honk"], walkable=True, title="Sedan")
    put("Car Kit", "taxi", cx(21) + 2.6, cx(9), 0, tags=["vehicle", "car", "sit", "honk"], walkable=True, title="Taxi")
    put("Car Kit", "van", cx(14) + 1, cx(21) + 2.6, 90, tags=["vehicle", "car", "sit", "honk"], walkable=True, title="Van")
    put("Cube Pets", "animal-cat", cx(7) + 0.5, cx(10) + 1.0, 200, scale=0.8, tags=["animal", "cat", "pet"], walkable=False, fp=(0.5, 0.6), title="Cat")

    places = {}
    def place(key, label, o, aliases, enter=False):
        if o: places[key] = {"label": label, "object": o["id"], "aliases": aliases, "enter": enter}
    place("home", "home", home, ["home", "pad", "bed", "house", "cabin"], True)
    place("clothing_store", "shop", shop, ["shop", "store", "market", "clothing", "clothes"], True)
    place("gallery", "gallery", gallery, ["gallery", "art", "museum"], True)
    place("fuel_station", "charging station", charger, ["charging", "charger", "station", "fuel", "battery", "food"])
    places["plaza"] = {"label": "plaza", "at": [0.0, 0.0], "aliases": ["plaza", "square", "center", "centre"]}
    places["park"] = {"label": "park", "at": [cx(4), cx(19)], "aliases": ["park", "garden", "benches"]}
    places["pond"] = {"label": "pond", "at": [cx(18) - 0.6, cx(4)], "aliases": ["pond", "water", "lake"]}
    return {"version": 1, "name": "city", "cell": C, "n": N, "ground": ground, "objects": objs, "places": places}


def starter_room():
    return [{"x": 0, "z": -5.1, "w": 11.0, "d": 0.9}, {"x": -5.1, "z": 0, "w": 0.9, "d": 11.0}, {"x": 5.1, "z": 0, "w": 0.9, "d": 11.0},
            {"x": -3.7, "z": 5.1, "w": 3.6, "d": 0.9}, {"x": 3.7, "z": 5.1, "w": 3.6, "d": 0.9}]


def ensure(db, force=False):
    p = maps.path_for("city")
    if force or not p.is_file():
        maps.save(build(db), db)
    return maps.load("city")
