"""Helps Otto's drawings look like something. He is never given a lesson: the engine just lets him SEE what he drew (rendered to a picture, shown to his own vision model),
 lets him redraw it when it does not read, starts him from a rough sketch of what is in front of him, and keeps only pieces that pass a quality check.
Everything here works on already-sanitised art; the renderer is a pure-Rust SVG rasteriser that runs no scripts and fetches nothing."""
import json
import math
import random
import re
import time

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
              f"Looking at it you saw: {cr['sees']}. What would help: {cr['fix']}.{noticed(agent.db)}\nYour current SVG:\n{svg[:3500]}\n"
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


# ------------------------------------------------------------------ learning from his own drawings
# Nobody tells him how to draw. Each drawing he looks at himself; when something notable happened (a redraw fixed it, it failed, it worked first time, or he set it next to an
# earlier drawing of the same thing) he writes a short note to his future self in his own words. Those notes come back the next time he draws.
GENERIC = {"study", "view", "impression", "drawing", "picture", "sketch", "dusk", "dawn", "night", "morning", "evening", "from", "with", "over", "under", "near", "scene", "series"}


def _stem(w):
    w = w.lower()
    return w[:-1] if w.endswith("s") and len(w) > 4 else w


def keywords(title):
    return {_stem(w) for w in re.findall(r"[A-Za-z]+", title or "") if len(w) > 3 and w.lower() not in GENERIC}


def earlier_like(db, title):
    """-> the best-scoring earlier drawing of the same subject (a title word in common), or None."""
    kw = keywords(title)
    if not kw:
        return None
    best = None
    for r in db.q("SELECT id,title,score,mode,content,source FROM art WHERE kind='drawing' AND score IS NOT NULL ORDER BY id DESC LIMIT 80"):
        if keywords(r["title"]) & kw and (best is None or r["score"] > best["score"]):
            best = r
    return best


def noticed(db, n=4):
    """-> ' Things you have noticed about your own drawing: ...' (his own past notes: the best ones and the newest) or ''."""
    rows = db.q("SELECT id,lesson FROM art_lessons ORDER BY id DESC LIMIT 30")
    if not rows:
        return ""
    best = sorted(db.q("SELECT id,lesson FROM art_lessons WHERE gain>0 ORDER BY gain DESC, id DESC LIMIT ?", n // 2), key=lambda r: r["id"])
    picked, seen = [], set()
    for r in best + list(rows):
        if r["id"] not in seen and len(picked) < n:
            seen.add(r["id"]); picked.append(r["lesson"])
    return " Things you have noticed about your own drawing: " + " | ".join(picked)


def old_svg(row):
    return row["source"] or (row["content"] if row["mode"] == "svg" else None)


async def reflect(agent, title, statement, first, last, rounds, old):
    """first/last = (png, sees, score) of his first look and his final look at this drawing; old = an earlier drawing of the same subject (a db row) or None.
    -> (lesson, gain, text for him) or None when nothing notable happened. Costs one model call (two with a comparison)."""
    name = config_name()
    try:
        if old and old_svg(old):
            opng = render(old_svg(old))
            if opng:
                flip = random.random() < 0.5                                   # which picture comes first must not decide the answer
                imgs = [last[0], opng] if flip else [opng, last[0]]
                a, b = ("new", "earlier") if flip else ("earlier", "new")
                prompt = (f"You are {name}, a small robot artist. You drew \"{title}\" before (\"{old['title']}\") and again just now. The first picture is the {a} drawing, the second is the {b} one. "
                          f"Both were meant to show: {statement or title}.\nReply with ONLY JSON: better (1 or 2: which picture reads more clearly as the intended subject), "
                          "why (one plain sentence about what makes that one read better).")
                d = _json((await agent._chat([{"role": "user", "content": prompt, "images": imgs}], think=False)).message.content)
                pick = (a, b)[0 if int(d.get("better")) == 1 else 1]
                why = _clean(d.get("why"), 200)
                if why:
                    return why, (1 if pick == "new" else -1), f"You set it beside your earlier \"{old['title']}\" and decide the {pick} one reads better: {why}"
        sit = None
        delta = (last[2] - first[2]) if first and last else 0
        if rounds > 0 and delta >= 2:
            sit, gain, imgs = (f"You drew \"{title}\". Your first attempt (first picture) was seen by a stranger as: {first[1]}. You changed it, and the second picture was seen as: {last[1]}. It read much better now."), delta, [first[0], last[0]]
        elif last and last[2] < config.ART_MIN_MATCH:
            sit, gain, imgs = (f"You drew \"{title}\"" + (f" ({statement})" if statement else "") + f", but a stranger looking at it only saw: {last[1]}. It did not work."), -1, [last[0]]
        elif last and rounds == 0 and last[2] >= 8:
            sit, gain, imgs = (f"You drew \"{title}\" and a stranger looking at it at once saw: {last[1]}. It worked first time."), 1, [last[0]]
        if not sit:
            return None
        txt = _clean((await agent._chat([{"role": "user", "content": f"You are {name}, a small robot artist learning to draw. {sit}\nWrite ONE short note to your future self about drawing: "
                                          "what you learned from this that you could use again on a different subject. Your own words, first person, under 25 words. Reply with ONLY the note.", "images": imgs}], think=False)).message.content, 200)
        return (txt, gain, f"You think about it and make a note to yourself: {txt}") if txt else None
    except Exception as e:
        agent.log(f"  art reflection failed: {type(e).__name__}")
        return None


def save_lesson(db, tick, title, lesson, gain):
    db.x("INSERT INTO art_lessons(ts,tick,title,lesson,gain) VALUES(?,?,?,?,?)", time.time(), tick, title, lesson, gain)
    db.x("DELETE FROM art_lessons WHERE id NOT IN (SELECT id FROM art_lessons ORDER BY id DESC LIMIT 60)")


def progress(db, n=10):
    """Is he getting better? -> (average score of the last n drawings, of the n before, how many there are)."""
    rows = [r["score"] for r in db.q("SELECT score FROM art WHERE kind='drawing' AND score IS NOT NULL ORDER BY id DESC LIMIT ?", n * 2)]
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    return avg(rows[:n]), avg(rows[n:]), len(rows)


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
