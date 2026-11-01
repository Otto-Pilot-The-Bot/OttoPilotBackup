// The Plan editor: the HUMAN's map editor (never reachable by the model; it only talks to the server with map_* messages).
// Palette of Kenney models grouped by kit, grid snapping, place / rotate / move / delete, undo/redo, ground paint, save/load/new,
// overlays for footprints and walkable areas, and editable tags. Edits a working copy; "Save" sends it to the server, which validates it.
import * as THREE from 'three';
import { LOOKS, TILE_NAMES } from './mapview.js';

const CORE = ['Space Kit', 'Modular Space Kit', 'Space Station Kit'];
const SUPPORT = ['City Kit - Roads', 'Road Pack', 'Car Kit', 'Furniture Kit', 'Nature Kit', 'Food Kit', 'City Kit - Suburban', 'City Kit - Commercial'];
const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));

export function createEditor({ camera, controls, dom, MV, send, CAM, thumbDesign, applyLook }) {
  let open = false, doc = null, rows = [], byKit = new Map(), maps = [], active = '', dirty = false;
  let tool = 'select', sel = null, pick = null, tile = 'r', snap = 1, rsnap = 15, kit = 'Space Kit', q = '', cat = '', limit = 48, drag = null, painting = false;
  const undo = [], redo = [];
  const ndc = new THREE.Vector2(), ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3();

  // ---------------------------------------------------------------- DOM
  const btn = document.createElement('button'); btn.id = 'planBtn'; btn.textContent = '🗺️ Plan'; btn.title = 'Open the map editor (only you can use it)'; document.body.appendChild(btn);
  const el = document.createElement('aside'); el.id = 'plan'; el.hidden = true; document.body.appendChild(el);
  const ghost = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-1, 0.12, -1), new THREE.Vector3(1, 0.12, -1), new THREE.Vector3(1, 0.12, 1), new THREE.Vector3(-1, 0.12, 1)]),
    new THREE.LineBasicMaterial({ color: 0x00e5ff, depthTest: false })); ghost.visible = false; ghost.renderOrder = 40; MV.root.add(ghost);

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
    commit(); const d = defaults(r), id = nextId();
    doc.objects.push({ id, asset: r.file, aid: r.id, fit: r.fit, kit: r.pack, name: r.name, x, z, rot: 0, scale: 1, ...d });
    sel = id; refresh(); return id;
  }

  // ---------------------------------------------------------------- panel
  const tileSw = { g: '#a8d08a', p: '#e9dfc6', r: '#5b6270', t: '#dccfa9', w: '#6db4d6', s: '#eedca8', d: '#b78f68' };
  function kitList() {
    const all = [...byKit.keys()].sort(); const core = CORE.filter((k) => byKit.has(k)), sup = SUPPORT.filter((k) => byKit.has(k)), rest = all.filter((k) => !core.includes(k) && !sup.includes(k));
    return { core, sup, rest };
  }
  function render(full = true) {
    if (!open) return;
    if (!doc) { el.innerHTML = '<div class="ph"><b>Plan</b><button data-a="close">✕</button></div><p class="dim">Waiting for the map…</p>'; return; }
    const s = sel ? objOf(sel) : null, kl = kitList();
    const opt = (k) => `<option ${k === kit ? 'selected' : ''} value="${esc(k)}">${esc(k)} (${byKit.get(k).length})</option>`;
    const cats = [...new Set((byKit.get(kit) || []).map((r) => r.cat))].sort();
    el.innerHTML = `
      <div class="ph"><b>🗺️ Plan editor</b><span class="dim small">only you can edit; Otto can only wish</span><button data-a="close" title="Close (Esc)">✕</button></div>
      <div class="sec"><label>Map <select id="pMap">${maps.map((m) => `<option ${m === doc.name ? 'selected' : ''}>${esc(m)}</option>`).join('')}${maps.includes(doc.name) ? '' : `<option selected>${esc(doc.name)} (unsaved)</option>`}</select></label>
        <div class="row"><button data-a="save" class="pri">💾 Save${dirty ? ' •' : ''}</button><button data-a="saveas">Save as…</button><button data-a="new">New</button><button data-a="load">Load</button></div>
        <div class="row"><button data-a="undo" ${undo.length ? '' : 'disabled'}>↶ Undo</button><button data-a="redo" ${redo.length ? '' : 'disabled'}>↷ Redo</button><span class="dim small">${doc.objects.length} objects · ${doc.n}×${doc.n} cells of ${doc.cell} m</span></div></div>
      <div class="sec"><div class="row tools">${[['select', '☝ Select / move'], ['place', '➕ Place'], ['paint', '🖌 Ground']].map(([k, l]) => `<button data-a="tool" data-k="${k}" class="${tool === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        <div class="row"><label>Snap <select id="pSnap">${[[0, 'off'], [0.5, '0.5 m'], [1, '1 m'], [2, '2 m'], [doc.cell, `cell (${doc.cell} m)`]].map(([v, l]) => `<option value="${v}" ${v === snap ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
        <label>Turn <select id="pRot">${[15, 45, 90].map((v) => `<option ${v === rsnap ? 'selected' : ''}>${v}</option>`).join('')}</select>°</label></div>
        <div class="row"><label><input type="checkbox" id="pFoot" ${MV.overlays.foot ? 'checked' : ''}> footprints &amp; doors</label><label><input type="checkbox" id="pWalk" ${MV.overlays.walk ? 'checked' : ''}> blocked (last save)</label></div>
        <div class="row"><label>Look <select id="pLook">${Object.entries(LOOKS).map(([k, v]) => `<option value="${k}" ${k === MV.look ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label></div>
        <div class="dim small">Ground and lighting are not decided yet: A/B/C are previews only.</div></div>
      ${tool === 'paint' ? `<div class="sec"><b>Ground</b><div class="row">${Object.entries(TILE_NAMES).map(([k, n]) => `<button data-a="tile" data-k="${k}" class="tilebtn ${tile === k ? 'on' : ''}"><i style="background:${tileSw[k]}"></i>${n}</button>`).join('')}</div><div class="dim small">Click or drag on the map. Water cannot be walked; roads and paths are preferred by Otto.</div></div>` : ''}
      ${s ? `<div class="sec"><b>${esc(s.name)}</b> <span class="dim small">#${s.id} · ${esc(s.kit)}</span>
        <div class="row"><button data-a="rot" data-d="-1">⟲</button><button data-a="rot" data-d="1">⟳</button><button data-a="dup">Duplicate</button><button data-a="del" class="warn">🗑 Delete</button></div>
        <div class="grid2"><label>x <input data-p="x" type="number" step="0.5" value="${s.x}"></label><label>z <input data-p="z" type="number" step="0.5" value="${s.z}"></label>
        <label>turn ° <input data-p="rot" type="number" step="15" value="${s.rot}"></label><label>scale <input data-p="scale" type="number" step="0.1" min="0.2" max="6" value="${s.scale}"></label>
        <label>footprint w <input data-p="fw" type="number" step="0.1" value="${s.fw}"></label><label>footprint d <input data-p="fd" type="number" step="0.1" value="${s.fd}"></label>
        <label>door x <input data-p="dx" type="number" step="0.5" value="${s.door ? s.door[0] : ''}" placeholder="none"></label><label>door z <input data-p="dz" type="number" step="0.5" value="${s.door ? s.door[1] : ''}" placeholder="none"></label></div>
        <label class="row"><input type="checkbox" data-p="walkable" ${s.walkable ? 'checked' : ''}> walkable (no collision)</label>
        <label>tags <input data-p="tags" type="text" value="${esc((s.tags || []).join(', '))}" placeholder="bench, seat, park"></label>
        ${s.panel ? `<div class="grid2"><label>art w <input data-p="pw" type="number" step="0.1" value="${s.panel.w}"></label><label>art h <input data-p="ph" type="number" step="0.1" value="${s.panel.h}"></label><label>height y <input data-p="y" type="number" step="0.1" value="${s.y}"></label></div><div class="dim small">Flat panels show Otto's newest pictures.</div>` : ''}</div>` : ''}
      <div class="sec"><b>Models</b>${pick ? ` <span class="dim small">placing: ${esc(pick.name)}</span>` : ''}
        <div class="row"><select id="pKit"><optgroup label="Core">${kl.core.map(opt).join('')}</optgroup><optgroup label="Supporting">${kl.sup.map(opt).join('')}</optgroup><optgroup label="Other kits (ask before using)">${kl.rest.map(opt).join('')}</optgroup></select></div>
        <div class="row"><input id="pQ" type="text" placeholder="search…" value="${esc(q)}"><select id="pCat"><option value="">all</option>${cats.map((c) => `<option ${c === cat ? 'selected' : ''}>${c}</option>`).join('')}</select></div>
        <div class="pal" id="pPal"></div></div>`;
    paintPalette();
  }
  function listRows() {
    const ql = q.toLowerCase();
    return (byKit.get(kit) || []).filter((r) => (!cat || r.cat === cat) && (!ql || (r.name + ' ' + r.tags.join(' ')).toLowerCase().includes(ql)));
  }
  function paintPalette() {
    const host = $('#pPal'); if (!host) return;
    const list = listRows(), shown = list.slice(0, limit);
    host.innerHTML = shown.map((r) => `<button class="card ${pick && pick.id === r.id ? 'on' : ''}" data-a="pick" data-id="${r.id}" title="${esc(r.name)} · ${esc(r.cat)} · ${r.fw}×${r.fd} m"><img alt="" data-k="a:${r.id}"><span>${esc(r.name)}</span></button>`).join('')
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
    else if (a === 'undo') doUndo(); else if (a === 'redo') doRedo();
    else if (a === 'tool') { tool = b.dataset.k; if (tool !== 'place') pick = null; applyTool(); render(); }
    else if (a === 'tile') { tile = b.dataset.k; render(); }
    else if (a === 'pick') { pick = rows.find((r) => r.id === +b.dataset.id); tool = 'place'; sel = null; MV.select(null); applyTool(); render(); }
    else if (a === 'more') { limit += 48; paintPalette(); }
    else if (a === 'del') delSel();
    else if (a === 'dup') { const s = objOf(sel); if (s) { commit(); const c = clone(s); c.id = nextId(); c.x += 2; c.z += 2; doc.objects.push(c); sel = c.id; refresh(); } }
    else if (a === 'rot') turn(+b.dataset.d);
  });
  el.addEventListener('change', (e) => {
    const t = e.target;
    if (t.id === 'pMap') return;
    if (t.id === 'pSnap') snap = +t.value; else if (t.id === 'pRot') rsnap = +t.value;
    else if (t.id === 'pKit') { kit = t.value; cat = ''; limit = 48; render(); }
    else if (t.id === 'pCat') { cat = t.value; limit = 48; paintPalette(); }
    else if (t.id === 'pFoot') { MV.setOverlay('foot', t.checked); }
    else if (t.id === 'pWalk') { MV.setOverlay('walk', t.checked); }
    else if (t.id === 'pLook') { applyLook(t.value); }
    else if (t.dataset.p && sel) editProp(t);
  });
  el.addEventListener('input', (e) => { if (e.target.id === 'pQ') { q = e.target.value; limit = 48; paintPalette(); } });

  function editProp(t) {
    const s = objOf(sel), p = t.dataset.p; if (!s) return; commit();
    const n = +t.value;
    if (p === 'x' || p === 'z' || p === 'rot' || p === 'scale' || p === 'fw' || p === 'fd' || p === 'y') { if (Number.isFinite(n)) s[p] = p === 'scale' ? Math.max(0.2, Math.min(6, n)) : n; }
    else if (p === 'dx' || p === 'dz') { const cur = s.door || [0, 0]; if (t.value === '') s.door = null; else { cur[p === 'dx' ? 0 : 1] = n; s.door = cur; } }
    else if (p === 'walkable') s.walkable = t.checked;
    else if (p === 'tags') s.tags = t.value.split(',').map((x) => x.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '')).filter(Boolean).slice(0, 12);
    else if (p === 'pw' && s.panel) s.panel.w = Math.max(0.3, n); else if (p === 'ph' && s.panel) s.panel.h = Math.max(0.3, n);
    refresh();
  }
  function turn(dir) { const s = objOf(sel); if (!s) return; commit(); s.rot = (((s.rot + dir * rsnap) % 360) + 360) % 360; refresh(); }
  function delSel() { if (!sel) return; commit(); doc.objects = doc.objects.filter((o) => o.id !== sel); sel = null; refresh(); }
  let awaitingSave = false;
  function save() { awaitingSave = true; setTimeout(() => { awaitingSave = false; }, 4000); send({ type: 'map_save', doc: doc, use: true }); }

  // ---------------------------------------------------------------- events: the 3D view
  function worldAt(e) {
    const r = dom.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera); return ray.ray.intersectPlane(plane, hit) ? hit.clone() : null;
  }
  function paintAt(p) {
    const c = doc.cell, h = half(), i = Math.floor((p.x + h) / c), j = Math.floor((p.z + h) / c);
    if (i < 0 || j < 0 || i >= doc.n || j >= doc.n || doc.ground[j][i] === tile) return;
    doc.ground[j] = doc.ground[j].slice(0, i) + tile + doc.ground[j].slice(i + 1); dirty = true; MV.doc = doc; MV.rebuildGround();
  }
  function applyTool() {
    controls.mouseButtons = tool === 'select' ? { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN } : { LEFT: -1, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    dom.style.cursor = tool === 'select' ? '' : 'crosshair'; ghost.visible = false;
  }
  window.addEventListener('pointerdown', (e) => {
    if (!open || e.target !== dom || e.button !== 0 || !doc) return;
    const p = worldAt(e); if (!p) return;
    if (tool === 'paint') { commit(); painting = true; paintAt(p); return; }
    if (tool === 'place') {
      if (!pick) return; addObject(pick, snapV(Math.max(-half(), Math.min(half(), p.x))), snapV(Math.max(-half(), Math.min(half(), p.z)))); return;
    }
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
    const id = MV.pick(ray);
    if (id != null) {
      sel = id; MV.select(id); const o = objOf(id); drag = { id, dx: o.x - p.x, dz: o.z - p.z, moved: false, snapshot: JSON.stringify(doc) }; controls.enabled = false; render(false);
    } else if (sel) { sel = null; MV.select(null); render(false); }
  }, true);
  window.addEventListener('pointermove', (e) => {
    if (!open || !doc) return;
    if (e.target !== dom && !drag && !painting) return;
    const p = worldAt(e); if (!p) return;
    if (painting) { paintAt(p); return; }
    if (drag) {
      const o = objOf(drag.id); if (!o) return;
      const nx = snapV(p.x + drag.dx), nz = snapV(p.z + drag.dz);
      if (nx !== o.x || nz !== o.z) { o.x = Math.max(-half(), Math.min(half(), nx)); o.z = Math.max(-half(), Math.min(half(), nz)); drag.moved = true; MV.sync(); MV.select(o.id); MV.updateColliders(); }
      return;
    }
    if (tool === 'place' && pick) {
      const d = defaults(pick); ghost.visible = true; ghost.scale.set(Math.max(0.4, d.fw / 2), 1, Math.max(0.4, d.fd / 2)); ghost.position.set(snapV(p.x), 0, snapV(p.z));
    } else ghost.visible = false;
  });
  window.addEventListener('pointerup', () => {
    if (painting) { painting = false; render(false); }
    if (drag) { if (drag.moved) { undo.push(drag.snapshot); redo.length = 0; dirty = true; MV.rebuildOverlays(); } drag = null; controls.enabled = true; render(false); }
  });
  window.addEventListener('keydown', (e) => {
    if (!open || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '')) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? doRedo() : doUndo(); }
    else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); doRedo(); }
    else if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); delSel(); }
    else if (e.key.toLowerCase() === 'r' && !mod) turn(e.shiftKey ? -1 : 1);
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
    if (!open) return; open = false; el.hidden = true; btn.classList.remove('on'); document.body.classList.remove('planning'); ghost.visible = false; drag = null; painting = false;
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
    onMap(m) { maps = m.maps || maps; if (open) { const f = awaitingSave; awaitingSave = false; loadFromMsg(m, f); if (doc) { MV.doc = doc; MV.sync(); MV.updateColliders(); MV.rebuildOverlays(); MV.nav = m.nav; } render(); } },
    assetsData(m) {
      rows = m.rows || []; byKit = new Map(); for (const r of rows) { if (!byKit.has(r.pack)) byKit.set(r.pack, []); byKit.get(r.pack).push(r); }
      if (!byKit.has(kit)) kit = [...byKit.keys()][0]; if (open) render();
    },
    thumbsReady() { if (open) fillThumbs(); },
  };
}
