"""Brain bench: run Otto for N ticks on a COPY of the live database with one model, and record what he did.

    python tools/brain_bench.py <model> [--ticks 30] [--think low] [--ctx 4096] [--out data/bench]

The live database is never touched (it is copied with sqlite's backup API, so a running server is fine).
Tools that reach outside the computer (web search, page reading, publishing, 3D printing) are removed for the run.
Every run starts from the same copy, so models are compared from the same life situation.
"""
import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTSIDE = {"search_web", "read_page", "publish_page", "print3d"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--ticks", type=int, default=30)
    ap.add_argument("--think", default="low")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--out", default=str(ROOT / "data" / "bench"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = a.model.replace(":", "_").replace("/", "_") + f"_ctx{a.ctx}_{a.think}"
    dbcopy = out / f"{tag}.db"
    for p in out.glob(f"{tag}.db*"):
        p.unlink()
    src = sqlite3.connect(f"file:{ROOT / 'data' / 'sprocket.db'}?mode=ro", uri=True)
    dst = sqlite3.connect(dbcopy)
    src.backup(dst); src.close(); dst.close()

    os.environ.update(OLLAMA_HOST="http://127.0.0.1:11434", SPROCKET_DB=str(dbcopy), SPROCKET_MODEL=a.model, SPROCKET_FALLBACK=a.model,
                      SPROCKET_THINK=a.think, SPROCKET_NUM_CTX=str(a.ctx), SPROCKET_KEEP_ALIVE="10m")
    sys.path.insert(0, str(ROOT))
    from sprocket import config, tools
    from sprocket.agent import Agent
    from sprocket.db import DB
    if a.think.lower() in ("false", "off", "0"):
        config.THINK_MAIN = False
    config.PRINT_ENABLED = False
    real_schemas = tools.schemas
    tools.schemas = lambda *x, **k: [t for t in real_schemas(*x, **k) if t["function"]["name"] not in OUTSIDE]

    logs = []
    db = DB()
    ag = Agent(db, log=lambda *m: logs.append(" ".join(str(x) for x in m)))
    events = []
    ag.listeners.append(lambda e: events.append(e))
    base = {t: (db.one(f"SELECT MAX(id) m FROM {t}") or {}).get("m") or 0 for t in ("actions", "journal", "memories", "goals", "thoughts")}
    rows = []
    t_all = time.time()

    async def go():
        for i in range(a.ticks):
            n0 = len(events)
            t0 = time.time()
            try:
                await ag.tick()
            except Exception as e:
                rows.append({"i": i, "error": f"{type(e).__name__}: {str(e)[:160]}", "secs": round(time.time() - t0, 1)})
                continue
            acts = [e for e in events[n0:] if e.get("type") == "action" or "tool" in (e.get("data") or e)]
            act = None
            for e in events[n0:]:
                d = e.get("data", e)
                if isinstance(d, dict) and "tool" in d:
                    act = d
            rows.append({"i": i, "secs": round(time.time() - t0, 1), "tool": (act or {}).get("tool"),
                         "ok": (act or {}).get("ok"), "result": str((act or {}).get("result", ""))[:160],
                         "say": str((act or {}).get("say", ""))[:300]})
            print(f"[{tag}] {i + 1}/{a.ticks} {rows[-1]['secs']}s {rows[-1]['tool']} ok={rows[-1]['ok']}", flush=True)
    asyncio.run(go())

    d2 = DB()
    new = lambda t: (base[t] if t in base else 0)
    summary = {
        "model": a.model, "ctx": a.ctx, "think": a.think, "ticks": a.ticks, "wall_secs": round(time.time() - t_all),
        "actions": d2.q("SELECT tick,tool,args,result,ok FROM actions WHERE id>? ORDER BY id", new("actions")),
        "journal": d2.q("SELECT tick,kind,mood,text FROM journal WHERE id>? ORDER BY id", new("journal")),
        "memories": d2.q("SELECT tick,text,importance FROM memories WHERE id>? ORDER BY id", new("memories")),
        "goals": d2.q("SELECT text,status FROM goals WHERE id>? ORDER BY id", new("goals")),
        "thoughts": d2.q("SELECT tick,kind,text FROM thoughts WHERE id>? ORDER BY id", new("thoughts")),
        "rows": rows, "log_tail": logs[-40:],
    }
    (out / f"{tag}.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out / f"{tag}.json")


def _has(db, name):
    return bool(db.one("SELECT 1 FROM sqlite_master WHERE name=?", name))


if __name__ == "__main__":
    main()
