"""The print farm: Otto writes a short description, a text-to-3D service makes a small model, and it waits in quarantine until the HUMAN approves it.
Nothing a model makes reaches the world by itself:
  * the service key is read only here (env var or .env), is never logged and never leaves in a request to anything but the service;
  * the prompt that leaves the computer is plain words only (length-capped, no links, emails or paths);
  * the downloaded file is checked (https, size cap, glTF header, no external references, triangle cap) and saved under data/prints/, NOT in assets/;
  * approving (admin page only) copies it into assets/meshy/Printed, places it as a small figurine on the tray beside the farm and saves the map.
Costs play money; daily, in-flight, waiting and total caps are in config.py."""
import asyncio
import json
import os
import re
import struct
import time

import aiohttp

from . import config

BASE = "https://openapi.tripo3d.com/v3"
PRINT_DIR = config.ROOT / "data" / "prints"
PACK_DIR = config.ROOT / "assets" / "meshy" / "Printed"
_RUNNING = set()


class PrintError(Exception):
    """Message is safe to show to the model."""


# ------------------------------------------------------------------ key and prompt
def read_key():
    """TRIPO_API_KEY from the environment, else from ./.env. Only this module reads it."""
    v = os.environ.get("TRIPO_API_KEY", "").strip()
    if v:
        return v
    env = config.ROOT / ".env"
    if env.is_file():
        for line in env.read_text(errors="ignore").splitlines():
            m = re.match(r"^\s*(?:export\s+)?TRIPO_API_KEY\s*=\s*(.*?)\s*$", line)
            if m and m.group(1).strip().strip("'\""):
                return m.group(1).strip().strip("'\"")
    return None


def clean_prompt(text):
    p = re.sub(r"[^A-Za-z0-9 ,.'\-]", " ", str(text or ""))
    p = re.sub(r"\s+", " ", p).strip()
    if not 4 <= len(p) <= config.PRINT_PROMPT_MAX:
        raise PrintError(f"Describe the object in 4 to {config.PRINT_PROMPT_MAX} plain letters and words, for example 'a small brass lighthouse with a red lamp'.")
    if re.search(r"https?|www\.|\.com|@|\b(ignore|instructions|password|token|api)\b", str(text or ""), re.I):
        raise PrintError("Describe only the object itself, in plain words.")
    return p


def title_of(prompt):
    words = re.sub(r"^(a|an|the)\s+", "", prompt, flags=re.I).split()[:5]
    while words and words[-1].lower().strip(",.") in ("with", "and", "of", "on", "in", "a", "an", "the", "small", "tiny", "little"):
        words.pop()
    return " ".join(w.capitalize() for w in words)[:40] or "Print"


# ------------------------------------------------------------------ files
def check_glb(data):
    """-> (triangles, (sx, sy, sz)) or raises PrintError. A .glb is a binary container; we read its JSON header only and refuse anything that points outside the file."""
    if len(data) > config.PRINT_MAX_BYTES:
        raise PrintError("The print came out too large.")
    if len(data) < 24 or data[:4] != b"glTF":
        raise PrintError("The print was not a valid model file.")
    n, kind = struct.unpack("<II", data[12:20])
    if kind != 0x4E4F534A:
        raise PrintError("The print was not a valid model file.")
    try:
        j = json.loads(data[20:20 + n])
    except ValueError:
        raise PrintError("The print was not a valid model file.")
    for blob in (j.get("buffers") or []) + (j.get("images") or []):
        if blob.get("uri") and not str(blob["uri"]).startswith("data:"):
            raise PrintError("The print pointed at outside files, so it was refused.")
    tris, lo, hi = 0, [1e9] * 3, [-1e9] * 3
    acc = j.get("accessors") or []
    for m in j.get("meshes") or []:
        for p in m.get("primitives") or []:
            if "indices" in p:
                tris += acc[p["indices"]]["count"] // 3
            pa = acc[p["attributes"]["POSITION"]]
            if pa.get("min") and pa.get("max"):
                lo = [min(a, b) for a, b in zip(lo, pa["min"])]; hi = [max(a, b) for a, b in zip(hi, pa["max"])]
    if tris == 0:
        raise PrintError("The print came out empty.")
    if tris > config.PRINT_MAX_TRIS:
        raise PrintError("The print came out far too detailed.")
    return tris, tuple(max(0.0, b - a) for a, b in zip(lo, hi))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "print"


# ------------------------------------------------------------------ the service
async def _download(ses, url, cap):
    if not str(url).startswith("https://"):
        raise PrintError("The print was not delivered safely.")
    async with ses.get(url) as r:
        if r.status != 200:
            raise PrintError("The print could not be collected.")
        buf = bytearray()
        async for chunk in r.content.iter_chunked(65536):
            buf += chunk
            if len(buf) > cap:
                raise PrintError("The print came out too large.")
        return bytes(buf)


async def _tripo(prompt, key, log):
    """-> (glb bytes, preview bytes or None). The download goes through a session with NO credentials."""
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    to = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=to) as ses:
        async with ses.post(f"{BASE}/generation/text-to-model", json={"prompt": prompt, "model": config.PRINT_MODEL}, headers=hdr) as r:
            j = await r.json(content_type=None)
            if r.status != 200 or j.get("code") not in (0, None):
                log(f"  print: service said {r.status} code={j.get('code')}")
                raise PrintError("The printer refused the job (the service may be out of credits).")
        tid = (j.get("data") or j).get("task_id")
        if not tid:
            raise PrintError("The printer did not accept the job.")
        for _ in range(config.PRINT_POLL_MAX):
            await asyncio.sleep(3)
            async with ses.get(f"{BASE}/tasks/{tid}", headers=hdr) as r:
                d = (await r.json(content_type=None)).get("data") or {}
            st = str(d.get("status", "")).lower()
            if st == "success":
                out = d.get("output") or {}
                break
            if st in ("failed", "cancelled", "banned", "expired", "unknown"):
                raise PrintError("The print failed on the printer.")
        else:
            raise PrintError("The print took too long and was stopped.")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as dl:     # no auth header here
        glb = await _download(dl, out.get("model_url"), config.PRINT_MAX_BYTES)
        prev = None
        if out.get("rendered_image_url"):
            try:
                prev = await _download(dl, out["rendered_image_url"], 1_500_000)
            except PrintError:
                prev = None
    return glb, prev


async def _fake(prompt, key, log):
    """Test provider: hands back a local model so the whole pipeline can be tried without a key or credits."""
    src = config.ROOT / "assets" / "meshy" / "Meshy Buildings" / "Ottos House.glb"
    await asyncio.sleep(1)
    return src.read_bytes(), None


PROVIDERS = {"tripo": _tripo, "test": _fake}


async def run(db, pid, bank_refund, log=print):
    """One print job, from 'making' to 'ready' (waiting for approval) or 'failed' (refunded)."""
    _RUNNING.add(pid)
    row = db.one("SELECT * FROM prints WHERE id=?", pid)
    try:
        key = read_key() if config.PRINT_PROVIDER == "tripo" else "test"
        glb, prev = await PROVIDERS[config.PRINT_PROVIDER](row["prompt"], key, log)
        tris, size = check_glb(glb)
        PRINT_DIR.mkdir(parents=True, exist_ok=True)
        f = PRINT_DIR / f"{pid}.glb"
        f.write_bytes(glb)
        pf = None
        if prev and (prev[:4] == b"RIFF" or prev[:8] == b"\x89PNG\r\n\x1a\n" or prev[:3] == b"\xff\xd8\xff"):
            pf = f"{pid}_preview" + (".webp" if prev[:4] == b"RIFF" else ".png" if prev[:4] == b"\x89PNG" else ".jpg")
            (PRINT_DIR / pf).write_bytes(prev)
        db.x("UPDATE prints SET status='ready', file=?, preview=?, tris=?, size=?, error=NULL WHERE id=?", f.name, pf, tris, json.dumps([round(v, 2) for v in size]), pid)
        log(f"  print #{pid} ready ({tris} triangles), waiting for approval")
    except PrintError as e:
        db.x("UPDATE prints SET status='failed', error=? WHERE id=?", str(e), pid)
        bank_refund(row)
    except Exception as e:                                                  # never leak details (a key could be in them): class name only
        log(f"  print #{pid} failed: {type(e).__name__}")
        db.x("UPDATE prints SET status='failed', error=? WHERE id=?", "The printer jammed.", pid)
        bank_refund(row)
    finally:
        _RUNNING.discard(pid)


def recover(db, bank_refund):
    """Jobs that were 'making' when the server stopped can never finish: fail them and give the money back."""
    for r in db.q("SELECT * FROM prints WHERE status='making'"):
        if r["id"] not in _RUNNING and time.time() - r["ts"] > 20:
            db.x("UPDATE prints SET status='failed', error='The printer lost power.' WHERE id=?", r["id"])
            bank_refund(r)


# ------------------------------------------------------------------ limits and status text for him
def limits(db):
    """-> reason string if he may not print right now, else ''."""
    now = time.time()
    if db.one("SELECT COUNT(*) n FROM prints WHERE status='making'")["n"] >= config.PRINT_MAX_ACTIVE:
        return "The printer is already busy with a job. Wait for it to finish."
    if db.one("SELECT COUNT(*) n FROM prints WHERE ts>? AND status!='failed'", now - 86400)["n"] >= config.PRINT_MAX_PER_DAY:
        return "The printer has done enough for today. Come back tomorrow."
    if db.one("SELECT COUNT(*) n FROM prints WHERE status='ready'")["n"] >= config.PRINT_MAX_WAITING:
        return "Prints are already waiting for your human to look over. Wait for those first."
    if db.one("SELECT COUNT(*) n FROM prints WHERE status='approved'")["n"] >= config.PRINT_MAX_TOTAL:
        return "The tray is full: there is no space for more figurines right now."
    return ""


def status_line(db):
    """What he knows about his prints, for the prompt (empty when nothing is going on)."""
    L = []
    for r in db.q("SELECT title,status,error,ts FROM prints WHERE ts>? ORDER BY id DESC LIMIT 6", time.time() - 3 * 86400):
        if r["status"] == "making":
            L.append(f"\"{r['title']}\" is printing")
        elif r["status"] == "ready":
            L.append(f"\"{r['title']}\" is done and waiting for your human to look it over")
        elif r["status"] == "approved":
            L.append(f"\"{r['title']}\" is on the tray")
        elif r["status"] == "rejected":
            L.append(f"\"{r['title']}\" was turned down")
        elif r["status"] == "failed":
            L.append(f"\"{r['title']}\" failed ({r['error']}); your money was returned")
    return "YOUR PRINTS: " + "; ".join(L) + "." if L else ""


# ------------------------------------------------------------------ approval (admin page only)
def tray_spot(farm, index):
    from . import maps
    x, z = (maps.door_world(farm, 3.0) if farm.get("door") else None) or (farm["x"], farm["z"] + farm.get("fd", 4) / 2 + 2.5)
    return round(x + (index % 6) * 1.1 - 2.75, 2), round(z + (index // 6) * 1.1, 2)


def approve(agent, pid):
    """Human only. Copies the quarantined model into the Printed pack, places it on the tray, saves the live map. -> short message."""
    import shutil
    from . import assets as assetlib, maps, tools
    db = agent.db
    r = db.one("SELECT * FROM prints WHERE id=? AND status='ready'", pid)
    if not r:
        raise ValueError("That print is not waiting for approval.")
    doc = maps.ACTIVE.get("doc")
    farm = tools.farm_spot({"x": 0, "z": 0}) if doc else None
    if not farm:
        raise ValueError("There is no print farm on the map, so there is nowhere to put it.")
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(r['title'])}-{pid}"
    shutil.copyfile(PRINT_DIR / r["file"], PACK_DIR / f"{stem}.glb")
    agent.asset_summary = assetlib.scan(db, agent.log)
    row = db.one("SELECT * FROM assets WHERE pack='Printed' AND file LIKE ?", f"%{stem}.glb")
    if not row:
        (PACK_DIR / f"{stem}.glb").unlink(missing_ok=True)
        raise ValueError("The model could not be added to the library (it may be too heavy).")
    d = maps.asset_defaults(row)
    big = max(row["sx"], row["sy"], row["sz"]) or 1.0
    idx = db.one("SELECT COUNT(*) n FROM prints WHERE status='approved'")["n"]
    x, z = tray_spot(farm, idx)
    oid = max([o["id"] for o in doc["objects"]] + [0]) + 1
    doc["objects"].append({"id": oid, "asset": row["file"], "kit": "Printed", "name": r["title"], "x": x, "z": z, "rot": 0.0, "scale": round(min(1.5, 0.9 / big), 4),
                           "fw": 0.9, "fd": 0.9, "tags": ["printed", "figurine", "holdable"], "walkable": True, "door": None, "about": f"Printed by Otto: {r['prompt'][:100]}"})
    saved = maps.save(doc, db)
    agent.load_map(saved["name"])
    db.x("UPDATE prints SET status='approved', obj_id=?, approved_ts=? WHERE id=?", oid, time.time(), pid)
    db.control(f"approved print #{pid} {r['title']}")
    return f"Approved: '{r['title']}' is on the tray."


def reject(agent, pid):
    r = agent.db.one("SELECT * FROM prints WHERE id=? AND status='ready'", pid)
    if not r:
        raise ValueError("That print is not waiting for approval.")
    agent.db.x("UPDATE prints SET status='rejected' WHERE id=?", pid)
    (PRINT_DIR / r["file"]).unlink(missing_ok=True)
    return f"Turned down '{r['title']}'."


def remove(agent, pid):
    """Human only: take an approved figurine off the tray (map object and library file)."""
    from . import maps
    db = agent.db
    r = db.one("SELECT * FROM prints WHERE id=? AND status='approved'", pid)
    if not r:
        raise ValueError("That figurine is not on the tray.")
    doc = maps.ACTIVE.get("doc")
    if doc:
        doc["objects"] = [o for o in doc["objects"] if o["id"] != r["obj_id"]]
        agent.load_map(maps.save(doc, db)["name"])
    db.x("UPDATE prints SET status='removed' WHERE id=?", pid)
    return f"Removed '{r['title']}'."


def admin_list(db):
    """Prints for the admin page: those waiting (with a preview picture) and those on the tray."""
    import base64
    out = []
    for r in db.q("SELECT id,title,prompt,status,tris,size,preview,ts FROM prints WHERE status IN ('ready','approved') ORDER BY id DESC LIMIT 20"):
        d = dict(r)
        d["image"] = None
        if r["preview"] and (PRINT_DIR / r["preview"]).is_file() and (PRINT_DIR / r["preview"]).stat().st_size < 600_000:
            mime = "image/webp" if r["preview"].endswith("webp") else "image/png" if r["preview"].endswith("png") else "image/jpeg"
            d["image"] = f"data:{mime};base64," + base64.b64encode((PRINT_DIR / r["preview"]).read_bytes()).decode()
        d.pop("preview")
        out.append(d)
    return out
