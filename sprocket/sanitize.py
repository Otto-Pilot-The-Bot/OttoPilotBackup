"""Everything a page must pass BEFORE it can be queued, and again right before it is published.
Static HTML/CSS only: no scripts, forms, images, iframes, trackers or remote assets. No personal or machine information.
This module is code the model cannot change (it has no file tools); the publisher re-runs it as a second gate."""
import getpass
import html as htmllib
import re
import socket
from html.parser import HTMLParser
from pathlib import Path

from . import artcheck, config


class PageError(Exception):
    """Message is safe to show to the model: it NEVER contains the text that triggered it."""


# ---------------------------------------------------------------------------------- markdown -> html
def _inline(t):
    t = htmllib.escape(t, quote=False)
    t = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"(?<![\w])_([^_\n]+)_(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]\n]+)\]\((https://[^\s)\"'<>]+)\)", r'<a href="\2">\1</a>', t)
    return t


def markdown_to_html(md):
    out, para, lst, code = [], [], None, None

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_list():
        nonlocal lst
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{_inline(i)}</li>" for i in lst[1]) + f"</{lst[0]}>")
            lst = None
    for raw in md.replace("\r", "").split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if code is None:
                flush_para(); flush_list(); code = []
            else:
                out.append("<pre><code>" + htmllib.escape("\n".join(code), quote=False) + "</code></pre>"); code = None
            continue
        if code is not None:
            code.append(raw); continue
        if not line.strip():
            flush_para(); flush_list(); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            flush_para(); flush_list(); n = len(m.group(1)); out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>"); continue
        if re.match(r"^(-{3,}|\*{3,})$", line.strip()):
            flush_para(); flush_list(); out.append("<hr>"); continue
        m = re.match(r"^\s*([-*]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para(); kind = "ol" if m.group(1)[0].isdigit() else "ul"
            if lst and lst[0] != kind:
                flush_list()
            lst = lst or (kind, [])
            lst[1].append(m.group(2)); continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            flush_para(); flush_list(); out.append(f"<blockquote><p>{_inline(m.group(1))}</p></blockquote>"); continue
        flush_list(); para.append(line.strip())
    flush_para(); flush_list()
    if code is not None:
        out.append("<pre><code>" + htmllib.escape("\n".join(code), quote=False) + "</code></pre>")
    return "\n".join(out)


# ---------------------------------------------------------------------------------- html sanitizer (allow-list rebuild)
ALLOWED = {"h1", "h2", "h3", "h4", "p", "br", "hr", "ul", "ol", "li", "strong", "em", "b", "i", "code", "pre", "blockquote", "a",
           "table", "thead", "tbody", "tr", "th", "td"}
VOID = {"br", "hr"}
FORBIDDEN = {"script", "style", "iframe", "frame", "frameset", "object", "embed", "applet", "form", "input", "button", "textarea", "select",
             "option", "link", "meta", "base", "svg", "math", "img", "picture", "video", "audio", "source", "track", "canvas", "template", "portal"}
_HREF = re.compile(r"^https://[A-Za-z0-9.-]+(?::\d+)?(?:/[^\s\"'<>]*)?$")


class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.links = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in FORBIDDEN:
            raise PageError(f"<{tag}> is not allowed: pages are static text only (no scripts, images, forms, iframes or embeds)")
        for k, v in attrs:
            if k.startswith("on"):
                raise PageError("event handlers are not allowed")
            if v and re.search(r"javascript:|data:text|vbscript:", v, re.I):
                raise PageError("script URLs are not allowed")
        if tag not in ALLOWED:
            return                                                   # unknown wrapper tags (div, span...) are dropped, their text is kept
        if tag == "a":
            href = next((v for k, v in attrs if k == "href"), "") or ""
            if not _HREF.match(href.strip()):
                self.stack.append(None); return                      # not a plain https link: keep the text, drop the link
            self.links += 1
            if self.links > 12:
                raise PageError("too many links (max 12)")
            self.out.append(f'<a href="{htmllib.escape(href.strip(), quote=True)}" rel="nofollow noopener noreferrer">')
            self.stack.append("a"); return
        if tag == "h1":                                              # the page title is the only h1
            tag = "h2"
        self.out.append(f"<{tag}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID or tag not in ALLOWED:
            return
        if tag == "a" and None in self.stack and "a" not in self.stack:
            self.stack.remove(None); return
        if tag == "h1":
            tag = "h2"
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                if t:
                    self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data):
        self.out.append(htmllib.escape(data, quote=False))


def sanitize_html(src):
    p = _Clean()
    p.feed(src)
    p.close()
    while p.stack:
        t = p.stack.pop()
        if t:
            p.out.append(f"</{t}>")
    return "".join(p.out).strip()


def to_text(html):
    t = re.sub(r"</?(?:p|h[1-4]|li|ul|ol|br|hr|blockquote|pre|table|tr|td|th|thead|tbody)\b[^>]*>", " ", html)   # block tags separate words
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", t))).strip()


# ---------------------------------------------------------------------------------- page design (themes, layout blocks, his own drawings)
# The sanitizer above is untouched: every piece of TEXT still goes through it. Design is added around the text by this code, from fixed templates:
# a colour theme (a CSS class from a short list), cards / callouts / two columns (fixed div classes), and his own drawings as inline SVG that passes the SVG allow-list again.
# He writes plain directive lines such as  [[theme: night]]  [[card]] ... [[/card]]  [[art 115]];  nothing he writes is ever copied into a tag or an attribute.
THEMES = ("paper", "night", "sunset", "ocean", "forest", "mint")
_TOKEN = re.compile(r"^\s*\[\[\s*(/?)(theme|art|card|callout|columns|column)\s*:?\s*([^\]]*?)\s*\]\]\s*$", re.I)
MAX_ART_ON_PAGE = 6


def _text_html(text):
    raw = text if re.search(r"<\s*[a-zA-Z/!]", text) else markdown_to_html(text)
    return sanitize_html(raw)


def _art_figure(ref, art_lookup):
    if not art_lookup:
        raise PageError("drawings cannot be shown on this page")
    found = art_lookup(ref)
    if not found:
        raise PageError("there is no drawing of yours with that number or title (use the number from your list of drawings)")
    title, svg = found
    if not svg or len(svg) > 24000:
        raise PageError("that drawing cannot be shown on a page")
    try:
        clean = artcheck.sanitize_svg(svg)
    except artcheck.ArtError:
        raise PageError("that drawing cannot be shown on a page")
    cap = htmllib.escape(re.sub(r"\s+", " ", str(title or "a drawing")).strip()[:80], quote=True)
    return f'<figure class="art">{clean}<figcaption>{cap}</figcaption></figure>'


def build_body(body, art_lookup=None):
    """body text with directive lines -> the finished inner html. Raises PageError (safe to show him)."""
    theme, parts, buf, stack, arts = "paper", [], [], [], 0

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            parts.append(_text_html(text))
    for line in body.replace("\r", "").split("\n"):
        m = _TOKEN.match(line)
        if not m:
            buf.append(line)
            continue
        flush()
        closing, tok, arg = m.group(1) == "/", m.group(2).lower(), m.group(3).strip()
        if tok == "theme" and not closing:
            if arg.lower() not in THEMES:
                raise PageError("the theme must be one of: " + ", ".join(THEMES))
            theme = arg.lower()
        elif tok == "art" and not closing:
            arts += 1
            if arts > MAX_ART_ON_PAGE:
                raise PageError(f"too many drawings on one page (max {MAX_ART_ON_PAGE})")
            parts.append(_art_figure(arg, art_lookup))
        elif tok in ("card", "callout", "columns") and not closing:
            if stack:
                raise PageError("blocks cannot be put inside other blocks (a drawing can)")
            stack.append(tok)
            parts.append({"card": '<div class="card">', "callout": '<div class="callout">', "columns": '<div class="cols"><div class="col">'}[tok])
        elif tok == "column" and not closing:
            if stack != ["columns"]:
                raise PageError("[[column]] only goes inside [[columns]] ... [[/columns]]")
            parts.append('</div><div class="col">')
        elif closing and tok in ("card", "callout", "columns"):
            if stack != [tok]:
                raise PageError(f"[[/{tok}]] has no matching [[{tok}]]")
            stack.pop()
            parts.append("</div></div>" if tok == "columns" else "</div>")
        else:
            raise PageError("that design line is not understood. Use: [[theme: name]], [[card]]...[[/card]], [[callout]]...[[/callout]], [[columns]]...[[column]]...[[/columns]], [[art number]]")
    flush()
    if stack:
        raise PageError(f"[[/{stack[0]}]] is missing")
    return f'<div class="page theme-{theme}">' + "\n".join(parts) + "</div>"


# ---------------------------------------------------------------------------------- privacy
def _machine_terms():
    terms = set()
    try:
        terms.add(getpass.getuser().lower())
    except Exception:
        pass
    terms.add(Path.home().name.lower())
    host = socket.gethostname().lower()
    terms |= {host, host.split(".")[0]}
    terms.add(str(config.ROOT).lower())
    for f in (config.PRIVATE_TERMS_FILE, config.ROOT / "data" / "gift_terms.txt"):      # gifts are private: their names never go on the site
        if not f.is_file():
            continue
        for line in f.read_text(errors="ignore").splitlines():
            line = line.strip().lower()
            if len(line) >= 3 and not line.startswith("#"):
                terms.add(line)
    return {t for t in terms if len(t) >= 3}


_PATTERNS = [
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "an email address"),
    (r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?!\d)", "a phone-number-like number"),
    (r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|way|place|pl)\b", "a street address"),
    (r"(?:^|[\s(\"'])(?:/Users/|/home/|/private/|/Volumes/|/var/|/etc/|/tmp/|~/|[A-Za-z]:\\)", "a file path"),
    (r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|xox[baprs]-[A-Za-z0-9-]{8,}|AIza[0-9A-Za-z_-]{20,}", "something that looks like a secret key"),
    (r"-----BEGIN [A-Z ]*(?:KEY|CERTIFICATE)", "a key block"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "an IP address"),
    (r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b|\.local\b", "a local address"),
    (r"\bGITHUB_TOKEN\b|(?:^|[\s(])\.env\b|sprocket\.db|data/sprocket|private_terms", "a reference to this machine's configuration"),
    (r"(?<![\w/])[A-Za-z0-9+/_=-]{40,}(?![\w/])", "a long random-looking string"),
]


def check_privacy(*texts, secrets=()):
    """Raises PageError (without quoting the match) if any text holds personal info, machine info, or a secret."""
    blob = "\n".join(t for t in texts if t)
    low = blob.lower()
    for s in secrets:
        if s and len(s) > 8 and s in blob:
            raise PageError("it contains a secret value")
    for rx, what in _PATTERNS:
        flags = re.M | (re.I if what == "a street address" else 0)
        found = list(re.finditer(rx, blob, flags))
        if not found:
            continue
        if what == "a phone-number-like number" and not any(len(re.sub(r"\D", "", m.group(0))) >= 9 for m in found):
            continue
        raise PageError(f"it seems to contain {what}; personal or machine information must never go on the site")
    for t in _machine_terms():
        if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low):
            raise PageError("it mentions something private about this computer or its owner")


# ---------------------------------------------------------------------------------- the whole gate
def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50].strip("-")
    return s or "page"


def clean_tags(tags):
    if isinstance(tags, str):
        tags = re.split(r"[,;#]", tags)
    out = []
    for t in (tags or [])[:5]:
        t = re.sub(r"[^a-z0-9-]+", "-", str(t).lower()).strip("-")[:20]
        if t and t not in out:
            out.append(t)
    return out


FINAL_BAD = re.compile(r"<\s*(script|style|iframe|form|img|object|embed|link|meta|svg|input|video|audio)\b|\bon\w+\s*=|javascript:|\bsrc\s*=|srcset|@import|url\(", re.I)


_ART_FIG = re.compile(r'<figure class="art">(<svg\b.*?</svg>)<figcaption>[^<]*</figcaption></figure>', re.S)


def _check_figure(m):
    svg = m.group(1)
    try:
        same = artcheck.sanitize_svg(svg) == svg
    except artcheck.ArtError:
        same = False
    if not same:
        raise PageError("page contains something that is not static text")
    return '<figure class="art"></figure>'


def assert_static(html, allow_shell=False):
    """Last-gate check on finished HTML; the publisher calls this too. The one exception to 'no svg': a drawing figure whose svg is unchanged by the SVG allow-list."""
    h = _ART_FIG.sub(_check_figure, html)
    if allow_shell:                                          # our own page shell legitimately has one <meta CSP>, <link css>, <style-free>
        h = re.sub(r"<meta [^>]*>|<link rel=\"stylesheet\" href=\"(?:\.\./)?style\.css\">", "", h)
    if FINAL_BAD.search(h):
        raise PageError("page contains something that is not static text")


def process_page(title, body, tags=None, secrets=(), art_lookup=None):
    """-> {'title','slug','tags','html','text'} or raises PageError."""
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not 3 <= len(title) <= config.TITLE_MAX or re.search(r"[<>]", title):
        raise PageError(f"the title must be 3-{config.TITLE_MAX} characters of plain text")
    body = str(body or "").strip()
    if not config.PAGE_MIN_CHARS <= len(body) <= config.PAGE_MAX_CHARS:
        raise PageError(f"the body must be {config.PAGE_MIN_CHARS}-{config.PAGE_MAX_CHARS} characters")
    if re.search(r"!\[[^\]]*\]\(", body):
        raise PageError("images are not allowed: pages are static text only")
    html = build_body(body, art_lookup)
    text = to_text(html)
    if len(text) < config.PAGE_MIN_CHARS:
        raise PageError("the page has almost no readable text")
    tags = clean_tags(tags)
    links = re.findall(r'href="([^"]+)"', html)
    check_privacy(title, " ".join(tags), text, " ".join(links), secrets=secrets)
    assert_static(html)
    return {"title": title, "slug": slugify(title), "tags": tags, "html": html, "text": text}


# ---------------------------------------------------------------------------------- the static site itself
CSS = """:root{--paper:#fbf4e2;--ink:#4b3b29;--dim:#8f7a58;--acc:#c46a1f;--line:#e2d3ad}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 ui-rounded,"SF Pro Rounded",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:720px;margin:0 auto;padding:32px 20px 60px}header.site{border-bottom:1px solid var(--line);margin-bottom:28px;padding-bottom:12px}
header.site a{color:var(--ink);text-decoration:none;font-weight:700;font-size:20px}h1{font-size:30px;line-height:1.2;margin:.2em 0}h2,h3,h4{margin-top:1.6em}
a{color:var(--acc)}code,pre{background:#f1e6c6;border-radius:6px;padding:2px 6px}pre{padding:12px;overflow:auto}blockquote{margin:1em 0;padding:.1em 1em;border-left:4px solid var(--line);color:var(--dim)}
.meta,.tags{color:var(--dim);font-size:14px}.tags span{background:#f1e6c6;border-radius:99px;padding:1px 9px;margin-right:6px}
ul.posts{list-style:none;padding:0}ul.posts li{padding:14px 0;border-bottom:1px dashed var(--line)}ul.posts a{font-size:20px;font-weight:600}
.page{border-radius:14px;padding:4px 4px}.page.theme-paper{background:transparent}
.theme-night{--paper:#1d2030;--ink:#e8e9f5;--dim:#a3a8c4;--acc:#8fb4ff;--line:#3a3f5c;background:#1d2030;color:#e8e9f5;padding:8px 22px;--cardbg:#2a2e45}
.theme-sunset{--ink:#4a2a2a;--dim:#8a5a4a;--acc:#d9532b;--line:#f0b98f;background:linear-gradient(180deg,#ffe3c2,#ffc9a3);color:#4a2a2a;padding:8px 22px;--cardbg:#fff2e3}
.theme-ocean{--ink:#17324d;--dim:#4a6d8c;--acc:#1c6fb8;--line:#9cc7e6;background:linear-gradient(180deg,#dff1fb,#bcdff4);color:#17324d;padding:8px 22px;--cardbg:#f1faff}
.theme-forest{--ink:#223a22;--dim:#5a7a56;--acc:#2f7a3a;--line:#a9cf9c;background:linear-gradient(180deg,#e6f3dc,#cbe5b8);color:#223a22;padding:8px 22px;--cardbg:#f4fbee}
.theme-mint{--ink:#1f3d3a;--dim:#4f7f78;--acc:#1f9a8a;--line:#a6dcd2;background:linear-gradient(180deg,#e3faf4,#c4f0e5);color:#1f3d3a;padding:8px 22px;--cardbg:#f2fffb}
.theme-night a,.theme-night h2,.theme-night h3{color:var(--acc)}
.card{background:var(--cardbg,#fffaf0);border:1px solid var(--line);border-radius:12px;padding:4px 18px;margin:16px 0}
.callout{border-left:5px solid var(--acc);background:var(--cardbg,#f6e9c6);padding:4px 18px;margin:16px 0;border-radius:0 12px 12px 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin:16px 0}@media(max-width:620px){.cols{grid-template-columns:1fr}}
figure.art{margin:18px auto;max-width:440px;text-align:center}figure.art svg{width:100%;height:auto;border-radius:12px;border:1px solid var(--line);background:#fff}
figcaption{color:var(--dim);font-size:14px;margin-top:6px}
footer{margin-top:48px;color:var(--dim);font-size:13px;border-top:1px solid var(--line);padding-top:12px}table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:4px 8px}
"""
CSP_META = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'self\'; base-uri \'none\'; form-action \'none\'">'


def _shell(title, body, root):
    t = htmllib.escape(title, quote=True)
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">{CSP_META}<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{t}</title><link rel="stylesheet" href="{root}style.css"></head><body><main>'
            f'<header class="site"><a href="{root}index.html">{htmllib.escape(config.SHORT_NAME)}\'s corner of the web</a></header>{body}'
            f'<footer>Written by {htmllib.escape(config.SHORT_NAME)}, an autonomous robot. Every page here was approved by a human before it was published.</footer></main></body></html>\n')


def render_page(p, date_text):
    tags = "".join(f"<span>{htmllib.escape(t)}</span>" for t in p["tags"])
    body = f'<article><h1>{htmllib.escape(p["title"])}</h1><p class="meta">{htmllib.escape(date_text)}</p>{'<p class="tags">' + tags + "</p>" if tags else ""}{p["html"]}</article>'
    html = _shell(p["title"], body, "../")
    assert_static(html, allow_shell=True)
    return html


def render_index(pages):
    """pages: list of dicts(title, slug, excerpt, date) newest first."""
    items = "".join(
        f'<li><a href="pages/{htmllib.escape(p["slug"])}.html">{htmllib.escape(p["title"])}</a><div class="meta">{htmllib.escape(p["date"])}</div>'
        f'<div>{htmllib.escape(p["excerpt"])}</div></li>' for p in pages)
    body = f'<h1>{htmllib.escape(config.SHORT_NAME)}\'s pages</h1><p class="meta">Notes from a small robot that lives in a 3D world.</p>' + \
           (f'<ul class="posts">{items}</ul>' if items else "<p>Nothing published yet.</p>")
    html = _shell(f"{config.SHORT_NAME}'s pages", body, "")
    assert_static(html, allow_shell=True)
    return html
