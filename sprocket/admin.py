"""Admin dashboard back end: what the HUMAN can adjust about Otto from /admin.html (behind the same sign-in as the rest of the page).
These messages come only from the page; no model tool can reach anything in this file. It never touches the bank, his gifts or his art. The one thing it may do to the map is place or remove an approved print figurine.
The one destructive control (wiping his memory) needs a typed confirmation and always writes a backup of the database first."""
import shutil
import time

from . import config, printfarm, traits, world, kit

WIPE_TABLES = ("memories", "journal", "thoughts", "interests", "goals", "prefs", "sketches")     # his mind only
NEEDS = ("energy", "battery", "boredom", "creativity")
WEATHERS = ["", "clear", "cloudy", "light rain", "drizzle", "thunderstorm", "foggy", "breezy", "falling leaves", "light snow", "snow", "frosty", "warm and hazy"]


def view(agent):
    """Everything the admin page shows, in one message."""
    s, db = agent.state, agent.db
    wt = world.world_time(s["tick"])
    t = traits.get(db)
    return {
        "type": "admin", "tick": s["tick"], "mood": s["mood"], "paused": bool(s.get("paused")), "sleeping": bool(s.get("sleeping")),
        "needs": {k: round(float(s.get(k, 0)), 1) for k in NEEDS}, "world": wt,
        "weather": world.weather(wt["day"], kit.season_now()), "weather_override": world.OVERRIDE or "", "weathers": WEATHERS, "season": kit.season_now(),
        "dials": t["dials"], "dial_info": {k: {"high": v[1], "low": v[2]} for k, v in traits.DIALS.items()}, "quirks": t["quirks"], "quirk_pool": traits.QUIRKS,
        "omen": s.get("omen"),
        "goals": db.q("SELECT id,text FROM goals WHERE status='active' ORDER BY id"),
        "interests": db.q("SELECT topic,round(strength,1) AS strength FROM interests ORDER BY strength DESC LIMIT 20"),
        "places": {k: {"label": p["label"]} for k, p in world.PLACES.items()},
        "recent": db.q("SELECT tick,tool,substr(result,1,110) AS result FROM actions ORDER BY id DESC LIMIT 10"),
        "prints": printfarm.admin_list(db), "print_ready": printfarm.read_key() is not None or config.PRINT_PROVIDER != "tripo",
        "memories": db.one("SELECT COUNT(*) n FROM memories")["n"], "journal": db.one("SELECT COUNT(*) n FROM journal")["n"],
    }


def apply(agent, runner, t, m):
    """Run one admin message. Returns a short plain-text result for the page's toast, or raises ValueError with a plain message."""
    s, db = agent.state, agent.db
    if t == "admin_needs":
        for k in NEEDS:
            if k in m:
                s[k] = max(0.0, min(100.0, float(m[k])))
        db.control("admin: needs set"); return "Needs updated."
    if t == "admin_refill":
        s["energy"] = s["battery"] = 100.0
        s["boredom"] = min(s["boredom"], 30.0)
        db.control("admin: refilled energy and battery"); return "Refilled his energy and battery."
    if t == "admin_traits":
        traits.set_dials(db, m)
        db.control("admin: traits changed"); return "Character saved."
    if t == "admin_omen":
        text = " ".join(str(m.get("text", "")).split())[:140]
        if not text:
            raise ValueError("Write what the omen says.")
        tone = m.get("tone") if m.get("tone") in ("positive", "negative", "neutral") else "neutral"
        inten = max(0.0, min(1.0, float(m.get("intensity", 0.5))))
        ticks = max(1, min(60, round(float(m.get("seconds", 120)) / max(10.0, runner.interval()))))
        s["omen"] = {"text": text, "tone": tone, "until": s["tick"] + ticks}
        s["mood_valence"] = max(-1.0, min(1.0, s.get("mood_valence", 0.0) + {"positive": 0.18, "negative": -0.18, "neutral": 0.0}[tone] * (0.5 + inten)))   # one small mood nudge
        db.control(f"admin: omen ({tone}) {text[:40]}"); return "Omen sent: he will notice it on his next thoughts."
    if t == "admin_force_think":
        if s.get("sleeping") or s.get("paused"):
            raise ValueError("He is paused or in game mode: resume him first.")
        runner.wake.set(); db.control("admin: force think"); return "He will think now."
    if t == "admin_goal_drop":
        db.x("UPDATE goals SET status='dropped', closed_tick=? WHERE id=? AND status='active'", s["tick"], int(m.get("id", 0)))
        db.control("admin: goal dropped"); return "Goal dropped."
    if t == "admin_interest_drop":
        db.x("DELETE FROM interests WHERE topic=?", str(m.get("topic", "")))
        db.control("admin: interest removed"); return "Interest removed."
    if t == "admin_weather":
        name = str(m.get("name", ""))
        if name not in WEATHERS:
            raise ValueError("Unknown weather.")
        world.OVERRIDE = name
        db.control(f"admin: weather = {name or 'automatic'}"); return f"Weather: {name or 'automatic again'}."
    if t in ("admin_print_approve", "admin_print_reject", "admin_print_remove"):             # the human's side of the print farm; the one place a printed model can enter the world
        fn = {"admin_print_approve": printfarm.approve, "admin_print_reject": printfarm.reject, "admin_print_remove": printfarm.remove}[t]
        return fn(agent, int(m.get("id", 0)))
    if t == "admin_goto":
        p = world.PLACES.get(str(m.get("place", "")))
        if not p:
            raise ValueError("Unknown place.")
        s["x"], s["z"], s["path"] = float(p["x"]), float(p["z"]), []
        s["inside"] = None
        db.control(f"admin: moved Otto to {p['label']}"); return f"Moved him to the {p['label']}."
    if t == "admin_wipe_memory":
        if str(m.get("confirm", "")).strip() != "WIPE":
            raise ValueError('Type WIPE (capital letters) to confirm.')
        backup = config.DB_PATH.parent / "backups"
        backup.mkdir(parents=True, exist_ok=True)
        dest = backup / f"sprocket-before-wipe-{time.strftime('%Y%m%d-%H%M%S')}.db"
        db.c.commit()
        import sqlite3
        out = sqlite3.connect(str(dest))
        try:
            db.c.backup(out)                                           # a consistent copy, even with the database in use
        finally:
            out.close()
        for tbl in WIPE_TABLES:
            db.x(f"DELETE FROM {tbl}")
        for k in ("inspiration", "last_say", "focus", "sky_obs", "omen"):
            s.pop(k, None)
        db.control(f"admin: memory wiped (backup {dest.name})"); return f"Memory wiped. A backup was saved as {dest.name} in data/backups."
    raise ValueError("Unknown admin command.")
