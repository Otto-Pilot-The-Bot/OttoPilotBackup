#!/usr/bin/env python3
"""Makes textured trees (regular, apple, pink blossom; three shapes each) as light .glb files for the model library.

    .venv/Scripts/python tools/make_trees.py [output folder]          (needs Blender; BLENDER env var or the usual install path)

Each tree is a branched trunk with a painted bark texture and a canopy of leaf cards (sprites with painted veins, blossoms) cut out with alpha;
apples are real little meshes. Around 6-10k triangles, ~1 MB. Same seed, same tree. Default output: assets/meshy/Trees.
Steps: (1) paint the textures with Pillow, (2) build the trees in Blender (tools/_blender_tree.py), (3) mark the leaf material as alpha-cutout in the .glb."""
import glob
import json
import math
import os
import random
import struct
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "meshy", "Trees")
S = 1024                                                                   # painted at 1024, saved at 512


def blender_exe():
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    c = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
    if not c:
        sys.exit("Blender not found: set the BLENDER environment variable.")
    return c[-1]


# ------------------------------------------------------------------ textures
def hexc(h, v=0, a=255):
    h = h.lstrip("#")
    return tuple(max(0, min(255, int(h[i:i + 2], 16) + v)) for i in (0, 2, 4)) + (a,)


def leaf_poly(x, y, length, width, ang):
    pts = []
    for i in range(0, 13):
        t = i / 12
        pts.append((t * length, width * math.sin(math.pi * t) ** 0.85 * (1 - 0.25 * t)))
    for i in range(12, -1, -1):
        t = i / 12
        pts.append((t * length, -width * math.sin(math.pi * t) ** 0.85 * (1 - 0.25 * t)))
    c, s = math.cos(ang), math.sin(ang)
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]


def draw_leaf(d, x, y, length, width, ang, col, rng):
    d.polygon(leaf_poly(x, y, length, width, ang), fill=hexc(col, -28))                       # dark rim
    d.polygon(leaf_poly(x, y, length * 0.96, width * 0.82, ang), fill=hexc(col, rng.randint(-8, 14)))
    d.polygon(leaf_poly(x + math.cos(ang) * length * 0.1, y + math.sin(ang) * length * 0.1, length * 0.7, width * 0.4, ang), fill=hexc(col, rng.randint(14, 30)))   # lighter middle
    ex, ey = x + math.cos(ang) * length * 0.95, y + math.sin(ang) * length * 0.95
    d.line([(x, y), (ex, ey)], fill=hexc(col, -45), width=max(2, int(width * 0.09)))              # midrib
    for k in (0.3, 0.5, 0.7):                                                                      # side veins
        bx, by = x + math.cos(ang) * length * k, y + math.sin(ang) * length * k
        for sgn in (-1, 1):
            a2 = ang + sgn * 0.9
            d.line([(bx, by), (bx + math.cos(a2) * width * 0.65, by + math.sin(a2) * width * 0.65)], fill=hexc(col, -38), width=max(1, int(width * 0.05)))


def sprite(kind, seed):
    """A twig that grows straight up from the bottom middle of a 1024x1024 transparent picture."""
    rng = random.Random(seed)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    greens = {"green": ["#4f8f3f", "#5aa044", "#3f7a35", "#68a84a"], "apple": ["#5d9c42", "#6fb050", "#4c8a37", "#7bb957"], "pink": ["#5b9a47", "#4f8f3f"]}[kind]
    stem = [(S * 0.5 + math.sin(t * 2.2) * S * 0.04, S - 30 - t * (S - 160)) for t in [i / 24 for i in range(25)]]
    d.line(stem, fill=hexc("#6b4a2f"), width=10)
    n = 11 if kind != "pink" else 6
    for i in range(n):
        t = 0.12 + 0.8 * i / n
        sx, sy = stem[int(t * 24)]
        side = 1 if i % 2 else -1
        ang = -math.pi / 2 + side * rng.uniform(0.7, 1.1)
        ln = (330 if kind != "pink" else 220) * (1 - 0.45 * t)
        draw_leaf(d, sx, sy, ln, ln * 0.33, ang, rng.choice(greens), rng)
    draw_leaf(d, stem[-1][0], stem[-1][1], 300 if kind != "pink" else 200, 100 if kind != "pink" else 66, -math.pi / 2, rng.choice(greens), rng)
    if kind == "pink":                                                                              # blossoms along the twig
        for i in range(17):
            t = rng.uniform(0.15, 0.98)
            sx, sy = stem[min(24, int(t * 24))]
            bx, by = sx + rng.uniform(-170, 170) * (0.4 + t), sy + rng.uniform(-60, 60)
            r = rng.uniform(46, 74)
            tint = rng.choice(["#f4a9c4", "#f7c4d6", "#ee8fb0", "#fbd9e4"])
            for k in range(5):
                a = k * 2 * math.pi / 5 + rng.uniform(0, 1)
                px, py = bx + math.cos(a) * r * 0.62, by + math.sin(a) * r * 0.62
                d.ellipse([px - r * 0.58, py - r * 0.58, px + r * 0.58, py + r * 0.58], fill=hexc(tint, -14))
                d.ellipse([px - r * 0.46, py - r * 0.46, px + r * 0.46, py + r * 0.46], fill=hexc(tint, 4))
            d.ellipse([bx - r * 0.2, by - r * 0.2, bx + r * 0.2, by + r * 0.2], fill=hexc("#e8c250"))
    return im.filter(ImageFilter.GaussianBlur(0.6)).resize((512, 512), Image.LANCZOS)


def bark(seed, dark):
    rng = random.Random(seed)
    n = Image.effect_noise((128, 32), 90).resize((256, 512), Image.BICUBIC)
    col = ImageOps.colorize(n.convert("L"), black="#2e2018" if dark else "#3a3027", white="#7a5c42" if dark else "#8f7c68").convert("RGBA")
    d = ImageDraw.Draw(col)
    for _ in range(90):                                                                            # deep vertical cracks
        x = rng.randint(0, 255); y = rng.randint(0, 480); ln = rng.randint(40, 200)
        d.line([(x, y), (x + rng.randint(-5, 5), y + ln)], fill=(28, 20, 14, 255), width=rng.randint(1, 3))
    return col.filter(ImageFilter.GaussianBlur(0.7)).convert("RGB")


# ------------------------------------------------------------------ patch the .glb: leaves are alpha-cutout, double sided
def patch_glb(path):
    d = open(path, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + n])
    for m in j.get("materials", []):
        if m.get("name", "").startswith("Leaf"):
            m["alphaMode"] = "MASK"; m["alphaCutoff"] = 0.5; m["doubleSided"] = True
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    rest = d[20 + n:]
    out = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + len(rest)) + struct.pack("<II", len(js), 0x4E4F534A) + js + rest
    open(path, "wb").write(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="trees_")
    for k, seed in (("green", 11), ("apple", 22), ("pink", 33)):
        sprite(k, seed).save(os.path.join(tmp, f"leaf_{k}.png"))
    bark(1, False).save(os.path.join(tmp, "bark.png")); bark(2, True).save(os.path.join(tmp, "bark_dark.png"))
    for old in glob.glob(os.path.join(OUT, "*.glb")):
        os.remove(old)                                                                              # the pack is rebuilt from scratch
    r = subprocess.run([blender_exe(), "-b", "--python", os.path.join(ROOT, "tools", "_blender_tree.py"), "--", tmp, OUT], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith(("WROTE", "ERROR")) or "Traceback" in line:
            print(line)
    if r.returncode:
        print(r.stderr[-1500:])
    for f in glob.glob(os.path.join(OUT, "*.glb")):
        patch_glb(f)


if __name__ == "__main__":
    main()
