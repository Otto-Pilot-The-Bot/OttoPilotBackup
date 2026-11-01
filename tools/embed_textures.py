#!/usr/bin/env python3
"""Embed external textures into the project's copies of the Kenney .glb files (the originals are only READ).

Many Kenney .glb files point at 'Textures/colormap.png' next to them. The importer copies only .glb files, so those models would show up
untextured (and the scanner refuses external references). This reads each texture from the SOURCE folder (read-only) and packs it into
the project's copy of the .glb. The picture is embedded byte-for-byte, so nothing is recolored. Files are written to a temp name then renamed.

    python tools/embed_textures.py            # dry run
    python tools/embed_textures.py --go
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "Library/CloudStorage/GoogleDrive-averagedru@gmail.com/My Drive/Sprocket Assests/3D assets"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def read_glb(p):
    d = p.read_bytes()
    if d[:4] != b"glTF":
        raise ValueError("not a glb")
    jl, jt = struct.unpack("<I4s", d[12:20]); j = json.loads(d[20:20 + jl]); off = 20 + jl
    binc = b""
    if off + 8 <= len(d):
        bl, bt = struct.unpack("<I4s", d[off:off + 8]); binc = d[off + 8:off + 8 + bl]
    return j, binc


def write_glb(p, j, binc):
    while len(binc) % 4:
        binc += b"\0"
    js = json.dumps(j, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(binc)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(binc), b"BIN\0") + binc
    tmp = p.with_name(p.name + ".part"); tmp.write_bytes(out); tmp.replace(p)


def find_tex(src_pack, glb_rel_dir, uri):
    if ".." in uri or "://" in uri or uri.startswith("/"):
        return None
    base = Path(uri).name
    for c in (src_pack / glb_rel_dir / uri, src_pack / "Models" / "Textures" / base, src_pack / "Textures" / base):
        if c.is_file() and c.suffix.lower() in MIME:
            return c
    hits = [h for h in src_pack.rglob(base) if h.is_file() and h.suffix.lower() in MIME]
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", type=Path, default=DEFAULT_SRC); ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dest = ROOT / "assets/kenney"
    n_ok = n_skip = n_missing = 0; missing = {}
    cache = {}
    for pack in sorted(p for p in dest.iterdir() if p.is_dir()):
        sp = a.src / pack.name
        for f in sorted(pack.rglob("*.glb")):
            try:
                j, binc = read_glb(f)
            except Exception as e:
                print("skip", f, e); continue
            imgs = j.get("images", [])
            todo = [i for i in imgs if "uri" in i and not i["uri"].startswith("data:")]
            if not todo:
                n_skip += 1; continue
            rel_dir = f.parent.relative_to(pack)
            ok = True
            for im in todo:
                t = find_tex(sp, rel_dir, im["uri"])
                if not t:
                    ok = False; missing.setdefault(pack.name, set()).add(im["uri"]); break
                im["_bytes"] = cache.setdefault(t, t.read_bytes()); im["_mime"] = MIME[t.suffix.lower()]
            if not ok:
                n_missing += 1; continue
            if a.go:
                for im in todo:
                    data = im.pop("_bytes"); mime = im.pop("_mime"); im.pop("uri")
                    while len(binc) % 4:
                        binc += b"\0"
                    j.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": len(binc), "byteLength": len(data)})
                    binc += data
                    im["bufferView"] = len(j["bufferViews"]) - 1; im["mimeType"] = mime
                j.setdefault("buffers", [{}])[0]["byteLength"] = len(binc)
                if "uri" in j["buffers"][0]:
                    del j["buffers"][0]["uri"]
                write_glb(f, j, binc)
            n_ok += 1
    print(f"{'embedded' if a.go else 'would embed'}: {n_ok}; already self-contained: {n_skip}; texture not found: {n_missing}")
    for k, v in missing.items():
        print("  missing in", k, sorted(v)[:3])


if __name__ == "__main__":
    main()
