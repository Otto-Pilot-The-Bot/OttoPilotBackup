// Renders a data-driven map (see sprocket/maps.py): ground tiles, model objects, flat art panels, and the editor overlays.
// All 3D models come from assets/kenney and are shown exactly as authored (never tinted). The page never trusts a path: models load by asset id from /asset/<id>.
import * as THREE from 'three';
import { buildDesign } from './models.js';
import { buildTerrain, heightAt, baseHeight } from './terrain.js';

// Three ground options (UNDECIDED, see STYLE.md). They only change flat tile colours, never the models. Lighting follows the day/night cycle.
export const LOOKS = {
  A: { label: 'A · Soft pastel tiles', hideGrass: true, tiles: { g: 0xa8d08a, p: 0xe9dfc6, r: 0x5b6270, t: 0xdccfa9, w: 0x6db4d6, s: 0xeedca8, d: 0xb78f68 } },
  B: { label: 'B · Grass field', hideGrass: false, tiles: { p: 0xd8cdb0, r: 0x4f545e, t: 0xcdb98d, w: 0x5aa3c6, s: 0xe3cf98, d: 0x9a7a55 } },
  C: { label: 'C · Dark ground', hideGrass: true, tiles: { g: 0x27402f, p: 0x41445c, r: 0x23252f, t: 0x4a4a58, w: 0x1d4a78, s: 0x59553f, d: 0x3a2f2c } },
};
export const TILE_NAMES = { g: 'grass', p: 'plaza', r: 'road', t: 'path', w: 'water', s: 'sand', d: 'dirt' };

export function createMapView({ scene, art, onReady }) {
  const root = new THREE.Group(); root.name = 'map'; scene.add(root);
  const tileG = new THREE.Group(), objG = new THREE.Group(), overG = new THREE.Group(), selG = new THREE.Group();
  root.add(tileG, objG, overG, selG);
  const meshes = new Map();                 // object id -> { g, sig }
  const MV = { doc: null, nav: null, look: 'B', colliders: [], root, objG, meshes, overlays: { foot: false, walk: false }, selected: null };
  let panelMats = [];

  const sig = (o) => JSON.stringify([o.asset, o.aid, o.fit, o.scale, o.panel && [o.panel.w, o.panel.h, o.panel.art_id, o.panel.gift_id, o.panel.style]]);   // what needs a rebuild; moving/turning does not

  MV.setDoc = (doc, nav) => { MV.doc = doc; if (nav) MV.nav = nav; MV.rebuildGround(); MV.sync(); MV.rebuildOverlays(); MV.updateColliders(); };

  MV.setLook = (name) => { MV.look = LOOKS[name] ? name : 'B'; MV.rebuildGround(); return LOOKS[MV.look]; };

  let terrain = null;
  MV.heightAt = (x, z) => heightAt(MV.doc, x, z);                         // ground height here (0 when the map has no hills)
  MV.rebuildGround = () => {
    for (const c of [...tileG.children]) { tileG.remove(c); c.geometry?.dispose?.(); c.material?.dispose?.(); }
    if (terrain) { terrain.dispose(); terrain = null; }
    const doc = MV.doc; if (!doc) return;
    const L = LOOKS[MV.look], n = doc.n, cell = doc.cell;
    terrain = buildTerrain(doc, { g: 0x8fbf6a, ...L.tiles }); MV.terrain = terrain.ground; tileG.add(terrain.group);
    const side = n * cell, M = 260, bm = new THREE.MeshStandardMaterial({ color: L.tiles.g ?? 0x8fbf6a, roughness: 1 });       // a wide frame of plain ground around the map so its edge is not a void (a full plane would cover the lake)
    for (const [w, d, x, z] of [[side + 2 * M, M, 0, -(side + M) / 2], [side + 2 * M, M, 0, (side + M) / 2], [M, side, -(side + M) / 2, 0], [M, side, (side + M) / 2, 0]]) {
      const f = new THREE.Mesh(new THREE.PlaneGeometry(w, d).rotateX(-Math.PI / 2), bm); f.position.set(x, -0.04, z); f.receiveShadow = true; tileG.add(f);
    }
    for (const m of meshes.values()) placeWrap(m.g, m.o);                  // things stand on the new ground
  };

  // ------------- objects
  // graffiti: no frame; the picture is painted straight onto the wall with soft, uneven edges (an alpha map), so it reads as spray paint instead of a poster
  const softEdge = (() => { let t = null; return () => { if (t) return t; const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, 128, 128);
    x.filter = 'blur(5px)'; x.fillStyle = '#fff'; x.beginPath(); x.roundRect(9, 9, 110, 110, 14); x.fill(); t = new THREE.CanvasTexture(c); return t; }; })();
  function makeArtPanel(o) {
    const g = new THREE.Group(), w = o.panel.w, h = o.panel.h;
    if (o.panel.style === 'graffiti') {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false, transparent: true, alphaMap: softEdge(), alphaTest: 0.02, polygonOffset: true, polygonOffsetFactor: -2 });
      panelMats.push({ mat, o });
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(w * 1.08, h * 1.08), mat); pic.position.z = 0.012; g.add(pic); g.userData.pic = pic; return g;
    }
    const frame = new THREE.Mesh(new THREE.BoxGeometry(w + 0.16, h + 0.16, 0.08), new THREE.MeshStandardMaterial({ color: 0x2c2a30, roughness: 0.6 }));
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }); panelMats.push({ mat, o });
    const pic = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); pic.position.z = 0.045;
    frame.castShadow = true; g.add(frame, pic); g.userData.pic = pic; return g;
  }
  const emptyTex = (() => { const c = document.createElement('canvas'); c.width = 256; c.height = 192; const x = c.getContext('2d'); x.fillStyle = '#efe9da'; x.fillRect(0, 0, 256, 192);
    x.fillStyle = '#b7ad95'; x.font = '20px system-ui'; x.textAlign = 'center'; x.fillText('empty frame', 128, 100); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
  MV.refreshArt = () => {
    const ids = [...(art?.canvas?.keys() || [])].sort((a, b) => b - a);              // newest pictures first
    let slot = 0;
    for (const { mat, o } of panelMats) {
      if (o.panel.gift_id) {                                                       // a picture you gave Otto
        new THREE.TextureLoader().load(`/gift/${o.panel.gift_id}/file`, (t) => { t.colorSpace = THREE.SRGBColorSpace; mat.map = t; mat.color.set(0xffffff); mat.needsUpdate = true; }, undefined, () => { mat.map = emptyTex; mat.needsUpdate = true; });
        continue;
      }
      const id = o.panel.art_id || ids[slot++]; const cv = id && art.canvas.get(id);
      if (cv) { const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; mat.map = t; mat.color.set(0xffffff); }
      else { mat.map = emptyTex; }
      mat.needsUpdate = true;
    }
  };
  art?.onChange?.(() => MV.refreshArt());

  function build(o) {
    let g;
    if (o.panel) g = makeArtPanel(o);
    else if (o.aid) {
      const fit = o.fit || 1;
      g = buildDesign({ parts: [{ a: o.aid, f: fit, x: 0, y: 0, z: 0, s: 1, r: [0, 0, 0] }], scale: o.scale || 1, rot: 0 });
    } else g = new THREE.Group();
    const wrap = new THREE.Group(); wrap.add(g);
    wrap.userData.mapId = o.id;
    placeWrap(wrap, o); return wrap;
  }
  function placeWrap(w, o) { const gy = o.panel ? heightAt(MV.doc, o.x, o.z) : baseHeight(MV.doc, o); w.position.set(o.x, gy + (o.panel ? (o.y ?? 1.2) : (o.y || 0)), o.z); w.rotation.y = (o.rot * Math.PI) / 180; }

  MV.sync = () => {
    const doc = MV.doc; if (!doc) return;
    const ids = new Set(doc.objects.map((o) => o.id));
    for (const [id, m] of meshes) if (!ids.has(id)) { objG.remove(m.g); meshes.delete(id); }
    panelMats = panelMats.filter((p) => ids.has(p.o.id));
    for (const o of doc.objects) {
      const s = sig(o), cur = meshes.get(o.id);
      if (cur && cur.sig === s) { cur.o = o; placeWrap(cur.g, o); continue; }
      if (cur) { objG.remove(cur.g); panelMats = panelMats.filter((p) => p.o.id !== o.id); }
      const g = build(o); objG.add(g); meshes.set(o.id, { g, sig: s, o });
    }
    MV.refreshArt();
  };
  MV.byId = (id) => doc_obj(id);
  const doc_obj = (id) => MV.doc?.objects.find((o) => o.id === id);
  MV.updateColliders = () => {
    MV.colliders = [];
    for (const o of MV.doc?.objects || []) {
      if (o.walkable || o.panel || (o.y || 0) >= 1.8) continue;
      const c = Math.cos((o.rot * Math.PI) / 180), sn = Math.sin((o.rot * Math.PI) / 180), sc = o.scale || 1;
      for (const r of o.solids || [{ x: 0, z: 0, w: o.fw, d: o.fd }]) MV.colliders.push({ x: o.x + r.x * sc * c + r.z * sc * sn, z: o.z - r.x * sc * sn + r.z * sc * c, hw: (r.w * sc) / 2, hd: (r.d * sc) / 2, rot: (o.rot * Math.PI) / 180, id: o.id });
    }
    window.__colliders = MV.colliders;
  };
  /** Which object is under this ray (null if none). */
  MV.pick = (ray) => {
    const hits = ray.intersectObjects(objG.children, true);
    for (const h of hits) { let n = h.object; while (n && n.userData.mapId === undefined) n = n.parent; if (n) return n.userData.mapId; }
    return null;
  };

  // ------------- overlays: footprints, doors, walkable grid, selection
  const lineMat = new THREE.LineBasicMaterial({ color: 0xff5252, depthTest: false, transparent: true });
  const okMat = new THREE.LineBasicMaterial({ color: 0x4cd964, depthTest: false, transparent: true });
  const doorMat = new THREE.MeshBasicMaterial({ color: 0xffd400, depthTest: false });
  const walkMat = new THREE.MeshBasicMaterial({ color: 0xff3b30, transparent: true, opacity: 0.3, depthTest: false });
  MV.rebuildOverlays = () => {
    for (const c of [...overG.children]) { overG.remove(c); c.geometry?.dispose?.(); }
    const doc = MV.doc; if (!doc) return;
    if (MV.overlays.foot) {
      for (const o of doc.objects) {
        const l = new THREE.Group(); l.position.set(o.x, 0, o.z); l.rotation.y = (o.rot * Math.PI) / 180; l.renderOrder = 20; overG.add(l);
        const sc = o.scale || 1;
        for (const r of (o.walkable ? null : o.solids) || [{ x: 0, z: 0, w: o.fw, d: o.fd }]) {
          const hw = (r.w * sc) / 2, hd = (r.d * sc) / 2, cx = r.x * sc, cz = r.z * sc;
          const ln = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(cx - hw, 0.08, cz - hd), new THREE.Vector3(cx + hw, 0.08, cz - hd), new THREE.Vector3(cx + hw, 0.08, cz + hd), new THREE.Vector3(cx - hw, 0.08, cz + hd)]), o.walkable ? okMat : lineMat);
          ln.renderOrder = 20; l.add(ln);
        }
        if (o.door) { const d = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.7, 8), doorMat); d.position.set(o.door[0], 0.5, o.door[1]); d.renderOrder = 21; l.add(d); }
      }
    }
    if (MV.overlays.walk && MV.nav) {
      const W = MV.nav.length, half = (doc.n * doc.cell) / 2, cells = [];
      for (let j = 0; j < W; j++) for (let i = 0; i < W; i++) if (MV.nav[j][i] === '1') cells.push([i, j]);
      const im = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.94, 0.94).rotateX(-Math.PI / 2), walkMat, Math.max(1, cells.length)); const m4 = new THREE.Matrix4();
      cells.forEach(([i, j], k) => { m4.makeTranslation(-half + i + 0.5, 0.12, -half + j + 0.5); im.setMatrixAt(k, m4); }); im.count = cells.length; im.renderOrder = 19; overG.add(im);
    }
  };
  MV.setOverlay = (k, on) => { MV.overlays[k] = on; MV.rebuildOverlays(); };

  const ringMat = new THREE.LineBasicMaterial({ color: 0x00b7ff, depthTest: false });
  MV.select = (id) => {
    MV.selected = id; for (const c of [...selG.children]) { selG.remove(c); c.geometry?.dispose?.(); }
    const o = id && doc_obj(id); if (!o) return;
    const hw = Math.max(0.4, (o.fw * o.scale) / 2) + 0.2, hd = Math.max(0.4, (o.fd * o.scale) / 2) + 0.2;
    const l = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-hw, 0.1, -hd), new THREE.Vector3(hw, 0.1, -hd), new THREE.Vector3(hw, 0.1, hd), new THREE.Vector3(-hw, 0.1, hd)]), ringMat);
    l.position.set(o.x, 0, o.z); l.rotation.y = (o.rot * Math.PI) / 180; l.renderOrder = 30; selG.add(l);
  };
  // ------------- fade a building's walls and roof while Otto is inside (materials are cloned per object so other copies are untouched)
  const faded = new Map();
  MV.fade = (id, on) => {                      // idempotent: models that finish loading later are picked up on the next call
    const m = meshes.get(id); if (!m) return;
    if (on) {
      const saved = faded.get(id) || []; const have = new Set(saved.map((x) => x[0]));
      m.g.traverse((n) => { if (!n.isMesh || have.has(n)) return; saved.push([n, n.material]);
        const c = (Array.isArray(n.material) ? n.material : [n.material]).map((x) => { const y = x.clone(); y.transparent = true; y.opacity = 0.22; y.depthWrite = false; return y; });
        n.material = Array.isArray(n.material) ? c : c[0]; });
      faded.set(id, saved);
    } else if (faded.has(id)) { for (const [n, mat] of faded.get(id)) { (Array.isArray(n.material) ? n.material : [n.material]).forEach((x) => x.dispose()); n.material = mat; } faded.delete(id); }
  };
  MV.fadedIds = () => [...faded.keys()];
  MV.dispose = () => { scene.remove(root); };
  return MV;
}
