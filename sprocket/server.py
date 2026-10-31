"""aiohttp server: static 3D page + WebSocket. Bound to localhost only."""
import asyncio
import base64
import hashlib
import html
import json
import re
import time

from aiohttp import web, WSMsgType

from . import assets as assetlib, config, layout, world

WEB = config.ROOT / "web"


async def serve(agent, runner, interval=None):
    clients = set()
    loop_task = None

    def push(msg):
        data = json.dumps(msg)
        for ws in list(clients):
            if ws.closed:
                clients.discard(ws)
                continue
            asyncio.ensure_future(_send(ws, data))

    async def _send(ws, data):
        try:
            await ws.send_str(data)
        except Exception:
            clients.discard(ws)

    agent.listeners.append(push)

    async def ws_handler(request):
        if request.headers.get("Origin") and not re.match(rf"^https?://(127\.0\.0\.1|localhost):{config.PORT}$", request.headers["Origin"]):
            return web.Response(status=403)
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        clients.add(ws)
        await ws.send_str(json.dumps(agent.snapshot()))
        async for m in ws:
            if m.type != WSMsgType.TEXT:
                continue
            try:
                handle(json.loads(m.data), ws)
            except Exception as e:
                agent.log(f"  ui message error: {e}")
        clients.discard(ws)
        return ws

    def handle(m, ws=None):
        t, s, db = m.get("type"), agent.state, agent.db
        if t == "set_interval":
            runner.set_interval(float(m.get("seconds", config.TICK_SECONDS)))
        elif t == "get_log" and ws is not None:
            asyncio.ensure_future(_send(ws, json.dumps({"type": "log", "rows": agent.raw_log(int(min(300, max(10, m.get("limit", 150)))))})))
        elif t == "get_art" and ws is not None:
            ids = [int(i) for i in (m.get("ids") or [])[:12]]
            for r in db.q(f"SELECT id,kind,mode,content FROM art WHERE id IN ({','.join('?' * len(ids))})", *ids) if ids else []:
                asyncio.ensure_future(_send(ws, json.dumps({"type": "art_content", **r})))
        elif t == "art_result":
            a = db.one("SELECT id,title,status FROM art WHERE id=?", int(m.get("id", 0)))
            if a and not m.get("ok") and a["status"] == "ok":       # the browser could not draw it: tell him, hide it
                err = re.sub(r"\s+", " ", str(m.get("error", "")))[:150]
                db.x("UPDATE art SET status='broken' WHERE id=?", a["id"])
                txt = f"Your artwork \"{a['title']}\" could not be drawn ({err}). Simpler code usually works."
                db.x("INSERT INTO actions(ts,tick,tool,args,result,ok,feeling,valence) VALUES(?,?,?,?,?,?,?,?)", time.time(), s["tick"],
                     "system", "{}", txt, 0, s["mood"], 0)
                db.thought(s["tick"], "system", txt)
                push(agent.snapshot())
        elif t == "pause":
            runner.set_paused(True)
        elif t == "resume":
            runner.set_paused(False)
        elif t == "kill":
            runner.kill("kill switch (UI)")
        elif t == "toggle_publish":
            s["publish_enabled"] = bool(m.get("on"))
            db.control(f"publish_enabled={s['publish_enabled']}")
            agent.save(); push(agent.snapshot())
        elif t == "place_object":
            kind = m.get("kind") if m.get("kind") in world.KINDS else "other"
            if len(agent.objects()) >= config.MAX_OBJECTS:
                return
            name = re.sub(r"[^\w \-']", "", str(m.get("name") or kind))[:24].strip() or kind
            col = m.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(m.get("color", ""))) else "#9e9e9e"
            r = layout.KIND_RADIUS.get(kind, 1.2)
            (x, z), _ = agent.place_near(world.clamp(float(m.get("x", 0))), world.clamp(float(m.get("z", 0))), r)   # engine avoids overlaps
            oid = db.x("INSERT INTO objects(ts,kind,name,x,z,color,source,radius) VALUES(?,?,?,?,?,?,'user',?)", time.time(), kind, name, x, z, col, r)
            agent.note_gift(name, kind, x, z)
            db.thought(s["tick"], "system", f"The human placed a {kind} called '{name}' at ({x:.0f},{z:.0f}).")
            db.control(f"placed {kind} {name} #{oid}")
            agent.save()
            push(agent.snapshot())
        elif t == "rescan_assets":
            agent.asset_summary = assetlib.scan(db, agent.log)
            db.control(f"rescanned assets: {agent.asset_summary['total']} files")
            push(agent.snapshot())
        elif t in ("approve_page", "reject_page"):
            p = db.one("SELECT * FROM pages WHERE id=? AND status='pending'", int(m.get("id", 0)))
            if not p:
                return
            if t == "approve_page":
                # "Approved" = exported as a static file inside ./published. Nothing is uploaded anywhere.
                config.PUBLISH_DIR.mkdir(exist_ok=True)
                slug = re.sub(r"[^a-z0-9]+", "-", p["title"].lower()).strip("-")[:40] or "page"
                (config.PUBLISH_DIR / f"{p['id']}-{slug}.html").write_text(
                    f"<!doctype html><meta charset=utf-8><title>{html.escape(p['title'])}</title>"
                    f"<h1>{html.escape(p['title'])}</h1><p>{html.escape(p['body']).replace(chr(10), '<br>')}</p>")
            db.x("UPDATE pages SET status=? WHERE id=?", "approved" if t == "approve_page" else "rejected", p["id"])
            db.control(f"{t} #{p['id']}")
            push(agent.snapshot())

    index_html = (WEB / "index.html").read_text()
    m_ = re.search(r'<script type="importmap">(.*?)</script>', index_html, re.S)
    imap_hash = base64.b64encode(hashlib.sha256(m_.group(1).encode()).digest()).decode() if m_ else ""
    origin = f"{config.HOST}:{config.PORT}"
    CSP_PAGE = ("default-src 'none'; script-src 'self' 'sha256-%s'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "connect-src 'self' blob: ws://%s ws://localhost:%d; frame-src 'self'; worker-src 'self' blob:; "
                "base-uri 'none'; form-action 'none'; object-src 'none'" % (imap_hash, origin, config.PORT))
    # The art sandbox: no network at all, may run blob workers (where drawing code lives), may post a PNG back to its parent.
    CSP_SANDBOX = "default-src 'none'; script-src 'self' blob:; worker-src blob:; img-src data: blob:; base-uri 'none'; form-action 'none'"

    @web.middleware
    async def security_headers(request, handler):
        resp = await handler(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path in ("/", "/index.html"):
            resp.headers["Content-Security-Policy"] = CSP_PAGE
            resp.headers["Cache-Control"] = "no-store"
        elif request.path == "/art-sandbox.html":
            resp.headers["Content-Security-Policy"] = CSP_SANDBOX
        elif request.path.endswith((".js", ".html", ".css")):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    async def asset_file(request):
        """Serves ONLY files that the scanner indexed as usable models, never an arbitrary path."""
        try:
            row = agent.db.one("SELECT file FROM assets WHERE id=? AND usable=1", int(request.match_info["id"]))
        except ValueError:
            row = None
        if not row:
            return web.Response(status=404)
        path = (config.ROOT / row["file"]).resolve()
        roots = [d.resolve() for d in assetlib.asset_dirs()]
        if path.suffix.lower() != ".glb" or not path.is_file() or not any(r in path.parents for r in roots):
            return web.Response(status=404)
        return web.FileResponse(path, headers={"Content-Type": "model/gltf-binary", "Cache-Control": "max-age=3600"})

    async def index(_):
        return web.FileResponse(WEB / "index.html")

    app = web.Application(middlewares=[security_headers])
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/asset/{id}", asset_file)
    app.router.add_static("/", WEB, show_index=False)
    ar = web.AppRunner(app)
    await ar.setup()
    await web.TCPSite(ar, config.HOST, config.PORT).start()
    agent.log(f"[{config.NAME}] world at http://{config.HOST}:{config.PORT}")
    try:
        await runner.run(interval=interval)
    finally:
        for ws in list(clients):
            await ws.close()
        await ar.cleanup()
