"""Safe, read-only page fetching. GET only. Public internet only. Text only.

Defences (all enforced here, not left to the model):
 * only http/https, only ports 80/443, no credentials in the URL
 * the hostname is resolved and EVERY resulting address must be public (is_global); the socket then connects to
   that exact validated IP, so DNS rebinding / odd IP notations (2130706433, 0x7f.1, ::ffff:127.0.0.1) can't slip through
 * redirects are followed manually (max 3) and each hop is re-validated
 * only text/html / text/plain, hard byte cap, hard time cap; scripts/forms/styles are dropped from the text
"""
import http.client
import ipaddress
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from . import config

UA = "SprocketBot/1.0 (hobby robot; read-only; text only)"


class Blocked(Exception):
    """Raised for anything we refuse to fetch. Message is safe to show to the model.
    remember=True means the SITE refused us (403/401/429...), so the caller should not retry it for a while."""

    def __init__(self, msg, code=None, remember=False, host=None):
        super().__init__(msg)
        self.code, self.remember, self.host = code, remember, host


def _check_public(host, port):
    if not host:
        raise Blocked("no host in URL")
    h = host.lower().rstrip(".")
    if h == "localhost" or h.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".corp")):
        raise Blocked("local addresses are not allowed")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise Blocked("could not resolve that host")
    if not infos:
        raise Blocked("could not resolve that host")
    for fam, _, _, _, sa in infos:
        ip = ipaddress.ip_address(sa[0].split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise Blocked("private, local or reserved network addresses are not allowed")
    return infos[0][4]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class _HTTP(http.client.HTTPConnection):
    def connect(self):
        sa = _check_public(self.host, self.port)
        self.sock = socket.create_connection((sa[0], sa[1]), self.timeout)


class _HTTPS(http.client.HTTPSConnection):
    def connect(self):
        sa = _check_public(self.host, self.port)
        sock = socket.create_connection((sa[0], sa[1]), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)   # certificate is verified


_SKIP = {"script", "style", "noscript", "svg", "head", "template", "iframe", "object", "embed", "canvas", "form",
         "button", "select", "textarea", "input", "nav", "footer", "aside", "dialog"}
_BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "section", "article",
          "header", "main", "blockquote", "pre", "hr"}
_VOID = {"br", "hr", "img", "input", "meta", "link"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.parts, self.title, self._in_title = 0, [], "", False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in _SKIP and tag not in _VOID:
            self.skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _SKIP and tag not in _VOID and self.skip:
            self.skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def clean_text(html_text, limit=config.PAGE_CHARS):
    p = _Text()
    try:
        p.feed(html_text)
        p.close()
    except Exception:
        pass
    t = "".join(p.parts)
    t = re.sub(r"[\u0000-\u0008\u000b-\u001f\u007f​-‏‪-‮⁠﻿]", "", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    # page text can never contain angle brackets, so it cannot close our "untrusted" wrapper or fake tags
    t = t.replace("<", "‹").replace(">", "›")
    title = re.sub(r"\s+", " ", p.title).strip()[:160].replace("<", "‹").replace(">", "›")
    return title, t[:limit]


def fetch_page(url):
    """Returns (final_url, title, text). Raises Blocked with a model-safe message."""
    url = str(url or "").strip()
    if len(url) > 500:
        raise Blocked("URL too long")
    deadline = time.monotonic() + config.FETCH_TIMEOUT
    for _hop in range(4):
        parts = urlsplit(url)
        if parts.scheme.lower() not in ("http", "https"):
            raise Blocked("only http and https pages can be read")
        if parts.username or parts.password:
            raise Blocked("URLs with logins are not allowed")
        try:
            port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
        except ValueError:
            raise Blocked("bad port")
        if port not in config.FETCH_PORTS:
            raise Blocked("only the standard web ports are allowed")
        host = parts.hostname
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Blocked("page took too long")
        cls = _HTTPS if parts.scheme.lower() == "https" else _HTTP
        kw = {"context": _ctx()} if cls is _HTTPS else {}
        conn = cls(host, port, timeout=min(remaining, config.FETCH_TIMEOUT), **kw)
        try:
            path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
            conn.request("GET", path, headers={"User-Agent": UA, "Accept": "text/html,text/plain;q=0.9",
                                               "Accept-Encoding": "identity", "Accept-Language": "en", "Connection": "close"})
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                loc = r.getheader("Location")
                if not loc:
                    raise Blocked("bad redirect")
                url = urljoin(url, loc).split("#")[0]
                continue
            if r.status in (401, 403, 429, 451):
                raise Blocked(f"that site blocks robots (HTTP {r.status})", r.status, True, host)
            if r.status != 200:
                raise Blocked(f"the page is not available (HTTP {r.status})", r.status, False, host)
            ctype = (r.getheader("Content-Type") or "").lower()
            if not (ctype.startswith("text/html") or ctype.startswith("text/plain") or "xhtml" in ctype):
                raise Blocked("not a text page (downloads are not allowed)", None, False, host)
            chunks, total = [], 0
            while total < config.FETCH_MAX_BYTES:
                if time.monotonic() > deadline:
                    break
                b = r.read(16384)
                if not b:
                    break
                chunks.append(b)
                total += len(b)
            m = re.search(r"charset=([\w\-]+)", ctype)
            raw = b"".join(chunks)[:config.FETCH_MAX_BYTES]
            try:
                body = raw.decode(m.group(1) if m else "utf-8", errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")
            if ctype.startswith("text/plain"):
                title, text = "", clean_text("<pre>" + body.replace("<", "&lt;") + "</pre>")[1]
            else:
                title, text = clean_text(body)
            if not text:
                raise Blocked("the page had no readable text")
            return url, title, text
        except Blocked as e:
            e.host = e.host or host
            raise
        except (OSError, http.client.HTTPException, ssl.SSLError) as e:
            raise Blocked(f"could not fetch the page ({type(e).__name__})", None, False, host)
        finally:
            conn.close()
    raise Blocked("too many redirects")
