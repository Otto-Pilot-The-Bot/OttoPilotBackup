"""Validates and normalises what he designs: up to 12 parts, each an asset from the library OR a primitive shape.
Pure data in, pure data out: nothing here executes anything, and every number is clamped."""
import ast
import json
import math

from . import assets, world

SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "plane")
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


def clean_design(db, parts=None, asset=None, scale=None, rotation=None, color=None, anim=None):
    """Returns {"parts":[...], "anim":..., "height":..., "radius":..., "summary":"..."} or raises DesignError (message is for the model)."""
    raw = parse_parts(parts)
    if asset and not raw:
        raw = [{"asset": asset}]
    elif asset and raw:
        raw = [{"asset": asset}] + raw
    if not raw:
        raise DesignError("give an asset (see search_assets) or parts")
    if len(raw) > MAX_PARTS:
        raise DesignError(f"at most {MAX_PARTS} parts (you gave {len(raw)})")
    out, tris, extent, top, names = [], 0, 0.0, 0.0, []
    g_scale = _num(scale, 1.0, 0.3, 3.0)
    g_rot = _num(rotation, 0.0, -720, 720)
    g_tint = world.to_hex(color)
    for p in raw:
        if not isinstance(p, dict):
            raise DesignError("every part must be an object")
        pos = _vec(p.get("offset"), [0, 0, 0]) if p.get("offset") else [0, 0, 0]
        x, y, z = _num(p.get("x"), pos[0], -6, 6), _num(p.get("y"), pos[1], -1, 8), _num(p.get("z"), pos[2], -6, 6)
        rot = p.get("rot", p.get("rotation", p.get("r", 0)))
        rv = _vec(rot, [0, 0, 0]) if isinstance(rot, (list, tuple)) else [0, _num(rot, 0, -720, 720), 0]
        col = world.to_hex(p.get("c") or p.get("color"))
        a_ref = p.get("asset") or p.get("a")
        if a_ref:
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
                w, h, d = [_num(v, 1.0, 0.05, 4.0) for v in (list(size) + [size[-1]] * 3)[:3]]
            else:
                base = _num(size, 1.0, 0.05, 4.0)
                w, h, d = _num(p.get("w", p.get("sx")), base, 0.05, 4.0), _num(p.get("h", p.get("sy")), base, 0.05, 4.0), _num(p.get("d", p.get("sz")), base, 0.05, 4.0)
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
         "tint": g_tint, "height": round(top, 2), "radius": round(max(0.5, min(7.0, extent)), 2)}
    d["summary"] = ", ".join(dict.fromkeys(names))[:80]
    return d


def auto_design(db, name, description="", color=None):
    """When he does not specify a design, pick the best-matching asset for the NAME so the object looks like what it is called."""
    row, sc = assets.best_match(db, name)
    if not row:
        return None
    try:
        return clean_design(db, asset=row["id"], color=color)
    except DesignError:
        return None
