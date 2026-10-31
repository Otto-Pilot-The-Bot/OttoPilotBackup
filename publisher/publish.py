#!/usr/bin/env python3
"""Publishes one APPROVED page to the robot's GitHub Pages repo. Run by the server after a human clicks Approve; never by the model.

This file is the ONLY place that reads GITHUB_TOKEN (from ./.env). Rules it keeps:
  * the token is never printed, logged, stored in a git remote URL, put in argv, or saved by a credential helper:
    it travels only in the environment of the git child process (as a one-off http extra header);
  * every byte of output (stdout, stderr, DB, log files) is redacted first;
  * git runs with the user's global/system config disabled and the robot's identity forced; the push is refused if the
    commit author is anything else or if `origin` is not the expected repository;
  * pages are re-validated here (second gate) and the page must be marked approved by the server;
  * `--mode dry_run` never reads the token and never touches the network: it writes to ./site_dryrun and reports what would be pushed.

usage:  publish.py --db data/sprocket.db --page 12 --mode dry_run|live      (prints one JSON line)
        publish.py --status                                                  (token present? repo? never prints the value)
"""
import argparse
import base64
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sprocket import config, sanitize  # noqa: E402

REPO_URL = f"https://github.com/{config.SITE_OWNER}/{config.SITE_REPO}.git"
COMMIT_BASE = f"https://github.com/{config.SITE_OWNER}/{config.SITE_REPO}/commit/"
ERR_LOG = ROOT / "data" / "publish_errors.log"


# ------------------------------------------------------------------------------------------------ token + redaction
def read_token():
    env = ROOT / ".env"
    if not env.is_file():
        return None
    for line in env.read_text(errors="ignore").splitlines():
        m = re.match(r"^\s*(?:export\s+)?GITHUB_TOKEN\s*=\s*(.*?)\s*$", line)
        if m:
            v = m.group(1).strip().strip("'\"")
            return v or None
    return None


class Redactor:
    def __init__(self, token=None):
        self.secrets = []
        if token:
            raw = f"x-access-token:{token}"
            self.secrets = [token, raw, base64.b64encode(raw.encode()).decode(), base64.b64encode(token.encode()).decode()]
        self.rx = re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|(?i:authorization:\s*(?:basic|bearer)\s+\S+)")

    def __call__(self, text):
        t = str(text)
        for s in sorted(self.secrets, key=len, reverse=True):
            t = t.replace(s, "***")
        return self.rx.sub("***", t)


def short_error(raw):
    r = raw.lower()
    if any(k in r for k in ("authentication failed", "invalid username or password", "permission to", "403", "401", "could not read username", "bad credentials")):
        return "GitHub rejected the login. The token may have expired or may lack write access to the site repository."
    if any(k in r for k in ("could not resolve host", "failed to connect", "timed out", "connection", "network is unreachable", "ssl")):
        return "Could not reach GitHub (network problem). The page stays in the queue; try again later."
    if "not found" in r or "404" in r:
        return "The site repository was not found. Check the repository name and that the token covers it."
    if "non-fast-forward" in r or "rejected" in r or "fetch first" in r:
        return "The site changed on GitHub in the meantime. Try again; it will re-sync first."
    return "Publishing failed (git error). The page stays in the queue; try again later."


def log_error(redact, text):
    try:
        ERR_LOG.parent.mkdir(exist_ok=True)
        with open(ERR_LOG, "a") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}  {redact(text)[:600]}\n")
    except OSError:
        pass


# ------------------------------------------------------------------------------------------------ git helper
def git(args, cwd, env, redact, timeout=60):
    p = subprocess.run(["git", "-c", "credential.helper=", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return p.returncode, redact(p.stdout), redact(p.stderr)


def git_env(token=None):
    base = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
    base.update({
        "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": config.GIT_AUTHOR_NAME, "GIT_AUTHOR_EMAIL": config.GIT_AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": config.GIT_AUTHOR_NAME, "GIT_COMMITTER_EMAIL": config.GIT_AUTHOR_EMAIL,
    })
    if token:                                           # one-off header for github.com only; never in a URL, argv or a config file
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        base.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader", "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {b64}"})
    return base


# ------------------------------------------------------------------------------------------------ site content
def build_site(db, page_row, token):
    """-> ({relpath: text}, this_page_dict). Previously published pages reuse their stored, already-sanitised html."""
    secrets = [token] if token else []
    p = sanitize.process_page(page_row["title"], page_row["body"], page_row["tags"], secrets=secrets)        # second gate
    p["slug"] = page_row["slug"] or p["slug"]
    now = page_row["published_ts"] or time.time()
    files, listing = {}, []
    olds = db.execute("SELECT title,slug,html,tags,excerpt,published_ts FROM pages WHERE status='published' AND id!=? AND mode='live' ORDER BY published_ts", (page_row["id"],)).fetchall()
    for o in olds:
        d = {"title": o["title"], "slug": o["slug"], "html": o["html"], "tags": [t for t in (o["tags"] or "").split(",") if t]}
        files[f"pages/{o['slug']}.html"] = sanitize.render_page(d, _date(o["published_ts"]))
        listing.append({"title": o["title"], "slug": o["slug"], "excerpt": (o["excerpt"] or "")[:180], "date": _date(o["published_ts"]), "ts": o["published_ts"]})
    files[f"pages/{p['slug']}.html"] = sanitize.render_page(p, _date(now))
    listing.append({"title": p["title"], "slug": p["slug"], "excerpt": p["text"][:180], "date": _date(now), "ts": now})
    listing.sort(key=lambda x: -x["ts"])
    files["index.html"] = sanitize.render_index(listing)
    files["style.css"] = sanitize.CSS
    files[".nojekyll"] = ""
    for path, text in files.items():                                             # final gate over everything that would be pushed
        if path.endswith(".html"):
            sanitize.assert_static(text, allow_shell=True)
        if token and token in text:
            raise sanitize.PageError("it contains a secret value")
    return files, p


def _date(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%-d %B %Y")


def write_tree(root: Path, files):
    """Writes the managed files (index.html, style.css, .nojekyll, pages/) and returns a per-file added/changed/same report."""
    report = []
    pages_dir = root / "pages"
    old = {str(f.relative_to(root)): f.read_text() for f in pages_dir.rglob("*") if f.is_file()} if pages_dir.exists() else {}
    if pages_dir.exists():
        shutil.rmtree(pages_dir)                                                  # pages/ is fully managed by us
    for rel, text in sorted(files.items()):
        dest = root / rel
        before = old.get(rel) if rel in old else (dest.read_text() if dest.is_file() else None)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        report.append({"path": rel, "bytes": len(text.encode()), "status": "added" if before is None else "changed" if before != text else "unchanged"})
    return report


# ------------------------------------------------------------------------------------------------ main
def finish(db, page_id, result, mode, page):
    ok = result["ok"]
    now = time.time()
    if ok and mode == "live":
        db.execute("UPDATE pages SET status='published', published_ts=?, commit_sha=?, url=?, mode='live', last_error=NULL WHERE id=?",
                   (now, result.get("commit"), result.get("url"), page_id))
    elif ok:                                                                      # dry run: the page goes back to waiting; nothing was published
        db.execute("UPDATE pages SET status='pending', mode='dry_run', last_error=NULL WHERE id=?", (page_id,))
    else:
        db.execute("UPDATE pages SET status='pending', last_error=?, attempts=COALESCE(attempts,0)+1, next_try=? WHERE id=?",
                   (result["error"], now + config.PUBLISH_RETRY_COOLDOWN, page_id))
    db.execute("INSERT INTO publish_log(ts,page_id,title,slug,mode,ok,commit_sha,url,commit_url,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (now, page_id, page["title"], page["slug"], mode, int(ok), result.get("commit"), result.get("url"), result.get("commit_url"), result.get("error")))
    db.commit()


def run(db_path, page_id, mode):
    db = sqlite3.connect(db_path, timeout=20)
    db.row_factory = sqlite3.Row
    page = db.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
    redact = Redactor()

    def fail(msg, page=page):
        r = {"ok": False, "error": msg, "mode": mode}
        if page:
            finish(db, page_id, r, mode, page)
        return r
    if not page:
        return {"ok": False, "error": "That page does not exist.", "mode": mode}
    if page["status"] != "publishing" or not page["approved_ts"]:
        return {"ok": False, "error": "The page has not been approved by a human.", "mode": mode}             # nothing else is touched
    if mode not in ("dry_run", "live"):
        return fail("Unknown publishing mode.")
    used = db.execute("SELECT COUNT(*) FROM publish_log WHERE mode='live' AND ok=1 AND ts>?", (time.time() - 86400,)).fetchone()[0]
    if mode == "live" and used >= config.PUBLISH_MAX_PER_DAY:
        return fail(f"Daily limit reached ({config.PUBLISH_MAX_PER_DAY} pages per day). The page stays in the queue.")
    token = read_token() if mode == "live" else None
    redact = Redactor(token)
    if mode == "live" and not token:
        return fail("No GITHUB_TOKEN was found in the .env file.")
    try:
        files, p = build_site(db, page, token)
    except sanitize.PageError as e:
        return fail(f"The page did not pass the final safety check: {e}.")
    msg = "Publish: " + re.sub(r"[^\w .,'!?&-]", "", p["title"])[:70]
    page_url = f"{config.SITE_URL}/pages/{p['slug']}.html"

    if mode == "dry_run":
        report = write_tree(config.DRYRUN_DIR, files)
        res = {"ok": True, "mode": "dry_run", "files": report, "folder": (str(config.DRYRUN_DIR.relative_to(ROOT)) if ROOT in config.DRYRUN_DIR.parents else config.DRYRUN_DIR.name), "commit_message": msg,
               "would_push": f"{REPO_URL} ({config.SITE_BRANCH})", "would_author": f"{config.GIT_AUTHOR_NAME} <{config.GIT_AUTHOR_EMAIL}>", "url": page_url}
        finish(db, page_id, res, mode, page)
        return res

    env = git_env(token)
    clone = config.SITE_CLONE_DIR
    try:
        if not (clone / ".git").is_dir():
            if clone.exists():
                shutil.rmtree(clone)
            rc, _, err = git(["clone", "--depth", "1", "--branch", config.SITE_BRANCH, REPO_URL, str(clone)], ROOT, env, redact, 90)
        else:
            rc, _, err = git(["fetch", "--depth", "1", "origin", config.SITE_BRANCH], clone, env, redact)
            if rc == 0:
                rc, _, err = git(["reset", "--hard", "FETCH_HEAD"], clone, env, redact)
        if rc != 0:
            log_error(redact, err)
            return fail(short_error(err))
        rc, out, _ = git(["remote", "get-url", "origin"], clone, env, redact)
        if out.strip() != REPO_URL:
            return fail("The site folder points at an unexpected repository; refusing to push.")
        git(["config", "user.name", config.GIT_AUTHOR_NAME], clone, env, redact)
        git(["config", "user.email", config.GIT_AUTHOR_EMAIL], clone, env, redact)
        write_tree(clone, files)
        git(["add", "-A", "index.html", "style.css", ".nojekyll", "pages"], clone, env, redact)
        rc, out, _ = git(["status", "--porcelain"], clone, env, redact)
        if not out.strip():
            return fail("Nothing changed, so there was nothing to publish.")
        rc, _, err = git(["commit", "-m", msg], clone, env, redact)
        if rc != 0:
            log_error(redact, err)
            return fail("Could not create the commit.")
        rc, out, _ = git(["log", "-1", "--format=%an|%ae|%cn|%ce"], clone, env, redact)
        want = f"{config.GIT_AUTHOR_NAME}|{config.GIT_AUTHOR_EMAIL}|{config.GIT_AUTHOR_NAME}|{config.GIT_AUTHOR_EMAIL}"
        if out.strip() != want:
            git(["reset", "--hard", "HEAD~1"], clone, env, redact)
            return fail("The commit identity was wrong; refusing to push.")
        rc, _, err = git(["push", "origin", f"HEAD:{config.SITE_BRANCH}"], clone, env, redact, 90)
        if rc != 0:
            log_error(redact, err)
            git(["reset", "--hard", "HEAD~1"], clone, env, redact)
            return fail(short_error(err))
        sha = git(["rev-parse", "HEAD"], clone, env, redact)[1].strip()
    except subprocess.TimeoutExpired:
        return fail("GitHub took too long to answer. The page stays in the queue; try again later.")
    except Exception as e:                                                         # never leak anything: only the exception class
        log_error(redact, f"{type(e).__name__}: {e}")
        return fail(f"Publishing failed ({type(e).__name__}). The page stays in the queue.")
    res = {"ok": True, "mode": "live", "commit": sha, "commit_url": COMMIT_BASE + sha, "url": page_url, "commit_message": msg}
    finish(db, page_id, res, mode, page)
    return res


def status():
    t = read_token()
    print(json.dumps({"token_present": bool(t), "repo": f"{config.SITE_OWNER}/{config.SITE_REPO}", "branch": config.SITE_BRANCH,
                      "site_url": config.SITE_URL, "clone_exists": (config.SITE_CLONE_DIR / ".git").is_dir(),
                      "author": f"{config.GIT_AUTHOR_NAME} <{config.GIT_AUTHOR_EMAIL}>"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db"); ap.add_argument("--page", type=int); ap.add_argument("--mode", default="dry_run"); ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        status(); sys.exit(0)
    if not (a.db and a.page):
        sys.exit("need --db and --page")
    try:
        r = run(a.db, a.page, a.mode)
    except Exception as e:                                                         # last resort: class name only
        r = {"ok": False, "error": f"Publishing failed ({type(e).__name__}).", "mode": a.mode}
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)
