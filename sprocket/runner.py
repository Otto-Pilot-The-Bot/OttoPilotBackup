"""Tick loop with pause / resume / kill. State is saved after every tick."""
import asyncio
import time

from . import config


class Runner:
    def __init__(self, agent, log=print):
        self.agent, self.log = agent, log
        self.stop = asyncio.Event()
        self.wake = asyncio.Event()
        self.current = None   # in-flight tick task
        self._override = None

    def interval(self):
        return float(self._override or self.agent.state.get("interval") or config.TICK_SECONDS)

    def set_interval(self, seconds):
        self._override = None
        self.agent.state["interval"] = max(3.0, min(120.0, float(seconds)))
        self.agent.db.control(f"tick interval {self.agent.state['interval']:.0f}s")
        self.agent.save()
        self.agent._emit("snapshot", {})
        self.wake.set()

    @property
    def paused(self):
        return self.agent.state["paused"]

    def set_paused(self, v):
        self.agent.state["paused"] = bool(v)
        self.agent.db.control("pause" if v else "resume")
        self.agent.save()
        self.agent._emit("snapshot", {})
        self.wake.set()

    def kill(self, why="kill switch"):
        self.agent.db.control(why)
        # if a tick is mid-flight, do NOT save: the last completed tick's state stays authoritative
        if not (self.current and not self.current.done()):
            self.agent.save()
        self.log(f"[{config.NAME}] stopping: {why}")
        self.stop.set()
        self.wake.set()
        if self.current and not self.current.done():
            self.current.cancel()   # abort an in-flight model call

    async def _watch_kill(self):
        while not self.stop.is_set():
            if config.KILL_FILE.exists():
                config.KILL_FILE.unlink(missing_ok=True)
                self.kill("KILL file")
                return
            await asyncio.sleep(0.5)

    async def run(self, max_ticks=None, interval=None):
        self._override = float(interval) if interval else None   # CLI override, not persisted
        n = 0
        self.log(f"[{config.NAME}] awake at tick {self.agent.state['tick']} (model {config.MODEL}, every {self.interval():.0f}s"
                 f"{', PAUSED' if self.paused else ''}). Ctrl-C or `touch KILL` to stop.")
        watcher = asyncio.ensure_future(self._watch_kill())
        while not self.stop.is_set():
            if self.paused:
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), 1.0)
                except asyncio.TimeoutError:
                    pass
                continue
            t0 = time.monotonic()
            self.current = asyncio.ensure_future(self.agent.tick())
            try:
                await self.current
            except asyncio.CancelledError:
                # killed mid-tick: throw away the half-finished tick so state resumes exactly
                self.agent.state = self.agent.db.get("state") or self.agent.state
                break
            except Exception as e:
                self.log(f"  tick error: {type(e).__name__}: {e}")
                self.agent.save()
            n += 1
            if max_ticks and n >= max_ticks:
                break
            self.wake.clear()
            try:
                await asyncio.wait_for(self.wake.wait(), max(0.2, self.interval() - (time.monotonic() - t0)))
            except asyncio.TimeoutError:
                pass
        watcher.cancel()
        self.agent.save()
