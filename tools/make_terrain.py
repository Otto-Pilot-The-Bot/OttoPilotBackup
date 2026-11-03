"""Adds gentle hills and a small lake to a map's "heights" (see sprocket/maps.py). Usage: py tools/make_terrain.py <map name> [--force]
Hills are low (up to ~2 m), the lake is a shallow dip with a sloped shore. The map's buildings and the area around the middle stay flat. Make a copy of the map first."""
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HILLS = [(30, -28, 18, 2.25), (-30, 26, 20, 1.75), (4, -36, 14, 1.25)]          # x, z, radius in meters, peak height
LAKES = [(-24, -14, 21, 16, 1.3)]                                              # x, z, radius x, radius z, depth below ground level


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def main(name, force):
    path = ROOT / "data" / "maps" / f"{name}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("heights") and not force:
        sys.exit("This map already has terrain. Use --force to replace it.")
    n, cell = doc["n"], doc["cell"]
    half = n * cell / 2
    keep = [(o["x"], o["z"], max(o["fw"], o["fd"]) * o.get("scale", 1) / 2 + 6) for o in doc["objects"]]     # leave buildings and their surroundings flat
    rows = []
    for j in range(n + 1):
        row = ""
        for i in range(n + 1):
            x, z = -half + i * cell, -half + j * cell
            h = 0.0
            for hx, hz, r, peak in HILLS:
                h += peak * smooth(1 - math.hypot(x - hx, z - hz) / r)
            for lx, lz, rx, rz, depth in LAKES:
                h -= depth * smooth(1 - math.hypot((x - lx) / rx, (z - lz) / rz))
            if any(math.hypot(x - kx, z - kz) < kr for kx, kz, kr in keep):
                h = 0.0
            edge = min(i, j, n - i, n - j)                                       # the outer ring stays flat
            h *= 0 if edge == 0 else min(1.0, edge / 3)
            row += chr(ord("m") + max(-12, min(12, round(h / 0.25))))
        rows.append(row)
    doc["heights"] = rows
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"{name}: terrain added ({n + 1}x{n + 1} corners)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    main(args[0], "--force" in sys.argv)
