"""python -m sprocket run [--ticks N] [--interval S]   headless terminal loop
   python -m sprocket serve                             loop + 3D page at http://127.0.0.1:8765
   python -m sprocket journal | status | reset"""
import argparse
import asyncio
import signal
import sys

from . import config
from .agent import Agent
from .db import DB
from .runner import Runner


def main():
    p = argparse.ArgumentParser(prog="sprocket")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--ticks", type=int); r.add_argument("--interval", type=float)
    sv = sub.add_parser("serve"); sv.add_argument("--interval", type=float)
    sub.add_parser("journal"); sub.add_parser("status")
    a = p.parse_args()
    db = DB()
    if a.cmd == "journal":
        for j in db.q("SELECT tick,kind,mood,text FROM journal ORDER BY id"):
            print(f"[t{j['tick']} {j['kind']} / {j['mood']}] {j['text']}\n")
        return
    if a.cmd == "status":
        ag = Agent(db)
        s = ag.state
        print(f"tick {s['tick']}  mood {s['mood']}  energy {s['energy']:.0f}  battery {s['battery']:.0f}  boredom {s['boredom']:.0f}  paused={s['paused']}")
        for g in db.q("SELECT id,text FROM goals WHERE status='active'"): print(f"  goal #{g['id']}: {g['text']}")
        for q in db.q("SELECT subject,round(score,1) score FROM prefs ORDER BY score DESC"): print(f"  taste {q['subject']}: {q['score']}")
        return
    agent = Agent(db)
    runner = Runner(agent)
    asyncio.run(go(a, agent, runner))


async def go(a, agent, runner):
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: runner.kill("signal"))
    if a.cmd == "serve":
        from .server import serve
        await serve(agent, runner, a.interval)
    else:
        await runner.run(a.ticks, a.interval)


if __name__ == "__main__":
    main()
