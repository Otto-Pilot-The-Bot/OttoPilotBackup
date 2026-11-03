// The Plan editor: the HUMAN's map editor (never reachable by the model; it only talks to the server with map_* messages).
// Palette of Kenney models grouped by kit, grid snapping, place / rotate / move / delete, undo/redo, ground paint, save/load/new,
// overlays for footprints and walkable areas, and editable tags. Edits a working copy; "Save" sends it to the server, which validates it.
import * as THREE from 'three';
import { LOOKS, TILE_NAMES } from './mapview.js';
import { H_ZERO, H_STEP } from './terrain.js';

const CORE = ['Space Kit', 'Modular Space Kit', 'Space Station Kit'];
const MINE = ['Meshy Buildings', 'Trees', 'Printed'];                       // the models you made or bought: shown first
const FAV = '★ Favorites';
const SUPPORT = ['City Kit - Roads', 'Road Pack', 'Car Kit', 'Furniture Kit', 'Nature Kit', 'Food Kit', 'City Kit - Suburban', 'City Kit - Commercial'];
const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));

export function createEditor({ camera, controls, dom, MV, send, CAM, thumbDesign, applyLook }) {
  let open = false, doc = null, rows = [], byKit = new Map(), maps = [], active = '', dirty = false;
  let pickName = '', pickRot = 0, pickY = 0, autoY = true, ghostY = 0, ceil = 0;
  let tool = 'select', sel = null, pick = null, tile = 'r', snap = 1, rsnap = 15, kit = 'Meshy Buildings', kitPicked = false, q = '', cat = '', limit = 48, drag = null, painting = false, tMode = 'raise', tRad = 8, tFlat = 0, lastTerr = 0;
  const undo = [], redo = [];
  const ndc = new THREE.Vector2(), ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3();

  // ---------------------------------------------------------------- DOM
  const btn = document.createElement('button'); btn.id = 'planBtn'; btn.textContent = '🗺️ Plan'; btn.title = 'Open the map editor (only you can use it)'; document.body.appendChild(btn);
  const gbtn = document.createElement('button'); gbtn.id = 'gameBtn'; gbtn.textContent = '🎮 Game mode'; gbtn.title = 'Pause Otto and free the graphics memory (for gaming or recording)'; document.body.appendChild(gbtn);
  gbtn.addEventListener('click', () => send({ type: 'game_mode', on: !window.__sleeping }));
  const el = document.createElement('aside'); el.id = 'plan'; el.hidden = true; document.body.appendChild(el);
  const ghost = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-1, 0.12, -1), new THREE.Vector3(1, 0.12, -1), new THREE.Vector3(1, 0.12, 1), new THREE.Vector3(-1, 0.12, 1)]),
    new THREE.LineBasicMaterial({ color: 0x00e5ff, depthTest: false })); ghost.visible = false; ghost.renderOrder = 40; MV.root.add(ghost);
  const arrow = new THREE.Group(); { const c = new THREE.Mesh(new THREE.ConeGeometry(0.35, 0.9, 10).rotateX(Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x00e5ff, depthTest: false })); c.renderOrder = 41; arrow.add(c); arrow.visible = false; MV.root.add(arrow); }   // points the way the front (+z, where doors are) will face

  const toast = (t) => { const x = $('#toast'); if (x) { x.textContent = t; x.hidden = false; setTimeout(() => { x.hidden = true; }, 2200); } };
  const snapV = (v) => (snap > 0 ? Math.round(v / snap) * snap : v);
  const half = () => (doc ? (doc.n * doc.cell) / 2 : 40);
  const nextId = () => Math.max(0, ...doc.objects.map((o) => o.id)) + 1;
  const objOf = (id) => doc.objects.find((o) => o.id === id);

  function commit(label) {                                    // call BEFORE changing doc
    undo.push(JSON.stringify(doc)); if (undo.length > 100) undo.shift(); redo.length = 0; dirty = true;
  }
  function refresh(rebuildGround = false) {
    MV.doc = doc; if (rebuildGround) MV.rebuildGround(); MV.sync(); MV.updateColliders(); MV.rebuildOverlays(); MV.select(sel); render(false);
  }
  function doUndo() { if (!undo.length) return; redo.push(JSON.stringify(doc)); doc = JSON.parse(undo.pop()); dirty = true; if (sel && !objOf(sel)) sel = null; refresh(true); }
  function doRedo() { if (!redo.length) return; undo.push(JSON.stringify(doc)); doc = JSON.parse(redo.pop()); dirty = true; if (sel && !objOf(sel)) sel = null; refresh(true); }

  // ---------------------------------------------------------------- defaults for a new object (same rules as sprocket/maps.py asset_defaults; the server re-checks on save)
  function defaults(r) {
    const tags = r.tags || []; let fw = r.fw || 1, fd = r.fd || 1;
    if (r.cat === 'tree' || (tags.includes('plant') && !tags.includes('building'))) { fw = Math.max(0.5, fw * 0.3); fd = Math.max(0.5, fd * 0.3); }
    const bld = r.cat === 'building' || r.cat === 'shop';
    return { fw: +fw.toFixed(2), fd: +fd.toFixed(2), tags: tags.slice(0, 10), door: bld && r.door_x != null ? [r.door_x, r.door_z] : null,
      walkable: r.cat === 'road' || fw * fd < 0.04 || (r.sy * r.fit < 0.25 && !bld) };
  }
  function addObject(r, x, z) {
    commit(); const d = defaults(r), id = nextId(), y = autoY ? ghostY : pickY;
    doc.objects.push({ id, asset: r.file, aid: r.id, fit: r.fit, kit: r.pack, name: (pickName.trim() || r.name).slice(0, 60), x, z, rot: pickRot, scale: 1, ...d, ...(y > 0 ? { y } : {}) });
    sel = id; refresh(); return id;
  }

  // ---------------------------------------------------------------- panel
  const tileSw = { g: '#a8d08a', p: '#e9dfc6', r: '#5b6270', t: '#dccfa9', w: '#6db4d6', s: '#eedca8', d: '#b78f68' };
  const favKey = 'otto_fav_models';
  const favs = (() => { try { return new Set(JSON.parse(localStorage.getItem(favKey) || '[]')); } catch { return new Set(); } })();       // asset files, kept per browser
  const saveFavs = () => { try { localStorage.setItem(favKey, JSON.stringify([...favs])); } catch { /* storage may be blocked */ } };
  const kitRows = (k) => (k === FAV ? rows.filter((r) => favs.has(r.file)) : (byKit.get(k) || []));
  function kitList() {
    const all = [...byKit.keys()].sort(); const mine = [FAV, ...MINE.filter((k) => byKit.has(k))], core = CORE.filter((k) => byKit.has(k)), sup = SUPPORT.filter((k) => byKit.has(k)), rest = all.filter((k) => !core.includes(k) && !sup.includes(k) && !MINE.includes(k));
    return { mine, core, sup, rest };
  }
  function render(full = true) {
    if (!open) return;
    if (!doc) { el.innerHTML = '<div class="ph"><b>Plan</b><button data-a="close">✕</button></div><p class="dim">Waiting for the map…</p>'; return; }
    const s = sel ? objOf(sel) : null, kl = kitList();
    const opt = (k) => `<option ${k === kit ? 'selected' : ''} value="${esc(k)}">${esc(k)} (${kitRows(k).length})</option>`;
    const cats = [...new Set(kitRows(kit).map((r) => r.cat))].sort();
    el.innerHTML = `
      <div class="ph"><b>🗺️ Plan editor</b><span class="dim small">only you can edit; Otto can only wish</span><button data-a="close" title="Close (Esc)">✕</button></div>
      ${editing ? `<div class="warnbox" style="background:#e4eefc;border-color:#a9c4ee">✏️ Editing <b>${esc(doc.name)}</b> (not where Otto is). Saving will not move him. <button data-a="backlive">Back to the live map</button></div>` : ''}
      ${(window.__mapMsg?.warnings || []).map((w) => `<div class="warnbox">⚠️ ${esc(w)}</div>`).join('')}
      <div class="sec"><label>Map <select id="pMap">${maps.map((m) => `<option ${m === doc.name ? 'selected' : ''}>${esc(m)}</option>`).join('')}${maps.includes(doc.name) ? '' : `<option selected>${esc(doc.name)} (unsaved)</option>`}</select></label>
        <div class="row"><button data-a="save" class="pri">💾 Save${dirty ? ' •' : ''}</button><button data-a="saveas">Save as…</button><button data-a="new">New</button><button data-a="load">Load</button></div>
        <div class="row"><button data-a="undo" ${undo.length ? '' : 'disabled'}>↶ Undo</button><button data-a="redo" ${redo.length ? '' : 'disabled'}>↷ Redo</button><span class="dim small">${doc.objects.length} objects · ${doc.n}×${doc.n} cells of ${doc.cell} m</span></div></div>
      <details class="sec" ${doc.bounds || doc.exit ? 'open' : ''}><summary><b>Room settings</b> <span class="dim small">(for an interior map)</span></summary>
        <div class="dim small">A room Otto can walk in: set the walkable rectangle (everything outside it is wall) and where he appears and leaves. Leave empty for an outdoor map.</div>
        <div class="grid2">${['x0', 'z0', 'x1', 'z1'].map((k) => `<label>${k} <input data-r="${k}" type="number" step="0.5" value="${doc.bounds ? doc.bounds[k] : ''}" placeholder="none"></label>`).join('')}
        ${['x', 'z'].map((k) => `<label>exit ${k} <input data-r="e${k}" type="number" step="0.5" value="${doc.exit ? doc.exit[k] : ''}" placeholder="none"></label>`).join('')}</div>
        <div class="row"><button data-a="room" title="Walls at 8 m each way, the way out on the front side">Make it a 16 × 16 m room</button><button data-a="noroom">Clear</button></div></details>
      <div class="sec"><div class="row tools">${[['select', '☝ Select / move'], ['place', '➕ Place'], ['paint', '🖌 Ground'], ['terrain', '⛰ Terrain']].map(([k, l]) => `<button data-a="tool" data-k="${k}" class="${tool === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        <div class="row"><label>Snap <select id="pSnap">${[[0, 'off'], [0.5, '0.5 m'], [1, '1 m'], [2, '2 m'], [doc.cell, `cell (${doc.cell} m)`]].map(([v, l]) => `<option value="${v}" ${v === snap ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
        <label>Turn <select id="pRot">${[15, 45, 90].map((v) => `<option ${v === rsnap ? 'selected' : ''}>${v}</option>`).join('')}</select>°</label></div>
        <div class="row"><label><input type="checkbox" id="pFoot" ${MV.overlays.foot ? 'checked' : ''}> footprints &amp; doors</label><label><input type="checkbox" id="pWalk" ${MV.overlays.walk ? 'checked' : ''}> blocked (last save)</label></div>
        <div class="row"><label>Look <select id="pLook">${Object.entries(LOOKS).map(([k, v]) => `<option value="${k}" ${k === MV.look ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label></div>
        <div class="dim small">The ground look is not decided yet: A/B/C are previews. Lighting follows the day/night cycle.</div></div>
      ${tool === 'paint' ? `<div class="sec"><b>Ground</b><div class="row">${Object.entries(TILE_NAMES).map(([k, n]) => `<button data-a="tile" data-k="${k}" class="tilebtn ${tile === k ? 'on' : ''}"><i style="background:${tileSw[k]}"></i>${n}</button>`).join('')}</div><div class="dim small">Click or drag on the map. Water cannot be walked; roads and paths are preferred by Otto.</div></div>` : ''}
      ${tool === 'terrain' ? `<div class="sec"><b>Terrain</b><div class="row">${[['raise', '⬆ Raise'], ['lower', '⬇ Lower'], ['smooth', '〰 Smooth'], ['flat', '▭ Flatten']].map(([k, l]) => `<button data-a="tmode" data-k="${k}" class="${tMode === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        <div class="row"><label>Brush <select id="tRad">${[[4, 'small (4 m)'], [8, 'medium (8 m)'], [14, 'large (14 m)']].map(([v, l]) => `<option value="${v}" ${v === tRad ? 'selected' : ''}>${l}</option>`).join('')}</select></label></div>
        <div class="dim small">Click or drag to sculpt hills. Lower the ground below the water line (about 0.3 m under the level ground) for a lake. Otto can walk on slopes and wade in the shallow edge, but not into deep water. Things you place stand on the ground.</div></div>` : ''}
      ${s ? `<div class="sec"><label><b>Name</b> <input data-p="name" type="text" value="${esc(s.name)}" maxlength="60" placeholder="e.g. Otto's computer"></label> <span class="dim small">#${s.id} · ${esc(s.kit)}</span>
        <label><b>About it</b> <input data-p="about" type="text" value="${esc(s.about || '')}" maxlength="160" placeholder="tell Otto what it is, e.g. my computer: use it to write" style="width:100%"></label>
        <div class="row"><button data-a="rot" data-d="-1">⟲</button><button data-a="rot" data-d="1">⟳</button><button data-a="dup">Duplicate</button><button data-a="drop" title="Put it on top of whatever is directly under it (a desk, a shelf)">⤓ Drop on surface</button><button data-a="del" class="warn">🗑 Delete</button></div>
        <div class="grid2"><label>x <input data-p="x" type="number" step="0.5" value="${s.x}"></label><label>z <input data-p="z" type="number" step="0.5" value="${s.z}"></label>
        <label>turn ° <input data-p="rot" type="number" step="15" value="${s.rot}"></label><label>scale <input data-p="scale" type="number" step="0.1" min="0.2" max="6" value="${s.scale}"></label>
        <label>footprint w <input data-p="fw" type="number" step="0.1" value="${s.fw}"></label><label>footprint d <input data-p="fd" type="number" step="0.1" value="${s.fd}"></label>
        <label>height y <input data-p="y" type="number" step="0.5" value="${s.y || 0}"></label><span></span>
        <label>door x <input data-p="dx" type="number" step="0.5" value="${s.door ? s.door[0] : ''}" placeholder="none"></label><label>door z <input data-p="dz" type="number" step="0.5" value="${s.door ? s.door[1] : ''}" placeholder="none"></label></div>
        <label>Otto's… <select data-p="placekey"><option value="">(nothing special)</option>${[['home', 'home'], ['clothing_store', 'shop'], ['gallery', 'gallery'], ['fuel_station', 'charging station'], ['plaza', 'plaza'], ['park', 'park'], ['pond', 'pond']].map(([k, l]) => `<option value="${k}" ${doc.places?.[k]?.object === s.id ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
        ${s.door ? `<label>Interior (its inside) <select data-p="interior"><option value="">none: walls just fade when he goes in</option>${maps.filter((m) => m !== doc.name).map((m) => `<option ${m === s.interior ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select></label>
        <div class="row"><button data-a="newint">➕ New interior for this</button><button data-a="editint" ${s.interior ? '' : 'disabled'}>✏️ Edit its inside</button></div>` : ''}
        <label class="row"><input type="checkbox" data-p="walkable" ${s.walkable ? 'checked' : ''}> walkable (no collision)</label>
        <label>tags <input data-p="tags" type="text" value="${esc((s.tags || []).join(', '))}" placeholder="bench, seat, park"></label>
        ${s.panel ? `<div class="grid2"><label>art w <input data-p="pw" type="number" step="0.1" value="${s.panel.w}"></label><label>art h <input data-p="ph" type="number" step="0.1" value="${s.panel.h}"></label></div><div class="dim small">Flat panels show Otto's newest pictures.</div>` : ''}</div>` : ''}
      ${giftPics().length ? `<div class="sec"><b>Pictures you gave Otto</b> <span class="dim small">(flat panels)</span><div class="row">${giftPics().map((g) => `<button data-a="gift" data-id="${g.id}" title="Put this picture on a flat panel">🖼 ${esc(g.name)}</button>`).join('')}</div></div>` : ''}
      <div class="sec"><b>Models</b>${pick ? ` <span class="dim small">placing: ${esc(pick.name)}</span>` : ''}
        ${tool === 'place' && pick ? `<div class="row"><label>Name it <input id="pName" type="text" maxlength="60" placeholder="${esc(pick.name)} (e.g. Otto's computer)" value="${esc(pickName)}" style="width:190px"></label></div><div class="row"><span>Turn before placing</span><button data-a="prot" data-d="-1" title="Turn left (Shift+R)">⟲</button><b>${pickRot}°</b><button data-a="prot" data-d="1" title="Turn right (R)">⟳</button></div>
        <div class="row"><label><input type="checkbox" id="pAuto" ${autoY ? 'checked' : ''}> sit on top of whatever is under the cursor (roofs, shelves)</label></div>
        <div class="row"><label>${autoY ? 'extra' : ''} height <input id="pY" type="number" step="0.5" min="0" max="30" value="${pickY}" style="width:70px"> m</label></div>
        ${autoY ? `<div class="row"><label title="To put something on a shelf inside a building, set this a little below the ceiling (for example 2.5): roofs and anything higher are skipped, and the object lands where the cursor touches the shelf. 0 = off.">ignore above <input id="pCeil" type="number" step="0.5" min="0" max="30" value="${ceil}" style="width:70px"> m</label> <span class="dim small">to place inside a building (try 2.5)</span></div>` : ''}` : ''}
        <div class="row"><select id="pKit"><optgroup label="Yours">${kl.mine.map(opt).join('')}</optgroup><optgroup label="Core">${kl.core.map(opt).join('')}</optgroup><optgroup label="Supporting">${kl.sup.map(opt).join('')}</optgroup><optgroup label="Other kits (ask before using)">${kl.rest.map(opt).join('')}</optgroup></select></div>
        <div class="row"><input id="pQ" type="text" placeholder="search…" value="${esc(q)}"><select id="pCat"><option value="">all</option>${cats.map((c) => `<option ${c === cat ? 'selected' : ''}>${c}</option>`).join('')}</select></div>
        <div class="pal" id="pPal"></div></div>`;
    paintPalette();
  }
  function giftPics() { return (window.__last?.()?.gifts || []).filter((g) => g.kind === 'picture').slice(0, 8); }
  function listRows() {
    const ql = q.toLowerCase();
    return kitRows(kit).filter((r) => (!cat || r.cat === cat) && (!ql || (r.name + ' ' + r.tags.join(' ')).toLowerCase().includes(ql)));
  }
  function paintPalette() {
    const host = $('#pPal'); if (!host) return;
    const list = listRows(), shown = list.slice(0, limit);
    host.innerHTML = shown.map((r) => `<button class="card ${pick && pick.id === r.id ? 'on' : ''}" data-a="pick" data-id="${r.id}" title="${esc(r.name)} · ${esc(r.cat)} · ${r.fw}×${r.fd} m"><img alt="" data-k="a:${r.id}"><span>${esc(r.name)}</span><span class="fav ${favs.has(r.file) ? 'on' : ''}" data-a="fav" data-id="${r.id}" title="${favs.has(r.file) ? 'Remove from favorites' : 'Add to favorites'}">${favs.has(r.file) ? '★' : '☆'}</span></button>`).join('')
      + (list.length > shown.length ? `<button class="card more" data-a="more">+${list.length - shown.length} more</button>` : '') + (list.length ? '' : '<div class="dim">Nothing matches.</div>');
    fillThumbs();
  }
  function fillThumbs() {
    for (const img of el.querySelectorAll('#pPal img[data-k]:not([src])')) {
      const id = +img.dataset.k.slice(2), r = rows.find((x) => x.id === id); if (!r) continue;
      const u = thumbDesign('a:' + id, { parts: [{ a: id, f: r.fit, x: 0, y: 0, z: 0, s: 1, r: [0, 0, 0] }], scale: 1, rot: 0 }, r.name);
      if (u) img.src = u;
    }
  }

  // ---------------------------------------------------------------- events: panel
  el.addEventListener('click', (e) => {
    const b = e.target.closest('[data-a]'); if (!b) return; const a = b.dataset.a;
    if (a === 'close') close();
    else if (a === 'save') save();
    else if (a === 'saveas') { const n = (window.prompt('Name for this map (letters, numbers, spaces, - _):', doc.name) || '').trim(); if (n) { doc.name = n; save(); } }
    else if (a === 'new') { const n = (window.prompt('Name for the new, empty map:', 'my map') || '').trim(); if (n && (!dirty || window.confirm('Discard unsaved changes?'))) send({ type: 'map_new', name: n, n: 20 }); }
    else if (a === 'load') { const n = $('#pMap').value; if (n && n !== doc.name && (!dirty || window.confirm('Discard unsaved changes?'))) send({ type: 'map_load', name: n }); }
    else if (a === 'backlive') { send({ type: 'get_map' }); }
    else if (a === 'room') { commit(); doc.bounds = { x0: -8, z0: -8, x1: 8, z1: 8 }; doc.exit = { x: 0, z: 6 }; refresh(); }
    else if (a === 'noroom') { commit(); delete doc.bounds; delete doc.exit; refresh(); }
    else if (a === 'newint') { const o = objOf(sel); if (!o) return; const n = (window.prompt('Name for the inside map:', (o.name + ' inside').slice(0, 40)) || '').trim(); if (n) { commit(); o.interior = n; save(); send({ type: 'map_new', name: n, n: 8, interior: true, edit: true }); } }
    else if (a === 'editint') { const o = objOf(sel); if (o && o.interior) { if (dirty && !window.confirm('Discard unsaved changes?')) return; send({ type: 'map_edit', name: o.interior }); } }
    else if (a === 'undo') doUndo(); else if (a === 'redo') doRedo();
    else if (a === 'tool') { tool = b.dataset.k; if (tool !== 'place') pick = null; applyTool(); render(); }
    else if (a === 'tile') { tile = b.dataset.k; render(); }
    else if (a === 'tmode') { tMode = b.dataset.k; render(); }
    else if (a === 'fav') { const r = rows.find((x) => x.id === +b.dataset.id); if (r) { if (favs.has(r.file)) favs.delete(r.file); else favs.add(r.file); saveFavs(); render(); } }
    else if (a === 'pick') { pick = rows.find((r) => r.id === +b.dataset.id); tool = 'place'; sel = null; MV.select(null); applyTool(); render(); }
    else if (a === 'gift') {
      const g = giftPics().find((x) => x.id === +b.dataset.id); if (!g) return; commit();
      const id = nextId(), asp = g.w && g.h ? g.w / g.h : 1.3, h = 1.6;
      doc.objects.push({ id, asset: null, kit: 'flat', name: g.name.slice(0, 40), x: 0, z: 0, rot: 0, scale: 1, fw: +(h * asp).toFixed(1), fd: 0.2, tags: ['art', 'gift'], door: null, walkable: true, y: 1.6,
        panel: { w: +(h * asp).toFixed(2), h, art_id: null, gift_id: g.id, caption: g.name.slice(0, 80) } });
      sel = id; refresh(); toast('Panel placed at the middle of the map: drag it where you want it.');
    }
    else if (a === 'prot') { pickRot = (((pickRot + (+b.dataset.d) * rsnap) % 360) + 360) % 360; render(); }
    else if (a === 'more') { limit += 48; paintPalette(); }
    else if (a === 'del') delSel();
    else if (a === 'dup') { const s = objOf(sel); if (s) { commit(); const c = clone(s); c.id = nextId(); c.x += 2; c.z += 2; doc.objects.push(c); sel = c.id; refresh(); } }
    else if (a === 'rot') turn(+b.dataset.d);
    else if (a === 'drop') { const o = objOf(sel); if (o) { commit(); const y = dropY(o, o.x, o.z); if (y > 0) o.y = y; else delete o.y; refresh(); toast(y > 0 ? `Resting on a surface at ${y.toFixed(2)} m` : 'Nothing under it; it is on the ground.'); } }
  });
  el.addEventListener('change', (e) => {
    const t = e.target;
    if (t.id === 'pMap') return;
    if (t.id === 'tRad') tRad = +t.value;
    else if (t.id === 'pSnap') snap = +t.value; else if (t.id === 'pRot') rsnap = +t.value;
    else if (t.id === 'pKit') { kit = t.value; kitPicked = true; cat = ''; limit = 48; render(); }
    else if (t.id === 'pCat') { cat = t.value; limit = 48; paintPalette(); }
    else if (t.id === 'pAuto') { autoY = t.checked; render(); }
    else if (t.id === 'pCeil') { ceil = Math.max(0, Math.min(30, +t.value || 0)); }
    else if (t.id === 'pY') { pickY = Math.max(0, Math.min(30, +t.value || 0)); }
    else if (t.id === 'pFoot') { MV.setOverlay('foot', t.checked); }
    else if (t.id === 'pWalk') { MV.setOverlay('walk', t.checked); }
    else if (t.id === 'pLook') { applyLook(t.value); }
    else if (t.dataset.r) { commit(); const k = t.dataset.r, v = t.value === '' ? null : +t.value; doc.bounds = doc.bounds || { x0: -8, z0: -8, x1: 8, z1: 8 }; doc.exit = doc.exit || { x: 0, z: 6 };
      if (k[0] === 'e') { if (v !== null) doc.exit[k[1]] = v; } else if (v !== null) doc.bounds[k] = v; refresh(); }
    else if (t.dataset.p && sel) editProp(t);
  });
  el.addEventListener('input', (e) => { if (e.target.id === 'pName') pickName = e.target.value; if (e.target.id === 'pQ') { q = e.target.value; limit = 48; paintPalette(); } });

  function editProp(t) {
    const s = objOf(sel), p = t.dataset.p; if (!s) return; commit();
    const n = +t.value;
    if (p === 'x' || p === 'z' || p === 'rot' || p === 'scale' || p === 'fw' || p === 'fd' || p === 'y') { if (Number.isFinite(n)) s[p] = p === 'scale' ? Math.max(0.2, Math.min(6, n)) : n; }
    else if (p === 'dx' || p === 'dz') { const cur = s.door || [0, 0]; if (t.value === '') s.door = null; else { cur[p === 'dx' ? 0 : 1] = n; s.door = cur; } }
    else if (p === 'walkable') s.walkable = t.checked;
    else if (p === 'placekey') {
      doc.places = doc.places || {}; for (const k of Object.keys(doc.places)) if (doc.places[k].object === s.id) delete doc.places[k];
      if (t.value) { const L = { home: 'home', clothing_store: 'shop', gallery: 'gallery', fuel_station: 'charging station', plaza: 'plaza', park: 'park', pond: 'pond' }[t.value];
        doc.places[t.value] = { label: L, object: s.id, aliases: [L], enter: !!s.door && ['home', 'clothing_store', 'gallery'].includes(t.value) }; }
    }
    else if (p === 'about') { if (t.value.trim()) s.about = t.value.slice(0, 160); else delete s.about; }
    else if (p === 'interior') { if (t.value) s.interior = t.value; else delete s.interior; }
    else if (p === 'name') s.name = t.value.slice(0, 60) || s.name;
    else if (p === 'tags') s.tags = t.value.split(',').map((x) => x.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '')).filter(Boolean).slice(0, 12);
    else if (p === 'pw' && s.panel) s.panel.w = Math.max(0.3, n); else if (p === 'ph' && s.panel) s.panel.h = Math.max(0.3, n);
    refresh();
  }
  function turn(dir) { const s = objOf(sel); if (!s) return; commit(); s.rot = (((s.rot + dir * rsnap) % 360) + 360) % 360; refresh(); }
  function delSel() { if (!sel) return; commit(); doc.objects = doc.objects.filter((o) => o.id !== sel); sel = null; refresh(); }
  let awaitingSave = false, editing = false;
  function save() { awaitingSave = true; setTimeout(() => { awaitingSave = false; }, 4000); send({ type: 'map_save', doc: doc, use: !editing }); }

  // ---------------------------------------------------------------- events: the 3D view
  function worldAt(e) {
    const r = dom.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera); if (!ray.ray.intersectPlane(plane, hit)) return null;
    if (doc && doc.heights) {                                  // hills: slide the cursor point onto the real ground (a few passes are plenty for gentle slopes)
      for (let k = 0; k < 4; k++) { plane.constant = -MV.heightAt(hit.x, hit.z); if (!ray.ray.intersectPlane(plane, hit)) break; }
      plane.constant = 0;
    }
    return hit.clone();
  }
  /** What is under the cursor: { y: height of the surface (0 = open ground), x, z: where the ray touched it, only when "ignore above" is on }.
   *  With "ignore above" (ceil) set, anything higher than that is skipped, so a shelf inside a building can be reached through its roof. */
  function surfaceAt(e) {
    if (!autoY) return { y: pickY };
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(MV.objG.children, true);
    const h = ceil > 0 ? hits.find((x) => x.point.y - MV.heightAt(x.point.x, x.point.z) <= ceil) : hits[0];
    if (!h) return { y: 0 };
    return { y: Math.max(0, Math.round((h.point.y - MV.heightAt(h.point.x, h.point.z)) * 4) / 4), ...(ceil > 0 ? { x: h.point.x, z: h.point.z } : {}) };
  }
  const surfaceY = (e) => surfaceAt(e).y;
  function dropY(o, ex, ez) {                                   // top of whatever is directly below (x, z), ignoring the object itself
    const r = new THREE.Raycaster(new THREE.Vector3(ex, 60, ez), new THREE.Vector3(0, -1, 0));
    const hits = r.intersectObjects(MV.objG.children.filter((c) => c.userData.mapId !== o.id), true);       // (raycasts ignore .visible, so leave the object itself out of the list)
    const h = ceil > 0 ? hits.find((x) => x.point.y - MV.heightAt(ex, ez) <= ceil) : hits[0];
    return h ? Math.max(0, Math.round((h.point.y - MV.heightAt(ex, ez)) * 100) / 100) : 0;
  }
  function paintAt(p) {
    const c = doc.cell, h = half(), i = Math.floor((p.x + h) / c), j = Math.floor((p.z + h) / c);
    if (i < 0 || j < 0 || i >= doc.n || j >= doc.n || doc.ground[j][i] === tile) return;
    doc.ground[j] = doc.ground[j].slice(0, i) + tile + doc.ground[j].slice(i + 1); dirty = true; MV.doc = doc; MV.rebuildGround();
  }
  // Raise / lower / smooth / flatten the corner heights around a point. Heights are kept as letters (0.25 m steps) in doc.heights; the outer ring stays flat.
  function sculptAt(p, first) {
    const n = doc.n, c = doc.cell, h0 = half(); if (!doc.heights) doc.heights = Array.from({ length: n + 1 }, () => String.fromCharCode(H_ZERO).repeat(n + 1));
    const rows = doc.heights.map((r) => [...r].map((ch) => (ch.charCodeAt(0) - H_ZERO) * H_STEP)), rad = tRad, src = rows.map((r) => r.slice());
    if (first) tFlat = rows[Math.max(0, Math.min(n, Math.round((p.z + h0) / c)))][Math.max(0, Math.min(n, Math.round((p.x + h0) / c)))];
    for (let j = 1; j < n; j++) for (let i = 1; i < n; i++) {
      const d = Math.hypot(-h0 + i * c - p.x, -h0 + j * c - p.z); if (d > rad) continue;
      const w = (1 - d / rad) ** 1.5 * 0.5 + 0.05;                                            // soft edge, still reaches the nearest corner of a small brush
      if (tMode === 'raise') rows[j][i] += 0.75 * w; else if (tMode === 'lower') rows[j][i] -= 0.75 * w;
      else if (tMode === 'flat') rows[j][i] += (tFlat - src[j][i]) * Math.min(1, w * 1.6);
      else rows[j][i] += ((src[j - 1][i] + src[j + 1][i] + src[j][i - 1] + src[j][i + 1]) / 4 - src[j][i]) * Math.min(1, w * 1.6);
    }
    const next = rows.map((r) => r.map((v) => String.fromCharCode(H_ZERO + Math.max(-12, Math.min(12, Math.round(v / H_STEP))))).join(''));
    if (next.join() === doc.heights.join()) return false;
    doc.heights = next; dirty = true; return true;
  }
  function terrainAt(p, first) {
    if (!sculptAt(p, first)) return;
    const now = performance.now(); if (!first && now - lastTerr < 90) return; lastTerr = now;      // rebuilding the ground is not free: at most about 11 times a second while dragging
    MV.doc = doc; MV.rebuildGround(); MV.updateColliders();
  }
  function applyTool() {
    controls.mouseButtons = tool === 'select' ? { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN } : { LEFT: -1, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    dom.style.cursor = tool === 'select' ? '' : 'crosshair'; ghost.visible = false; arrow.visible = false;
  }
  window.addEventListener('pointerdown', (e) => {
    if (!open || e.target !== dom || e.button !== 0 || !doc) return;
    const p = worldAt(e); if (!p) return;
    if (tool === 'paint') { commit(); painting = true; paintAt(p); return; }
    if (tool === 'terrain') { commit(); painting = true; terrainAt(p, true); return; }
    if (tool === 'place') {
      if (!pick) return; const sf = surfaceAt(e); ghostY = sf.y; const px = sf.x ?? p.x, pz = sf.z ?? p.z; addObject(pick, snapV(Math.max(-half(), Math.min(half(), px))), snapV(Math.max(-half(), Math.min(half(), pz)))); return;
    }
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
    const id = MV.pick(ray);
    if (id != null) {
      sel = id; MV.select(id); const o = objOf(id); drag = { id, dx: o.x - p.x, dz: o.z - p.z, auto: !(o.y > 0), moved: false, snapshot: JSON.stringify(doc) }; controls.enabled = false; render(false);
    } else if (sel) { sel = null; MV.select(null); render(false); }
  }, true);
  window.addEventListener('pointermove', (e) => {
    if (!open || !doc) return;
    if (e.target !== dom && !drag && !painting) return;
    const p = worldAt(e); if (!p) return;
    if (painting) { if (tool === 'terrain') terrainAt(p, false); else paintAt(p); return; }
    if (drag) {
      const o = objOf(drag.id); if (!o) return;
      const nx = snapV(p.x + drag.dx), nz = snapV(p.z + drag.dz);
      if (nx !== o.x || nz !== o.z) { o.x = Math.max(-half(), Math.min(half(), nx)); o.z = Math.max(-half(), Math.min(half(), nz)); drag.moved = true;
        if (autoY && drag.auto && !o.panel) { const y = dropY(o, o.x, o.z); if (y > 0) o.y = y; else delete o.y; } MV.sync(); MV.select(o.id); MV.updateColliders(); }
      return;
    }
    if (tool === 'place' && pick) {
      const d = defaults(pick), sf = surfaceAt(e); ghostY = sf.y; const px = sf.x ?? p.x, pz = sf.z ?? p.z; ghost.visible = true; ghost.scale.set(Math.max(0.4, d.fw / 2), 1, Math.max(0.4, d.fd / 2));
      ghost.position.set(snapV(px), ghostY, snapV(pz)); ghost.rotation.y = (pickRot * Math.PI) / 180; arrow.visible = true;
      arrow.position.set(snapV(px), ghostY + 0.3, snapV(pz)); arrow.rotation.y = (pickRot * Math.PI) / 180; arrow.children[0].position.z = Math.max(0.4, d.fd / 2) + 0.7;
    } else { ghost.visible = false; arrow.visible = false; }
  });
  window.addEventListener('pointerup', () => {
    if (painting) { painting = false; if (tool === 'terrain') { MV.doc = doc; MV.rebuildGround(); MV.updateColliders(); } render(false); }
    if (drag) { if (drag.moved) { undo.push(drag.snapshot); redo.length = 0; dirty = true; MV.rebuildOverlays(); } drag = null; controls.enabled = true; render(false); }
  });
  window.addEventListener('keydown', (e) => {
    if (!open || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '')) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? doRedo() : doUndo(); }
    else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); doRedo(); }
    else if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); delSel(); }
    else if (e.key.toLowerCase() === 'r' && !mod) { if (tool === 'place' && pick && !sel) { pickRot = (((pickRot + (e.shiftKey ? -1 : 1) * rsnap) % 360) + 360) % 360; render(); } else turn(e.shiftKey ? -1 : 1); }
    else if (e.key === 'Escape') { if (tool !== 'select') { tool = 'select'; pick = null; applyTool(); render(); } else if (sel) { sel = null; MV.select(null); render(false); } else close(); }
    else if (e.key.startsWith('Arrow') && sel) {
      e.preventDefault(); const s = objOf(sel), st = snap || 0.5; commit();
      if (e.key === 'ArrowLeft') s.x -= st; if (e.key === 'ArrowRight') s.x += st; if (e.key === 'ArrowUp') s.z -= st; if (e.key === 'ArrowDown') s.z += st; refresh();
    }
  });

  // ---------------------------------------------------------------- open / close
  function openEd() {
    if (open) return; open = true; el.hidden = false; btn.classList.add('on'); document.body.classList.add('planning');
    CAM.setMode('overhead'); send({ type: 'get_assets' }); send({ type: 'get_map' });
    if (window.__mapMsg?.doc) loadFromMsg(window.__mapMsg, true);
    applyTool(); render();
  }
  function close() {
    if (!open) return; open = false; el.hidden = true; btn.classList.remove('on'); document.body.classList.remove('planning'); ghost.visible = false; arrow.visible = false; drag = null; painting = false;
    controls.enabled = CAM.mode === 'overhead'; controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    if (dirty && window.__mapMsg?.doc) { doc = null; MV.setDoc(window.__mapMsg.doc, window.__mapMsg.nav); dirty = false; undo.length = redo.length = 0; }   // unsaved edits are dropped from view
    sel = null; MV.select(null);
  }
  btn.addEventListener('click', () => (open ? close() : openEd()));

  function loadFromMsg(m, force) {
    maps = m.maps || maps; active = m.active || active;
    if (!m.doc) return;
    if (force || !dirty || !doc || doc.name !== m.doc.name) { doc = clone(m.doc); dirty = false; if (!doc || doc.name !== m.doc.name) { undo.length = redo.length = 0; } sel = null; MV.doc = doc; }
    else { /* working copy has unsaved changes: keep it */ }
  }
  return {
    get open() { return open; }, close, openEd,
    onMap(m) { maps = m.maps || maps; editing = !!m.edit; if (open) { const f = awaitingSave; awaitingSave = false; loadFromMsg(m, f); if (doc) { MV.doc = doc; MV.sync(); MV.updateColliders(); MV.rebuildOverlays(); MV.nav = m.nav; } render(); } },
    assetsData(m) {
      rows = m.rows || []; byKit = new Map(); for (const r of rows) { if (!byKit.has(r.pack)) byKit.set(r.pack, []); byKit.get(r.pack).push(r); }
      if (kit !== FAV && !byKit.has(kit)) kit = byKit.has('Meshy Buildings') ? 'Meshy Buildings' : [...byKit.keys()][0]; if (open) render();
    },
    thumbsReady() { if (open) fillThumbs(); },
  };
}
