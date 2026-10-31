"""The builder kit catalog: safe, parameterised generators (the 3D geometry itself lives in web/kit/gens.js).
Style and palette are adapted from the read-only reference project in reference/city (soft palette, seasons, part layouts).
The model only ever picks a generator name and numbers/colours/choices; everything is validated and clamped here."""
import datetime
import re

from . import world


class KitError(Exception):
    pass


SEASONS = ("spring", "summer", "fall", "winter")


def season_now(today=None):
    """Same rule as the reference project (northern hemisphere, Denver-like latitude)."""
    m = (today or datetime.date.today()).month
    return "spring" if 3 <= m <= 5 else "summer" if 6 <= m <= 8 else "fall" if 9 <= m <= 11 else "winter"


def num(lo, hi, d): return ("num", lo, hi, d)
def ints(lo, hi, d): return ("int", lo, hi, d)
def choice(opts, d): return ("choice", opts, d)
def color(d): return ("color", d)
def flag(d): return ("bool", d)
def text(n, d): return ("text", n, d)


ROOFS = ["gable", "hip", "flat", "shed"]
TREES = ["leaf", "pine", "blossom", "aspen", "autumn", "bare"]
SPEC = {
    "house": dict(w=num(3.5, 7, 4.6), d=num(3, 6, 4.0), floors=ints(1, 3, 1), roof=choice(ROOFS, "gable"), wall=color("cream"),
                  roof_color=color("terracotta"), door_color=color("brown"), chimney=flag(True), porch=flag(False)),
    "cottage": dict(w=num(2.6, 4.2, 3.2), d=num(2.4, 3.6, 2.8), roof=choice(["gable", "hip"], "gable"), wall=color("ivory"),
                    roof_color=color("terracotta"), door_color=color("slate"), chimney=flag(True)),
    "tower": dict(w=num(2.5, 5, 3.2), floors=ints(3, 10, 5), roof=choice(["pyramid", "flat", "spire"], "pyramid"), wall=color("tan"), roof_color=color("slate"), glass=color("sky")),
    "shop": dict(w=num(3.5, 6.5, 4.6), d=num(3, 5, 3.6), floors=ints(1, 2, 1), wall=color("cream"), awning=color("terracotta"), sign=text(16, "SHOP"), roof=choice(["flat", "gable"], "flat")),
    "workshop_building": dict(w=num(5, 9, 6.5), d=num(4, 7, 5), roof=choice(["gable", "saw"], "gable"), wall=color("slate"), roof_color=color("charcoal"), door_color=color("terracotta"), chimney=flag(True)),
    "tree": dict(kind=choice(TREES, "leaf"), h=num(1.8, 5.5, 3.2), seed=ints(0, 999, 1)),
    "bush": dict(r=num(0.5, 1.4, 0.8), kind=choice(["leaf", "blossom", "pine", "autumn"], "leaf"), seed=ints(0, 999, 1)),
    "rock": dict(size=num(0.5, 2.2, 1.0), tone=color("stone"), seed=ints(0, 999, 1), stack=flag(False)),
    "fence": dict(length=num(2, 10, 5), style=choice(["picket", "rail", "stone"], "picket"), tone=color("ivory"), height=num(0.6, 1.4, 0.9)),
    "lamp": dict(h=num(2, 4, 3), style=choice(["post", "lantern"], "post"), tone=color("charcoal"), glow=color("gold")),
    "path": dict(length=num(2, 9, 6), width=num(0.8, 2.5, 1.4), material=choice(["stone", "dirt", "brick", "sand"], "stone"), curve=num(-1, 1, 0.3)),
    "pond": dict(r=num(1.2, 4, 2.2), lilies=flag(True), water=color("sky")),
    "flower_bed": dict(w=num(1.2, 5, 2.4), d=num(1, 3, 1.4), colors=("colors", ["rose", "gold", "plum"]), seed=ints(0, 999, 1)),
    "sign": dict(text=text(16, "WELCOME"), post=color("wood"), board=color("cream")),
    "car": dict(kind=choice(["car", "pickup", "van"], "car"), tone=color("terracotta")),
}
COMMON = dict(season=choice(["auto"] + list(SEASONS), "auto"))
ROOF_H = {"gable": 1.5, "hip": 1.5, "flat": 0.3, "shed": 1.0, "pyramid": 1.6, "spire": 2.8, "saw": 1.2}
KEYWORDS = {"cottage": "cottage", "cabin": "cottage", "hut": "cottage", "house": "house", "home": "house", "villa": "house", "tower": "tower", "skyscraper": "tower",
            "lighthouse": "tower", "shop": "shop", "store": "shop", "bakery": "shop", "cafe": "shop", "market": "shop", "workshop": "workshop_building",
            "garage": "workshop_building", "factory": "workshop_building", "tree": "tree", "oak": "tree", "pine": "tree", "bush": "bush", "hedge": "bush", "shrub": "bush",
            "rock": "rock", "boulder": "rock", "fence": "fence", "lamp": "lamp", "lantern": "lamp", "streetlight": "lamp", "path": "path", "road": "path", "walkway": "path",
            "pond": "pond", "lake": "pond", "flowerbed": "flower_bed", "flowers": "flower_bed", "garden": "flower_bed", "sign": "sign", "signpost": "sign", "noticeboard": "sign",
            "car": "car", "truck": "car", "van": "car", "pickup": "car"}


def _hex(v, d):
    return world.to_hex(v) or world.to_hex(d)


def _dims(gen, p):
    r = ROOF_H
    if gen == "house": return p["w"], p["d"], p["floors"] * 2.4 + r[p["roof"]] + (0.9 if p["chimney"] else 0)
    if gen == "cottage": return p["w"], p["d"], 2.3 + r[p["roof"]] + 0.5
    if gen == "tower": return p["w"], p["w"], p["floors"] * 2.0 + r[p["roof"]]
    if gen == "shop": return p["w"], p["d"], p["floors"] * 2.4 + 0.8 + (r[p["roof"]] if p["roof"] == "gable" else 0)
    if gen == "workshop_building": return p["w"], p["d"], 3.4 + r[p["roof"]] + 0.6
    if gen == "tree": return p["h"] * 0.6, p["h"] * 0.6, p["h"]
    if gen == "bush": return p["r"] * 2, p["r"] * 2, p["r"] * 1.4
    if gen == "rock": return p["size"] * 1.4, p["size"] * 1.2, p["size"] * (1.6 if p["stack"] else 0.9)
    if gen == "fence": return p["length"], 0.3, p["height"]
    if gen == "lamp": return 0.6, 0.6, p["h"]
    if gen == "path": return p["length"], p["width"] + 1.0, 0.05
    if gen == "pond": return p["r"] * 2.2, p["r"] * 2.2, 0.2
    if gen == "flower_bed": return p["w"], p["d"], 0.7
    if gen == "sign": return 1.5, 0.3, 1.9
    if gen == "car": return {"car": 2.6, "pickup": 3.0, "van": 2.8}[p["kind"]], 1.3, {"car": 1.1, "pickup": 1.2, "van": 1.6}[p["kind"]]
    return 2, 2, 2


def clean(gen, raw):
    """-> {"g": gen, "pp": resolved params incl. dims w_,d_,h_, season, hex colours}. Unknown names are ignored; bad values are clamped."""
    gen = str(gen or "").strip().lower().replace(" ", "_")
    if gen not in SPEC:
        raise KitError(f"unknown generator '{gen}'. Available: {', '.join(SPEC)}")
    raw = raw if isinstance(raw, dict) else {}
    p = {}
    for name, spec in {**SPEC[gen], **COMMON}.items():
        v, kind = raw.get(name), spec[0]
        if kind == "num":
            try: x = float(v)
            except (TypeError, ValueError): x = spec[3]
            p[name] = round(max(spec[1], min(spec[2], x)), 3)
        elif kind == "int":
            try: x = int(round(float(v)))
            except (TypeError, ValueError): x = spec[3]
            p[name] = max(spec[1], min(spec[2], x))
        elif kind == "choice":
            p[name] = str(v).lower() if str(v).lower() in spec[1] else spec[2]
        elif kind == "color":
            p[name] = _hex(v, spec[1])
        elif kind == "bool":
            p[name] = bool(v) if isinstance(v, bool) else (spec[1] if v is None else str(v).lower() in ("1", "true", "yes"))
        elif kind == "text":
            p[name] = re.sub(r"[^\w !?.,'-]", "", str(v if v is not None else spec[2]))[:spec[1]].upper() or spec[2]
        elif kind == "colors":
            vals = v if isinstance(v, (list, tuple)) else re.split(r"[,; ]+", str(v or ""))
            cols = [world.to_hex(c) for c in vals if world.to_hex(c)][:4] or [world.to_hex(c) for c in spec[1]]
            p[name] = cols
    if p["season"] == "auto":
        p["season"] = season_now()
    w, d, h = _dims(gen, p)
    p.update(w_=round(w, 2), d_=round(d, 2), h_=round(h, 2))
    return {"g": gen, "pp": p}


def match_name(name):
    """The generator whose job matches the head noun of a name ('Pine Cabin' -> cottage, 'Garden Lamp' -> lamp), else None."""
    words = [w for w in re.findall(r"[a-z]+", str(name).lower())]
    for w in reversed(words):
        w = w[:-1] if w.endswith("s") and len(w) > 3 and w[:-1] in KEYWORDS else w
        if w in KEYWORDS:
            return KEYWORDS[w]
    return None


def catalog_text():
    """Compact catalog for his prompt: one line per generator with the knobs that matter."""
    out = []
    for g, spec in SPEC.items():
        bits = []
        for n, s in spec.items():
            if s[0] in ("num", "int"): bits.append(f"{n} {s[1]}-{s[2]}")
            elif s[0] == "choice": bits.append(f"{n}=" + "|".join(s[1]))
            elif s[0] in ("color", "colors"): bits.append(n)
            elif s[0] == "bool": bits.append(n)
            elif s[0] == "text": bits.append(n + "(text)")
        out.append(f"{g}({', '.join(bits)})")
    return "; ".join(out) + ". All also take season=auto|spring|summer|fall|winter."
