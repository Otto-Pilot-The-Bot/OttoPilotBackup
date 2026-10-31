#!/usr/bin/env python3
"""Import 3D models (.glb only) from an outside folder into the project's asset folder.

    python tools/import_assets.py                  # DRY RUN: shows what would be copied (nothing is written)
    python tools/import_assets.py --go             # copy for real
    python tools/import_assets.py --go --only "Nature Kit,Car Kit"
    python tools/import_assets.py --go --existing merge      # what to do when a pack already exists in the project

Rules
- The source folder is only ever READ. Nothing in it is moved, renamed, written or deleted (the script refuses to run
  if the destination is inside the source or the source is inside the destination).
- Each top-level folder of the source is one pack/category and stays separate: <dest>/<pack>/... keeps the sub-folder layout.
- Only .glb files are copied (the model type the project uses). Other model types (obj, fbx, gltf, dae, blend, ...) are counted
  and reported, never copied. A pack that has no .glb at all is listed as NEEDS A DECISION.
- Files over the scanner's size limit are skipped and listed. Existing files with the same size are skipped, so re-running is cheap.
- If a pack folder already exists in the project: --existing skip | merge (copy only missing files) | rename (add " (2)") | ask.
  `ask` (default) asks on a terminal; without a terminal it skips the pack and lists it as NEEDS A DECISION.
- After copying, rescan the library (More panel > Rescan, or restart) and the new packs appear in the Assets panel.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "Library/CloudStorage/GoogleDrive-averagedru@gmail.com/My Drive/Sprocket Assests/3D assets"
OTHER_MODEL_EXT = {".obj", ".fbx", ".gltf", ".dae", ".blend", ".stl", ".usd", ".usdz", ".3ds", ".ply", ".bin"}


def default_dest():
    for n in ("assests", "assets"):                    # the project accepts both spellings; use the one that exists
        if (ROOT / n).is_dir():
            return ROOT / n
    return ROOT / "assests"


def scan_pack(folder):
    """-> glb files [(path, size)], counts of other model types."""
    glbs, other = [], {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "__MACOSX"))]
        for fn in filenames:
            if fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower()
            p = Path(dirpath) / fn
            if ext == ".glb":
                try:
                    glbs.append((p, p.stat().st_size))
                except OSError:
                    pass
            elif ext in OTHER_MODEL_EXT:
                other[ext] = other.get(ext, 0) + 1
    return sorted(glbs), other


def inside(a, b):
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--dest", type=Path, default=None)
    ap.add_argument("--go", action="store_true", help="really copy (default is a dry run)")
    ap.add_argument("--only", default="", help="comma-separated pack names to import")
    ap.add_argument("--existing", choices=("ask", "skip", "merge", "rename"), default="ask")
    ap.add_argument("--max-mb", type=float, default=25.0, help="skip models bigger than this (the scanner's limit)")
    a = ap.parse_args()
    src, dest = a.src.expanduser(), (a.dest or default_dest()).expanduser()
    if not src.is_dir():
        sys.exit(f"Source folder not found: {src}")
    if inside(dest, src) or inside(src, dest):
        sys.exit("Refusing to run: the source and destination folders must be separate.")
    only = {x.strip().lower() for x in a.only.split(",") if x.strip()}
    limit = int(a.max_mb * 1_000_000)

    packs = sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith("."))
    loose = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() == ".glb")
    plan, decide = [], []
    print(f"Source: {src}\nDest:   {dest}\nMode:   {'COPY' if a.go else 'DRY RUN (nothing is written)'}\n")
    for folder in packs:
        if only and folder.name.lower() not in only:
            continue
        t0 = time.time()
        glbs, other = scan_pack(folder)
        keep = [(p, s) for p, s in glbs if s <= limit]
        big = [(p, s) for p, s in glbs if s > limit]
        target = dest / folder.name
        status = "new"
        if not glbs:
            status = "NEEDS A DECISION: no .glb files" + (f" (has {', '.join(f'{n} {e}' for e, n in sorted(other.items()))})" if other else "")
            decide.append((folder.name, status))
        elif target.exists():
            choice = a.existing
            if choice == "ask":
                if sys.stdin.isatty():
                    choice = input(f"'{folder.name}' already exists in the project. [s]kip / [m]erge / [r]ename? ").strip().lower()[:1]
                    choice = {"s": "skip", "m": "merge", "r": "rename"}.get(choice, "skip")
                else:
                    choice = "skip"; status = "NEEDS A DECISION: already exists in the project (rerun with --existing merge|rename)"
                    decide.append((folder.name, status))
            if choice == "rename":
                n = 2
                while (dest / f"{folder.name} ({n})").exists():
                    n += 1
                target = dest / f"{folder.name} ({n})"; status = f"renamed -> {target.name}"
            elif choice == "merge":
                status = "merge (copy missing files only)"
            elif choice == "skip" and not status.startswith("NEEDS"):
                status = "skipped (already exists)"
        if not status.startswith(("NEEDS", "skipped")):
            plan.append((folder, target, keep))
        mb = sum(s for _, s in keep) / 1e6
        print(f"  {folder.name:<34} {len(keep):>5} glb  {mb:>8.1f} MB  {status}"
              + (f"  | {len(big)} over {a.max_mb:g} MB skipped" if big else "")
              + (f"  | not copied: {', '.join(f'{n} {e}' for e, n in sorted(other.items()))}" if other and glbs else "") + f"   ({time.time() - t0:.0f}s)", flush=True)
    if loose and not only:
        print(f"  (loose .glb files at the top level: {len(loose)}; they go into a pack called 'Loose models')")
        plan.append((None, dest / "Loose models", [(p, p.stat().st_size) for p in loose if p.stat().st_size <= limit]))

    total = sum(len(k) for _, _, k in plan)
    print(f"\n{len(plan)} pack(s), {total} model file(s) to copy; {len(decide)} pack(s) need a decision.")
    for n, why in decide:
        print(f"  - {n}: {why}")
    if not a.go:
        print("\nDry run only. Run again with --go to copy.")
        return

    manifest, copied, skipped, done = [], 0, 0, 0
    for folder, target, files in plan:
        for p, size in files:
            rel = p.relative_to(folder) if folder else Path(p.name)
            out = target / rel
            if out.exists() and out.stat().st_size == size:
                skipped += 1; continue
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(out.name + ".part")
            shutil.copyfile(p, tmp)                                  # source opened read-only; destination written under a temp name first
            tmp.replace(out)
            copied += 1
            manifest.append({"pack": target.name, "file": str(rel), "bytes": size})
            done += 1
            if done % 100 == 0:
                print(f"  ... {done}/{total}", flush=True)
    mf = ROOT / "data" / "import_manifest.json"
    mf.parent.mkdir(exist_ok=True)
    old = json.loads(mf.read_text()) if mf.exists() else []
    mf.write_text(json.dumps(old + [{"ts": time.time(), "src": str(src), "files": manifest}], indent=1))
    print(f"\nDone: {copied} copied, {skipped} already there. Manifest: {mf.relative_to(ROOT)}")
    print("Next: More panel > Rescan (or restart) to index the new packs.")


if __name__ == "__main__":
    main()
