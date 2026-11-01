"""Asset library: scan model packs, index them in SQLite, search them. Model files are DATA ONLY:
we read the JSON header of each .glb, never execute anything, and reject files that reference external URLs."""
import json
import math
import re
import struct
import time
from pathlib import Path

from . import config

FORBIDDEN_EXT = {"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu", "EXT_texture_webp"}  # we ship no decoders
TRUNC = [("Corner Inn", "Corner Inner"), ("Diagona", "Diagonal"), ("Patch Larg", "Patch Large"), ("Wide Rou", "Wide Round"), ("Wide Ro", "Wide Round"),
         ("Round De", "Round Detail"), ("Square D", "Square Detail"), ("Corner D", "Corner Diagonal"), ("Corner R", "Corner Round"),
         ("Corner S", "Corner Small"), ("Column B", "Column Big"), ("Column S", "Column Small")]
VOCAB = {
    "tree": "nature plant tree wood", "cactus": "nature plant desert cactus", "flowers": "nature plant flower bloom", "flower": "nature plant flower bloom",
    "bloom": "nature plant flower", "marigold": "nature plant flower", "rock": "nature stone", "log": "nature wood camp", "fire": "fire light warm camp",
    "campfire": "fire camp light warm", "tent": "camp shelter", "island": "nature terrain small", "barricade": "defense barrier structure",
    "border": "edge border structure", "column": "structure pillar", "pillar": "structure pillar", "corrugated": "metal sheet roof industrial",
    "iron": "metal", "pipe": "industrial pipe", "floor": "floor tile structure", "tile": "floor tile structure", "door": "door entrance structure building",
    "doorway": "entrance door structure", "gutter": "pipe drain building", "roof": "roof structure building", "stairs": "stairs structure",
    "wall": "wall structure building", "window": "window building structure", "crate": "container storage box scifi", "barrel": "container storage scifi",
    "engine": "machine scifi motor", "pod": "scifi vehicle capsule", "rover": "vehicle space machine", "probe": "space machine", "station": "space structure",
    "moon": "space celestial", "planet": "space celestial", "turtle": "animal creature", "hummingbird": "animal bird creature", "wren": "animal bird creature",
    "rake": "tool garden", "ladder": "tool climb", "lighting": "light lamp", "support": "structure", "desert": "terrain nature", "organ": "plant cactus",
    "camera": "holdable tool", "cup": "holdable", "mug": "holdable", "book": "holdable", "brush": "holdable tool", "pen": "holdable tool", "ball": "holdable",
    "sci": "scifi", "scifi": "scifi", "space": "space", "habitat": "space", "detail": "detail", "modern": "modern", "wooden": "wood", "red": "red", "grey": "grey", "white": "white",
}
SYN = {"lamp": "light", "lantern": "light", "house": "building", "hut": "building", "cabin": "building", "shed": "building", "plant": "plant",
       "bush": "plant", "garden": "plant", "campsite": "camp", "stone": "rock", "boulder": "rock", "bird": "animal", "pet": "animal", "ship": "space",
       "rocket": "space", "satellite": "space", "robot": "machine", "crate": "container", "box": "container", "chest": "container", "table": "structure",
       "gate": "door", "fence": "border", "barrier": "barricade", "steps": "stairs", "star": "celestial", "fireplace": "fire", "torch": "fire"}


def asset_dirs():
    return [config.ROOT / d for d in config.ASSET_DIRS if (config.ROOT / d).is_dir()]


def _words(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s.lower()) if w and not w.isdigit()]


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def clean_name(stem):
    n = re.sub(r"-[A-Za-z0-9]{10}$", "", stem).replace("_", " ").strip()
    for a, b in TRUNC:
        if n.endswith(a):
            n = n[: -len(a)] + b
    return re.sub(r"\s+", " ", n)


# ----- minimal glTF reading (JSON chunk only) + a bounding box that honours node transforms -----
def read_glb_json(path):
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"glTF":
            raise ValueError("not a .glb file")
        chunk = f.read(8)
        length, ctype = struct.unpack("<I4s", chunk)
        if ctype != b"JSON" or length > 8_000_000:
            raise ValueError("unexpected glb layout")
        return json.loads(f.read(length))


def _mat(n):
    if "matrix" in n:
        m = n["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t, q, s = n.get("translation", [0, 0, 0]), n.get("rotation", [0, 0, 0, 1]), n.get("scale", [1, 1, 1])
    x, y, z, w = q
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t[0]], [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t[1]],
            [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t[2]], [0, 0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inspect(path):
    j = read_glb_json(path)
    ext = set(j.get("extensionsUsed", [])) | set(j.get("extensionsRequired", []))
    bad = ext & FORBIDDEN_EXT
    for coll in ("images", "buffers"):
        for item in j.get(coll, []):
            if "uri" in item and not str(item["uri"]).startswith("data:"):
                raise ValueError("references an external file/URL (refused)")
    acc, meshes, nodes = j.get("accessors", []), j.get("meshes", []), j.get("nodes", [])
    tris = 0
    for m in meshes:
        for pr in m["primitives"]:
            tris += (acc[pr["indices"]]["count"] if "indices" in pr else acc[pr["attributes"]["POSITION"]]["count"]) // 3
    lo, hi, seen = [1e18] * 3, [-1e18] * 3, 0

    def walk(i, parent, depth=0):
        nonlocal seen
        if depth > 64 or i >= len(nodes):
            return
        n = nodes[i]
        m = _mul(parent, _mat(n))
        if "mesh" in n:
            for pr in meshes[n["mesh"]]["primitives"]:
                a = acc[pr["attributes"]["POSITION"]]
                if "min" in a and "max" in a:
                    for cx in (a["min"][0], a["max"][0]):
                        for cy in (a["min"][1], a["max"][1]):
                            for cz in (a["min"][2], a["max"][2]):
                                p = [sum(m[r][c] * v for c, v in enumerate((cx, cy, cz))) + m[r][3] for r in range(3)]
                                for k in range(3):
                                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
                                seen += 1
        for c in n.get("children", []):
            walk(c, m, depth + 1)
    ident = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    scenes = j.get("scenes", [])
    for r in (scenes[j.get("scene", 0)].get("nodes", []) if scenes else range(len(nodes))):
        walk(r, ident)
    size = [max(0.0, hi[k] - lo[k]) for k in range(3)] if seen else [1.0, 1.0, 1.0]
    return {"lo": lo if seen else [0, 0, 0], "hi": hi if seen else [1, 1, 1], "size": size, "tris": tris, "anims": [a.get("name", f"anim{i}") for i, a in enumerate(j.get("animations", []))],
            "skins": bool(j.get("skins")), "bad_ext": sorted(bad), "extras": j.get("asset", {}).get("extras") or {}, "copyright": j.get("asset", {}).get("copyright", "")}


# Tags guessed from names (editable later per map object). First matching rule wins for `cat`; every matching rule adds its tags.
CAT_RULES = [
    (r"\b(character|astronaut|alien|robot|person|man|woman|boy|girl|skin|npc)\b", "character", "character"),
    (r"\b(road|street|path|track|rail|crossing|bridge|asphalt|pavement|sidewalk|intersection|roundabout|curve|ramp)\b", "road", "road"),
    (r"\b(car|truck|van|bus|taxi|police|ambulance|sedan|suv|hatchback|kart|cart|vehicle|bike|motorcycle|scooter|rover|tractor|train|locomotive|wagon|tram|boat|ship|spaceship|craft|rocket|shuttle|speeder|ufo)\b", "vehicle", "vehicle"),
    (r"\b(tree|pine|palm|oak|bush|shrub|hedge|grass|flower|plant|cactus|fern|mushroom|leaf|stump|log|bamboo)\b", "tree", "nature"),
    (r"\b(rock|stone|boulder|cliff|hill|mountain|crystal)\b", "rock", "nature"),
    (r"\b(bench|seat|sofa|couch|stool|chair|armchair)\b", "bench", "seat"),
    (r"\b(charger|charging|battery|generator|reactor|power|solar|antenna|tower|pylon)\b", "charger", "power"),
    (r"\b(ride|coaster|ferris|carousel|swing|slide|merry|roundabout|bumper|arcade)\b", "ride", "ride"),
    (r"\b(shop|store|market|stand|kiosk|stall|vending|bakery|cafe|restaurant|diner)\b", "shop", "shop"),
    (r"\b(building|house|home|cottage|hut|cabin|skyscraper|tower|garage|warehouse|factory|station|habitat|hangar|dome|module|castle|church|barn|silo|tent|apartment|hotel)\b", "building", "building"),
    (r"\b(wall|floor|roof|window|door|corridor|stairs|stair|pillar|column|fence|gate|railing|ceiling|hull)\b", "structure", "structure"),
]
PROP_CAT = "prop"
PROP_WORDS = r"\b(planter|driveway|fence|path|awning|overhang|parasol|detail|sign|light|pole|wires)\b"


PACK_CAT = {"Car Kit": "vehicle", "Racing Kit": "vehicle", "Toy Car Kit": "vehicle", "Train Kit": "vehicle", "Watercraft Pack": "vehicle",
            "Road Pack": "road", "City Kit - Roads": "road", "Blocky Characters": "character", "Mini Characters": "character", "Cube Pets": "character",
            "Coaster Kit": "ride", "Nature Kit": "tree", "Mini Forest": "tree", "Modular Buildings": "building", "Fantasy Town Kit": "building"}


def category(name, pack):
    """-> (cat, tags). The model name decides; the kit name only decides when the name says nothing."""
    text = " ".join(_words(name))
    if re.search(PROP_WORDS, text) and not re.search(r"\b(building|house|shop|store)\b", text):
        return PROP_CAT, [PROP_CAT]
    hits = [(cat, tag) for rx, cat, tag in CAT_RULES if re.search(rx, text)]
    if not hits and pack in PACK_CAT:
        c = PACK_CAT[pack]
        hits = [(c, next((t for _, cc, t in CAT_RULES if cc == c), c))]
    if not hits:
        return PROP_CAT, [PROP_CAT]
    return hits[0][0], list(dict.fromkeys([h[0] for h in hits] + [h[1] for h in hits]))


def door_guess(cat, tags, fw, fd):
    """Best guess for where a visitor goes in: the middle of the front (+z) side, for things people can enter. Editable per object."""
    if cat in ("building", "shop") or "building" in tags:
        return 0.0, round(fd / 2, 2)
    return None, None


def tags_for(name, pack):
    toks = [_stem(w) for w in _words(name)]
    tags = []
    for w in toks:
        tags += VOCAB.get(w, "").split()
        tags.append(w)
    tags += [_stem(w) for w in _words(pack) if w not in ("undefined", "glb", "kit", "pack", "bundle", "small")]
    return list(dict.fromkeys(t for t in tags if t))


# ----- packs: license / credit info ------------------------------------------------------------------------
def pack_info(folder: Path):
    """Looks for credits.json or LICENSE/CREDITS/README text files. Missing = license UNKNOWN (we never guess)."""
    info = {"license": "unknown", "credit": "", "source": "", "attribution_required": 0,
            "notes": "No LICENSE/CREDITS file found in this pack folder. Add credits.json or LICENSE.txt to record it."}
    cj = folder / "credits.json"
    if cj.is_file():
        try:
            d = json.loads(cj.read_text()[:4000])
            info.update({"license": str(d.get("license", "unknown"))[:80], "credit": str(d.get("credit") or d.get("author") or "")[:300],
                         "source": str(d.get("source", ""))[:300], "notes": str(d.get("notes", ""))[:300]})
        except Exception:
            info["notes"] = "credits.json could not be read"
    else:
        for f in sorted(folder.iterdir()):
            if f.is_file() and re.match(r"(licen[sc]e|credit|attribution|readme|copying)", f.name, re.I) and f.suffix.lower() in ("", ".txt", ".md"):
                txt = f.read_text(errors="replace")[:3000]
                info["notes"] = txt[:300].strip()
                m = re.search(r"CC0|CC[- ]BY(?:[- ](?:SA|NC|ND))*(?:[- ]\d\.\d)?|MIT|Apache|public domain", txt, re.I)
                info["license"] = m.group(0) if m else "see file"
                info["credit"] = txt[:200].strip()
                break
    info["attribution_required"] = int(bool(re.search(r"CC[- ]BY", info["license"], re.I)) or "attribution" in info["notes"].lower())
    return info


def _pack_name(folder_name):
    n = re.sub(r"\.undefined-glb$|[-.]glb$|\.zip$", "", folder_name, flags=re.I)
    return n.strip()


INDEX_VERSION = 9          # bump when the way entries are computed changes (forces a re-index that keeps asset ids)


def scan(db, log=print):
    """(Re)index every pack folder. Unchanged files are skipped, vanished files removed. Returns a summary."""
    t0 = time.time()
    force = db.get("asset_index_v") != INDEX_VERSION
    seen_files, added, updated, skipped = set(), 0, 0, []
    used_names = {}
    for root in asset_dirs():
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            pack = _pack_name(folder.name)
            files = sorted(f for f in folder.rglob("*") if f.suffix.lower() == ".glb" and f.is_file() )
            pi = pack_info(folder)
            n_usable = 0
            for f in files:
                rel = str(f.relative_to(config.ROOT))
                seen_files.add(rel)
                st = f.stat()
                row = db.one("SELECT id,mtime,size_bytes FROM assets WHERE file=?", rel)
                if row and not force and abs(row["mtime"] - st.st_mtime) < 1 and row["size_bytes"] == st.st_size:
                    n_usable += 1 if db.one("SELECT usable FROM assets WHERE id=?", row["id"])["usable"] else 0
                    continue
                name = clean_name(f.stem)
                usable, reason, meta = 1, "", None
                try:
                    if st.st_size > config.ASSET_MAX_BYTES:
                        raise ValueError(f"file too big ({st.st_size // 1_000_000} MB)")
                    meta = inspect(f)
                    nat = max(meta["size"]) or 1.0
                    if meta["bad_ext"]:
                        usable, reason = 0, f"needs unsupported compression {meta['bad_ext']}"
                    elif meta["tris"] > config.ASSET_MAX_TRIS:
                        usable, reason = 0, f"too heavy ({meta['tris']} triangles)"
                    elif nat > 300:
                        usable, reason = 0, "terrain-sized (too large to place as an object)"
                except Exception as e:
                    usable, reason = 0, f"unreadable: {str(e)[:80]}"
                    meta = {"lo": [0, 0, 0], "hi": [1, 1, 1], "size": [1, 1, 1], "tris": 0, "anims": [], "extras": {}, "copyright": ""}
                nat = max(meta["size"]) or 1.0
                cat, ctags = category(name, pack)
                tags = list(dict.fromkeys(ctags + tags_for(name, pack)))
                fit = config.kit_scale(pack, name)               # STYLE.md: 1 unit = 1 m; only a per-kit/per-name correction, never a recolor
                sx, sy, sz = meta["size"]
                radius = max(0.4, max(sx, sz) * fit / 2)
                lo, hi = meta["lo"], meta["hi"]
                ox, oy, oz = -(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2       # model units: puts the middle of the footprint on the spot, feet on the ground
                fw, fd = round(sx * fit, 3), round(sz * fit, 3)
                dxx, dzz = door_guess(cat, tags, fw, fd)
                credit = (meta.get("copyright") or "")[:200] or (json.dumps(meta["extras"])[:200] if meta["extras"] else "")
                vals = (pack, name, rel, json.dumps(tags), sx, sy, sz, meta["tris"], json.dumps(meta["anims"]), usable, reason, fit, radius,
                        st.st_mtime, st.st_size, credit, ox, oy, oz, fw, fd, dxx, dzz, cat)
                if row:
                    db.x("UPDATE assets SET pack=?,name=?,file=?,tags=?,sx=?,sy=?,sz=?,tris=?,anims=?,usable=?,reason=?,fit=?,radius=?,mtime=?,size_bytes=?,credit=?,ox=?,oy=?,oz=?,fw=?,fd=?,door_x=?,door_z=?,cat=? WHERE id=?", *vals, row["id"])
                    updated += 1
                else:
                    db.x("INSERT INTO assets(pack,name,file,tags,sx,sy,sz,tris,anims,usable,reason,fit,radius,mtime,size_bytes,credit,ox,oy,oz,fw,fd,door_x,door_z,cat) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", *vals)
                    added += 1
                if usable:
                    n_usable += 1
                else:
                    skipped.append(f"{pack}/{name}: {reason}")
            db.x("INSERT INTO asset_packs(pack,path,n,usable,license,credit,source,attribution_required,notes) VALUES(?,?,?,?,?,?,?,?,?) "
                 "ON CONFLICT(pack) DO UPDATE SET path=excluded.path,n=excluded.n,usable=excluded.usable,license=excluded.license,credit=excluded.credit,"
                 "source=excluded.source,attribution_required=excluded.attribution_required,notes=excluded.notes",
                 pack, str(folder.relative_to(config.ROOT)), len(files), n_usable, pi["license"], pi["credit"], pi["source"], pi["attribution_required"], pi["notes"])
    removed = 0
    for r in db.q("SELECT id,file FROM assets"):
        if r["file"] not in seen_files:
            db.x("DELETE FROM assets WHERE id=?", r["id"]); removed += 1
    db.x("DELETE FROM asset_packs WHERE pack NOT IN (SELECT DISTINCT pack FROM assets)") if db.one("SELECT COUNT(*) n FROM assets")["n"] else None
    _unique_names(db)
    db.put("asset_index_v", INDEX_VERSION)
    total = db.one("SELECT COUNT(*) n, SUM(usable) u FROM assets")
    return {"added": added, "updated": updated, "removed": removed, "total": total["n"], "usable": total["u"] or 0, "skipped": skipped, "seconds": round(time.time() - t0, 2)}


def _unique_names(db):
    """Variants with the same cleaned name get '(2)', '(3)' so a name always means one model."""
    rows = db.q("SELECT id,name,pack FROM assets ORDER BY pack,name,id")
    seen = {}
    for r in rows:
        base = re.sub(r" \(\d+\)$", "", r["name"])
        k = (r["pack"], base.lower())
        seen[k] = seen.get(k, 0) + 1
        want = base if seen[k] == 1 else f"{base} ({seen[k]})"
        if want != r["name"]:
            db.x("UPDATE assets SET name=? WHERE id=?", want, r["id"])


# ----- search ----------------------------------------------------------------------------------------------
def _query_tokens(q):
    toks = [_stem(w) for w in _words(q)]
    out = []
    for w in toks:
        out.append(w)
        if w in SYN:
            out.append(SYN[w])
    return list(dict.fromkeys(out))


def score(row, tokens):
    name_toks = [_stem(w) for w in _words(row["name"])]
    tags = set(json.loads(row["tags"]))
    s = 0
    for t in tokens:
        if t in name_toks:
            s += 5
        elif any(t in n or n in t for n in name_toks if len(n) > 3 and len(t) > 3):
            s += 3
        if t in tags:
            s += 2
        if t in _words(row["pack"]):
            s += 1
    if row["name"].lower() == " ".join(tokens[:len(name_toks)]):
        s += 6
    return s


def search(db, query, limit=8, usable_only=True):
    toks = _query_tokens(query)
    rows = db.q("SELECT * FROM assets" + (" WHERE usable=1" if usable_only else ""))
    if not toks:
        rows = [r for r in rows if r["name"] and "(" not in r["name"]]
        import random
        random.shuffle(rows)
        return rows[:limit]
    scored = [(score(r, toks), r) for r in rows]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [dict(r, _score=s) for s, r in scored[:limit]]


def find(db, ref):
    """Resolve an id (#12 / 12) or a name to a usable asset row."""
    ref = str(ref or "").strip().lstrip("#")
    if not ref:
        return None
    if ref.isdigit():
        return db.one("SELECT * FROM assets WHERE id=? AND usable=1", int(ref))
    r = db.one("SELECT * FROM assets WHERE lower(name)=lower(?) AND usable=1", ref)
    if r:
        return r
    best = search(db, ref, 1)
    return best[0] if best and best[0]["_score"] >= 5 else None


GENERIC = {"small", "tiny", "little", "big", "large", "huge", "mini", "miniature", "shiny", "new", "old", "simple", "fancy", "cozy", "pretty", "a", "an",
           "the", "my", "first", "second", "third", "another", "special", "magic", "magical", "red", "blue", "green", "yellow", "golden", "wooden", "grey", "white", "black",
           "pink", "purple", "orange", "teal", "brown", "silver", "gold", "dark", "bright", "round", "square", "flat", "half", "tall", "short", "long", "high", "low"}


def best_match(db, name, description="", threshold=6):
    """Match on the CONTENT words of a name. Adjectives like 'small' or 'red' must never create a match on their own."""
    exact = db.one("SELECT * FROM assets WHERE usable=1 AND lower(name)=lower(?)", re.sub(r"\s+", " ", str(name)).strip())
    if exact:
        return exact, 99
    words = [_stem(w) for w in _words(name) if w not in GENERIC and not w.isdigit()]
    if not words:
        return None, 0
    toks = list(dict.fromkeys(t for w in words for t in ([w] + ([SYN[w]] if w in SYN else []))))
    head = words[-1]                                       # "Pine Tree" -> tree, "Garden Rock" -> rock
    best, bs = None, 0
    for r in db.q("SELECT * FROM assets WHERE usable=1"):
        have = set(_stem(w) for w in _words(r["name"])) | set(json.loads(r["tags"]))
        if head not in have and SYN.get(head) not in have:  # the thing it IS must match; modifiers are optional
            continue
        s = score(r, toks)
        if s > bs or (s == bs and best and len(r["name"]) < len(best["name"])):
            best, bs = r, s
    return (best, bs) if best and bs >= threshold else (None, bs)


def describe(r):
    nat = max(r["sx"], r["sy"], r["sz"]) or 1
    h = r["sy"] * r["fit"]
    return f"#{r['id']} {r['name']} [{r['pack']}; {', '.join(json.loads(r['tags'])[:5])}] ~{h:.1f} tall, {max(r['sx'], r['sz']) * r['fit']:.1f} wide" + \
           (", has animation" if json.loads(r["anims"] or "[]") else "")
