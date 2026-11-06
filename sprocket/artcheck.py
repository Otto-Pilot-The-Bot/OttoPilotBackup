"""Validation / sanitising of artwork. Nothing here executes anything.

kinds:  drawing  -> SVG markup (rebuilt from an allow-list) or canvas JS (only ever run in a sandboxed browser worker)
        pixel    -> grid of letters + palette (parsed into JSON)
        sculpture-> list of primitive shapes (parsed into JSON)
"""
import ast
import json
import re
from html.parser import HTMLParser
from xml.sax.saxutils import escape, quoteattr

from . import config, world

KINDS = ("drawing", "pixel", "sculpture")
SHAPES = ("box", "sphere", "cone", "cylinder", "torus")


class ArtError(Exception):
    pass


# ---------------------------------------------------------------- SVG
_TAGS = {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "defs", "lineargradient",
         "radialgradient", "stop", "text", "tspan"}
_CASE = {"lineargradient": "linearGradient", "radialgradient": "radialGradient"}
_ATTRS = {"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "d", "points", "fill", "stroke",
          "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity",
          "fill-rule", "transform", "viewbox", "offset", "stop-color", "stop-opacity", "id", "gradientunits",
          "gradienttransform", "fx", "fy", "font-size", "text-anchor", "font-family", "preserveaspectratio", "dx", "dy"}
_ATTR_CASE = {"viewbox": "viewBox", "gradientunits": "gradientUnits", "gradienttransform": "gradientTransform",
              "preserveaspectratio": "preserveAspectRatio"}
_BAD_VAL = re.compile(r"javascript:|data:|https?:|//|expression\(|@import|<|>", re.I)


class _Svg(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.n, self.stack = [], 0, []

    def _open(self, tag, attrs, selfclose):
        self.n += 1
        if self.n > 400:
            raise ArtError("SVG too complex (max 400 elements)")
        if tag not in _TAGS:
            raise ArtError(f"SVG element <{tag}> is not allowed")
        a = []
        for k, v in attrs:
            if k not in _ATTRS or v is None:
                continue                      # silently drop on*, href, style, xmlns, etc.
            v = v.strip()
            if _BAD_VAL.search(v):
                continue
            if "url(" in v.lower() and not re.fullmatch(r"url\(#[\w\-]+\)", v):
                continue
            a.append(f"{_ATTR_CASE.get(k, k)}={quoteattr(v[:400])}")
        if tag == "svg":
            if not any(x.startswith("viewBox=") for x in a):
                a.append('viewBox="0 0 100 100"')
            a.append('xmlns="http://www.w3.org/2000/svg"')
        t = _CASE.get(tag, tag)
        self.out.append(f"<{t} {' '.join(a)}{'/' if selfclose else ''}>")
        if not selfclose:
            self.stack.append(t)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, True)

    def handle_endtag(self, tag):
        if self.stack:
            self.out.append(f"</{self.stack.pop()}>")

    def handle_data(self, data):
        if self.stack and self.stack[-1] in ("text", "tspan") and data.strip():
            self.out.append(escape(data[:200]))


def sanitize_svg(src):
    m = re.search(r"<svg\b.*</svg>", src, re.S | re.I)
    if not m:
        raise ArtError("SVG must start with <svg> and end with </svg>")
    p = _Svg()
    p.feed(m.group(0))
    p.close()
    while p.stack:
        p.out.append(f"</{p.stack.pop()}>")
    out = "".join(p.out)
    if not out.startswith("<svg"):
        raise ArtError("SVG root must be <svg>")
    return out


# ---------------------------------------------------------------- canvas JS (never run on the server)
_JS_FORBID = re.compile(
    r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts|import|require|eval|Function|constructor|prototype|__proto__|"
    r"globalThis|window|self|document|parent|top|frames|opener|location|navigator|localStorage|sessionStorage|indexedDB|"
    r"Worker|SharedWorker|ServiceWorker|postMessage|Atomics|SharedArrayBuffer|WebAssembly|Reflect|Proxy|setTimeout|"
    r"setInterval|requestAnimationFrame|close|process|Deno|Bun|globalThis|caches|crypto|Image|Blob|URL|FileReader)\b|\\u|\\x|`\s*\$\{[^}]*\bthis\b",
    re.I)


def check_js(src):
    if len(src) > 4000:
        raise ArtError("canvas code too long (max 4000 characters)")
    m = _JS_FORBID.search(src)
    if m:
        raise ArtError(f"'{m.group(0)}' is not available. You only get ctx (2D canvas 256x256), W, H, rand() and Math")
    if "ctx" not in src:
        raise ArtError("that is not drawing code. Draw with an <svg viewBox=\"0 0 100 100\">...</svg>, or canvas code that uses ctx")
    if src.count("{") != src.count("}") or src.count("(") != src.count(")"):
        raise ArtError("unbalanced brackets in the canvas code")
    return src


# ---------------------------------------------------------------- pixel art
def parse_pixels(src):
    palette, rows = {}, []
    for line in src.replace("\r", "").split("\n"):
        line = line.strip("\n")
        if not line.strip():
            continue
        if "=" in line:
            for k, v in re.findall(r"(\S)\s*=\s*(#?\w+)", line):
                hx = world.to_hex(v)
                if hx and k not in ".":
                    palette[k] = hx
        else:
            rows.append(line.strip())
    if not rows:
        raise ArtError("no pixel rows found")
    rows = rows[:32]
    w = min(32, max(len(r) for r in rows))
    rows = [r[:w].ljust(w, ".") for r in rows]
    used = {c for r in rows for c in r if c not in ". _-"}
    for c in used:
        if c not in palette:                      # unknown letters get a stable colour so the picture still works
            palette[c] = list(world.COLORS.values())[ord(c) % len(world.COLORS)]
    return {"w": w, "h": len(rows), "rows": rows, "palette": {c: palette[c] for c in used}}


# ---------------------------------------------------------------- sculpture
def parse_sculpture(src):
    try:
        data = json.loads(src)
    except Exception:
        try:
            data = ast.literal_eval(src)            # literal_eval only parses data, it cannot run code
        except Exception:
            raise ArtError('sculpture content must be a JSON list like [{"s":"box","x":0,"y":0.5,"z":0,"size":1,"c":"teal"}]')
    if isinstance(data, dict):
        data = data.get("parts") or data.get("shapes")
    if not isinstance(data, list) or not data:
        raise ArtError("sculpture needs a list of shapes")
    parts = []

    def num(v, d, lo, hi):
        try:
            return max(lo, min(hi, float(v)))
        except Exception:
            return d
    for p in data[:24]:
        if not isinstance(p, dict):
            continue
        s = str(p.get("s") or p.get("shape") or "box").lower()
        if s not in SHAPES:
            s = "box"
        size = num(p.get("size"), 1.0, 0.15, 2.0)
        parts.append({"s": s, "x": num(p.get("x"), 0, -1.8, 1.8), "y": num(p.get("y"), 0.5, 0, 3.5), "z": num(p.get("z"), 0, -1.8, 1.8),
                      "sx": num(p.get("sx"), size, 0.1, 2.5), "sy": num(p.get("sy"), size, 0.1, 2.5), "sz": num(p.get("sz"), size, 0.1, 2.5),
                      "c": world.to_hex(p.get("c") or p.get("color")) or "#b0bec5"})
    if not parts:
        raise ArtError("no valid shapes in the sculpture")
    shapes = {p["s"] for p in parts}
    if len(parts) < 6 or len(shapes) < 3:
        raise ArtError("that sculpture is just a few plain shapes. Make something recognisable (a tree, a bird, a lighthouse, a robot, a boat) from at least 6 parts using at least 3 different shapes, "
                       "with sensible sizes, positions and colours")
    return parts


# ---------------------------------------------------------------- entry point
def check_art(kind, content):
    """-> (mode, cleaned_content_str, colors[list of hex])"""
    kind, content = str(kind or "").lower(), str(content or "").strip()
    if kind not in KINDS:
        raise ArtError(f"kind must be one of: {', '.join(KINDS)}")
    if not content:
        raise ArtError("content is empty")
    if len(content) > config.ART_MAX_CHARS:
        raise ArtError(f"content too long (max {config.ART_MAX_CHARS} characters)")
    if kind == "drawing":
        if re.match(r"^\s*(<\?xml[^>]*>\s*)?<svg\b", content, re.I):
            out, mode = sanitize_svg(content), "svg"
        else:
            out, mode = check_js(content), "js"
        cols = list(dict.fromkeys(world.to_hex(c) for c in re.findall(r"#[0-9a-fA-F]{6}\b", out) if world.to_hex(c)))
        for n in re.findall(r"['\"= ]([a-z]{3,7})['\"; ]", out.lower()):
            if n in world.COLORS:
                cols.append(world.COLORS[n])
        return mode, out, list(dict.fromkeys(cols))[:6]
    if kind == "pixel":
        d = parse_pixels(content)
        return "pixel", json.dumps(d), list(dict.fromkeys(d["palette"].values()))[:6]
    parts = parse_sculpture(content)
    return "sculpture", json.dumps(parts), list(dict.fromkeys(p["c"] for p in parts))[:6]
