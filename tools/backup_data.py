"""Makes one zip of everything Otto needs that is NOT in git: his database (safe snapshot via the sqlite3 backup API, since the DB runs in WAL mode),
maps, gifts, library notes, and the Meshy models. It never includes .env, tokens, logs or the old before-*.db copies.
Run with the project venv:   .venv\\Scripts\\python.exe tools\\backup_data.py [output_folder]
Default output: <project>\\backup\\OttoPilot-data-YYYYMMDD-HHMM.zip   (backup/ is git-ignored).
The Kenney model packs (assets/kenney) are not included: their licence is unknown, so copy that folder by hand if you move machines."""
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "backup"
OUT.mkdir(parents=True, exist_ok=True)
SKIP_NAMES = {"server.log", "publish_errors.log", "sprocket.db", "sprocket.db-shm", "sprocket.db-wal", "blender_materials.txt"}


def main():
    zpath = OUT / f"OttoPilot-data-{time.strftime('%Y%m%d-%H%M')}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "sprocket.db"
        src = sqlite3.connect(ROOT / "data" / "sprocket.db")
        dst = sqlite3.connect(snap)
        src.backup(dst)                                   # consistent copy even while the server is running
        dst.close(); src.close()
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "data/sprocket.db")
            for sub in ("data/maps", "data/gifts", "data/library"):
                for f in (ROOT / sub).rglob("*"):
                    if f.is_file():
                        z.write(f, f.relative_to(ROOT).as_posix())
            for f in (ROOT / "data").glob("*"):
                if f.is_file() and f.name not in SKIP_NAMES and not f.name.startswith("before-") and f.suffix in (".json", ".txt"):
                    z.write(f, f.relative_to(ROOT).as_posix())
            for f in (ROOT / "assets" / "meshy").rglob("*.glb"):
                z.write(f, f.relative_to(ROOT).as_posix())
    print(f"{zpath}  ({zpath.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
