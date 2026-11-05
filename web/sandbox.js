// A separate play area for trying models out. It talks to the server only to list and download models (read-only); layouts live in this browser or in files you export.
// Nothing here touches Otto, his map, his database or his world.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const $ = (id) => document.getElementById(id);
const LS_LAYOUTS = 'ottoSandbox:layouts', LS_CURRENT = 'ottoSandbox:current';
const HALF = 60;                                   // the ground is 120 m across

// ---------------------------------------------------------------- scene
const canvas = $('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xcfd8dc);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 600);
camera.position.set(40, 38, 48);
const controls = new OrbitControls(camera, canvas);
controls.target.set(0, 0, 0);
controls.maxPolarAngle = Math.PI * 0.49;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.35));
const sun = new THREE.DirectionalLight(0xffffff, 2.0);
sun.position.set(40, 70, 30);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -HALF, right: HALF, top: HALF, bottom: -HALF, near: 1, far: 220 });
scene.add(sun);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(HALF * 2, HALF * 2), new THREE.MeshStandardMaterial({ color: 0xb9c4b0, roughness: 1 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true;
scene.add(ground);
const grid = new THREE.GridHelper(HALF * 2, HALF / 2, 0x7d8a78, 0xa3ad9e);   // lines every 4 m
grid.position.y = 0.01;
scene.add(grid);

function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();

// ---------------------------------------------------------------- models
let assets = [], byId = new Map();
const loader = new GLTFLoader();
const templates = new Map();
function template(a) {
  if (!templates.has(a.id)) {
    templates.set(a.id, new Promise((res, rej) => loader.load(`/asset/${a.id}?v=2`, res, undefined, rej)).then((g) => {
      const holder = new THREE.Group(), s = g.scene;
      s.scale.multiplyScalar(a.fit > 0 ? a.fit : 1);
      holder.add(s);
      const b = new THREE.Box3().setFromObject(holder), c = b.getCenter(new THREE.Vector3());
      s.position.set(-c.x, -b.min.y, -c.z);                     // sits on the ground, centred
      s.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true; o.receiveShadow = true;
        for (const m of Array.isArray(o.material) ? o.material : [o.material]) {   // colours stay as authored; only fully-metal files (black without reflections) are made matte
          if (m && m.isMeshStandardMaterial && m.metalness > 0.3) m.metalness = m.metalnessMap ? 0.15 : (m.roughness >= 0.99 ? 0 : 0.3);
        }
      });
      return holder;
    }));
  }
  return templates.get(a.id);
}

// ---------------------------------------------------------------- the layout
let items = [];                                    // {uid, a: asset id, x, z, r (degrees), s (scale), g: THREE.Group}
let uidn = 1, selected = null, brush = null, ghost = null;
const history = [];

const snapshot = () => items.map((i) => ({ a: i.a, x: i.x, z: i.z, r: i.r, s: i.s }));
function remember() { history.push(JSON.stringify(snapshot())); if (history.length > 60) history.shift(); persist(); }
function persist() { try { localStorage.setItem(LS_CURRENT, JSON.stringify(snapshot())); } catch (e) { /* storage may be blocked */ } }

function apply(i) {
  i.g.position.set(i.x, 0, i.z);
  i.g.rotation.y = -i.r * Math.PI / 180;
  i.g.scale.setScalar(i.s);
}
async function addItem(d, quiet) {
  const a = byId.get(d.a);
  if (!a) return null;
  const item = { uid: uidn++, a: a.id, x: +d.x || 0, z: +d.z || 0, r: +d.r || 0, s: Math.min(5, Math.max(0.1, +d.s || 1)), g: null };
  try {
    const t = await template(a);
    item.g = t.clone(true);
  } catch (e) { say(`Could not load ${a.name}.`); return null; }
  item.g.userData.uid = item.uid;
  scene.add(item.g); items.push(item); apply(item);
  if (!quiet) remember();
  return item;
}
function removeItem(i, quiet) {
  scene.remove(i.g);
  items = items.filter((o) => o !== i);
  if (selected === i) select(null);
  if (!quiet) remember();
}
async function setLayout(list) {
  for (const i of [...items]) removeItem(i, true);
  select(null);
  let skipped = 0;
  for (const d of Array.isArray(list) ? list.slice(0, 2000) : []) { if (!(await addItem(d, true))) skipped++; }
  persist();
  return skipped;
}

// ---------------------------------------------------------------- selection
const box = new THREE.BoxHelper(new THREE.Object3D(), 0xffb347);
box.visible = false; scene.add(box);
function select(i) {
  selected = i;
  $('selCtl').hidden = !i;
  $('selInfo').hidden = !!i;
  if (i) {
    const a = byId.get(i.a);
    $('rot').value = ((i.r % 360) + 360) % 360; $('rotV').textContent = Math.round(((i.r % 360) + 360) % 360) + '°';
    $('scl').value = i.s; $('sclV').textContent = i.s.toFixed(2);
    $('selInfo').textContent = '';
    box.setFromObject(i.g); box.visible = true;
    say(`${a ? a.name : 'model'}  (${i.x.toFixed(1)}, ${i.z.toFixed(1)})`);
  } else box.visible = false;
}

// ---------------------------------------------------------------- palette
const listEl = $('list');
function renderList() {
  const q = $('q').value.trim().toLowerCase(), pack = $('pack').value;
  const hit = assets.filter((a) => (!pack || a.pack === pack) && (!q || (a.name + ' ' + a.tags.join(' ')).toLowerCase().includes(q)));
  $('count').textContent = `${hit.length} model${hit.length === 1 ? '' : 's'}` + (hit.length > 300 ? ' (showing 300: type to narrow)' : '');
  listEl.innerHTML = '';
  for (const a of hit.slice(0, 300)) {
    const d = document.createElement('div');
    d.className = 'item' + (brush && brush.id === a.id ? ' on' : '');
    const b = document.createElement('b'); b.textContent = a.name;
    const s = document.createElement('span'); s.textContent = `${a.pack} · ${(Math.max(a.fw || 0, a.fd || 0)).toFixed(1)} m wide · ${(a.sy * (a.fit || 1)).toFixed(1)} m tall`;
    d.append(b, s);
    d.onclick = () => setBrush(a);
    listEl.appendChild(d);
  }
}
async function setBrush(a) {
  if (ghost) { scene.remove(ghost); ghost = null; }
  brush = a;
  $('brush').hidden = !a;
  if (a) {
    $('brush').textContent = `Placing: ${a.name}  (click the ground, Esc to stop)`;
    select(null);
    try { const t = await template(a); if (brush === a) { ghost = t.clone(true); ghost.visible = false; scene.add(ghost); } } catch (e) { say(`Could not load ${a.name}.`); }
  }
  renderList();
}
$('q').oninput = renderList; $('pack').onchange = renderList;

// ---------------------------------------------------------------- pointer handling
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
let cursor = null, down = null, drag = null;
function setNdc(e) { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera); }
function groundPoint(e) { setNdc(e); const h = ray.intersectObject(ground, false)[0]; return h ? h.point : null; }
function snapV(v) { const n = +$('snap').value; return n ? Math.round(v / n) * n : v; }
function pickItem(e) {
  setNdc(e);
  const hit = ray.intersectObjects(items.map((i) => i.g), true)[0];
  if (!hit) return null;
  let o = hit.object; while (o && o.userData.uid == null) o = o.parent;
  return o ? items.find((i) => i.uid === o.userData.uid) : null;
}
canvas.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  down = { x: e.clientX, y: e.clientY, moved: false };
  if (brush) return;
  const it = pickItem(e);
  if (it) {
    select(it);
    const p = groundPoint(e);
    drag = { it, ox: p ? it.x - p.x : 0, oz: p ? it.z - p.z : 0, changed: false };
    controls.enabled = false;
  }
}, true);
canvas.addEventListener('pointermove', (e) => {
  if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) down.moved = true;
  const p = groundPoint(e);
  cursor = p;
  if (drag && p) {
    drag.it.x = snapV(Math.max(-HALF, Math.min(HALF, p.x + drag.ox)));
    drag.it.z = snapV(Math.max(-HALF, Math.min(HALF, p.z + drag.oz)));
    drag.changed = true; apply(drag.it); box.setFromObject(drag.it.g);
  }
  if (ghost && p) { ghost.visible = true; ghost.position.set(snapV(p.x), 0, snapV(p.z)); ghost.rotation.y = -ghostRot * Math.PI / 180; ghost.scale.setScalar(ghostScale); }
});
let ghostRot = 0, ghostScale = 1;
addEventListener('pointerup', async (e) => {
  if (e.button !== 0 || !down) return;
  const wasClick = !down.moved;
  down = null;
  controls.enabled = true;
  if (drag) { if (drag.changed) remember(); drag = null; return; }
  if (!wasClick || e.target !== canvas) return;
  if (brush) {
    const p = groundPoint(e);
    if (p) { const it = await addItem({ a: brush.id, x: snapV(p.x), z: snapV(p.z), r: ghostRot, s: ghostScale }); if (it) select(it); }
  } else select(null);
});
canvas.addEventListener('contextmenu', (e) => e.preventDefault());

// ---------------------------------------------------------------- keys and buttons
function rotate(d) { if (selected) { selected.r += d; apply(selected); box.setFromObject(selected.g); select(selected); remember(); } else if (brush) ghostRot += d; }
function resizeSel(k) { if (selected) { selected.s = Math.min(5, Math.max(0.1, selected.s * k)); apply(selected); select(selected); remember(); } else if (brush) ghostScale = Math.min(5, Math.max(0.1, ghostScale * k)); }
async function duplicate() { if (selected) { const it = await addItem({ a: selected.a, x: selected.x + 2, z: selected.z + 2, r: selected.r, s: selected.s }); if (it) select(it); } }
async function undo() {
  if (history.length < 2) return;
  history.pop();
  await setLayout(JSON.parse(history[history.length - 1]));
}
addEventListener('keydown', (e) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement && document.activeElement.tagName) && e.key !== 'Escape') return;
  const k = e.key.toLowerCase();
  if (k === 'escape') { if (brush) setBrush(null); else select(null); }
  else if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); undo(); }
  else if (k === 'q') rotate(-15); else if (k === 'e') rotate(15);
  else if (k === 'r') resizeSel(1.1); else if (k === 'f') resizeSel(1 / 1.1);
  else if (k === 'd') duplicate();
  else if ((k === 'delete' || k === 'backspace') && selected) removeItem(selected);
});
$('rot').oninput = () => { if (selected) { selected.r = +$('rot').value; $('rotV').textContent = selected.r + '°'; apply(selected); box.setFromObject(selected.g); } };
$('rot').onchange = () => remember();
$('scl').oninput = () => { if (selected) { selected.s = +$('scl').value; $('sclV').textContent = selected.s.toFixed(2); apply(selected); box.setFromObject(selected.g); } };
$('scl').onchange = () => remember();
$('dup').onclick = duplicate;
$('del').onclick = () => { if (selected) removeItem(selected); };
$('undo').onclick = undo;
$('clear').onclick = async () => { if (!items.length || confirm('Remove everything from the sandbox? (Undo brings it back.)')) { await setLayout([]); remember(); } };

// ---------------------------------------------------------------- saving, loading, files
function layouts() { try { return JSON.parse(localStorage.getItem(LS_LAYOUTS) || '{}') || {}; } catch (e) { return {}; } }
function putLayouts(o) { try { localStorage.setItem(LS_LAYOUTS, JSON.stringify(o)); } catch (e) { say('This browser would not store the layout. Use Export file instead.'); } }
function refreshSaved() {
  const names = Object.keys(layouts()).sort();
  $('saved').innerHTML = names.length ? '' : '<option value="">(no saved layouts yet)</option>';
  for (const n of names) { const o = document.createElement('option'); o.value = o.textContent = n; $('saved').appendChild(o); }
}
const layoutName = () => ($('lname').value.trim() || 'my layout').slice(0, 60);
$('save').onclick = () => { const o = layouts(); o[layoutName()] = snapshot(); putLayouts(o); refreshSaved(); $('saved').value = layoutName(); say(`Saved "${layoutName()}" (${items.length} models).`); };
$('load').onclick = async () => { const n = $('saved').value, l = layouts()[n]; if (!l) return; const sk = await setLayout(l); remember(); $('lname').value = n; say(`Loaded "${n}"` + (sk ? `; ${sk} model(s) no longer exist and were skipped.` : '.')); };
$('rm').onclick = () => { const n = $('saved').value, o = layouts(); if (n && o[n] && confirm(`Forget "${n}"?`)) { delete o[n]; putLayouts(o); refreshSaved(); } };
$('export').onclick = () => {
  const data = JSON.stringify({ format: 'otto-sandbox', version: 1, name: layoutName(), items: snapshot() }, null, 1);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
  a.download = layoutName().replace(/[^\w\- ]+/g, '_') + '.sandbox.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
$('import').onclick = () => $('file').click();
$('file').onchange = async () => {
  const f = $('file').files[0]; $('file').value = '';
  if (!f || f.size > 4e6) return say('That file is too big or missing.');
  try {
    const d = JSON.parse(await f.text());
    if (d.format !== 'otto-sandbox' || !Array.isArray(d.items)) throw new Error('not a sandbox layout');
    const sk = await setLayout(d.items); remember();
    if (d.name) $('lname').value = String(d.name).slice(0, 60);
    say(`Imported ${d.items.length - sk} models` + (sk ? `; ${sk} skipped (their models are not in this library).` : '.'));
  } catch (e) { say('Could not read that file: ' + e.message); }
};
let msgT = 0;
function say(t) { const m = $('msg'); m.textContent = t; m.hidden = false; clearTimeout(msgT); msgT = setTimeout(() => { m.hidden = true; }, 5000); }

// ---------------------------------------------------------------- go
(async function start() {
  try {
    assets = await (await fetch('/sandbox/assets')).json();
  } catch (e) { return say('Could not get the model list. Is the server running?'); }
  byId = new Map(assets.map((a) => [a.id, a]));
  const packs = [...new Set(assets.map((a) => a.pack))];
  for (const p of packs) { const o = document.createElement('option'); o.value = o.textContent = p; $('pack').appendChild(o); }
  renderList(); refreshSaved();
  try { const cur = JSON.parse(localStorage.getItem(LS_CURRENT) || '[]'); if (cur.length) { await setLayout(cur); say(`Restored your last session (${items.length} models).`); } } catch (e) { /* nothing to restore */ }
  history.push(JSON.stringify(snapshot()));
})();
(function loop() {
  requestAnimationFrame(loop);
  controls.update();
  if (box.visible && selected && !drag) box.setFromObject(selected.g);
  renderer.render(scene, camera);
})();
