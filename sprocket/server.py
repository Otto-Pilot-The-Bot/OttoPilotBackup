"""aiohttp server: static 3D page + WebSocket. Bound to localhost only."""
import asyncio
import os
import base64
import sys
import hashlib
import hmac
import html
import json
import re
import time

from aiohttp import web, WSMsgType

from . import admin as adminlib, assets as assetlib, maps as maplib, starter as starterlib, config, design, gifts as giftlib, kit, layout, world

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
    seen_rev = [getattr(agent, "map_rev", 0)]

    def _watch_map(ev):                                  # he walked into a building that has an interior (or back out): the page must switch maps too
        r = getattr(agent, "map_rev", 0)
        if r != seen_rev[0]:
            seen_rev[0] = r
            push(map_msg())
    agent.listeners.append(_watch_map)

    if config.REMOTE and len(config.TOKEN) < 16:
        raise SystemExit("SPROCKET_HOST is set to a non-local address, so SPROCKET_TOKEN is required (at least 16 random characters). Nothing was started.")
    AUTH_VAL = hashlib.sha256(("sprocket-auth:" + config.TOKEN).encode()).hexdigest()

    def origin_ok(request, required=False):
        """The page must be this very site: Origin equals the address it was loaded from (or, on this computer, localhost)."""
        o = request.headers.get("Origin", "")
        if not o:
            return not required
        if o in (f"http://{request.host}", f"https://{request.host}"):
            return True
        return (not config.REMOTE) and bool(re.match(rf"^https?://(127\.0\.0\.1|localhost):{config.PORT}$", o))

    @web.middleware
    async def auth(request, handler):
        """Only when the server can be reached from other computers: a secret token (set once through ?token=..., then kept in a cookie)."""
        if not config.REMOTE:
            return await handler(request)
        if hmac.compare_digest(request.cookies.get("sprocket_auth", "").encode(), AUTH_VAL.encode()):
            return await handler(request)
        t = request.query.get("token", "")
        if t and hmac.compare_digest(t.encode(), config.TOKEN.encode()):
            resp = web.HTTPFound(request.path)                      # the token leaves the address bar
            resp.set_cookie("sprocket_auth", AUTH_VAL, httponly=True, samesite="Strict", max_age=60 * 60 * 24 * 30)
            raise resp
        return web.Response(status=401, text="Sign-in needed: open this address once with ?token=<your token> on the end.")

    async def ws_handler(request):
        if not origin_ok(request):
            return web.Response(status=403)
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        clients.add(ws)
        await ws.send_str(json.dumps(agent.snapshot()))
        if config.MAPS_ENABLED:
            await ws.send_str(json.dumps(map_msg()))
        async for m in ws:
            if m.type != WSMsgType.TEXT:
                continue
            try:
                handle(json.loads(m.data), ws)
            except Exception as e:
                agent.log(f"  ui message error: {e}")
        clients.discard(ws)
        return ws

    def map_msg():
        """The live map for the page (each model object gets its current asset id so the page can fetch /asset/<id>)."""
        doc = maplib.ACTIVE["doc"]
        if not doc:
            return {"type": "map", "doc": None, "maps": maplib.list_maps()}
        ids = {r["file"]: r for r in agent.db.q("SELECT id,file,fit FROM assets WHERE usable=1")}
        d = dict(doc, objects=[dict(o, aid=(ids.get(o["asset"]) or {"id": None})["id"], fit=(ids.get(o["asset"]) or {"fit": 1.0})["fit"]) for o in doc["objects"]])
        bright = {r["id"]: config.kit_bright(r["pack"], r["name"]) for r in agent.db.q("SELECT id,pack,name FROM assets WHERE usable=1 AND pack LIKE 'Meshy%'") if config.kit_bright(r["pack"], r["name"]) != 1.0}
        nav = ["".join("1" if c else "0" for c in row) for row in maplib.ACTIVE["blocked"]]
        cars = [{"aid": r["id"], "fit": r["fit"], "name": r["name"]} for r in agent.db.q(
            "SELECT id,fit,name FROM assets WHERE usable=1 AND pack='Car Kit' AND name IN ('sedan','taxi','van','hatchback-sports','suv') ORDER BY name")]
        return {"type": "map", "doc": d, "bright": bright, "nav": nav, "traffic": cars, "warnings": maplib.ACTIVE.get("warnings", []), "maps": maplib.list_maps(), "active": agent.db.get("active_map"), "rev": getattr(agent, "map_rev", 0)}

    def map_edit_msg(name):
        """A map to EDIT while Otto stays where he is (an interior, say). It is built the same way, then the live map is put back."""
        doc = maplib.load(name)
        prev = maplib.ACTIVE["doc"]
        maplib.activate(doc)
        try:
            msg = map_msg()
        finally:
            if prev:
                maplib.activate(prev)
        msg["edit"] = True
        return msg

    def map_handle(t, m, ws):
        """Map editing. HUMAN ONLY: these messages come from the page's Plan editor; no model tool can reach maplib's writers."""
        db = agent.db
        try:
            if t == "get_map":
                if ws is not None:
                    asyncio.ensure_future(_send(ws, json.dumps(map_msg())))
                return
            if t == "map_edit":
                if ws is not None:
                    asyncio.ensure_future(_send(ws, json.dumps(map_edit_msg(str(m.get("name", ""))))))
                return
            if t == "map_load":
                maplib.load(str(m.get("name", "")))
                agent.load_map(str(m.get("name"))); db.control(f"map loaded: {m.get('name')}")
            elif t == "map_save":
                doc = maplib.save(m.get("doc"), db)
                if m.get("use", True):
                    agent.load_map(doc["name"])
                db.control(f"map saved: {doc['name']} ({len(doc['objects'])} objects)")
                toast(f"Saved map '{doc['name']}'." + ("" if m.get("use", True) else " Otto stays where he is."))
                if not m.get("use", True) and ws is not None:                 # editing a map he is not in: keep showing it
                    asyncio.ensure_future(_send(ws, json.dumps(map_edit_msg(doc["name"]))))
                    return
            elif t == "map_new":
                nm = str(m.get("name", "")).strip()
                new = maplib.blank(nm, int(m.get("n", 20)))
                if m.get("interior"):                                           # a room: walls at +-8 m, the way in/out on the front (+z) side
                    new["bounds"] = {"x0": -8, "z0": -8, "x1": 8, "z1": 8}; new["exit"] = {"x": 0, "z": 6}
                doc = maplib.save(new, db)
                db.control(f"map created: {nm}")
                if m.get("edit") and ws is not None:                            # open it for editing without moving Otto
                    asyncio.ensure_future(_send(ws, json.dumps(map_edit_msg(doc["name"]))))
                    return
                agent.load_map(doc["name"])
            elif t == "map_city":
                from . import city as citylib
                doc = citylib.ensure(db, force=True); agent.load_map(doc["name"]); db.control("city map generated"); toast("City map generated and loaded.")
            elif t == "map_starter":
                doc = starterlib.ensure(db, force=True); agent.load_map(doc["name"]); db.control("starter map regenerated")
                toast("Starter map regenerated.")
            agent.save(); push(agent.snapshot()); push(map_msg())
        except ValueError as e:
            toast(str(e), False)

    def handle(m, ws=None):
        t, s, db = m.get("type"), agent.state, agent.db
        if t in ("get_map", "map_edit", "map_load", "map_save", "map_new", "map_starter", "map_city") and config.MAPS_ENABLED:
            return map_handle(t, m, ws)
        if t == "admin_get":                                    # the admin page (HUMAN ONLY, same sign-in as everything else; no model tool can reach sprocket/admin.py)
            if ws is not None:
                asyncio.ensure_future(_send(ws, json.dumps(adminlib.view(agent))))
            return
        if isinstance(t, str) and t.startswith("admin_"):
            try:
                toast(adminlib.apply(agent, runner, t, m))
            except (ValueError, TypeError) as e:
                toast(str(e), False)
            agent.save(); push(agent.snapshot()); push(adminlib.view(agent))
            return
        if t in ("place_object", "place_design") and config.MAPS_ENABLED:
            return toast("Placing now happens in the Plan editor (the 🗺️ Plan button, bottom left).", False)
        if t == "set_pace":
            name = m.get("name")
            if name in config.PACE_PRESETS:
                s["pace"] = name
                db.control(f"pace = {name}")
                runner.set_interval(config.PACE_PRESETS[name]["interval"])
        elif t == "set_interval":
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
        elif t == "game_mode":
            asyncio.ensure_future(runner.set_sleeping(bool(m.get("on"))))
        elif t == "visitor":                                    # the page tells him someone is walking around his world (walk mode); sent every second or so while they are
            try:
                x, z, here = float(m.get("x", 0)), float(m.get("z", 0)), bool(m.get("here", True))
            except (TypeError, ValueError):
                return
            old = getattr(agent, "visitor", None)
            arrived = here and not (old and old["here"] and time.time() - old["seen"] < 10)
            agent.visitor = {"here": here, "x": x, "z": z, "seen": time.time(), "since": s["tick"] if arrived else (old or {}).get("since", s["tick"])}
            if arrived and not runner.paused:
                db.control("a visitor started walking around his world")
                runner.wake.set()                               # he notices straight away instead of waiting out the thinking interval
            return
        elif t == "pause":
            runner.set_paused(True)
        elif t == "resume":
            runner.set_paused(False)
        elif t == "kill":
            runner.kill("kill switch (UI)")
        elif t in ("bank_grant", "bank_take") and config.BANK_ENABLED:
            # HUMAN ONLY: money entering or leaving Otto's world. No model tool can reach these.
            from . import bank as bnk
            try:
                cents = bnk.parse_amount(m.get("amount"))
                if t == "bank_grant":
                    bnk.grant(db, cents, str(m.get("memo") or "Gift from your human")[:80], s["tick"], bnk.ACCOUNT if m.get("to") == "account" else bnk.WALLET)
                    toast(f"Gave Otto {bnk.fmt(cents)}.")
                else:
                    bnk.take_back(db, cents, "Taken back by your human", s["tick"])
                    toast(f"Took {bnk.fmt(cents)} back.")
                db.control(f"{t} {bnk.fmt(cents)}")
            except bnk.BankError as e:
                toast(str(e), False)
            push(agent.snapshot())
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
            agent.note_gift(name, kind, x, z, oid)
            db.thought(s["tick"], "system", f"The human placed a {kind} called '{name}' at ({x:.0f},{z:.0f}).")
            db.control(f"placed {kind} {name} #{oid}")
            agent.save()
            push(agent.snapshot())
        elif t == "get_assets" and ws is not None:
            rows = [dict(r, tags=json.loads(r["tags"])[:8]) for r in db.q("SELECT id,name,pack,tags,sx,sy,sz,fit,tris,file,cat,fw,fd,door_x,door_z FROM assets WHERE usable=1 ORDER BY pack,name")]
            asyncio.ensure_future(_send(ws, json.dumps({"type": "assets", "rows": rows, "kit": kit.spec_json() if config.KIT_ENABLED else {}, "zones": [{"key": k, "label": z["label"]} for k, z in layout.ZONES.items()]})))
        elif t == "design_preview" and ws is not None:
            try:
                d = design.clean_design(db, gen=m.get("gen"), gparams=m.get("params") if isinstance(m.get("params"), dict) else {})
                asyncio.ensure_future(_send(ws, json.dumps({"type": "design_preview", "key": str(m.get("key", "")), "design": d})))
            except design.DesignError as e:
                asyncio.ensure_future(_send(ws, json.dumps({"type": "toast", "ok": False, "text": str(e)})))
        elif t == "place_design":
            place_design(m)
        elif t in ("object_move", "object_rotate", "object_scale", "object_remove"):
            edit_object(t, m)
        elif t in ("wish_fulfil", "wish_decline", "wish_hide"):
            wish_action(t, m)
        elif t == "delete_gift":
            if giftlib.delete(db, int(m.get("id", 0))):
                db.control(f"deleted gift #{m.get('id')}")
                agent.save(); push(agent.snapshot())
        elif t == "rescan_assets":
            agent.asset_summary = assetlib.scan(db, agent.log)
            db.control(f"rescanned assets: {agent.asset_summary['total']} files")
            push(agent.snapshot())
        elif t == "approve_page":
            asyncio.ensure_future(approve(int(m.get("id", 0))))
        elif t == "reject_page":
            p = db.one("SELECT id,title FROM pages WHERE id=? AND status='pending'", int(m.get("id", 0)))
            if p:
                db.x("UPDATE pages SET status='rejected' WHERE id=?", p["id"])
                db.control(f"rejected page #{p['id']}")
                notice("Page rejected. It will not be published.", True)
        elif t == "set_publish_mode":
            mode = m.get("mode")
            if mode == "live" and not (agent.site_status or {}).get("token_present"):
                notice("Cannot go live: no GitHub token was found in the .env file.", False)
            elif mode in ("dry_run", "live"):
                s["publish_mode"] = mode
                db.control(f"publish mode = {mode}")
                notice("Dry run: nothing will be uploaded; files are written to site_dryrun/." if mode == "dry_run" else
                       "LIVE: approved pages will be pushed to the website.", True)
        elif t == "check_site":
            asyncio.ensure_future(check_site())

    def toast(text, ok=True):
        push({"type": "toast", "text": text, "ok": ok})

    def spot(m, radius, group):
        """Where something goes: a clicked spot or zone, nudged by the engine so nothing overlaps - unless 'exact' (for assembling pieces)."""
        snap = float(m["snap"]) if str(m.get("snap") or "0") in ("0.5", "1", "1.0", "2") else 0.0
        sn = (lambda v: round(v / snap) * snap) if snap else (lambda v: v)
        try:
            x0, z0 = sn(world.clamp(float(m["x"]))), sn(world.clamp(float(m["z"])))
        except (KeyError, TypeError, ValueError):
            zk = m.get("zone") if m.get("zone") in layout.ZONES else "open_field"
            x0, z0 = layout.ZONES[zk]["c"]
            if not m.get("zone"):
                x0, z0 = None, None
        if m.get("exact") and x0 is not None:
            return round(max(-world.half() + 0.5, min(world.half() - 0.5, x0)), 2), round(max(-world.half() + 0.5, min(world.half() - 0.5, z0)), 2)
        if x0 is None:
            x0, z0 = layout.ZONES[layout.default_zone_for({group})]["c"]
        (x, z), _ = agent.place_near(x0, z0, radius, group=group)
        return x, z

    def place_design(m):
        """Human-only: place a model from the asset library or a kit building/prop, with scale, rotation, tint and spot."""
        db, s = agent.db, agent.state
        try:
            if m.get("src") == "kit":
                if not config.KIT_ENABLED:
                    return toast("The procedural kits are switched off (STYLE.md: Kenney models only).", False)
                d = design.clean_design(db, gen=m.get("gen"), gparams=m.get("params") if isinstance(m.get("params"), dict) else {}, scale=m.get("scale"), rotation=m.get("rot"), color=m.get("color"))
                base = str(m.get("gen")).replace("_", " ").title()
            else:
                row = db.one("SELECT id,name FROM assets WHERE id=? AND usable=1", int(m.get("asset", 0)))
                if not row:
                    return toast("Choose a model first.", False)
                d = design.clean_design(db, asset=row["id"], scale=m.get("scale"), rotation=m.get("rot"), color=m.get("color"))
                base = row["name"]
        except (design.DesignError, ValueError, TypeError) as e:
            return toast(str(e), False)
        name = re.sub(r"[^\w \-']", "", str(m.get("name") or base)).strip()[:30] or base
        x, z = spot(m, d["radius"] + (0.05 if m.get("exact") else 0.3), layout.group_of(name))
        meta = {"stage": "finished", "description": "Placed by you", "design": d}
        oid = db.x("INSERT INTO objects(ts,kind,name,x,z,color,source,meta,radius) VALUES(?,?,?,?,?,?,'user',?,?)", time.time(), "creation", name, x, z, "#9e9e9e", json.dumps(meta), d["radius"] + 0.05)
        agent.note_gift(name, "creation", x, z, oid)
        db.thought(s["tick"], "system", f"Your human placed a {name} at ({x:.0f},{z:.0f}).")
        db.control(f"placed {name} #{oid}"); agent.save()
        push(agent.snapshot()); toast(f"Placed {name}.")

    def edit_object(t, m):
        """Human-only edits of things YOU placed (or gifts set out): move, rotate, resize, remove. His own world features are not touched."""
        db = agent.db
        o = db.one("SELECT * FROM objects WHERE id=? AND source IN ('user','gift')", int(m.get("id", 0)))
        if not o:
            return toast("That item cannot be edited.", False)
        meta = json.loads(o["meta"] or "{}")
        if t == "object_remove":
            db.x("DELETE FROM objects WHERE id=?", o["id"])
            db.x("UPDATE gifts SET status='kept', obj_id=NULL WHERE obj_id=?", o["id"])
            db.x("UPDATE wishes SET obj_id=NULL WHERE obj_id=?", o["id"])
            db.control(f"removed {o['name']} #{o['id']}")
        elif t == "object_move":
            try:
                x, z = spot({**m, "exact": bool(m.get("exact"))}, o["radius"] or 1.0, layout.group_of(o["name"]))
            except Exception:
                return toast("Could not move it there.", False)
            db.x("UPDATE objects SET x=?, z=? WHERE id=?", x, z, o["id"])
        else:
            d = meta.get("design")
            if not d:
                return toast("This item cannot be rotated or resized.", False)
            if t == "object_rotate":
                d["rot"] = round((float(d.get("rot", 0)) + float(m.get("deg", 45))) % 360, 1)
            else:
                f = max(0.5, min(2.0, float(m.get("factor", 1.1))))
                new = max(0.3, min(3.0, float(d.get("scale", 1.0)) * f))
                db.x("UPDATE objects SET radius=? WHERE id=?", max(0.4, (o["radius"] or 1.0) * new / float(d.get("scale", 1.0))), o["id"])
                d["scale"] = round(new, 3)
            db.x("UPDATE objects SET meta=? WHERE id=?", json.dumps(meta), o["id"])
        agent.save(); push(agent.snapshot())

    def wish_result(text, ok):
        push({"type": "wish_result", "text": text, "ok": ok, "ts": time.time()})
        push(agent.snapshot())

    def wish_action(t, m):
        """Answering a wish. Fulfil places a model from the asset library (the engine picks the spot unless one was clicked); decline is gentle."""
        db, s = agent.db, agent.state
        w = db.one("SELECT * FROM wishes WHERE id=?", int(m.get("id", 0)))
        if not w:
            return
        if t == "wish_hide":
            db.x("UPDATE wishes SET hidden=1 WHERE id=?", w["id"])
            return wish_result("Hidden from your list. Otto is not told.", True)
        if w["status"] != "open":
            return wish_result("That wish has already been answered.", False)
        if t == "wish_decline":
            db.x("UPDATE wishes SET status='declined', resolved_ts=?, notified=1 WHERE id=?", time.time(), w["id"])
            agent.wish_event("declined", w); db.control(f"wish declined #{w['id']}"); agent.save()
            return wish_result(f"Told Otto \"not now\" about \"{w['item']}\".", True)
        if config.MAPS_ENABLED:                              # you placed it yourself in the Plan editor; pick which object it is so Otto is told
            from . import maps as _maps
            o = next((x for x in (_maps.ACTIVE["doc"] or {"objects": []})["objects"] if x["id"] == int(m.get("map_obj", 0) or 0)), None)
            if not o:
                return wish_result("Pick the object you placed for this wish (in the list, or click it in the world).", False)
            db.x("UPDATE wishes SET status='granted', resolved_ts=?, asset_name=? WHERE id=?", time.time(), o["name"][:60], w["id"])
            agent.wish_event("granted", w, None, where=o)
            db.thought(s["tick"], "system", f"Your human granted a wish: {w['item']} (it is the {o['name']} at {o['x']:.0f},{o['z']:.0f}).")
            db.control(f"wish granted #{w['id']} -> map object #{o['id']} {o['name']}"); agent.save()
            return wish_result(f"Granted! Otto has been told that \"{w['item']}\" is the {o['name']}.", True)
        aid = m.get("asset") or w["asset_id"]
        row = db.one("SELECT id,name,tags FROM assets WHERE id=? AND usable=1", int(aid)) if str(aid or "").isdigit() else None
        if not row:
            return wish_result("Choose a model from the library first.", False)
        try:
            d = design.clean_design(db, asset=row["id"], scale=m.get("scale"))
        except design.DesignError as e:
            return wish_result(f"Could not place that model: {e}", False)
        try:
            x0, z0 = (world.clamp(float(m["x"])), world.clamp(float(m["z"]))) if m.get("x") is not None else (None, None)
        except (TypeError, ValueError):
            x0 = z0 = None
        if x0 is None:
            zk = m.get("zone") if m.get("zone") in layout.ZONES else layout.default_zone_for(set(json.loads(row["tags"])) | {layout.group_of(w["item"])})
            x0, z0 = layout.ZONES[zk]["c"]
        (x, z), _ = agent.place_near(x0, z0, d["radius"] + 0.3, group=layout.group_of(w["item"]))
        name = re.sub(r"[^\w \-']", "", w["item"])[:30] or row["name"]
        meta = {"stage": "finished", "description": f"Granted wish: {w['item']}", "design": d, "wish_id": w["id"]}
        oid = db.x("INSERT INTO objects(ts,kind,name,x,z,color,source,meta,radius) VALUES(?,?,?,?,?,?,'user',?,?)", time.time(), "creation", name, x, z, "#9e9e9e", json.dumps(meta), d["radius"] + 0.3)
        db.x("UPDATE wishes SET status='granted', resolved_ts=?, obj_id=?, asset_id=?, asset_name=? WHERE id=?", time.time(), oid, row["id"], row["name"], w["id"])
        agent.attract(oid, name, "creation", 1.0)
        agent.wish_event("granted", w, oid)
        db.thought(s["tick"], "system", f"Your human granted a wish: {w['item']}.")
        db.control(f"wish granted #{w['id']} ({row['name']})"); agent.save()
        wish_result(f"Granted! \"{w['item']}\" is now in his world.", True)

    def notice(text, ok):
        agent.state["site_notice"] = {"text": text, "ok": ok, "ts": time.time()}
        agent.save()
        push(agent.snapshot())

    async def check_site():
        """Asks the publisher whether a token exists. The answer is yes/no only; the token never reaches this process."""
        try:
            proc = await asyncio.create_subprocess_exec(sys.executable, str(config.ROOT / "publisher" / "publish.py"), "--status",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, cwd=str(config.ROOT))
            out, _ = await asyncio.wait_for(proc.communicate(), 20)
            agent.site_status = json.loads(out.decode().strip().splitlines()[-1])
        except Exception:
            agent.site_status = {"token_present": False, "error": "could not run the publisher"}
        push(agent.snapshot())

    publish_lock = asyncio.Lock()

    async def approve(pid):
        db, s = agent.db, agent.state
        now = time.time()
        if not s["publish_enabled"]:
            return notice("Publishing is switched off. Turn it on first; nothing was sent.", False)
        if publish_lock.locked():
            return notice("Another page is being published right now. Try again in a moment.", False)
        async with publish_lock:
            p = db.one("SELECT * FROM pages WHERE id=? AND status='pending'", pid)
            if not p:
                return
            if (p["next_try"] or 0) > now:
                return notice(f"That page failed a moment ago. Please wait {int(p['next_try'] - now)}s before trying again.", False)
            mode = s.get("publish_mode", config.PUBLISH_MODE_DEFAULT)
            db.x("UPDATE pages SET status='publishing', approved_ts=? WHERE id=?", now, pid)       # the human's approval, recorded
            db.control(f"approved page #{pid} ({mode})")
            push(agent.snapshot())
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
            res = None
            try:
                proc = await asyncio.create_subprocess_exec(sys.executable, str(config.ROOT / "publisher" / "publish.py"), "--db", str(config.DB_PATH),
                                                            "--page", str(pid), "--mode", mode, stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.DEVNULL, cwd=str(config.ROOT), env=env)
                out, _ = await asyncio.wait_for(proc.communicate(), config.PUBLISH_TIMEOUT)
                res = json.loads(out.decode().strip().splitlines()[-1])
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                res = {"ok": False, "error": "Publishing took too long. The page stays in the queue; try again later."}
            except Exception:
                res = {"ok": False, "error": "Publishing could not run. The page stays in the queue."}
            if not res.get("ok") and db.one("SELECT status FROM pages WHERE id=?", pid)["status"] == "publishing":    # script died before recording
                db.x("UPDATE pages SET status='pending', last_error=?, attempts=COALESCE(attempts,0)+1, next_try=? WHERE id=?",
                     str(res.get("error"))[:200], time.time() + config.PUBLISH_RETRY_COOLDOWN, pid)
            title = (db.one("SELECT title FROM pages WHERE id=?", pid) or {}).get("title", "")
            if res.get("ok") and res.get("mode") == "live":
                notice(f"Published \u201c{title}\u201d: {res.get('url')}", True)
            elif res.get("ok"):
                notice("Dry run complete: the files were written to site_dryrun/ and nothing was uploaded.", True)
            else:
                notice("Not published: " + str(res.get("error", "unknown problem"))[:200], False)
            db.control(f"publish #{pid} {mode} ok={bool(res.get('ok'))}")
            if res.get("ok") and config.BANK_ENABLED and config.PAGE_REWARD_CENTS > 0:
                from . import bank
                try:
                    bank.post(db, bank.MINT, bank.WALLET, config.PAGE_REWARD_CENTS, "grant", f"Thank-you for your page: {title}"[:120], actor="human", tick=s["tick"], idem=f"page:{pid}:approved")
                    db.x("INSERT INTO memories(ts,tick,text,importance) VALUES(?,?,?,?)", time.time(), s["tick"], f"My human approved my page \"{title}\" and added a small thank-you of {bank.fmt(config.PAGE_REWARD_CENTS)}."[:220], 3)
                    db.thought(s["tick"], "system", f"Your human approved your page \"{title}\" and left you a small thank-you ({bank.fmt(config.PAGE_REWARD_CENTS)}).")
                except Exception:
                    pass

    index_html = (WEB / "index.html").read_text()
    m_ = re.search(r'<script type="importmap">(.*?)</script>', index_html, re.S)
    imap_hash = base64.b64encode(hashlib.sha256(m_.group(1).encode()).digest()).decode() if m_ else ""
    def csp_page(host):                                  # `host` is the address the page was loaded from (the socket must go to that same place)
        return ("default-src 'none'; script-src 'self' 'sha256-%s'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "connect-src 'self' blob: ws://%s%s; frame-src 'self'; worker-src 'self' blob:; "
                "base-uri 'none'; form-action 'none'; object-src 'none'" % (imap_hash, host, "" if config.REMOTE else " ws://localhost:%d" % config.PORT))
    # The art sandbox: no network at all, may run blob workers (where drawing code lives), may post a PNG back to its parent.
    CSP_SANDBOX = "default-src 'none'; script-src 'self' blob:; worker-src blob:; img-src data: blob:; base-uri 'none'; form-action 'none'"

    @web.middleware
    async def security_headers(request, handler):
        resp = await handler(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path in ("/", "/index.html", "/admin.html", "/sandbox", "/sandbox.html"):
            resp.headers["Content-Security-Policy"] = csp_page(request.host)
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
        return web.FileResponse(path, headers={"Content-Type": "model/gltf-binary", "Cache-Control": "no-cache"})

    async def gift_file(request):
        """Serves a stored (already cleaned) gift by id, with a fixed content type. Nothing else is ever served from data/gifts."""
        try:
            row = agent.db.one("SELECT file,mime FROM gifts WHERE id=?", int(request.match_info["id"]))
        except ValueError:
            row = None
        if not row or row["mime"] not in ("image/png", "image/jpeg", "model/gltf-binary"):
            return web.Response(status=404)
        path = giftlib.GIFT_DIR / row["file"]
        if not path.is_file() or path.parent.resolve() != giftlib.GIFT_DIR.resolve():
            return web.Response(status=404)
        return web.FileResponse(path, headers={"Content-Type": row["mime"], "Cache-Control": "no-cache"})

    async def gift_upload(request):
        """Local-only upload. The page must be on this machine (Origin check + a custom header a foreign page cannot send)."""
        j = lambda ok, **k: web.json_response({"ok": ok, **k}, status=200 if ok else 400)
        if not origin_ok(request, True) or request.headers.get("X-Gift-Upload") != "1":
            return web.json_response({"ok": False, "error": "Uploads are only accepted from this page."}, status=403)
        if request.content_length and request.content_length > giftlib.MAX_MODEL + 2_000_000:
            return j(False, error="That file is too big.")
        fields, data, filename = {}, None, ""
        try:
            reader = await request.multipart()
            async for part in reader:
                if part.name == "file":
                    filename, buf = part.filename or "", bytearray()
                    while True:
                        chunk = await part.read_chunk(1 << 16)
                        if not chunk:
                            break
                        buf += chunk
                        if len(buf) > giftlib.MAX_MODEL + 1:
                            return j(False, error=f"That file is too big (limit {giftlib.MAX_IMAGE // 1_000_000} MB for pictures, {giftlib.MAX_MODEL // 1_000_000} MB for 3D models).")
                    data = bytes(buf)
                elif part.name in ("name", "note"):
                    fields[part.name] = (await part.text())[:400]
        except Exception:
            return j(False, error="The upload could not be read.")
        if not data:
            return j(False, error="No file was received.")
        try:
            prepared = await asyncio.get_running_loop().run_in_executor(None, giftlib.prepare, filename, data)
            gid = giftlib.store(agent.db, prepared, fields.get("name"), fields.get("note"), filename, agent.state["tick"])
        except giftlib.GiftError as e:
            return j(False, error=str(e))
        row = agent.db.one("SELECT name,kind FROM gifts WHERE id=?", gid)
        agent.db.thought(agent.state["tick"], "system", f"Your human left a gift: {row['name']} ({'picture' if row['kind'] == 'picture' else '3D model'}).")
        agent.db.control(f"gift received #{gid}")
        push(agent.snapshot())
        return j(True, id=gid, name=row["name"])

    async def index(_):
        return web.FileResponse(WEB / "index.html")

    async def sandbox_page(_):
        """A separate play area for trying models out. Nothing on it touches Otto, his world, his map or his database."""
        return web.FileResponse(WEB / "sandbox.html")

    async def sandbox_assets(_):
        rows = agent.db.q("SELECT id,pack,name,tags,fit,fw,fd,sy,tris,size_bytes FROM assets WHERE usable=1 ORDER BY pack, name")
        for r in rows:
            try:
                r["tags"] = json.loads(r["tags"] or "[]")[:6]
            except ValueError:
                r["tags"] = []
        bright = {r["id"]: config.kit_bright(r["pack"], r["name"]) for r in rows if config.kit_bright(r["pack"], r["name"]) != 1.0}
        return web.json_response({"assets": rows, "bright": bright}, headers={"Cache-Control": "no-cache"})

    app = web.Application(middlewares=[auth, security_headers])
    app.router.add_get("/", index)
    app.router.add_get("/sandbox", sandbox_page)
    app.router.add_get("/sandbox/assets", sandbox_assets)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/asset/{id}", asset_file)
    app.router.add_get("/gift/{id}/file", gift_file)
    app.router.add_post("/gift", gift_upload)
    app.router.add_static("/", WEB, show_index=False)
    ar = web.AppRunner(app)
    await ar.setup()
    await web.TCPSite(ar, config.HOST, config.PORT).start()
    agent.site_status = None
    asyncio.ensure_future(check_site())
    agent.log(f"[{config.NAME}] world at http://{config.HOST}:{config.PORT}")
    try:
        await runner.run(interval=interval)
    finally:
        for ws in list(clients):
            await ws.close()
        await ar.cleanup()
