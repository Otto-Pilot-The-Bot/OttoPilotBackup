// Terrain for a map: hills and lakes as a grid of corner heights, drawn as a tile-grid ground (like a board game).
// The height formula is the same as sprocket/maps.py (height_at), so the page and the server agree on every height.
//   doc.heights: n+1 strings of n+1 letters, one per grid corner. 'm' is ground level, each letter step is 0.25 m (a = -3 m ... z = +3.25 m).
import * as THREE from 'three';

export const H_ZERO = 'm'.charCodeAt(0), H_STEP = 0.25, WATER_Y = -0.3;      // ground below WATER_Y is a lake

const hv = (rows, n, i, j) => (rows[Math.min(n, Math.max(0, j))].charCodeAt(Math.min(n, Math.max(0, i))) - H_ZERO) * H_STEP;
const cr = (p0, p1, p2, p3, t) => 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);

/** Ground height in meters at a world position (0 when the map has no terrain). */
export function heightAt(doc, x, z) {
  const rows = doc && doc.heights; if (!rows) return 0;
  const n = doc.n, c = doc.cell, half = (n * c) / 2;
  const gx = Math.min(Math.max((x + half) / c, 0), n), gz = Math.min(Math.max((z + half) / c, 0), n);
  const i = Math.min(Math.floor(gx), n - 1), j = Math.min(Math.floor(gz), n - 1), fx = gx - i, fz = gz - j;
  const col = (dj) => cr(hv(rows, n, i - 1, j + dj), hv(rows, n, i, j + dj), hv(rows, n, i + 1, j + dj), hv(rows, n, i + 2, j + dj), fx);
  return cr(col(-1), col(0), col(1), col(2), fz);
}

/** The lowest ground under an object's footprint, so a building on a slope sits on its low side and is buried on its high side (never floats). */
export function baseHeight(doc, o) {
  if (!doc || !doc.heights) return 0;
  const sc = o.scale || 1, hw = ((o.fw || 1) * sc) / 2, hd = ((o.fd || 1) * sc) / 2, a = ((o.rot || 0) * Math.PI) / 180, cs = Math.cos(a), sn = Math.sin(a);
  let m = heightAt(doc, o.x, o.z);
  for (const [lx, lz] of [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]]) m = Math.min(m, heightAt(doc, o.x + lx * cs + lz * sn, o.z - lx * sn + lz * cs));
  return m;
}

export function hasLake(doc) {
  if (!doc || !doc.heights) return false;
  for (const r of doc.heights) for (let i = 0; i < r.length; i++) if ((r.charCodeAt(i) - H_ZERO) * H_STEP < WATER_Y) return true;
  return false;
}

// One thin light line around every tile, so the ground reads as a grid.
let gridTex = null;
function gridTexture() {
  if (gridTex) return gridTex;
  const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, 64, 64);
  g.strokeStyle = 'rgba(40,60,30,0.22)'; g.lineWidth = 3; g.strokeRect(0, 0, 64, 64);
  gridTex = new THREE.CanvasTexture(c); gridTex.colorSpace = THREE.SRGBColorSpace; gridTex.anisotropy = 4; return gridTex;
}

const SAND = new THREE.Color(0xe3cf98), BED = new THREE.Color(0x6a8f9a);
const _c = new THREE.Color();
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

/** The ground as one mesh: every tile a small subdivided patch (own vertices, so each tile keeps its flat colour), plus the lake surface when there is one.
 *  tileColors: { g, p, r, t, w, s, d } hex colours. Returns { group, dispose }. */
export function buildTerrain(doc, tileColors, sub = 4) {
  const n = doc.n, cell = doc.cell, half = (n * cell) / 2, V = sub + 1, per = V * V;
  const pos = new Float32Array(n * n * per * 3), nor = new Float32Array(n * n * per * 3), col = new Float32Array(n * n * per * 3), uv = new Float32Array(n * n * per * 2);
  const idx = new Uint32Array(n * n * sub * sub * 6);
  let vi = 0, ii = 0, e = cell / sub;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const t = doc.ground[j][i], base = new THREE.Color(tileColors[t] ?? tileColors.g ?? 0x8fbf6a), checker = (i + j) & 1 ? 1.045 : 1, start = vi;
    for (let b = 0; b < V; b++) for (let a = 0; a < V; a++) {
      const x = -half + i * cell + a * e, z = -half + j * cell + b * e, h = heightAt(doc, x, z);
      pos.set([x, h, z], vi * 3);
      const dx = heightAt(doc, x - 0.25, z) - heightAt(doc, x + 0.25, z), dz = heightAt(doc, x, z - 0.25) - heightAt(doc, x, z + 0.25), L = Math.hypot(dx, 0.5, dz);
      nor.set([dx / L, 0.5 / L, dz / L], vi * 3);
      _c.copy(base).multiplyScalar(checker * (1 + Math.min(Math.max(h, 0), 3) * 0.035));                  // hills are a touch lighter on top
      if (t === 'g' || t === 'd') { _c.lerp(SAND, 1 - smooth(WATER_Y, 0, h)); _c.lerp(BED, 1 - smooth(WATER_Y - 0.5, WATER_Y, h)); }   // sandy shore, darker lake bed
      col.set([_c.r, _c.g, _c.b], vi * 3); uv.set([a / sub, b / sub], vi * 2); vi++;
    }
    for (let b = 0; b < sub; b++) for (let a = 0; a < sub; a++) {
      const p = start + b * V + a; idx.set([p, p + V, p + 1, p + 1, p + V, p + V + 1], ii); ii += 6;
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3)); geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geo.setIndex(new THREE.BufferAttribute(idx, 1));
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, map: gridTexture(), roughness: 0.95, metalness: 0 });
  const ground = new THREE.Mesh(geo, mat); ground.receiveShadow = true; ground.userData.terrain = true; ground.frustumCulled = false;
  const group = new THREE.Group(); group.add(ground);
  const parts = [ground];
  if (hasLake(doc)) {
    const w = new THREE.Mesh(new THREE.PlaneGeometry(n * cell, n * cell).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: tileColors.w ?? 0x5aa3c6, roughness: 0.18, metalness: 0.05, transparent: true, opacity: 0.72, depthWrite: false }));
    w.position.y = WATER_Y; w.renderOrder = 2; w.userData.water = true; group.add(w); parts.push(w);
  }
  return { group, ground, dispose() { for (const p of parts) { p.geometry.dispose(); p.material.dispose(); } } };
}
