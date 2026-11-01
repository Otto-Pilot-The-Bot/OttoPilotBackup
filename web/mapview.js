// Renders a data-driven map (see sprocket/maps.py): ground tiles, model objects, flat art panels, and the editor overlays.
// All 3D models come from assets/kenney and are shown exactly as authored (never tinted). The page never trusts a path: models load by asset id from /asset/<id>.
import * as THREE from 'three';
import { buildDesign } from './models.js';

// Three ground/lighting options (UNDECIDED, see STYLE.md). They only change flat tile colours and the light, never the models.
export const LOOKS = {
  A: { label: 'A · Soft tiles, bright day', hour: 11, hideGrass: true, tiles: { g: 0xa8d08a, p: 0xe9dfc6, r: 0x5b6270, t: 0xdccfa9, w: 0x6db4d6, s: 0xeedca8, d: 0xb78f68 } },
  B: { label: 'B · Grass field, golden afternoon', hour: 16.6, hideGrass: false, tiles: { p: 0xd8cdb0, r: 0x4f545e, t: 0xcdb98d, w: 0x5aa3c6, s: 0xe3cf98, d: 0x9a7a55 } },
  C: { label: 'C · Dusk, glowing night town', hour: 21.3, hideGrass: true, tiles: { g: 0x27402f, p: 0x41445c, r: 0x23252f, t: 0x4a4a58, w: 0x1d4a78, s: 0x59553f, d: 0x3a2f2c } },
};
export const TILE_NAMES = { g: 'grass', p: 'plaza', r: 'road', t: 'path', w: 'water', s: 'sand', d: 'dirt' };

export function createMapView({ scene, art, onReady }) {
  const root = new THREE.Group(); root.name = 'map'; scene.add(root);
  const tileG = new THREE.Group(), objG = new THREE.Group(), overG = new THREE.Group(), selG = new THREE.Group();
  root.add(tileG, objG, overG, selG);
  const meshes = new Map();                 // object id -> { g, sig }
  const MV = { doc: null, nav: null, look: 'B', colliders: [], root, objG, meshes, overlays: { foot: false, walk: false }, selected: null };
  let panelMats = [];

  const sig = (o) => JSON.stringify([o.asset, o.aid, o.fit, o.scale, o.panel && [o.panel.w, o.panel.h, o.panel.art_id]]);   // what needs a rebuild; moving/turning does not

  MV.setDoc = (doc, nav) => { MV.doc = doc; if (nav) MV.nav = nav; MV.rebuildGround(); MV.sync(); MV.rebuildOverlays(); MV.updateColliders(); };

  MV.setLook = (name) => { MV.look = LOOKS[name] ? name : 'B'; MV.rebuildGround(); return LOOKS[MV.look]; };

  MV.rebuildGround = () => {
    for (const c of [...tileG.children]) { tileG.remove(c); c.geometry?.dispose?.(); c.material?.dispose?.(); }
    const doc = MV.doc; if (!doc) return;
    const L = LOOKS[MV.look], n = doc.n, cell = doc.cell, half = (n * cell) / 2;
    const by = {};
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const t = doc.ground[j][i]; if (t === 'g' && !L.hideGrass) continue; (by[t] ||= []).push([i, j]); }
    const geo = new THREE.PlaneGeometry(cell, cell); geo.rotateX(-Math.PI / 2);
    const m4 = new THREE.Matrix4();
    for (const [t, cells] of Object.entries(by)) {
      const mat = new THREE.MeshStandardMaterial({ color: L.tiles[t] ?? 0x888888, roughness: 0.95, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
        ...(t === 'w' ? { roughness: 0.25, metalness: 0.05, transparent: true, opacity: 0.9 } : {}) });
      const im = new THREE.InstancedMesh(geo, mat, cells.length); im.receiveShadow = true;
      cells.forEach(([i, j], k) => { m4.makeTranslation(-half + (i + 0.5) * cell, t === 'w' ? 0.015 : 0.03, -half + (j + 0.5) * cell); im.setMatrixAt(k, m4); });
      im.userData.tile = t; tileG.add(im);
    }
    if (L.hideGrass) {                                  // a base so the world edge is not a void
      const base = new THREE.Mesh(new THREE.PlaneGeometry(n * cell + 40, n * cell + 40).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ color: L.tiles.g, roughness: 1 }));
      base.position.y = 0.005; base.receiveShadow = true; tileG.add(base);
    }
  };

  // ------------- objects
  function makeArtPanel(o) {
    const g = new THREE.Group(), w = o.panel.w, h = o.panel.h;
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
  function placeWrap(w, o) { w.position.set(o.x, o.panel ? (o.y ?? 1.2) : (o.y || 0), o.z); w.rotation.y = (o.rot * Math.PI) / 180; }

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
    MV.colliders = (MV.doc?.objects || []).filter((o) => !o.walkable && !o.panel).map((o) => ({ x: o.x, z: o.z, hw: (o.fw * o.scale) / 2, hd: (o.fd * o.scale) / 2, rot: (o.rot * Math.PI) / 180, id: o.id }));
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
        const hw = (o.fw * o.scale) / 2, hd = (o.fd * o.scale) / 2;
        const l = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-hw, 0.08, -hd), new THREE.Vector3(hw, 0.08, -hd), new THREE.Vector3(hw, 0.08, hd), new THREE.Vector3(-hw, 0.08, hd)]), o.walkable ? okMat : lineMat);
        l.position.set(o.x, 0, o.z); l.rotation.y = (o.rot * Math.PI) / 180; l.renderOrder = 20; overG.add(l);
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
  MV.dispose = () => { scene.remove(root); };
  return MV;
}
