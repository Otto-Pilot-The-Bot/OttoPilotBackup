"""Validates and normalises what he designs: up to 12 parts, each an asset from the library OR a primitive shape.
Pure data in, pure data out: nothing here executes anything, and every number is clamped."""
import ast
import json
import math

from . import assets, kit, world

SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "plane", "prism", "pyramid")
MATS = ("matte", "shiny", "metal", "glow", "glass")
ANIMS = ("none", "spin", "bob", "sway", "blink")
MAX_PARTS, MAX_TRIS = 12, 24000


class DesignError(Exception):
    pass


def _num(v, d, lo, hi):
    try:
        x = float(v)
        return d if math.isnan(x) else max(lo, min(hi, x))
    except (TypeError, ValueError):
        return d


def _vec(v, d):
    if isinstance(v, (list, tuple)) and v:
        v = list(v) + [v[-1]] * (3 - len(v)) if len(v) < 3 else list(v)
        return [_num(v[0], d[0], -1e3, 1e3), _num(v[1], d[1], -1e3, 1e3), _num(v[2], d[2], -1e3, 1e3)]
    return list(d)


def parse_parts(raw):
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            try:
                raw = ast.literal_eval(raw)           # literal_eval only parses data
            except Exception:
                raise DesignError('parts must be a JSON list like [{"asset":"Tent","x":-1.5},{"s":"sphere","size":0.6,"c":"gold","y":1}]')
    if isinstance(raw, dict):
        raw = raw.get("parts") or [raw]
    if not isinstance(raw, list):
        raise DesignError("parts must be a list")
    return raw


def clean_design(db, parts=None, asset=None, scale=None, rotation=None, color=None, anim=None, gen=None, gparams=None, max_parts=MAX_PARTS):
    """Returns {"parts":[...], "anim":..., "height":..., "radius":..., "summary":"..."} or raises DesignError (message is for the model)."""
    raw = parse_parts(parts)
    big = max_parts > MAX_PARTS                                  # script designs may be larger and use bigger shapes
    pmax, cmax = (12.0, 12.0) if big else (4.0, 6.0)
    if gen:
        raw = [{"gen": gen, **(gparams if isinstance(gparams, dict) else {})}] + list(raw)
    if asset and not raw:
        raw = [{"asset": asset}]
    elif asset and raw:
        raw = [{"asset": asset}] + raw
    if not raw:
        raise DesignError("give an asset (see search_assets) or parts")
    if len(raw) > max_parts:
        raise DesignError(f"at most {max_parts} parts (you gave {len(raw)})")
    out, tris, extent, top, names = [], 0, 0.0, 0.0, []
    g_scale = _num(scale, 1.0, 0.3, 3.0)
    g_rot = _num(rotation, 0.0, -720, 720)
    g_tint = world.to_hex(color)
    for p in raw:
        if not isinstance(p, dict):
            raise DesignError("every part must be an object")
        pos = _vec(p.get("offset"), [0, 0, 0]) if p.get("offset") else [0, 0, 0]
        x, y, z = _num(p.get("x"), pos[0], -cmax, cmax), _num(p.get("y"), pos[1], -1, 12 if big else 8), _num(p.get("z"), pos[2], -cmax, cmax)
        rot = p.get("rot", p.get("rotation", p.get("r", 0)))
        rv = _vec(rot, [0, 0, 0]) if isinstance(rot, (list, tuple)) else [0, _num(rot, 0, -720, 720), 0]
        col = world.to_hex(p.get("c") or p.get("color"))
        a_ref = p.get("asset") or p.get("a")
        g_ref = p.get("gen") or p.get("g")
        if g_ref:                                                        # a generator from the builder kit
            try:
                kp = kit.clean(g_ref, p.get("params") or {k: v for k, v in p.items() if k not in ("gen", "g", "x", "y", "z", "rot", "rotation", "r", "scale", "anim", "params", "c", "color")})
            except kit.KitError as e:
                raise DesignError(str(e))
            sc = _num(p.get("scale"), 1.0, 0.4, 2.5)
            pp = kp["pp"]
            part = {"g": kp["g"], "pp": pp, "x": x, "y": y, "z": z, "s": round(sc, 3), "r": rv}
            hw, hh = max(pp["w_"], pp["d_"]) * sc / 2, pp["h_"] * sc
            names.append(kp["g"])
        elif p.get("gift") is not None or p.get("gf") is not None:               # a 3D model gift from the human
            gr = str(p.get("gift") if p.get("gift") is not None else p.get("gf")).strip().lstrip("#")
            row = db.one("SELECT * FROM gifts WHERE kind='model' AND (CAST(id AS TEXT)=? OR lower(name)=lower(?))", gr, gr)
            if not row:
                raise DesignError(f"no 3D model gift called '{gr}'")
            sc = _num(p.get("scale", p.get("s") if not isinstance(p.get("s"), str) else None), 1.0, 0.3, 3.0)
            hw = max(row["sx"], row["sz"]) * row["fit"] * sc / 2
            hh = row["sy"] * row["fit"] * sc
            tris += row["tris"]
            part = {"gf": row["id"], "n": row["name"], "f": round(row["fit"], 5), "x": x, "y": y, "z": z, "s": round(sc, 3), "r": rv, "c": col}
            names.append(row["name"])
        elif a_ref:
            row = assets.find(db, a_ref)
            if not row:
                hits = [h["name"] for h in assets.search(db, str(a_ref), 4)]
                raise DesignError(f"no asset called '{a_ref}'" + (f" (did you mean: {', '.join(hits)}?)" if hits else "; try search_assets"))
            s = _num(p.get("scale", p.get("s") if not isinstance(p.get("s"), str) else None), 1.0, 0.3, 3.0)
            tris += row["tris"]
            hw = max(row["sx"], row["sz"]) * row["fit"] * s / 2
            hh = row["sy"] * row["fit"] * s
            part = {"a": row["id"], "n": row["name"], "f": round(row["fit"], 5), "x": x, "y": y, "z": z, "s": round(s, 3), "r": rv, "c": col}
            names.append(row["name"])
        else:
            shape = str(p.get("s") if isinstance(p.get("s"), str) else p.get("shape") or p.get("p") or "box").lower()
            if shape not in SHAPES:
                raise DesignError(f"shape must be one of {', '.join(SHAPES)} (or give an asset)")
            size = p.get("size", p.get("dims"))
            if isinstance(size, (list, tuple)):
                w, h, d = [_num(v, 1.0, 0.05, pmax) for v in (list(size) + [size[-1]] * 3)[:3]]
            else:
                base = _num(size, 1.0, 0.05, pmax)
                w, h, d = _num(p.get("w", p.get("sx")), base, 0.05, pmax), _num(p.get("h", p.get("sy")), base, 0.05, pmax), _num(p.get("d", p.get("sz")), base, 0.05, pmax)
            mat = str(p.get("mat") or p.get("material") or p.get("m") or "matte").lower()
            part = {"p": shape, "x": x, "y": y, "z": z, "w": round(w, 3), "h": round(h, 3), "d": round(d, 3), "r": rv,
                    "c": col or "#b0bec5", "m": mat if mat in MATS else "matte"}
            hw, hh = max(w, d) / 2, h
            names.append(shape)
        pa = str(p.get("anim") or "").lower()
        if pa in ANIMS and pa != "none":
            part["anim"] = pa
        out.append(part)
        extent = max(extent, math.hypot(x, z) * g_scale + hw * g_scale)
        top = max(top, (y + hh) * g_scale)
    if tris > MAX_TRIS:
        raise DesignError(f"too many polygons ({tris}); use fewer or simpler assets")
    ga = str(anim or "").lower()
    d = {"parts": out, "anim": ga if ga in ANIMS and ga != "none" else None, "scale": round(g_scale, 3), "rot": round(g_rot, 1),
         "tint": g_tint, "height": round(top, 2), "radius": round(max(0.5, min(12.0 if big else 7.0, extent)), 2)}
    d["summary"] = ", ".join(dict.fromkeys(names))[:80]
    return d


def auto_design(db, name, description="", color=None):
    """When he does not specify a design, pick what best matches the NAME (a model, else a kit generator) so the object looks like what it is called."""
    row, sc = assets.best_match(db, name)
    if not row:
        g = kit.match_name(name)
        if g:
            try:
                return clean_design(db, gen=g, gparams={"wall": color} if color and g in ("house", "cottage", "tower", "shop", "workshop_building") else {})
            except DesignError:
                return None
        return None
    try:
        return clean_design(db, asset=row["id"], color=color)
    except DesignError:
        return None


def too_plain(d):
    """A build made only of a few plain boxes is just a block. Returns a hint for the model, or None if it has real detail."""
    prim = [p for p in d["parts"] if p.get("p")]
    if len(prim) != len(d["parts"]) or not prim:
        return None                                              # uses generators or models: already detailed
    shapes = {p["p"] for p in prim}
    if len(prim) < 4 or shapes <= {"box"}:
        return ("That is just a plain block. Give it real detail: a roof (prism or pyramid), windows, a door, trim, different shapes and colours "
                "(at least 4 parts, not only boxes), or use a kit generator like gen=\"cottage\".")
    return None
