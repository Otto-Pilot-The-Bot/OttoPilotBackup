import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as UI from './ui.js';
import { ArtStore } from './art.js';
import { createRealism } from './realism.js';
import { createCameraModes } from './camera.js';
import { createMapView, LOOKS } from './mapview.js';
import { createEditor } from './editor.js';
import { buildDesign, animateDesign, mixers, glowMats, kitGlow } from './models.js';

const HALF = 24;

// ------------------------------------------------------------------ renderer / scene
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9ec5e8);
scene.fog = new THREE.Fog(0x9ec5e8, 55, 120);
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 220);
const resetCamera = () => { const h = Math.max(24, curHalf || 24); camera.position.set(0, h * 0.95 + 4, h * 1.15 + 8); controls.target.set(0, 1, 0); };
const controls = new OrbitControls(camera, renderer.domElement);
controls.maxPolarAngle = Math.PI * 0.48; controls.minDistance = 5; controls.maxDistance = 70;
resetCamera(); window.__camera = camera; window.__controls = controls;
const hemi = new THREE.HemisphereLight(0xffffff, 0x6a7a55, 1.0); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff2d6, 2.2);
sun.castShadow = true;
Object.assign(sun.shadow.camera, { left: -38, right: 38, top: 38, bottom: -38 }); sun.shadow.mapSize.set(2048, 2048);
scene.add(sun);
const REAL = createRealism({ renderer, scene, camera, sun, hemi });          // realism pass (web/realism.js); ?plain=1 turns it off
var ground, groundParts = [], curHalf = 0;
function buildGround(half) {
  for (const o of groundParts) { scene.remove(o); o.geometry?.dispose?.(); }
  groundParts = []; curHalf = half;
  ground = new THREE.Mesh(new THREE.PlaneGeometry(half * 2 + 8, half * 2 + 8), new THREE.MeshStandardMaterial({ color: 0x8fbf6a }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true;
  const grid = new THREE.GridHelper(half * 2, half, 0x6a9a4a, 0x7aab58); grid.position.y = 0.01;
  const border = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(half * 2, 0.2, half * 2)), new THREE.LineBasicMaterial({ color: 0x4a6a3a }));
  groundParts = REAL.on ? [ground] : [ground, grid, border];
  if (REAL.on) { REAL.buildGround(half, ground); border.geometry.dispose(); grid.geometry.dispose(); }
  for (const o of groundParts) scene.add(o);
  Object.assign(sun.shadow.camera, { left: -half - 14, right: half + 14, top: half + 14, bottom: -half - 14 }); sun.shadow.camera.updateProjectionMatrix();
  controls.maxDistance = 70 + (half - 24) * 1.6; scene.fog.far = 120 + (half - 24) * 2.2;
}
buildGround(24);

const mat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8, ...o });
const mesh = (g, m, x = 0, y = 0, z = 0) => { const o = new THREE.Mesh(g, m); o.position.set(x, y, z); o.castShadow = true; o.receiveShadow = true; return o; };
const HEX = /^#[0-9a-f]{6}$/i;
const safeCol = (c, d = '#9e9e9e') => (HEX.test(c || '') ? c : d);

function label(text, scale = 1, color = '#fff') {
  if (text.length > 24) text = text.slice(0, 23) + '…';
  const c = document.createElement('canvas'); c.width = 512; c.height = 96;
  const g = c.getContext('2d'); g.font = 'bold 44px system-ui'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineWidth = 8; g.strokeStyle = '#000a'; g.strokeText(text, 256, 48); g.fillStyle = color; g.fillText(text, 256, 48);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false, transparent: true, fog: false }));
  s.scale.set(4 * scale, 0.75 * scale, 1); s.renderOrder = 10; return s;
}

// ------------------------------------------------------------------ day / night
const key = (arr, h) => { for (let i = 1; i < arr.length; i++) if (h <= arr[i][0]) { const [h0, a] = arr[i - 1], [h1, b] = arr[i], t = (h - h0) / (h1 - h0 || 1); return [a, b, t]; } const l = arr.at(-1)[1]; return [l, l, 0]; };
const numAt = (arr, h) => { const [a, b, t] = key(arr, h); return a + (b - a) * t; };
const colAt = (arr, h) => { const [a, b, t] = key(arr, h); return new THREE.Color(a).lerp(new THREE.Color(b), t); };
const SKY = [[0, 0x4a5c94], [5, 0x4a5c94], [6.5, 0xf4c49a], [8, 0x9ec5e8], [17, 0x9ec5e8], [18.5, 0xf2b080], [20, 0x52659e], [24, 0x4a5c94]];
const SUNC = [[0, 0x9fb0ff], [5, 0x9fb0ff], [6.5, 0xffb070], [8, 0xfff2d6], [17, 0xfff2d6], [18.5, 0xffa060], [20, 0x9fb0ff], [24, 0x9fb0ff]];
const SUNI = [[0, 1.3], [5, 1.3], [6.5, 1.6], [8, 2.2], [17, 2.2], [18.5, 1.6], [20, 1.3], [24, 1.3]];
const HEMI = [[0, 1.05], [5, 1.05], [6.5, 1.0], [8, 1], [17, 1], [18.5, 1.0], [20, 1.05], [24, 1.05]];
const lampMats = [];
let nightness = 0;
function applyTime(h) {
  const sky = colAt(SKY, h);
  scene.background.copy(sky); scene.fog.color.copy(sky);
  sun.color.copy(colAt(SUNC, h)); sun.intensity = numAt(SUNI, h); hemi.intensity = numAt(HEMI, h);
  if (h > 6 && h < 18) { const a = ((h - 6) / 12) * Math.PI; sun.position.set(Math.cos(a) * 36, Math.sin(a) * 30 + 3, 12); } else sun.position.set(-20, 28, -8);
  nightness = 1 - Math.min(1, Math.max(0, (numAt(SUNI, h) - 1.3) / 0.9));
  for (const m of lampMats) m.emissiveIntensity = 0.5 + nightness * 2.2;
}

// ------------------------------------------------------------------ places (with interiors he can walk into)
const frames = [], buildings = {}, placeLabels = [];
let wallMats = [], roofMats = [];
function startBuilding(key) { const b = (buildings[key] = { walls: [], roofs: [] }); wallMats = b.walls; roofMats = b.roofs; }
function shell(list, c, o = {}) { const m = new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, transparent: true, opacity: 1, ...o }); list.push(m); return m; }
function box(g, w, h, d, x, y, z, m) { const o = mesh(new THREE.BoxGeometry(w, h, d), m, x, y, z); g.add(o); return o; }
function addLabel(g, text, scale, y, x = 0, z = 0) { const l = label(text, scale); l.position.set(x, y, z); g.add(l); placeLabels.push(l); return l; }
// walls with a door gap (door centred on x=0 in the front wall)
function wallsWithDoor(g, w, h, d, cz, color, doorW = 1.8, doorH = 2.0, doorSide = 'front') {
  const wm = shell(wallMats, color), hw = w / 2, hd = d / 2, side = (w - doorW) / 2, fz = doorSide === 'front' ? cz + hd : cz - hd, bz = doorSide === 'front' ? cz - hd : cz + hd;
  box(g, w, h, 0.2, 0, h / 2, bz, wm);                                              // back
  box(g, 0.2, h, d, -hw, h / 2, cz, wm); box(g, 0.2, h, d, hw, h / 2, cz, wm);        // sides
  box(g, side, h, 0.2, -(doorW / 2 + side / 2), h / 2, fz, wm); box(g, side, h, 0.2, doorW / 2 + side / 2, h / 2, fz, wm);   // front pieces
  box(g, doorW, h - doorH, 0.2, 0, doorH + (h - doorH) / 2, fz, wm);                  // lintel
}
function buildPlaces(P) {
  const FB = P.home.enter;                                  // fixed buildings exist only if the server says places are enterable
  const home = new THREE.Group(); home.position.set(P.home.x, 0, P.home.z);
  home.add(mesh(new THREE.CylinderGeometry(3.4, 3.4, 0.2, 32), mat(0x7e8fa8), 0, 0.1, 0));
  if (FB) {
  startBuilding('home');
  const hm = shell(wallMats, 0xd9c7a3);
  box(home, 4.6, 2.6, 0.2, 0, 1.3, -1.9, hm); box(home, 0.2, 2.6, 3.8, -2.3, 1.3, 0, hm); box(home, 0.2, 2.6, 3.8, 2.3, 1.3, 0, hm);
  box(home, 5.2, 0.25, 4.6, 0, 2.72, 0, shell(roofMats, 0x8d3b2e));
  box(home, 2.0, 0.45, 1.2, -1.1, 0.45, -1.0, mat(0xd9534f)); box(home, 0.7, 0.2, 0.8, -1.6, 0.8, -1.0, mat(0xffffff));
  const lamp = mat(0xffe29a, { emissive: 0xffd36a, emissiveIntensity: 0.8 }); lampMats.push(lamp); box(home, 0.4, 0.4, 0.4, 1.6, 0.45, -1.3, lamp);
  }
  addLabel(home, FB ? 'home' : 'home pad', 0.8, FB ? 3.8 : 1.2); scene.add(home);

  // ---- fuel station (not enterable)
  const fuel = new THREE.Group(); fuel.position.set(P.fuel_station.x, 0, P.fuel_station.z);
  fuel.add(mesh(new THREE.CylinderGeometry(3, 3, 0.2, 32), mat(0x8c8c8c), 0, 0.1, 0));
  fuel.add(mesh(new THREE.BoxGeometry(1.2, 2.2, 1.2), mat(0xf4b400), 0, 1.2, 0));
  const scr = mat(0x222222, { emissive: 0x33ff88, emissiveIntensity: 0.6 }); lampMats.push(scr);
  fuel.add(mesh(new THREE.BoxGeometry(0.8, 0.6, 0.05), scr, 0, 1.6, 0.63));
  fuel.add(mesh(new THREE.CylinderGeometry(0.06, 0.06, 1.4), mat(0x222222), 0.9, 0.9, 0));
  addLabel(fuel, 'fuel station', 0.8, 3.2); scene.add(fuel);

  if (!FB) return;
  // ---- clothing store: racks, mirror, counter inside
  const store = new THREE.Group(); store.position.set(P.clothing_store.x, 0, P.clothing_store.z);
  store.add(mesh(new THREE.BoxGeometry(5.2, 0.12, 4.2), mat(0xe8dcc0), 0, 0.06, -1.5));
  startBuilding('clothing_store');
  wallsWithDoor(store, 5, 3, 4, -1.5, 0xf2e6d0);
  box(store, 5.4, 0.25, 4.4, 0, 3.1, -1.5, shell(roofMats, 0xc2185b));
  box(store, 5.6, 0.2, 1.2, 0, 2.75, 0.9, shell(wallMats, 0xc2185b));                              // awning
  for (const [x, c] of [[-1.6, 0xe53935], [0, 0x1e88e5], [1.6, 0xfdd835]]) { box(store, 1.2, 1.5, 0.35, x, 0.9, -3.15, mat(c)); box(store, 1.3, 0.08, 0.5, x, 1.7, -3.15, mat(0x6d4c41)); }
  box(store, 0.12, 1.6, 0.9, 2.3, 1.1, -1.6, mat(0xb3e5fc, { metalness: 0.7, roughness: 0.1 }));  // mirror
  box(store, 1.6, 0.9, 0.6, -1.6, 0.45, -1.6, mat(0x8d6e63));                                       // counter
  addLabel(store, 'clothing store', 0.9, 4.4, 0, -1.5); scene.add(store);

  // ---- workshop: door in front, workbench and printer inside
  const ws = new THREE.Group(); ws.position.set(P.workshop.x, 0, P.workshop.z);
  ws.add(mesh(new THREE.BoxGeometry(5.7, 0.12, 4.2), mat(0xb8b2a2), 0, 0.06, 1.5));
  startBuilding('workshop');
  wallsWithDoor(ws, 5.5, 3, 4, 1.5, 0x78909c, 1.8, 2.0, 'back');
  box(ws, 6, 0.3, 4.6, 0, 3.15, 1.5, shell(roofMats, 0x455a64));
  ws.add(mesh(new THREE.CylinderGeometry(0.3, 0.3, 1.6), mat(0x37474f), 1.8, 4, 2.5));
  box(ws, 2.4, 0.9, 0.8, 1.3, 0.45, 3.0, mat(0x8d6e63)); box(ws, 0.9, 0.7, 0.8, 1.6, 1.25, 3.0, mat(0xff7043));    // bench + printer
  box(ws, 0.3, 2, 2.2, -2.5, 1.2, 2.2, mat(0x5d4037));                                                           // shelf
  box(ws, 1.6, 1, 1.2, -1, 0.5, -1.2, mat(0xff7043));                                                             // outdoor print stand
  addLabel(ws, 'workshop', 0.9, 4.8, 0, 1.5); scene.add(ws);

  // ---- gallery: long wall on the far side; frames face the default camera; canopy fades when he is inside
  const gal = new THREE.Group(); gal.position.set(P.gallery.x, 0, P.gallery.z);
  gal.add(mesh(new THREE.BoxGeometry(17, 0.2, 8.5), mat(0xd9cfb8), 0, 0.1, 0.3));
  gal.add(mesh(new THREE.BoxGeometry(15, 5.2, 0.5), mat(0xf6efe0), 0, 2.7, -3));
  startBuilding('gallery');
  box(gal, 15.6, 0.3, 4.2, 0, 5.45, -1.0, shell(roofMats, 0x8d6e63));
  for (const x of [-7.2, 7.2]) gal.add(mesh(new THREE.BoxGeometry(0.3, 5.3, 0.3), mat(0x8d6e63), x, 2.65, 1.0));
  addLabel(gal, 'gallery', 1.1, 6.7, 0, -2.5);
  const px = [-5.1, -1.7, 1.7, 5.1];
  for (const y of [3.6, 1.5]) for (const x of px) {
    const g = new THREE.Group(); g.position.set(x, y, -2.7);
    g.add(mesh(new THREE.BoxGeometry(2.2, 2.2, 0.14), mat(0x8d6e63), 0, 0, 0));
    const m = new THREE.MeshStandardMaterial({ color: 0xfffaf0, roughness: 0.9 });
    const pic = new THREE.Mesh(new THREE.PlaneGeometry(1.85, 1.85), m); pic.position.z = 0.08; g.add(pic);
    gal.add(g); frames.push({ m, id: null });
  }
  scene.add(gal);
}

let insideKey = null;
function fadeBuildings(dt) {
  const k = Math.min(1, dt * 5);
  for (const [key, b] of Object.entries(buildings)) {
    const inHere = insideKey === key;
    const wallT = inHere && key !== 'gallery' ? 0.16 : 1, roofT = inHere ? 0.04 : 1;
    for (const [list, target] of [[b.walls, wallT], [b.roofs, roofT]]) for (const m of list) {
      m.opacity += (target - m.opacity) * k;
      const t = m.opacity < 0.985; if (m.transparent !== t) { m.transparent = t; m.needsUpdate = true; }
      m.depthWrite = !t || m.opacity > 0.5;
    }
  }
}

const texCache = new Map();
function updateGallery() {
  const list = [...art.meta.values()].filter((a) => a.status !== 'broken' && a.kind !== 'sculpture' && art.canvas.has(a.id)).sort((a, b) => b.id - a.id).slice(0, frames.length);
  frames.forEach((f, i) => {
    const a = list[i];
    if (!a) { if (f.id !== null) { f.m.map = null; f.m.color.set(0xfffaf0); f.m.needsUpdate = true; f.id = null; } return; }
    if (f.id === a.id) return;
    let t = texCache.get(a.id);
    if (!t) { t = new THREE.CanvasTexture(art.canvas.get(a.id)); t.colorSpace = THREE.SRGBColorSpace; texCache.set(a.id, t); }
    f.m.map = t; f.m.color.set(0xffffff); f.m.needsUpdate = true; f.id = a.id;
  });
}

// ------------------------------------------------------------------ world objects
const objMeshes = new Map();
let objectsById = new Map();
const hash = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); };
const creationGeo = (name) => [new THREE.OctahedronGeometry(0.6), new THREE.TorusKnotGeometry(0.4, 0.14, 48, 8), new THREE.BoxGeometry(0.8, 0.8, 0.8), new THREE.IcosahedronGeometry(0.55), new THREE.CylinderGeometry(0.3, 0.5, 1, 6)][hash(name) % 5];
const SHAPE = { box: () => new THREE.BoxGeometry(1, 1, 1), sphere: () => new THREE.SphereGeometry(0.5, 20, 14), cone: () => new THREE.ConeGeometry(0.5, 1, 20), cylinder: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 20), torus: () => new THREE.TorusGeometry(0.38, 0.13, 12, 28) };

function blueprintTex() {
  const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
  g.fillStyle = '#2b5fa8'; g.fillRect(0, 0, 128, 128); g.strokeStyle = '#cfe3ff'; g.lineWidth = 1;
  for (let i = 0; i <= 128; i += 16) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 128); g.moveTo(0, i); g.lineTo(128, i); g.stroke(); }
  g.lineWidth = 3; g.strokeRect(34, 34, 60, 60); g.beginPath(); g.arc(64, 64, 18, 0, 7); g.stroke();
  return new THREE.CanvasTexture(c);
}
let bpTex;

function makeProject(o, stage, c) {
  const g = new THREE.Group();
  g.add(mesh(new THREE.BoxGeometry(2.6, 0.12, 1.8), mat(0x8d6e63), 0, 0.85, 0));
  for (const [x, z] of [[-1.1, -0.7], [1.1, -0.7], [-1.1, 0.7], [1.1, 0.7]]) g.add(mesh(new THREE.BoxGeometry(0.12, 0.85, 0.12), mat(0x5d4037), x, 0.42, z));
  if (stage === 'blueprint') {
    bpTex ||= blueprintTex();
    const p = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 1.3), new THREE.MeshStandardMaterial({ map: bpTex })); p.rotation.x = -Math.PI / 2; p.position.y = 0.92; g.add(p);
    g.add(mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.8, 10), mat(0xf5f5f5), 0.9, 1.0, 0.5)).rotation.z = Math.PI / 2;
  } else if (stage === 'gather') {
    let h = hash(o.name);
    for (let i = 0; i < 7; i++) { h = (h * 1103515245 + 12345) & 0x7fffffff; const gx = ((h % 100) / 100 - 0.5) * 2.0, gz = (((h >> 7) % 100) / 100 - 0.5) * 1.3, s = 0.15 + (h % 30) / 100;
      g.add(mesh(i % 2 ? new THREE.BoxGeometry(s, s, s) : new THREE.CylinderGeometry(s / 2, s / 2, s * 1.4, 8), mat(i % 3 ? c : 0xb0bec5), gx, 0.92 + s / 2, gz)); }
  } else {                                         // build: half-made scaffold around a growing piece
    const part = mesh(creationGeo(o.name), mat(c, { metalness: 0.3, roughness: 0.5 }), 0, 1.5, 0); part.scale.setScalar(0.7); g.add(part);
    const w = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.5, 1.5, 1.5)), new THREE.LineBasicMaterial({ color: 0xffd180 })); w.position.y = 1.6; g.add(w);
  }
  return g;
}

function makeObject(o, thumb = false) {
  const g = new THREE.Group(), c = new THREE.Color(safeCol(o.color)), m = mat(c);
  const stage = o.meta?.stage;
  let labelY = 2.4;
  switch (o.kind) {
    case 'tree': g.add(mesh(new THREE.CylinderGeometry(0.25, 0.35, 1.8), mat(0x6d4c41), 0, 0.9, 0)); g.add(mesh(new THREE.ConeGeometry(1.3, 2.6, 8), m, 0, 3, 0)); labelY = 4.6; break;
    case 'rock': { const r = mesh(new THREE.DodecahedronGeometry(0.9), m, 0, 0.6, 0); r.scale.set(1.2, 0.8, 1); g.add(r); break; }
    case 'flower': g.add(mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.9), mat(0x2e7d32), 0, 0.45, 0)); g.add(mesh(new THREE.SphereGeometry(0.28, 12, 8), m, 0, 1, 0)); g.add(mesh(new THREE.SphereGeometry(0.12), mat(0xfdd835), 0, 1.12, 0.16)); break;
    case 'ball': g.add(mesh(new THREE.SphereGeometry(0.6, 20, 14), m, 0, 0.6, 0)); break;
    case 'box': g.add(mesh(new THREE.BoxGeometry(1.2, 1.2, 1.2), m, 0, 0.6, 0)); break;
    case 'lamp': { g.add(mesh(new THREE.CylinderGeometry(0.08, 0.1, 3), mat(0x333333), 0, 1.5, 0)); const lm = mat(c, { emissive: c, emissiveIntensity: 0.9 }); lampMats.push(lm); g.userData.lamp = lm; g.add(mesh(new THREE.SphereGeometry(0.4), lm, 0, 3.1, 0)); labelY = 4; break; }
    case 'house': g.add(mesh(new THREE.BoxGeometry(3, 2, 3), m, 0, 1, 0)); g.add(mesh(new THREE.ConeGeometry(2.4, 1.4, 4), mat(0x8d3b2e), 0, 2.7, 0)).rotation.y = Math.PI / 4; g.add(mesh(new THREE.BoxGeometry(0.7, 1.2, 0.1), mat(0x4e342e), 0, 0.6, 1.53)); labelY = 4; break;
    case 'fountain': g.add(mesh(new THREE.CylinderGeometry(1.6, 1.8, 0.5, 24), mat(0x9e9e9e), 0, 0.25, 0)); g.add(mesh(new THREE.CylinderGeometry(1.3, 1.3, 0.1, 24), mat(0x4fc3f7, { transparent: true, opacity: 0.8 }), 0, 0.5, 0)); g.add(mesh(new THREE.CylinderGeometry(0.15, 0.2, 1.4), mat(0xbdbdbd), 0, 1.1, 0)); g.add(mesh(new THREE.SphereGeometry(0.3), m, 0, 1.9, 0)); break;
    case 'statue': g.add(mesh(new THREE.BoxGeometry(1.2, 0.8, 1.2), mat(0x9e9e9e), 0, 0.4, 0)); g.add(mesh(new THREE.CapsuleGeometry(0.35, 1.2, 4, 12), m, 0, 1.7, 0)); g.add(mesh(new THREE.SphereGeometry(0.3), m, 0, 2.7, 0)); break;
    case 'bench': g.add(mesh(new THREE.BoxGeometry(2.2, 0.15, 0.7), m, 0, 0.6, 0)); g.add(mesh(new THREE.BoxGeometry(2.2, 0.6, 0.12), m, 0, 1, -0.3)); for (const x of [-0.9, 0.9]) g.add(mesh(new THREE.BoxGeometry(0.12, 0.6, 0.6), mat(0x444444), x, 0.3, 0)); break;
    case 'creature': g.add(mesh(new THREE.SphereGeometry(0.7, 16, 12), m, 0, 0.7, 0)); for (const x of [-0.25, 0.25]) { g.add(mesh(new THREE.SphereGeometry(0.15), mat(0xffffff), x, 0.95, 0.55)); g.add(mesh(new THREE.SphereGeometry(0.07), mat(0x111111), x, 0.95, 0.68)); } break;
    case 'project': g.add(makeProject(o, stage || 'blueprint', c)); labelY = 3; break;
    case 'find': { const fm = new THREE.Mesh(new THREE.IcosahedronGeometry(0.2, 0), new THREE.MeshStandardMaterial({ color: c, flatShading: true, emissive: c, emissiveIntensity: 0.25 })); fm.position.y = 0.3; fm.castShadow = true; g.add(fm); g.userData.bob = fm; labelY = 0.9; break; }
    case 'ground': { const sq = o.meta?.shape === 'square', rr = o.meta?.r || 2; const gm = new THREE.Mesh(sq ? new THREE.PlaneGeometry(rr * 2, rr * 2) : new THREE.CircleGeometry(rr, 28), new THREE.MeshStandardMaterial({ color: c, roughness: 1 })); gm.rotation.x = -Math.PI / 2; gm.position.y = 0.012 + (o.id % 7) * 0.0015; gm.receiveShadow = true; g.add(gm); labelY = 0.4; break; }
    case 'gift_picture': {
      const gm = o.meta || {}, asp = Math.max(0.4, Math.min(2.5, (gm.w || 1) / (gm.h || 1))), H = Math.min(2.1, 2.5 / Math.max(1, asp)), W = H * asp, st = gm.style || 'frame', base = 0.5;
      const tex = new THREE.TextureLoader().load(`/gift/${gm.gift_id}/file`); tex.colorSpace = THREE.SRGBColorSpace;
      if (st === 'poster') { g.add(mesh(new THREE.CylinderGeometry(0.05, 0.05, base + H, 6), mat(0x6d4c41), 0, (base + H) / 2, -0.05)); g.add(mesh(new THREE.BoxGeometry(W + 0.1, H + 0.1, 0.04), mat(0xf5f0e0), 0, base + H / 2, 0)); }
      else { for (const x of [-W * 0.4, W * 0.4]) g.add(mesh(new THREE.CylinderGeometry(0.05, 0.05, base + H * 0.5, 6), mat(0x6d4c41), x, (base + H * 0.5) / 2, -0.12)); g.add(mesh(new THREE.BoxGeometry(W + 0.25, H + 0.25, st === 'canvas' ? 0.18 : 0.1), mat(st === 'canvas' ? 0xffffff : 0x8d6e63), 0, base + H / 2, 0)); }
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.MeshBasicMaterial({ map: tex })); pic.position.set(0, base + H / 2, st === 'poster' ? 0.03 : st === 'canvas' ? 0.1 : 0.07); g.add(pic);
      labelY = base + H + 0.6; break; }
    case 'gift_model':
    case 'landscape':
    case 'poi':
    case 'creation': {
      if (o.meta?.design) { const dg = buildDesign(o.meta.design, o.color); g.add(dg); g.userData.design = dg; labelY = Math.max(2.2, (o.meta.design.height || 1.5) + 0.9); break; }
      const b = mesh(creationGeo(o.name), mat(c, { metalness: 0.4, roughness: 0.4 }), 0, 1.0, 0); b.userData.spin = true; g.add(b); g.add(mesh(new THREE.CylinderGeometry(0.6, 0.7, 0.3, 16), mat(0x37474f), 0, 0.15, 0)); break; }
    case 'sculpture': {
      g.add(mesh(new THREE.CylinderGeometry(0.95, 1.05, 0.45, 24), mat(0xe9e1cf), 0, 0.22, 0));
      const s = new THREE.Group(); s.position.y = 0.45; s.userData.spin = true;
      for (const p of (o.meta?.parts || []).slice(0, 24)) {
        const gm = (SHAPE[p.s] || SHAPE.box)(); const pm = mesh(gm, mat(safeCol(p.c, '#b0bec5'), { roughness: 0.55 }), +p.x || 0, +p.y || 0, +p.z || 0);
        pm.scale.set(+p.sx || 1, +p.sy || 1, +p.sz || 1); s.add(pm);
      }
      g.add(s); labelY = 4.4; break; }
    default: g.add(mesh(new THREE.OctahedronGeometry(0.7), m, 0, 0.9, 0));
  }
  const tag = o.kind === 'project' ? `${o.name} · ${stage || 'blueprint'}` : o.name;
  g.userData.objId = o.id;
  g.userData.tip = { name: o.name, kind: o.kind, text: o.meta?.description || '', look: o.meta?.design?.summary || '', stage: o.kind === 'project' ? stage : '' };
  if (!thumb && o.kind !== 'ground' && o.kind !== 'find') {
    const l = label(tag, 0.6); l.position.y = labelY; g.add(l); g.userData.label = l;
    g.userData.born = performance.now(); g.scale.setScalar(0.01);
  }
  else if (!thumb) { g.userData.born = performance.now() - 5000; }
  g.position.set(o.x, 0, o.z);
  return g;
}
const sigOf = (o) => [o.kind, o.meta?.stage || '', o.name, o.color, o.meta?.parts?.length || '', o.meta?.design ? JSON.stringify(o.meta.design) : ''].join('|');
function syncObjects(list) {
  const ids = new Set(list.map((o) => o.id));
  for (const o of list) {
    const sig = sigOf(o), cur = objMeshes.get(o.id);
    if (cur && cur.userData.sig === sig) continue;
    if (cur) scene.remove(cur);
    const g = makeObject(o); g.userData.sig = sig; g.position.set(o.x, 0, o.z); scene.add(g); objMeshes.set(o.id, g);
  }
  for (const o of list) { const g = objMeshes.get(o.id); if (g && (g.position.x !== o.x || g.position.z !== o.z)) g.userData.glide = { x: o.x, z: o.z }; }   // the engine may move things
  objectsById = new Map(list.map((o) => [o.id, o]));
  for (const [id, g] of objMeshes) if (!ids.has(id)) { scene.remove(g); objMeshes.delete(id); }
}

// ------------------------------------------------------------------ thumbnails (offscreen render of any object, also sculptures)
const thumbCache = new Map(), thumbQueue = [], thumbWanted = new Set();
let thumbR = null, thumbScene = null, thumbCam = null, thumbBusy = false;
function thumbInit() {
  thumbR = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  thumbR.setSize(200, 200); thumbR.setPixelRatio(1);
  thumbScene = new THREE.Scene(); thumbScene.add(new THREE.HemisphereLight(0xffffff, 0x9a8f78, 1.5));
  const d = new THREE.DirectionalLight(0xffffff, 2.2); d.position.set(4, 8, 6); thumbScene.add(d);
  thumbCam = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
}
async function renderThumb(o) {
  if (!thumbR) thumbInit();
  const g = makeObject(o, true); g.position.set(0, 0, 0); thumbScene.add(g);
  if (g.userData.design) await Promise.race([g.userData.design.userData.ready, new Promise((r) => setTimeout(r, 5000))]);
  await new Promise((r) => setTimeout(r, 60));
  const box = new THREE.Box3().setFromObject(g), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
  const R = Math.max(size.x, size.y, size.z, 0.8) * 0.5 * 1.25 / Math.tan(THREE.MathUtils.degToRad(16));
  thumbCam.position.set(c.x + R * 0.62, c.y + R * 0.42, c.z + R * 0.78); thumbCam.lookAt(c);
  thumbR.render(thumbScene, thumbCam);
  const url = thumbR.domElement.toDataURL('image/png');
  thumbScene.remove(g);
  return url;
}
async function pumpThumbs() {
  if (thumbBusy) return; thumbBusy = true;
  while (thumbQueue.length) {
    const { key, o } = thumbQueue.shift();
    try { thumbCache.set(key, await renderThumb(o)); } catch (e) { thumbCache.set(key, ''); }
    UI.refreshSoon(); EDITOR?.thumbsReady();
  }
  thumbBusy = false;
}
/** Returns a data URL if ready (and queues it if not). */
function thumbOf(id) {
  const o = objectsById.get(id); if (!o) return null;
  const key = sigOf(o) + '|' + o.radius;
  if (thumbCache.has(key)) return thumbCache.get(key) || null;
  if (!thumbWanted.has(key)) { thumbWanted.add(key); thumbQueue.push({ key, o }); pumpThumbs(); }
  return null;
}
function thumbOfDesign(key, design, name) {                 // preview of any design (library model or kit building), rendered once and cached
  const k = 'd:' + key;
  if (thumbCache.has(k)) return thumbCache.get(k) || null;
  if (!thumbWanted.has(k)) { thumbWanted.add(k); thumbQueue.push({ key: k, o: { id: -1, kind: 'creation', name: name || 'x', color: '#9e9e9e', x: 0, z: 0, meta: { design } } }); pumpThumbs(); }
  return null;
}
function thumbOfArt(artId) {
  for (const o of objectsById.values()) if (o.meta?.art_id === artId) return thumbOf(o.id);
  return null;
}

// ------------------------------------------------------------------ labels: only nearby ones, never overlapping; full details on hover
let labelMode = 'smart', hoverId = null;
const tipEl = document.createElement('div'); tipEl.id = 'tip'; tipEl.hidden = true; document.body.appendChild(tipEl);
const _v = new THREE.Vector3();
function updateLabels() {
  const objs = [...objMeshes.values()].filter((g) => g.userData.label);
  if (labelMode === 'off') { for (const g of objs) g.userData.label.visible = false; for (const l of placeLabels) l.visible = false; return; }
  const H = innerHeight, f = 1 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
  const taken = [];
  const rect = (sp, wpos) => {
    _v.copy(wpos).project(camera);
    if (_v.z > 1 || Math.abs(_v.x) > 1.1 || Math.abs(_v.y) > 1.1) return null;
    const dist = camera.position.distanceTo(wpos), w = (sp.scale.x / dist) * f * H, h = (sp.scale.y / dist) * f * H;
    const x = (_v.x * 0.5 + 0.5) * innerWidth, y = (-_v.y * 0.5 + 0.5) * H;
    return [x - w / 2, y - h / 2, x + w / 2, y + h / 2];
  };
  const hit = (r) => taken.some((t) => r[0] < t[2] && r[2] > t[0] && r[1] < t[3] && r[3] > t[1]);
  for (const l of placeLabels) {                                    // buildings keep priority
    const wp = l.getWorldPosition(new THREE.Vector3()), r = rect(l, wp);
    l.visible = !!r; if (r) taken.push(r);
  }
  const cand = objs.map((g) => {
    const wp = g.position.clone(); wp.y = g.userData.label.position.y;
    return { g, wp, dCam: camera.position.distanceTo(wp), dBot: robot ? g.position.distanceTo(robotPos) : 99, hov: g.userData.objId === hoverId };
  }).sort((a, b) => (b.hov - a.hov) || (a.dCam - b.dCam));
  for (const c of cand) {
    const l = c.g.userData.label;
    const near = labelMode === 'all' || c.hov || c.dBot < 13 || c.dCam < 22;
    if (!near) { l.visible = false; continue; }
    const r = rect(l, c.wp);
    if (!r || (!c.hov && hit(r))) { l.visible = false; continue; }
    l.visible = true; taken.push(r);
  }
}
const hoverRay = new THREE.Raycaster(), hoverNdc = new THREE.Vector2(); let lastHover = 0;
renderer.domElement.addEventListener('pointermove', (e) => {
  const now = performance.now(); if (now - lastHover < 90 || e.buttons) return; lastHover = now;
  hoverNdc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); hoverRay.setFromCamera(hoverNdc, camera);
  const hits = hoverRay.intersectObjects([...objMeshes.values()], true);
  let id = null;
  for (const h of hits) { let n = h.object; while (n && n.userData.objId === undefined) n = n.parent; if (n) { id = n.userData.objId; break; } }
  hoverId = id;
  if (id === null) { tipEl.hidden = true; return; }
  const t = objMeshes.get(id)?.userData.tip; if (!t) return;
  const esc = (x) => String(x).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  tipEl.innerHTML = `<b>${esc(t.name)}</b> <span class="k">${esc(t.kind)}${t.stage ? ' · ' + esc(t.stage) : ''}</span>${t.look ? `<div>looks like: ${esc(t.look)}</div>` : ''}${t.text ? `<div class="d">${esc(t.text)}</div>` : ''}`;
  tipEl.style.left = Math.min(innerWidth - 270, e.clientX + 14) + 'px'; tipEl.style.top = Math.min(innerHeight - 90, e.clientY + 14) + 'px'; tipEl.hidden = false;
});
renderer.domElement.addEventListener('pointerleave', () => { hoverId = null; tipEl.hidden = true; });

// ------------------------------------------------------------------ robot
let robot, mixer, actions = {}, current = null, face, bodyMat, bodyOrig, headBone;
const accessories = new THREE.Group(); scene.add(accessories);
const accMeshes = {};
const robotPos = new THREE.Vector3(), targetPos = new THREE.Vector3();
let pendingAnim = null, oneShot = false, holdLoop = null, targetFace = null;
const LOOPING = new Set(['Idle', 'Walking', 'Running', 'Dance', 'Sitting', 'Death', 'Standing']);
let expr = { Angry: 0, Surprised: 0, Sad: 0 }, exprTarget = { Angry: 0, Surprised: 0, Sad: 0 };

new GLTFLoader().load('/models/RobotExpressive.glb', (gltf) => {
  robot = gltf.scene;
  const box = new THREE.Box3().setFromObject(robot); robot.scale.setScalar(1.7 / (box.max.y - box.min.y));      // keep in step with config.ROBOT_HEIGHT
  robot.traverse((o) => {
    if (o.isMesh) { o.castShadow = true; if (o.morphTargetDictionary) face = o; if (o.material && o.material.name === 'Main') { bodyMat = o.material; } }
    if (o.isBone && o.name === 'Head' && !headBone) headBone = o;
  });
  bodyOrig = bodyMat ? bodyMat.color.clone() : null;              // the model's own orange, kept so we can restore it
  scene.add(robot);
  mixer = new THREE.AnimationMixer(robot);
  for (const clip of gltf.animations) actions[clip.name] = mixer.clipAction(clip);
  for (const n of ['Jump', 'Yes', 'No', 'Wave', 'Punch', 'ThumbsUp', 'Death']) if (actions[n]) { actions[n].loop = THREE.LoopOnce; actions[n].clampWhenFinished = true; }
  mixer.addEventListener('finished', () => { oneShot = false; if (!holdLoop) play('Idle'); });
  play('Idle');
  if (last) applySnapshot(last, true);
});

function play(name, fade = 0.25) {
  const next = actions[name]; if (!next || (current === next && next.isRunning())) return;
  next.reset().fadeIn(fade).play();
  if (current && current !== next) current.fadeOut(fade);
  current = next; current.name = name;
}
function playEmote(name) {
  if (!actions[name]) return;
  if (LOOPING.has(name)) { holdLoop = name; oneShot = false; play(name); return; }
  holdLoop = null; oneShot = true; play(name, 0.2);
}

const ACC = {
  hat() { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.06, 24), null)); g.add(mesh(new THREE.CylinderGeometry(0.36, 0.42, 0.45, 24), null, 0, 0.25, 0)); return g; },
  scarf() { const g = new THREE.Group(); g.add(mesh(new THREE.TorusGeometry(0.66, 0.14, 10, 28), null)).rotation.x = Math.PI / 2; g.add(mesh(new THREE.BoxGeometry(0.22, 0.8, 0.12), null, 0.3, -0.45, 0.6)); return g; },
  goggles() { const g = new THREE.Group(); for (const x of [-0.24, 0.24]) g.add(mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.16, 20), null, x * 1.3, 0, 0)).rotation.x = Math.PI / 2; const s = mesh(new THREE.BoxGeometry(0.9, 0.05, 0.05), new THREE.MeshStandardMaterial({ color: 0x222222 }), 0, 0, -0.05); s.userData.fixed = true; g.add(s); return g; },
  antenna() { const g = new THREE.Group(); const st = mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.6), new THREE.MeshStandardMaterial({ color: 0x555555 }), 0, 0.3, 0); st.userData.fixed = true; g.add(st); g.add(mesh(new THREE.SphereGeometry(0.1, 12, 10), null, 0, 0.65, 0)); return g; },
};
const OFF = { hat: [0, 0.62, 0], scarf: [0, -0.38, 0], goggles: [0, 0.22, 0.8], antenna: [0.42, 0.7, 0] };

function syncOutfit(outfit) {
  for (const slot of Object.keys(ACC)) {
    const col = outfit[slot];
    if (!col) { if (accMeshes[slot]) { accessories.remove(accMeshes[slot]); delete accMeshes[slot]; } continue; }
    if (!accMeshes[slot]) { const g = ACC[slot](); accessories.add(g); accMeshes[slot] = g; }
    const g = accMeshes[slot];
    if (g.userData.color !== col) { g.userData.color = col; g.traverse((o) => { if (o.isMesh && !o.userData.fixed) { o.material = new THREE.MeshStandardMaterial({ color: safeCol(col), roughness: 0.6 }); o.castShadow = true; } }); }
  }
  if (bodyMat) { if (outfit.body) bodyMat.color.set(safeCol(outfit.body)); else if (bodyOrig) bodyMat.color.copy(bodyOrig); }
}

function setMood(m) {
  exprTarget = { Angry: 0, Surprised: 0, Sad: 0 };
  if (m === 'angry') exprTarget.Angry = 1;
  else if (['sad', 'tired', 'scared', 'bored'].includes(m)) exprTarget.Sad = m === 'bored' ? 0.5 : 1;
  else if (['surprised', 'excited'].includes(m)) exprTarget.Surprised = m === 'surprised' ? 1 : 0.6;
  else if (m === 'curious') exprTarget.Surprised = 0.3;
}

// ------------------------------------------------------------------ websocket
let ws, last = null, placesBuilt = false, snapHour = 8, snapAt = 0, intervalMs = 12000, paused = false, follow = true, placing = null, wasConnected = false;
const art = new ArtStore((o) => send(o));
let EDITOR = null;
const MV = createMapView({ scene, art });
let forcedHour = null, mapActive = false, mapSeen = false;
function applyLook(name) {
  const L = MV.setLook(name); forcedHour = L.hour; window.__look = MV.look;
  for (const o of groundParts) o.visible = !L.hideGrass;
  REAL.setTufts?.(false);
  UI.mapLook?.(MV.look);
}
window.__setFollow = (v) => { follow = v; }; window.__applyLook = applyLook; window.__MV = MV;
art.onChange(updateGallery);
const send = (o) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); };

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { wasConnected = true; UI.setConn(true); };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === 'snapshot') { const first = !last; last = m; applySnapshot(m, first); }
    else if (m.type === 'map') onMap(m);
    else if (m.type === 'action') onAction(m);
    else if (m.type === 'status') UI.status(m.text);
    else if (m.type === 'wish_result') UI.wishResult(m);
    else if (m.type === 'assets') { UI.assetsData(m); EDITOR?.assetsData(m); }
    else if (m.type === 'design_preview') UI.designPreview(m);
    else if (m.type === 'toast') UI.toast(m.text, m.ok === false ? 5000 : 2500);
    else if (m.type === 'log') UI.setLog(m.rows);
    else if (m.type === 'art_content') art.receive(m);
  };
  ws.onclose = () => { UI.setConn(false, wasConnected ? (last?.short_name || 'The robot') + ' has stopped or the connection dropped. Restart with ./run.sh — reconnecting…' : 'Connecting…'); setTimeout(connect, 2500); };
}

function onMap(m) {
  mapActive = !!m.doc;
  if (m.doc) {
    MV.setDoc(m.doc, m.nav);
    const q = new URLSearchParams(location.search).get('look'); applyLook(q || MV.look);
    if (m.doc.n * m.doc.cell / 2 !== curHalf) { buildGround(m.doc.n * m.doc.cell / 2); if (!mapSeen) { mapSeen = true; resetCamera(); } }
    applyLook(MV.look);
  }
  window.__mapMsg = m; EDITOR?.onMap?.(m);
}
function applySnapshot(m, teleport) {
  const s = m.state;
  if (!placesBuilt) { if (!(m.map && m.map.name)) buildPlaces(m.places); placesBuilt = true; }
  if (m.world_half && m.world_half !== curHalf) buildGround(m.world_half);
  insideKey = s.inside || null;
  UI.update(m);
  art.update(m.art);
  syncObjects(m.objects);
  syncOutfit(m.outfit);
  setMood(s.mood);
  { const dd = Math.hypot(s.x - robotPos.x, s.z - robotPos.z); walkSpeed = Math.max(1.3, Math.min(6, dd / Math.max(2, m.interval * 0.75))); }
  targetPos.set(s.x, 0, s.z);
  snapHour = m.world.hour; snapAt = performance.now(); intervalMs = (m.effective_interval || m.interval) * 1000; paused = s.paused;
  if (teleport && robot) { robotPos.copy(targetPos); robot.position.copy(robotPos); }
  updateGallery();
}

function onAction(a) {
  UI.onAction(a);
  if (a.mood) setMood(a.mood);
  pendingAnim = a.anim && a.anim !== 'Walking' && a.anim !== 'Running' ? a.anim : null;
  if (a.face) targetFace = new THREE.Vector3(a.face[0], 0, a.face[1]);
  if (a.anim === 'Death') playEmote('Death');
}

// ------------------------------------------------------------------ placing objects
function startPlace(cfg) { placing = cfg; document.body.classList.add('placing'); }
function cancelPlace() { placing = null; document.body.classList.remove('placing'); }
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(); let downAt = null;
renderer.domElement.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  if (CAM.mode === 'walk' || !placing || !downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObject(ground)[0]; if (!hit) return;
  const base = placing.design ? { type: 'place_design', ...placing.payload } : placing.move ? { type: 'object_move', id: placing.id, exact: placing.exact, snap: placing.snap }
    : placing.wish ? { type: 'wish_fulfil', ...placing } : { type: 'place_object', ...placing };
  send({ ...base, x: hit.point.x, z: hit.point.z });
  cancelPlace(); UI.placed();
});

const CAM = createCameraModes({
  camera, controls, dom: renderer.domElement,
  getRobot: () => ({ pos: robotPos, yaw: robot ? robot.rotation.y : 0 }),
  getHalf: () => curHalf || HALF, getColliders: () => (window.__colliders || []),
  onChange: (m) => { if (m === 'walk') cancelPlace(); if (m !== 'overhead') EDITOR?.close(); },
});
window.__cam = CAM;
EDITOR = createEditor({ camera, controls, dom: renderer.domElement, MV, send, CAM, thumbDesign: (k, d, n) => thumbOfDesign(k, d, n), applyLook });
window.__editor = EDITOR;
{ const q = new URLSearchParams(location.search), cm = q.get('cam');
  if (cm) setTimeout(() => { CAM.setMode(cm); const at = (q.get('at') || '').split(',').map(Number); if (at.length === 2 && cm === 'walk') CAM.pose(at[0], at[1], +q.get('yaw') || 0, +q.get('pitch') || 0); }, 2500); }
UI.init({ send, art, startPlace, cancelPlace, setFollow: (v) => { follow = v; }, resetCamera, thumb: thumbOf, thumbArt: thumbOfArt, thumbDesign: thumbOfDesign, setLabelMode: (m) => { labelMode = m; } });

// ------------------------------------------------------------------ frame loop
const clock = new THREE.Clock(), tmp = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);
let lastClock = '', frameN = 0, walkSpeed = 3;
const shortest = (a) => Math.atan2(Math.sin(a), Math.cos(a));
function frame() {
  requestAnimationFrame(frame);
  const dt = Math.min(clock.getDelta(), 0.1), now = performance.now();
  // world clock: glides between ticks (10 world minutes per tick)
  const hour = new URLSearchParams(location.search).get('hour') ? +new URLSearchParams(location.search).get('hour') : forcedHour != null ? forcedHour : (snapHour + (paused ? 0 : Math.min(1, (now - snapAt) / intervalMs)) * (10 / 60)) % 24;
  applyTime(hour); REAL.update(hour, nightness, dt, now / 1000);
  const hh = Math.floor(hour), mm = Math.floor((hour % 1) * 60), lbl = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
  if (lbl !== lastClock && last) { lastClock = lbl; UI.setClock({ label: lbl, day: last.world.day, phase: hour >= 5 && hour < 7.5 ? 'dawn' : hour >= 7.5 && hour < 18 ? 'day' : hour >= 18 && hour < 20 ? 'dusk' : 'night' }); }
  if (robot) {
    const d = tmp.subVectors(targetPos, robotPos); d.y = 0; const dist = d.length();
    if (dist > 0.12) {
      const speed = walkSpeed; robotPos.addScaledVector(d.normalize(), Math.min(dist, speed * dt));
      robot.rotation.y += shortest(Math.atan2(d.x, d.z) - robot.rotation.y) * Math.min(1, dt * 8);
      const want = speed > 4.2 ? 'Running' : 'Walking'; holdLoop = null;
      if (!current || current.name !== want) { oneShot = false; play(want); }
    } else if (current && (current.name === 'Walking' || current.name === 'Running')) {
      if (targetFace) { const f = targetFace.clone().sub(robotPos); robot.rotation.y = Math.atan2(f.x, f.z); }
      if (pendingAnim) { playEmote(pendingAnim); pendingAnim = null; } else play('Idle');
    } else if (pendingAnim && !oneShot) { playEmote(pendingAnim); pendingAnim = null; }
    robot.position.copy(robotPos);
    mixer.update(dt);
    if (face) for (const k of Object.keys(expr)) { expr[k] += (exprTarget[k] - expr[k]) * Math.min(1, dt * 4); face.morphTargetInfluences[face.morphTargetDictionary[k]] = expr[k]; }
    if (headBone) {
      headBone.getWorldPosition(tmp); accessories.position.copy(tmp); accessories.rotation.y = robot.rotation.y;
      for (const [slot, g] of Object.entries(accMeshes)) g.position.set(...OFF[slot]);
    }
  }
  const tsec = now / 1000;
  fadeBuildings(dt);
  for (const m of mixers) m.update(dt);
  for (const m of glowMats) m.emissiveIntensity = 1.0 + nightness * 1.6;
  for (const m of kitGlow) m.emissiveIntensity = 0.9 + nightness * 1.8;
  for (const g of objMeshes.values()) {
    if (g.userData.design) animateDesign(g.userData.design, tsec, dt);
    if (g.userData.glide) { const gl = g.userData.glide, k = Math.min(1, dt * 3); g.position.x += (gl.x - g.position.x) * k; g.position.z += (gl.z - g.position.z) * k; if (Math.hypot(gl.x - g.position.x, gl.z - g.position.z) < 0.03) { g.position.set(gl.x, 0, gl.z); g.userData.glide = null; } }
    if (g.userData.bob) { g.userData.bob.position.y = 0.3 + Math.sin(tsec * 2 + g.position.x) * 0.06; g.userData.bob.rotation.y += dt; }
    const age = (now - g.userData.born) / 600; g.scale.setScalar(Math.min(1, 0.01 + age) * (age < 1 ? 1 + Math.sin(age * Math.PI) * 0.25 : 1));
    g.children.forEach((c) => { if (c.userData.spin) c.rotation.y += dt * 0.8; });
  }
  if (CAM.mode === 'overhead') { if (follow && robot) controls.target.lerp(tmp.set(robotPos.x, 1, robotPos.z), Math.min(1, dt * 2)); controls.update(); }
  CAM.update(dt);
  if ((frameN++ & 3) === 0) updateLabels();
  renderer.render(scene, camera);
}
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
connect(); frame();
