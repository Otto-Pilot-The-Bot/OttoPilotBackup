"""SQLite persistence. Everything he thinks, does, searches or feels lands here."""
import json
import sqlite3
import time
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS thoughts(id INTEGER PRIMARY KEY, ts REAL, tick INT, kind TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY, ts REAL, tick INT, tool TEXT, args TEXT,
  result TEXT, ok INT, feeling TEXT, valence REAL);
CREATE TABLE IF NOT EXISTS searches(id INTEGER PRIMARY KEY, ts REAL, tick INT, query TEXT, results TEXT);
CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY, ts REAL, tick INT, kind TEXT, text TEXT, mood TEXT);
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, ts REAL, tick INT, text TEXT, importance INT);
CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY, ts REAL, text TEXT, status TEXT DEFAULT 'active',
  created_tick INT, closed_tick INT);
CREATE TABLE IF NOT EXISTS prefs(subject TEXT PRIMARY KEY, score REAL DEFAULT 0, n INT DEFAULT 0, last_tick INT);
CREATE TABLE IF NOT EXISTS objects(id INTEGER PRIMARY KEY, ts REAL, kind TEXT, name TEXT, x REAL, z REAL,
  color TEXT, source TEXT, meta TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS builds(id INTEGER PRIMARY KEY, ts REAL, tick INT, name TEXT, description TEXT,
  next_goal TEXT, object_id INT);
CREATE TABLE IF NOT EXISTS outfit(slot TEXT PRIMARY KEY, item TEXT, color TEXT);
CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY, ts REAL, title TEXT, body TEXT, status TEXT DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS reads(id INTEGER PRIMARY KEY, ts REAL, tick INT, url TEXT, title TEXT, chars INT, ok INT,
  error TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS art(id INTEGER PRIMARY KEY, ts REAL, tick INT, title TEXT, kind TEXT, mode TEXT, content TEXT,
  statement TEXT, inspiration TEXT, colors TEXT, status TEXT DEFAULT 'ok');
CREATE TABLE IF NOT EXISTS sketches(id INTEGER PRIMARY KEY, ts REAL, tick INT, idea TEXT, used INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, ts REAL, tick INT, name TEXT, description TEXT, stage TEXT,
  color TEXT, object_id INT, status TEXT DEFAULT 'active', last_tick INT, finished_tick INT);
CREATE TABLE IF NOT EXISTS interests(topic TEXT PRIMARY KEY, ts REAL, source TEXT, strength REAL);
CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY, pack TEXT, name TEXT, file TEXT UNIQUE, tags TEXT, sx REAL, sy REAL, sz REAL,
  tris INT, anims TEXT, usable INT, reason TEXT, fit REAL, radius REAL, mtime REAL, size_bytes INT, credit TEXT);
CREATE TABLE IF NOT EXISTS asset_packs(pack TEXT PRIMARY KEY, path TEXT, n INT, usable INT, license TEXT, credit TEXT, source TEXT,
  attribution_required INT, notes TEXT);
CREATE TABLE IF NOT EXISTS blocked_sites(host TEXT PRIMARY KEY, ts REAL, until REAL, reason TEXT, hits INT);
CREATE TABLE IF NOT EXISTS publish_log(id INTEGER PRIMARY KEY, ts REAL, page_id INT, title TEXT, slug TEXT, mode TEXT, ok INT,
  commit_sha TEXT, url TEXT, commit_url TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS designs(id INTEGER PRIMARY KEY, ts REAL, tick INT, name TEXT, kind TEXT, script TEXT, design TEXT, uses INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS tunes(id INTEGER PRIMARY KEY, ts REAL, tick INT, title TEXT, notes TEXT, tempo INT, wave TEXT, interest TEXT);
CREATE TABLE IF NOT EXISTS collection(id INTEGER PRIMARY KEY, ts REAL, tick INT, item TEXT, kind TEXT, place TEXT, color TEXT);
CREATE TABLE IF NOT EXISTS hobbies(id INTEGER PRIMARY KEY, ts REAL, name TEXT UNIQUE, kind TEXT, interest TEXT, last_tick INT);
CREATE TABLE IF NOT EXISTS hobby_entries(id INTEGER PRIMARY KEY, ts REAL, tick INT, hobby_id INT, text TEXT);
CREATE TABLE IF NOT EXISTS controls(id INTEGER PRIMARY KEY, ts REAL, what TEXT);
"""


class DB:
    def __init__(self, path=config.DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(str(path), check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.executescript(SCHEMA)
        cols = [r["name"] for r in self.c.execute("PRAGMA table_info(builds)")]
        if "stage" not in cols:                      # migration for databases made before projects existed
            self.c.execute("ALTER TABLE builds ADD COLUMN stage TEXT")
        for table, col, typ in (("objects", "radius", "REAL"), ("projects", "design", "TEXT"), ("projects", "area", "TEXT"),
                                ("builds", "design", "TEXT"), ("journal", "obj_id", "INT"),
                                ("pages", "slug", "TEXT"), ("pages", "html", "TEXT"), ("pages", "tags", "TEXT"), ("pages", "excerpt", "TEXT"),
                                ("pages", "last_error", "TEXT"), ("pages", "attempts", "INT"), ("pages", "next_try", "REAL"),
                                ("pages", "approved_ts", "REAL"), ("pages", "published_ts", "REAL"), ("pages", "commit_sha", "TEXT"),
                                ("pages", "url", "TEXT"), ("pages", "mode", "TEXT"), ("pages", "submitted_tick", "INT"), ("actions", "cat", "TEXT"), ("interests", "last_tick", "INT"), ("projects", "reason", "TEXT"),
                                ("projects", "review", "TEXT"), ("projects", "review_due", "INT")):
            if col not in [r["name"] for r in self.c.execute(f"PRAGMA table_info({table})")]:
                self.c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self.c.commit()

    # --- generic -------------------------------------------------------
    def q(self, sql, *a):
        return [dict(r) for r in self.c.execute(sql, a).fetchall()]

    def one(self, sql, *a):
        r = self.c.execute(sql, a).fetchone()
        return dict(r) if r else None

    def x(self, sql, *a):
        cur = self.c.execute(sql, a)
        self.c.commit()
        return cur.lastrowid

    # --- kv ------------------------------------------------------------
    def get(self, key, default=None):
        r = self.one("SELECT value FROM kv WHERE key=?", key)
        return json.loads(r["value"]) if r else default

    def put(self, key, value):
        self.x("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               key, json.dumps(value))

    # --- logging helpers ----------------------------------------------
    def thought(self, tick, kind, text):
        return self.x("INSERT INTO thoughts(ts,tick,kind,text) VALUES(?,?,?,?)", time.time(), tick, kind, text)

    def control(self, what):
        self.x("INSERT INTO controls(ts,what) VALUES(?,?)", time.time(), what)
