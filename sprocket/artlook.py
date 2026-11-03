"""Helps Otto's drawings look like something. He is never given a lesson: the engine just lets him SEE what he drew (rendered to a picture, shown to his own vision model),
 lets him redraw it when it does not read, starts him from a rough sketch of what is in front of him, and keeps only pieces that pass a quality check.
Everything here works on already-sanitised art; the renderer is a pure-Rust SVG rasteriser that runs no scripts and fetches nothing."""
import json
import math
import re

from . import artcheck, config, world

try:
    import resvg_py
except ImportError:                                        # without it art still works, it just is not reviewed
    resvg_py = None


def available():
    return resvg_py is not None


def pixel_svg(content):
    d = artcheck.parse_pixels(content)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{d["palette"][c]}"/>'
                    for y, row in enumerate(d["rows"]) for x, c in enumerate(row) if c in d["palette"])
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {d["w"]} {d["h"]}" shape-rendering="crispEdges">{rects}</svg>'


def svg_of(kind, mode, content):
    """-> a safe SVG string for a piece, or None when it cannot be drawn without running code (canvas JS)."""
    if kind == "pixel":
        return pixel_svg(content)
    return content if mode == "svg" else None


def render(svg, size=320):
    """-> PNG bytes or None."""
    if not resvg_py or not svg:
        return None
    try:
        return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size, background="#ffffff"))
    except Exception:
        return None


def plain_check(svg):
    """Cheap test before spending model calls: -> reason string if it is just a few plain shapes, else ''."""
    els = re.findall(r"<(rect|circle|ellipse|line|polyline|polygon|path|text)\b", svg)
    cols = set(re.findall(r'(?:fill|stroke)="(#?\w+)"', svg)) - {"none"}
    if len(els) < 1:
        return "there is nothing drawn in it yet"
    return ""


# ------------------------------------------------------------------ seeing and redrawing
async def critique(agent, title, statement, png):
    """He looks at his own picture. Two steps so the rating is not swayed by what he hoped to see: first he describes it without knowing the title, then compares.
    -> {'sees': str, 'match': 0-10, 'fix': str} or None when the model could not answer."""
    try:
        r = await agent._chat([{"role": "user", "content": "Here is a small flat picture. In one short sentence say what it shows: name the main subject and what is around it. Plain words, no art talk.",
                                "images": [png]}], think=False)
        sees = _clean(r.message.content, 160)
        if not sees:
            return None
        cmp_prompt = (f"A robot artist meant to draw: \"{title}\"" + (f" ({statement})" if statement else "") + f".\nA stranger who looked at the drawing said it shows: \"{sees}\".\n"
                      "Reply with ONLY JSON: match (0-10: 9-10 the stranger named the intended subject, 6-8 close or the right things are there, 3-5 only some of it, 0-2 not at all), "
                      "fix (one concrete change that would make the drawing read better as the intended thing).")
        d = _json((await agent._chat([{"role": "user", "content": cmp_prompt}], think=False)).message.content)
        return {"sees": sees, "match": max(0, min(10, int(float(d.get("match") or 0)))), "fix": _clean(d.get("fix"), 160)}
    except Exception as e:
        agent.log(f"  art review failed: {type(e).__name__}")
        return None


async def redraw(agent, title, statement, svg, cr, png):
    """He looks again at what he drew and tries once more. -> new (checked) SVG string or None."""
    prompt = (f"You are {config_name()}, a small robot artist. You drew \"{title}\"" + (f" ({statement})" if statement else "") + ". The attached picture is how it came out. "
              f"Looking at it you saw: {cr['sees']}. What would help: {cr['fix']}.\nYour current SVG:\n{svg[:3500]}\n"
              "Draw it again, better: one clear subject big in the middle with a recognisable outline, a background, 6-16 simple flat-coloured shapes, "
              "viewBox 0 0 100 100. Reply with ONLY the new <svg>...</svg>.")
    try:
        r = await agent._chat([{"role": "user", "content": prompt, "images": [png]}], think=False)
        m = re.search(r"<svg\b.*</svg>", r.message.content, re.S | re.I)
        if not m:
            return None
        mode, content, _ = artcheck.check_art("drawing", m.group(0))
        return content if mode == "svg" else None
    except Exception:
        return None


def config_name():
    return config.NAME


def _clean(v, n):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else {}


# ------------------------------------------------------------------ a rough view of what is in front of him
_ICONS = (
    (("tree", "pine", "bush", "shrub", "palm"), lambda x, b, h, c: f'<rect x="{x - b * .08:.1f}" y="{62 - h * .4:.1f}" width="{b * .16:.1f}" height="{h * .4:.1f}" fill="#7a5230"/>'
                                                  f'<circle cx="{x:.1f}" cy="{62 - h * .55:.1f}" r="{b * .45:.1f}" fill="#4f8f3f"/>'),
    (("house", "cabin", "shop", "store", "bank", "casino", "building", "hall", "tower", "school", "cafe", "inn", "barn", "garage"),
     lambda x, b, h, c: f'<rect x="{x - b / 2:.1f}" y="{62 - h:.1f}" width="{b:.1f}" height="{h:.1f}" fill="{c}"/>'
                        f'<polygon points="{x - b / 2 - 1:.1f},{62 - h:.1f} {x:.1f},{62 - h - b * .35:.1f} {x + b / 2 + 1:.1f},{62 - h:.1f}" fill="#8a3b34"/>'),
    (("hill",), lambda x, b, h, c: f'<ellipse cx="{x:.1f}" cy="64" rx="{b * .9:.1f}" ry="{h * .5:.1f}" fill="#5b9648"/>'),
    (("lake", "pond", "water", "river", "fountain"), lambda x, b, h, c: f'<ellipse cx="{x:.1f}" cy="68" rx="{b * .7:.1f}" ry="4" fill="#4b8fd0"/>'),
)


def view_sketch(agent):
    """A rough flat SVG of the nearest things as seen looking north (sky, ground, simple icons by kind). Only a starting point for him to improve."""
    from . import affordances as aff, maps
    s = agent.state
    items = []
    if config.MAPS_ENABLED and maps.ACTIVE.get("doc"):
        for o in aff.objects():
            if o["name"] in ("Road", "Street light") or o.get("panel"):
                continue
            d = world.dist(s["x"], s["z"], o["x"], o["z"])
            if d <= 45:
                items.append((d, o["x"] - s["x"], o["name"].lower(), o.get("fw") or 3.0, o.get("color") or "#c9b79c"))
    else:
        for o in agent.objects():
            d = world.dist(s["x"], s["z"], o["x"], o["z"])
            if d <= 45 and o["kind"] not in ("ground", "find"):
                items.append((d, o["x"] - s["x"], o["name"].lower(), 3.0, o["color"] or "#c9b79c"))
    for pl in getattr(world, "PLACES", {}).values():                                   # lakes, hills and so on from the terrain
        d = world.dist(s["x"], s["z"], pl["x"], pl["z"])
        if d <= 70 and any(k in str(pl.get("label", "")).lower() for k in ("lake", "pond", "hill", "tree", "forest")):
            items.append((d, pl["x"] - s["x"], str(pl["label"]).lower(), 8.0 if "lake" in str(pl["label"]).lower() else 6.0, "#6fa35a"))
    items.sort(key=lambda t: -t[0])                                                  # far ones first so near ones draw on top
    parts = ['<rect width="100" height="62" fill="#9ec9ee"/>', '<rect y="62" width="100" height="38" fill="#6fa35a"/>']
    for d, dx, name, w, col in items[:9]:
        k = max(.35, min(1.6, 14 / max(d, 6)))                                       # nearer = bigger
        x = max(8, min(92, 50 + dx * 1.4))
        base, h = min(30, w * 3 * k), min(34, w * 2.4 * k)
        for keys, draw in _ICONS:
            if any(t in name for t in keys):
                parts.append(draw(x, base, h, col if col.startswith("#") else "#c9b79c"))
                break
        else:
            parts.append(f'<rect x="{x - base / 3:.1f}" y="{62 - h * .8:.1f}" width="{base * .66:.1f}" height="{h * .8:.1f}" fill="{col if col.startswith("#") else "#c9b79c"}"/>')
    return '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">' + "".join(parts) + "</svg>"
