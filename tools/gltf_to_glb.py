#!/usr/bin/env python3
"""Pack .gltf + .bin (+ png/jpg textures) from a SOURCE kit into single .glb files in assets/kenney/<kit>/ (source is only read).
    python tools/gltf_to_glb.py "Nature Kit (Classic)" [--go]"""
import json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = Path.home() / "Library/CloudStorage/GoogleDrive-averagedru@gmail.com/My Drive/Sprocket Assests/3D assets"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

def pack(gf):
    j = json.loads(gf.read_text()); blob = bytearray()
    def add(data):
        while len(blob) % 4: blob.append(0)
        off = len(blob); blob.extend(data); return off
    # single merged buffer: re-point every bufferView
    bufs = []
    for b in j.get("buffers", []):
        uri = b.get("uri", "")
        if not uri or uri.startswith("data:") or ".." in uri or "://" in uri: raise ValueError("unsupported buffer uri")
        bufs.append((gf.parent / uri).read_bytes())
    base = [add(b) for b in bufs]
    for bv in j.get("bufferViews", []):
        bv["byteOffset"] = base[bv["buffer"]] + bv.get("byteOffset", 0); bv["buffer"] = 0
    for im in j.get("images", []):
        uri = im.get("uri")
        if uri:
            if ".." in uri or "://" in uri or uri.startswith("data:"): raise ValueError("unsupported image uri")
            p = gf.parent / uri
            if p.suffix.lower() not in MIME: raise ValueError("unsupported image type")
            off = add(p.read_bytes()); j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": p.stat().st_size})
            im.pop("uri"); im["bufferView"] = len(j["bufferViews"]) - 1; im["mimeType"] = MIME[p.suffix.lower()]
    while len(blob) % 4: blob.append(0)
    j["buffers"] = [{"byteLength": len(blob)}]
    js = json.dumps(j, separators=(",", ":")).encode()
    while len(js) % 4: js += b" "
    return struct.pack("<4sII", b"glTF", 2, 20 + len(js) + 8 + len(blob)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + bytes(blob)

kit, go = sys.argv[1], "--go" in sys.argv
files = sorted((SRC / kit).rglob("*.gltf")); dest = ROOT / "assets/kenney" / kit; n = bad = 0
for f in files:
    try:
        data = pack(f)
    except Exception as e:
        bad += 1; print("skip", f.name, e); continue
    if go:
        dest.mkdir(parents=True, exist_ok=True); t = dest / (f.stem + ".glb.part"); t.write_bytes(data); t.replace(dest / (f.stem + ".glb"))
    n += 1
print(f"{'wrote' if go else 'would write'} {n} glb ({bad} skipped) -> {dest}")
