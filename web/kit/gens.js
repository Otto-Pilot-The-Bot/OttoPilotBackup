// Builder kit: parameterised, flat-shaded low-poly generators (houses, trees, lamps, ponds, cars...).
// Palette and seasonal themes are adapted from the read-only reference project (reference/city); the geometry is new 3D.
// Every generator receives parameters ALREADY validated and clamped by sprocket/kit.py, draws around the origin on the
// ground (y=0 is the bottom), and returns a THREE.Group. No parameter is ever executed as code.
import * as THREE from 'three';

export const kitGlow = new Set();                       // glowing materials, boosted at night by main.js
const matCache = new Map();
const M = (hex, o = {}) => {
  const k = hex + JSON.stringify(o);
  if (!matCache.has(k)) {
    const m = new THREE.MeshStandardMaterial({ color: hex, flatShading: true, roughness: 0.92, ...o });
    if (o.glow) { m.emissive = new THREE.Color(hex); m.emissiveIntensity = 1.0; kitGlow.add(m); }
    matCache.set(k, m);
  }
  return matCache.get(k);
};
const shade = (hex, dl) => { const c = new THREE.Color(hex), h = {}; c.getHSL(h); c.setHSL(h.h, h.s, Math.max(0, Math.min(1, h.l + dl))); return '#' + c.getHexString(); };
const rngOf = (seed) => { let a = (seed | 0) + 1; return () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };

// ---- geometry helpers (also used for the prism/pyramid primitive shapes) ----
export function prismGeo(w, h, d) {                       // triangular prism: ridge along x, base d wide, h tall, centred on its bounding box
  const x = w / 2, z = d / 2, y0 = -h / 2, y1 = h / 2;
  const v = [[-x, y0, -z], [x, y0, -z], [x, y0, z], [-x, y0, z], [-x, y1, 0], [x, y1, 0]];
  const tri = [[3, 2, 5], [3, 5, 4], [1, 0, 4], [1, 4, 5], [0, 1, 2], [0, 2, 3], [0, 3, 4], [1, 5, 2]];   // front slope, back slope, bottom, two gable ends (all outward-facing)
  const pos = []; for (const t of tri) for (const i of t) pos.push(...v[i]);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); return g;
}
export function pyramidGeo(w, h, d) { const g = new THREE.ConeGeometry(0.7071, 1, 4); g.rotateY(Math.PI / 4); g.scale(w, h, d); return g; }

const add = (g, geo, hex, x, y, z, o) => { const m = new THREE.Mesh(geo, M(hex, o)); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; g.add(m); return m; };
const BOX = (g, w, h, d, x, y, z, hex, o) => add(g, new THREE.BoxGeometry(w, h, d), hex, x, y + h / 2, z, o);   // y = bottom
const CYL = (g, r, h, x, y, z, hex, seg = 7, o) => add(g, new THREE.CylinderGeometry(r, r, h, seg), hex, x, y + h / 2, z, o);
const CONE = (g, r, h, x, y, z, hex, seg = 7) => add(g, new THREE.ConeGeometry(r, h, seg), hex, x, y + h / 2, z);
const BLOB = (g, r, x, y, z, hex, sy = 1) => { const m = add(g, new THREE.IcosahedronGeometry(r, 0), hex, x, y, z); m.scale.y = sy; return m; };

// ---- seasonal themes (from the reference season engine) ----
const THEME = {
  spring: { leaf: ['#82bd5e', '#8fca69', '#76b157', '#9dd073'], blossom: ['#eaa0b4', '#f2b8c6'], aspen: ['#9dd073', '#a9d97f'] },
  summer: { leaf: ['#5f8f4a', '#6fa055', '#4f8250', '#7aa85b'], blossom: ['#eaa0b4', '#f2b8c6'], aspen: ['#7aa85b', '#6fa055'] },
  fall: { leaf: ['#d9822b', '#c9622f', '#e0a63a', '#b8472f', '#9aa045'], blossom: ['#d9822b', '#e0a63a'], aspen: ['#e8c85a', '#f0d46a', '#d9b440'] },
  winter: { leaf: ['#8a7a68', '#7a6a58'], blossom: ['#8a7a68'], aspen: ['#9a8a78'] },
};
const PINE = ['#3f6b4a', '#477752', '#35604a'];
const TRUNK = '#8a6240', STONE = '#c9c2b2', GLASS = '#8fb9cd', TRIM = '#fbf5e4', BRICK = '#b5694f';

function textPlane(text, w, h, bg, fg) {
  const c = document.createElement('canvas'); c.width = 256; c.height = Math.max(32, Math.round(256 * h / w));
  const x = c.getContext('2d'); x.fillStyle = bg; x.fillRect(0, 0, c.width, c.height); x.fillStyle = fg;
  x.font = `bold ${Math.round(c.height * 0.55)}px system-ui`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(text, c.width / 2, c.height / 2 + 2, c.width - 16);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c) })); return m;
}
function win(g, x, y, z, side, w = 0.7, h = 0.9) {                     // flat window with a trim frame on the front/back/side faces
  const rot = side === 'e' || side === 'w' ? Math.PI / 2 : 0, dir = side === 's' ? 1 : side === 'n' ? -1 : side === 'e' ? 1 : -1;
  const f = new THREE.Group(); f.position.set(x, y, z); f.rotation.y = rot;
  BOX(f, w + 0.16, h + 0.16, 0.05, 0, -0.08, dir * 0.025, TRIM); BOX(f, w, h, 0.06, 0, 0, dir * 0.05, GLASS, { roughness: 0.3 }); g.add(f);
}

// ---- roofs ----
function roofOver(g, style, w, d, y, color, h = 1.5) {
  if (style === 'gable') add(g, prismGeo(w + 0.5, h, d + 0.5), color, 0, y + h / 2, 0);
  else if (style === 'hip') add(g, pyramidGeo(w + 0.5, h, d + 0.5), color, 0, y + h / 2, 0);
  else if (style === 'shed') { const m = BOX(g, w + 0.4, 0.2, d + 0.5, 0, y + 0.3, 0, color); m.rotation.x = -Math.atan2(0.9, d + 0.5); }
  else { BOX(g, w + 0.3, 0.3, d + 0.3, 0, y, 0, color); BOX(g, w + 0.4, 0.12, d + 0.4, 0, y + 0.3, 0, shade(color, 0.08)); }
}

function houseLike(p, g, cottage) {
  const { w, d } = p, floors = cottage ? 1 : p.floors, FH = cottage ? 2.3 : 2.4, H = floors * FH;
  BOX(g, w + 0.2, 0.3, d + 0.2, 0, 0, 0, shade(p.wall, -0.14));
  BOX(g, w, H, d, 0, 0.1, 0, p.wall);
  const nW = Math.max(2, Math.round(w / 1.6)), sx = (w - 0.9) / nW;
  for (let f = 0; f < floors; f++) for (let i = 0; i < nW; i++) {
    const x = -w / 2 + 0.45 + sx * (i + 0.5);
    if (f === 0 && Math.abs(x - (-w * 0.2)) < 0.9) continue;                        // leave room for the door
    win(g, x, f * FH + 1.0, d / 2, 's');
  }
  for (let f = 0; f < floors; f++) for (let i = 0; i < Math.max(1, Math.round(d / 2.2)); i++) {
    const z = -d / 2 + 0.7 + (d - 1.4) * (i + 0.5) / Math.max(1, Math.round(d / 2.2));
    win(g, w / 2, f * FH + 1.0, z, 'e'); win(g, -w / 2, f * FH + 1.0, z, 'w');
  }
  BOX(g, 0.95, 1.85, 0.1, -w * 0.2, 0.1, d / 2 + 0.03, p.door_color); BOX(g, 1.15, 2.05, 0.05, -w * 0.2, 0.1, d / 2 + 0.01, TRIM);
  const rh = p.roof === 'flat' ? 0.3 : p.roof === 'shed' ? 1.0 : 1.5;
  roofOver(g, p.roof, w, d, H + 0.1, p.roof_color, rh);
  if (p.chimney) BOX(g, 0.5, 1.5, 0.5, w * 0.28, H + 0.1 - 0.2, -d * 0.18, BRICK);
  if (!cottage && p.porch) {
    BOX(g, w * 0.5, 0.18, 1.1, -w * 0.2, 0, d / 2 + 0.55, TRUNK);
    for (const s of [-1, 1]) BOX(g, 0.1, 1.9, 0.1, -w * 0.2 + s * w * 0.23, 0.18, d / 2 + 1.0, TRIM);
    BOX(g, w * 0.5 + 0.2, 0.12, 1.2, -w * 0.2, 2.05, d / 2 + 0.55, p.roof_color);
  }
}

function tower(p, g) {
  const { w, floors } = p, FH = 2.0, H = floors * FH;
  BOX(g, w + 0.3, 0.4, w + 0.3, 0, 0, 0, shade(p.wall, -0.15)); BOX(g, w, H, w, 0, 0.2, 0, p.wall);
  for (let f = 0; f < floors; f++) for (const [x, z, s] of [[0, w / 2, 's'], [0, -w / 2, 'n'], [w / 2, 0, 'e'], [-w / 2, 0, 'w']]) win(g, x, f * FH + 1.0, z, s, w * 0.55, 0.8);
  BOX(g, 1.0, 1.8, 0.1, 0, 0.2, w / 2 + 0.03, TRUNK);
  BOX(g, w + 0.3, 0.25, w + 0.3, 0, H + 0.2, 0, shade(p.wall, -0.08));
  if (p.roof === 'pyramid') add(g, pyramidGeo(w + 0.4, 1.6, w + 0.4), p.roof_color, 0, H + 0.45 + 0.8, 0);
  else if (p.roof === 'spire') { add(g, pyramidGeo(w, 1.8, w), p.roof_color, 0, H + 0.45 + 0.9, 0); CYL(g, 0.05, 1.0, 0, H + 2.2, 0, TRIM, 5); }
  else BOX(g, w * 0.6, 0.5, w * 0.6, 0, H + 0.45, 0, shade(p.roof_color, 0.1));
}

function shop(p, g) {
  const { w, d, floors } = p, H = floors * 2.4;
  BOX(g, w + 0.2, 0.25, d + 0.2, 0, 0, 0, shade(p.wall, -0.14)); BOX(g, w, H + 0.5, d, 0, 0.1, 0, p.wall);
  BOX(g, w * 0.62, 1.4, 0.07, -w * 0.12, 0.7, d / 2 + 0.03, GLASS, { roughness: 0.3 });                    // shop window
  BOX(g, 0.9, 1.85, 0.1, w * 0.3, 0.1, d / 2 + 0.03, TRUNK);
  const n = 6, aw = w + 0.3;
  for (let i = 0; i < n; i++) { const m = BOX(g, aw / n, 0.12, 1.1, -aw / 2 + aw / n * (i + 0.5), 2.1, d / 2 + 0.55, i % 2 ? TRIM : p.awning); m.rotation.x = 0.3; }
  const sign = textPlane(p.sign, Math.min(w * 0.7, 2.6), 0.55, shade(p.awning, -0.25), '#fff'); sign.position.set(0, 2.75, d / 2 + 0.06); g.add(sign);
  for (let f = 1; f < floors; f++) for (let i = 0; i < 3; i++) win(g, -w / 3 + i * w / 3, f * 2.4 + 1.0, d / 2, 's');
  if (p.roof === 'gable') roofOver(g, 'gable', w, d, H + 0.6, shade(p.awning, -0.1), 1.3); else BOX(g, w + 0.3, 0.3, d + 0.3, 0, H + 0.6, 0, shade(p.wall, -0.1));
}

function workshop(p, g) {
  const { w, d } = p, H = 3.4;
  BOX(g, w + 0.2, 0.25, d + 0.2, 0, 0, 0, shade(p.wall, -0.15)); BOX(g, w, H, d, 0, 0.1, 0, p.wall);
  BOX(g, w * 0.34, 2.5, 0.1, -w * 0.15, 0.1, d / 2 + 0.03, p.door_color); BOX(g, w * 0.34 + 0.2, 0.2, 0.12, -w * 0.15, 2.6, d / 2 + 0.03, TRIM);
  for (let i = 0; i < 3; i++) win(g, w * 0.22 + i * 0.95, 2.0, d / 2, 's', 0.7, 0.6);
  if (p.roof === 'saw') { const n = Math.max(2, Math.round(w / 2)); for (let i = 0; i < n; i++) add(g, prismGeo(w / n, 1.2, d + 0.4), p.roof_color, -w / 2 + w / n * (i + 0.5), H + 0.1 + 0.6, 0); }
  else roofOver(g, 'gable', w, d, H + 0.1, p.roof_color, 1.4);
  if (p.chimney) CYL(g, 0.3, 2.0, w * 0.3, H - 0.4, -d * 0.2, shade(BRICK, -0.1), 8);
}

function tree(p, g) {
  const r = rngOf(p.seed), th = THEME[p.season] || THEME.summer, h = p.h;
  let kind = p.kind; if (p.season === 'winter' && ['leaf', 'blossom', 'aspen', 'autumn'].includes(kind)) kind = 'bare';
  const pick = (a) => a[Math.floor(r() * a.length)];
  if (kind === 'pine') {
    CYL(g, h * 0.04, h * 0.25, 0, 0, 0, TRUNK, 6);
    for (let i = 0; i < 4; i++) CONE(g, h * (0.3 - i * 0.055), h * 0.34, 0, h * (0.14 + i * 0.2), 0, p.season === 'winter' && i === 3 ? '#f0f4f2' : pick(PINE), 7);
    return;
  }
  const trunk = kind === 'aspen' ? '#efe8dc' : TRUNK;
  CYL(g, h * (kind === 'aspen' ? 0.03 : 0.045), h * 0.45, 0, 0, 0, trunk, 6);
  if (kind === 'bare') { for (let i = 0; i < 4; i++) { const b = CYL(g, h * 0.02, h * 0.4, 0, h * 0.3, 0, TRUNK, 4); b.rotation.z = (i - 1.5) * 0.45; b.rotation.y = i * 1.7; b.position.set(Math.sin(i * 1.7) * h * 0.08, h * 0.5, Math.cos(i * 1.7) * h * 0.08); } return; }
  const pal = kind === 'blossom' ? th.blossom : kind === 'aspen' ? th.aspen : kind === 'autumn' ? THEME.fall.leaf : th.leaf;
  const n = kind === 'aspen' ? 2 : 3;
  for (let i = 0; i < n; i++) BLOB(g, h * (kind === 'aspen' ? 0.2 : 0.27) * (1 - i * 0.12), (r() - 0.5) * h * 0.18, h * (0.55 + i * 0.17), (r() - 0.5) * h * 0.18, pick(pal), 0.9);
}
function bush(p, g) { const r = rngOf(p.seed), th = THEME[p.season] || THEME.summer; const pal = p.kind === 'blossom' ? th.blossom : p.kind === 'autumn' ? THEME.fall.leaf : p.kind === 'pine' ? PINE : th.leaf;
  for (let i = 0; i < 3; i++) BLOB(g, p.r * (0.7 - i * 0.1), (r() - 0.5) * p.r * 0.9, p.r * 0.55, (r() - 0.5) * p.r * 0.9, pal[Math.floor(r() * pal.length)], 0.85); }
function rock(p, g) { const r = rngOf(p.seed), n = p.stack ? 3 : 1 + Math.floor(r() * 2);
  for (let i = 0; i < n; i++) { const m = add(g, new THREE.DodecahedronGeometry(p.size * (1 - i * 0.28) * 0.55, 0), shade(p.tone, (r() - 0.5) * 0.12), (r() - 0.5) * p.size * 0.5, p.size * 0.3 + (p.stack ? i * p.size * 0.5 : 0), (r() - 0.5) * p.size * 0.5); m.scale.set(1.2, 0.8, 1); m.rotation.y = r() * 3; } }
function fence(p, g) {
  const n = Math.max(2, Math.round(p.length / 0.9)), h = p.height;
  for (let i = 0; i <= n; i++) { const x = -p.length / 2 + p.length / n * i; p.style === 'stone' ? BOX(g, p.length / n, h * 0.6, 0.35, x + p.length / n / 2 - p.length / n / 2, 0, 0, shade(STONE, (i % 2) * 0.05)) : BOX(g, 0.12, h, 0.12, x, 0, 0, p.tone); }
  if (p.style === 'rail') for (const y of [h * 0.35, h * 0.7]) BOX(g, p.length, 0.08, 0.06, 0, y, 0, p.tone);
  if (p.style === 'picket') { BOX(g, p.length, 0.08, 0.05, 0, h * 0.3, 0, p.tone); BOX(g, p.length, 0.08, 0.05, 0, h * 0.7, 0, p.tone); }
}
function lamp(p, g) {
  CYL(g, 0.18, 0.2, 0, 0, 0, p.tone, 6); CYL(g, 0.06, p.h, 0, 0.2, 0, p.tone, 6);
  if (p.style === 'lantern') { BOX(g, 0.4, 0.5, 0.4, 0, p.h - 0.1, 0, p.glow, { glow: true }); add(g, pyramidGeo(0.55, 0.3, 0.55), p.tone, 0, p.h + 0.55, 0); }
  else add(g, new THREE.IcosahedronGeometry(0.28, 0), p.glow, 0, p.h + 0.25, 0, { glow: true });
}
function path(p, g) {
  const n = Math.max(3, Math.round(p.length / 0.8)), col = { stone: STONE, dirt: '#c9a97c', brick: BRICK, sand: '#e6d3a0' }[p.material], r = rngOf(7);
  let prev = null;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1), x = (t - 0.5) * p.length, z = Math.sin(t * Math.PI) * p.curve * 1.6;
    const tile = BOX(g, p.length / n * 0.92, 0.05, p.width * (0.88 + r() * 0.2), x, 0, z, shade(col, (r() - 0.5) * 0.06));
    if (prev) tile.rotation.y = -Math.atan2(z - prev[1], x - prev[0]); prev = [x, z];
  }
}
function pond(p, g) {
  add(g, new THREE.CylinderGeometry(p.r, p.r, 0.12, 20), p.water, 0, 0.05, 0, { roughness: 0.2, transparent: true, opacity: 0.9 });
  const r = rngOf(11), n = Math.round(p.r * 6);
  for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2, rr = p.r + 0.05 + r() * 0.15; add(g, new THREE.DodecahedronGeometry(0.22 + r() * 0.12, 0), shade(STONE, (r() - 0.5) * 0.1), Math.cos(a) * rr, 0.12, Math.sin(a) * rr).scale.y = 0.7; }
  if (p.lilies) for (let i = 0; i < Math.round(p.r * 1.5); i++) { const a = r() * 6.28, rr = r() * p.r * 0.7; CYL(g, 0.22, 0.03, Math.cos(a) * rr, 0.1, Math.sin(a) * rr, '#6fa055', 7); if (i % 2) add(g, new THREE.SphereGeometry(0.07, 5, 4), '#f2b8c6', Math.cos(a) * rr, 0.16, Math.sin(a) * rr); }
}
function flowerBed(p, g) {
  BOX(g, p.w, 0.28, p.d, 0, 0, 0, '#7a5a3a'); const r = rngOf(p.seed), n = Math.round(p.w * p.d * 3.5);
  for (let i = 0; i < n; i++) { const x = (r() - 0.5) * (p.w - 0.3), z = (r() - 0.5) * (p.d - 0.3), h = 0.25 + r() * 0.3; CYL(g, 0.015, h, x, 0.28, z, '#4f8250', 3); add(g, new THREE.IcosahedronGeometry(0.09, 0), p.colors[i % p.colors.length], x, 0.3 + h, z); }
}
function sign(p, g) { BOX(g, 0.12, 1.5, 0.12, 0, 0, 0, p.post); BOX(g, 1.5, 0.62, 0.08, 0, 1.1, 0, p.board); const t = textPlane(p.text, 1.36, 0.5, p.board, '#4b3b29'); t.position.set(0, 1.41, 0.05); g.add(t); const t2 = t.clone(); t2.rotation.y = Math.PI; t2.position.z = -0.05; g.add(t2); }
function car(p, g) {
  const L = { car: 2.6, pickup: 3.0, van: 2.8 }[p.kind];
  BOX(g, L, 0.55, 1.25, 0, 0.3, 0, p.tone);
  if (p.kind === 'car') { BOX(g, L * 0.5, 0.5, 1.1, -0.1, 0.85, 0, p.tone); BOX(g, L * 0.46, 0.38, 1.12, -0.1, 0.9, 0, GLASS, { roughness: 0.3 }); }
  else if (p.kind === 'pickup') { BOX(g, L * 0.36, 0.55, 1.1, 0.5, 0.85, 0, p.tone); BOX(g, L * 0.32, 0.38, 1.12, 0.5, 0.9, 0, GLASS); BOX(g, L * 0.5, 0.25, 1.2, -0.55, 0.85, 0, shade(p.tone, -0.12)); }
  else { BOX(g, L * 0.92, 0.9, 1.15, 0, 0.85, 0, p.tone); BOX(g, L * 0.2, 0.45, 1.17, 0.95, 1.1, 0, GLASS); }
  for (const [x, z] of [[-L / 3, 0.62], [L / 3, 0.62], [-L / 3, -0.62], [L / 3, -0.62]]) { const w = CYL(g, 0.27, 0.18, x, 0.0, z, '#2b2b30', 8); w.rotation.x = Math.PI / 2; w.position.y = 0.27; }
  for (const z of [-0.4, 0.4]) BOX(g, 0.06, 0.14, 0.2, L / 2, 0.45, z, '#ffe9a0', { glow: true });
}

const GENS = { house: (p, g) => houseLike(p, g, false), cottage: (p, g) => houseLike({ ...p, floors: 1, porch: false }, g, true), tower, shop, workshop_building: workshop, tree, bush, rock, fence, lamp, path, pond, flower_bed: flowerBed, sign, car };
export function buildGen(name, pp) { const g = new THREE.Group(); (GENS[name] || ((p, gr) => BOX(gr, 1, 1, 1, 0, 0, 0, '#bbbbbb')))(pp, g); return g; }
