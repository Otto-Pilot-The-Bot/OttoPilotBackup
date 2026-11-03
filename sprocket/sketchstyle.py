"""Draws Otto's SVG drawings in a hand-made marker style: wobbly doubled outlines, scribbled fills with the colour sitting a little off the line, paper grain.
He still decides WHAT to draw and writes the shapes; this only decides how they look, so every piece comes from the same hand.
Input is already-sanitised SVG (artcheck.sanitize_svg): rect, circle, ellipse, line, polyline, polygon, path, groups, simple gradients. Pillow only."""
import base64
import io
import math
import random
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import world

PAPER = (244, 239, 227)
W = 1024                                                                     # painted at 1024, saved smaller


# ------------------------------------------------------------------ colours
def _hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def parse_color(v, grads):
    """-> (r, g, b) or None for 'none'."""
    if v is None:
        return None
    v = v.strip().lower()
    if v in ("none", "transparent"):
        return None
    m = re.fullmatch(r"url\(#([\w\-]+)\)", v)
    if m:
        return grads.get(m.group(1), (128, 128, 128))
    m = re.fullmatch(r"rgb\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\)", v)
    if m:
        return tuple(min(255, int(x)) for x in m.groups())
    if re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", v):
        return _hex_rgb(v)
    h = world.to_hex(v)
    return _hex_rgb(h) if h else (0, 0, 0)


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _dark(c, k=0.42):
    return tuple(int(x * k) for x in c)


# ------------------------------------------------------------------ geometry
def _num(s, d=0.0):
    try:
        return float(re.sub(r"[a-z%]+$", "", str(s).strip()))
    except (TypeError, ValueError):
        return d


def _ellipse(cx, cy, rx, ry, n=56):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _bez(p0, p1, p2, p3, n=14):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]) for t in [i / n for i in range(1, n + 1)]]


def _quad(p0, p1, p2, n=12):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(1, n + 1)]]


def parse_path(d):
    """-> list of (points, closed). Arcs are drawn as straight lines to their end point."""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d or "")
    out, cur, start, i, cmd = [], [], (0.0, 0.0), 0, None
    p, last_c, last_q = (0.0, 0.0), None, None
    nums = lambda k: [float(toks[i + j]) for j in range(k)]
    argc = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
    while i < len(toks):
        if re.fullmatch(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                if cur:
                    out.append((cur, True)); cur = []
                p = start
                continue
        if cmd is None:
            break
        k = argc[cmd.upper()]
        if i + k > len(toks):
            break
        a = nums(k); i += k
        rel = cmd.islower(); c = cmd.upper()
        ox, oy = p if rel else (0.0, 0.0)
        if c == "M":
            if cur:
                out.append((cur, False))
            p = (a[0] + ox, a[1] + oy); start = p; cur = [p]; cmd = "l" if rel else "L"
        elif c == "L":
            p = (a[0] + ox, a[1] + oy); cur.append(p)
        elif c == "H":
            p = (a[0] + (p[0] if rel else 0), p[1]); cur.append(p)
        elif c == "V":
            p = (p[0], a[0] + (p[1] if rel else 0)); cur.append(p)
        elif c == "C":
            c1, c2, e = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy), (a[4] + ox, a[5] + oy)
            cur += _bez(p, c1, c2, e); p = e; last_c = c2
        elif c == "S":
            c1 = (2 * p[0] - last_c[0], 2 * p[1] - last_c[1]) if last_c else p
            c2, e = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            cur += _bez(p, c1, c2, e); p = e; last_c = c2
        elif c == "Q":
            c1, e = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            cur += _quad(p, c1, e); p = e; last_q = c1
        elif c == "T":
            c1 = (2 * p[0] - last_q[0], 2 * p[1] - last_q[1]) if last_q else p
            e = (a[0] + ox, a[1] + oy); cur += _quad(p, c1, e); p = e; last_q = c1
        elif c == "A":
            p = (a[5] + ox, a[6] + oy); cur.append(p)
        if c not in "CS":
            last_c = None
        if c not in "QT":
            last_q = None
    if cur:
        out.append((cur, False))
    return out


def _transform(attr):
    """-> 2x3 affine (a, b, c, d, e, f) for translate/scale/rotate/matrix; identity if none."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", attr or ""):
        v = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", args)]
        if name == "translate" and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale" and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate" and v:
            a = math.radians(v[0]); c, s = math.cos(a), math.sin(a); cx, cy = (v[1], v[2]) if len(v) >= 3 else (0, 0)
            t = (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)
        elif name == "matrix" and len(v) == 6:
            t = tuple(v)
        else:
            continue
        m = (m[0] * t[0] + m[2] * t[1], m[1] * t[0] + m[3] * t[1], m[0] * t[2] + m[2] * t[3], m[1] * t[2] + m[3] * t[3],
             m[0] * t[4] + m[2] * t[5] + m[4], m[1] * t[4] + m[3] * t[5] + m[5])
    return m


def _apply(m, pts):
    return [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x, y in pts]


def _compose(m1, m2):
    return (m1[0] * m2[0] + m1[2] * m2[1], m1[1] * m2[0] + m1[3] * m2[1], m1[0] * m2[2] + m1[2] * m2[3], m1[1] * m2[2] + m1[3] * m2[3],
            m1[0] * m2[4] + m1[2] * m2[5] + m1[4], m1[1] * m2[4] + m1[3] * m2[5] + m1[5])


def _walk(node, style, mtx, grads, out):
    tag = node.tag.split("}")[-1].lower()
    st = dict(style)
    for k in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity"):
        if node.get(k) is not None:
            st[k] = node.get(k)
    m = _compose(mtx, _transform(node.get("transform")))
    g = lambda k, d=0.0: _num(node.get(k), d)
    shape = None
    if tag == "rect":
        x, y, w, h = g("x"), g("y"), g("width"), g("height"); shape = [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
    elif tag == "circle":
        shape = [(_ellipse(g("cx"), g("cy"), g("r"), g("r")), True)]
    elif tag == "ellipse":
        shape = [(_ellipse(g("cx"), g("cy"), g("rx"), g("ry")), True)]
    elif tag == "line":
        shape = [([(g("x1"), g("y1")), (g("x2"), g("y2"))], False)]
    elif tag in ("polyline", "polygon"):
        v = [float(x) for x in re.findall(r"-?\d*\.?\d+", node.get("points", ""))]
        pts = list(zip(v[0::2], v[1::2]))
        shape = [(pts, tag == "polygon")] if len(pts) >= 2 else None
    elif tag == "path":
        shape = parse_path(node.get("d", ""))
    if shape:
        for pts, closed in shape:
            if len(pts) >= 2:
                out.append({"pts": _apply(m, pts), "closed": closed, "st": st, "tag": tag, "scale": math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0})
    for ch in node:
        if ch.tag.split("}")[-1].lower() in ("g", "svg"):
            _walk(ch, st, m, grads, out)
        else:
            _walk(ch, st, m, grads, out)


def _gradients(root):
    grads = {}
    for n in root.iter():
        if n.tag.split("}")[-1].lower() in ("lineargradient", "radialgradient") and n.get("id"):
            stops = [s for s in n if s.tag.split("}")[-1].lower() == "stop"]
            if stops:
                cs = [parse_color(s.get("stop-color", "#888"), {}) or (128, 128, 128) for s in stops]
                grads[n.get("id")] = tuple(sum(c[i] for c in cs) // len(cs) for i in range(3))
    return grads


# ------------------------------------------------------------------ the hand
class Hand:
    def __init__(self, seed):
        self.r = random.Random(seed)

    def wobble(self, pts, closed, amp, step):
        """Subdivide a polyline and push the points around smoothly, the way a pen drifts."""
        if closed and pts[0] != pts[-1]:
            pts = pts + [pts[0]]
        dense = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
            dense += [(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n) for t in range(1, n + 1)]
        f1, f2, p1, p2, q1, q2 = self.r.uniform(.02, .05), self.r.uniform(.07, .13), self.r.uniform(0, 6.3), self.r.uniform(0, 6.3), self.r.uniform(0, 6.3), self.r.uniform(0, 6.3)
        out = []
        for i, (x, y) in enumerate(dense):
            out.append((x + amp * (math.sin(i * f1 * 6 + p1) * .7 + math.sin(i * f2 * 6 + p2) * .3), y + amp * (math.cos(i * f1 * 6 + q1) * .7 + math.sin(i * f2 * 6 + q2) * .3)))
        return out


def _bbox(pts, pad, size):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad)), min(size, int(max(xs) + pad) + 1), min(size, int(max(ys) + pad) + 1))


def render(svg_text, size=512, seed=1):
    """-> a PIL RGB image (size x size) of the drawing in marker style. Raises on bad input."""
    root = ET.fromstring(svg_text)
    vb = [float(x) for x in re.findall(r"-?\d*\.?\d+", root.get("viewBox") or "0 0 100 100")][:4]
    vx, vy, vw, vh = vb if len(vb) == 4 and vb[2] > 0 and vb[3] > 0 else (0, 0, 100, 100)
    S = W / max(vw, vh)
    ox, H = (W - vw * S) / 2, (W - vh * S) / 2                                    # centre the drawing on the paper
    grads = _gradients(root)
    items = []
    _walk(root, {"fill": "black", "stroke": "none", "stroke-width": "1"}, (1, 0, 0, 1, 0, 0), grads, items)
    hand = Hand(seed); rng = hand.r
    paper = Image.new("RGB", (W, W), PAPER)
    canvas = paper.convert("RGBA")
    for it in items[:400]:
        pts = [((x - vx) * S + ox, (y - vy) * S + H) for x, y in it["pts"]]
        st = it["st"]
        fill = parse_color(st.get("fill"), grads) if it["closed"] or it["tag"] in ("path", "polyline") else None
        stroke = parse_color(st.get("stroke"), grads)
        op = max(0.0, min(1.0, _num(st.get("opacity"), 1.0) * _num(st.get("fill-opacity"), 1.0)))
        sw = max(2.0, _num(st.get("stroke-width"), 1.0) * S * it["scale"] * 0.9)
        x0, y0, x1, y1 = _bbox(pts, 20, W)
        area_big = (x1 - x0) > W * 0.88 and (y1 - y0) > W * 0.88
        # --- fill: a colour wash sitting a little off the outline, then scribbled hatching clipped to the shape
        if fill is not None and it["closed"] and len(pts) >= 3 and x1 > x0 and y1 > y0:
            shift = (rng.uniform(-1, 1) * W * 0.012, rng.uniform(-1, 1) * W * 0.012)
            wash = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
            mask = Image.new("L", wash.size, 0)
            ImageDraw.Draw(mask).polygon([(x - x0 + shift[0], y - y0 + shift[1]) for x, y in pts], fill=255)
            tint = _mix(fill, PAPER, 0.0 if not area_big else 0.5)
            wash.paste(Image.new("RGBA", wash.size, tint + (int(225 * op),)), (0, 0), mask)
            hl = Image.new("RGBA", wash.size, (0, 0, 0, 0)); hd = ImageDraw.Draw(hl)
            hatch_c = _mix(fill, (0, 0, 0), 0.30)
            ang = math.radians(rng.choice([35, 50, 125, 140]) + rng.uniform(-6, 6)); gap = W * (0.010 if not area_big else 0.026)
            diag = math.hypot(*wash.size); cx, cy = wash.size[0] / 2, wash.size[1] / 2
            k = -diag
            while k < diag:
                dx, dy = math.cos(ang), math.sin(ang); nx, ny = -dy, dx
                sx, sy = cx + nx * k - dx * diag, cy + ny * k - dy * diag
                t = 0.0
                while t < 2 * diag:                                              # a stroke is several short wobbling pieces, like a real marker
                    seg = rng.uniform(diag * 0.2, diag * 0.5)
                    a = (sx + dx * t + nx * rng.uniform(-2, 2), sy + dy * t + ny * rng.uniform(-2, 2)); b = (sx + dx * (t + seg) + nx * rng.uniform(-4, 4), sy + dy * (t + seg) + ny * rng.uniform(-4, 4))
                    mid = ((a[0] + b[0]) / 2 + nx * rng.uniform(-5, 5), (a[1] + b[1]) / 2 + ny * rng.uniform(-5, 5))      # the stroke bows a little, like a hand-pushed marker
                    hd.line([a, mid, b], fill=hatch_c + (int(rng.uniform(110, 190) * op),), width=int(max(3, W * 0.0048)), joint="curve")
                    t += seg + rng.uniform(0, diag * 0.08)
                k += gap * rng.uniform(0.8, 1.3)
            wash.alpha_composite(Image.composite(hl, Image.new("RGBA", wash.size, (0, 0, 0, 0)), mask.filter(ImageFilter.GaussianBlur(1))))
            canvas.alpha_composite(wash, (x0, y0))
        # --- outline: drawn twice, each time a little differently, in a dark version of the colour
        line_c = stroke if stroke is not None else (_dark(fill) if fill is not None else None)
        if line_c is not None and not area_big:
            lay = Image.new("RGBA", (W, W), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
            for rep in range(2):
                wp = hand.wobble(pts, it["closed"], amp=W * (0.004 + 0.003 * rep), step=W * 0.012)
                d.line(wp, fill=line_c + (int((240 if rep == 0 else 150) * (0.6 + 0.4 * op)),), width=int(max(3, sw * (1.35 if rep == 0 else 0.8))), joint="curve")
            canvas.alpha_composite(lay)
    # --- paper grain over everything, and a touch of softness so it does not look machine-sharp
    noise = Image.effect_noise((W, W), 40).convert("RGB")
    out = Image.blend(canvas.convert("RGB"), ImageChops.multiply(canvas.convert("RGB"), ImageOps.autocontrast(noise)), 0.10)
    return out.filter(ImageFilter.GaussianBlur(0.9)).resize((size, size), Image.LANCZOS)


def to_data_url(img, quality=84):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
