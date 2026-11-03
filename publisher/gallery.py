#!/usr/bin/env python3
"""Builds Otto's creations site (art, music, photos) as static sections of ONE repo. DRY RUN ONLY: writes to ./site_dryrun/gallery and
touches no network, no token, no git. Nothing here publishes; going live needs a separate human-approved step.

usage:  gallery.py [--db data/sprocket.db] [--out site_dryrun/gallery]
"""
import argparse
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sprocket import artcheck, config  # noqa: E402

CSS = """:root{--bg:#14131f;--fg:#ece8f6;--mut:#9a95b4;--card:#1f1d2e;--acc:#8a84cc}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header,main{max-width:960px;margin:0 auto;padding:16px}nav a{color:var(--acc);margin-right:16px;text-decoration:none}
h1{margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.card{background:var(--card);border-radius:10px;padding:10px}.card svg{width:100%;height:auto;display:block;background:#0003;border-radius:6px}
.card h3{margin:8px 0 2px;font-size:1rem}.mut{color:var(--mut);font-size:.85rem}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:6px 14px;font:inherit;cursor:pointer}
"""
CSP = "default-src 'none'; style-src 'self'; script-src 'unsafe-inline'; img-src 'self' data:"
SECTIONS = (("art", "Art"), ("music", "Music"), ("photos", "Photos"))


def esc(s):
    return html.escape(str(s or ""), quote=True)


def page(title, body, section=None, script=""):
    nav = '<a href="../index.html">Home</a>' if section else ""
    nav += "".join(f'<a href="{"../" if section else ""}{k}/index.html">{v}</a>' for k, v in SECTIONS)
    csp = CSP if script else CSP.replace("script-src 'unsafe-inline'", "script-src 'none'")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{csp}"><title>{esc(title)}</title>'
            f'<link rel="stylesheet" href="{"../" if section else ""}style.css"></head><body><header><nav>{nav}</nav><h1>{esc(title)}</h1></header>'
            f'<main>{body}</main>{f"<script>{script}</script>" if script else ""}</body></html>')


def pixel_svg(content):
    d = artcheck.parse_pixels(content)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{d["palette"][c]}"/>'
                    for y, row in enumerate(d["rows"]) for x, c in enumerate(row) if c in d["palette"])
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {d["w"]} {d["h"]}" shape-rendering="crispEdges">{rects}</svg>'


def art_section(db, min_score):
    cards, skipped = [], 0
    for r in db.execute("SELECT title,kind,mode,content,statement FROM art WHERE kind IN ('drawing','pixel') AND COALESCE(score,-1)>=? ORDER BY score DESC, ts DESC", (min_score,)):
        try:
            if r["kind"] == "pixel":
                svg = pixel_svg(r["content"])
            elif r["mode"] == "svg":
                svg = artcheck.sanitize_svg(r["content"])       # re-sanitised: the DB copy is never trusted
            else:
                skipped += 1                                    # canvas-code drawings need a script; left out
                continue
        except artcheck.ArtError:
            skipped += 1
            continue
        cards.append(f'<div class="card">{svg}<h3>{esc(r["title"])}</h3><div class="mut">{esc(r["statement"])}</div></div>')
    body = f'<div class="grid">{"".join(cards)}</div>' if cards else "<p>Nothing here yet.</p>"
    return page("Art", body, "art"), len(cards), skipped


PLAYER = """const F={C:0,D:2,E:4,F:5,G:7,A:9,B:11},D={w:4,h:2,q:1,e:.5,s:.25};let ac;
function hz(n){const m=/^([A-G])([#b]?)(\\d)$/.exec(n);if(!m)return 0;return 440*Math.pow(2,(F[m[1]]+(m[2]=='#'?1:m[2]=='b'?-1:0)+12*(+m[3]+1)-69)/12)}
function play(i){ac=ac||new AudioContext();const t=TUNES[i],sec=60/t.tempo;let at=ac.currentTime+.05;
for(const tok of t.notes.split(' ')){const[n,d]=tok.split(':'),len=(D[d]||1)*sec;
if(n!='R'){const o=ac.createOscillator(),g=ac.createGain();o.type=t.wave=='chime'?'sine':t.wave;o.frequency.value=hz(n);
g.gain.setValueAtTime(.18,at);g.gain.exponentialRampToValueAtTime(.001,at+len*.95);o.connect(g).connect(ac.destination);o.start(at);o.stop(at+len)}at+=len}}
document.querySelectorAll('button[data-i]').forEach(b=>b.onclick=()=>play(+b.dataset.i));"""


def music_section(db):
    tunes = [dict(r) for r in db.execute("SELECT title,notes,tempo,wave FROM tunes ORDER BY ts DESC")]
    tunes = [t for t in tunes if re.fullmatch(r"(?:[A-G][#b]?\d:[whqes]|R:[whqes])(?: (?:[A-G][#b]?\d:[whqes]|R:[whqes]))*", t["notes"])]
    rows = "".join(f'<div class="card"><h3>{esc(t["title"])}</h3><div class="mut">{len(t["notes"].split())} notes · {int(t["tempo"])} bpm · {esc(t["wave"])}</div>'
                   f'<p><button data-i="{i}">Play</button></p></div>' for i, t in enumerate(tunes))
    data = json.dumps(tunes).replace("<", "\\u003c")
    body = f'<div class="grid">{rows}</div>' if tunes else "<p>Nothing here yet.</p>"
    return page("Music", body, "music", f"const TUNES={data};\n{PLAYER}"), len(tunes)


def photos_section():
    body = "<p>Otto has not taken any real photographs yet. This section is ready for when he does.</p>"
    return page("Photos", body, "photos")


def build(db_path, out, min_score=config.ART_GALLERY_MATCH):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    art, n_art, skipped = art_section(db, min_score)
    music, n_music = music_section(db)
    out = Path(out)
    files = {"style.css": CSS, ".nojekyll": "", "art/index.html": art, "music/index.html": music, "photos/index.html": photos_section()}
    home = "".join(f'<div class="card"><h3><a href="{k}/index.html" style="color:inherit">{v}</a></h3></div>' for k, v in SECTIONS)
    files["index.html"] = page("Otto's creations", f'<p class="mut">Made by a robot in a small 3D world.</p><div class="grid">{home}</div>')
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return {"out": str(out), "art": n_art, "art_skipped": skipped, "music": n_music, "photos": 0, "files": sorted(files)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(config.ROOT / "data" / "sprocket.db"))
    ap.add_argument("--out", default=str(config.DRYRUN_DIR / "gallery"))
    ap.add_argument("--include-unrated", action="store_true", help="also show older pieces that were never rated")
    a = ap.parse_args()
    print(json.dumps(build(a.db, a.out, -1 if a.include_unrated else config.ART_GALLERY_MATCH)))
