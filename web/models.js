// Renders a validated "design" (assets + primitive parts) as a THREE.Group.
// Models are lazy-loaded once, cached, normalised (origin at the bottom centre, longest side within 0.6..5 units) and cloned per use.
// Model files are only ever parsed as data by GLTFLoader; nothing in them is executed.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as skClone } from 'three/addons/utils/SkeletonUtils.js';
import { buildGen, prismGeo, pyramidGeo, kitGlow } from './kit/gens.js';

const FIT_MIN = 0.6, FIT_MAX = 5.0, KEEP_LO = 0.4, KEEP_HI = 6.0;   // same rule as the server's footprint calculation
const HEX = /^#[0-9a-f]{6}$/i;
const loader = new GLTFLoader();
const templates = new Map();          // asset id -> Promise<{scene, clips}>
const waiting = [];
let active = 0;
const MAX_PARALLEL = 3;

export const mixers = new Set();      // AnimationMixers of models that carry their own animations
export const glowMats = new Set();    // glowing materials (boosted at night by main.js)
export { kitGlow };

function pump() {
  while (active < MAX_PARALLEL && waiting.length) {
    const job = waiting.shift(); active++;
    loader.load(job.url || `/asset/${job.id}`, (g) => { active--; job.res(g); pump(); }, undefined, (e) => { active--; job.rej(e); pump(); });
  }
}
function template(id, fit, url) {
  if (!templates.has(id)) {
    templates.set(id, new Promise((res, rej) => { waiting.push({ id, url, res, rej }); pump(); }).then((g) => {
      const scene = g.scene;
      const box = new THREE.Box3().setFromObject(scene), size = box.getSize(new THREE.Vector3());
      const nat = Math.max(size.x, size.y, size.z) || 1;
      const k = fit > 0 ? fit : (nat >= KEEP_LO && nat <= KEEP_HI ? 1 : Math.min(FIT_MAX, Math.max(FIT_MIN, nat)) / nat);   // server-decided fit wins; else the same rule
      const holder = new THREE.Group();
      scene.scale.multiplyScalar(k);
      holder.add(scene);
      const b2 = new THREE.Box3().setFromObject(holder), c = b2.getCenter(new THREE.Vector3());
      scene.position.set(-c.x, -b2.min.y, -c.z);                                  // sits on the ground, centred
      scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      return { holder, clips: g.animations || [] };
    }));
  }
  return templates.get(id);
}

function tintMaterials(root, hex, amount = 0.65) {
  const c = new THREE.Color(hex);
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const out = mats.map((m) => { const n = m.clone(); if (n.color) n.color.lerp(c, amount); return n; });
    o.material = Array.isArray(o.material) ? out : out[0];
  });
}

function materialFor(kind, hex) {
  const c = new THREE.Color(HEX.test(hex || '') ? hex : '#b0bec5');
  switch (kind) {
    case 'shiny': return new THREE.MeshStandardMaterial({ color: c, roughness: 0.25, metalness: 0.1 });
    case 'metal': return new THREE.MeshStandardMaterial({ color: c, roughness: 0.35, metalness: 0.85 });
    case 'glow': { const m = new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 1.2, roughness: 0.5 }); glowMats.add(m); return m; }
    case 'glass': return new THREE.MeshStandardMaterial({ color: c, roughness: 0.1, transparent: true, opacity: 0.45 });
    default: return new THREE.MeshStandardMaterial({ color: c, roughness: 0.85 });
  }
}

const GEO = {
  box: (w, h, d) => new THREE.BoxGeometry(w, h, d),
  sphere: (w, h, d) => { const g = new THREE.SphereGeometry(0.5, 20, 14); g.scale(w, h, d); return g; },
  cylinder: (w, h, d) => { const g = new THREE.CylinderGeometry(0.5, 0.5, 1, 22); g.scale(w, h, d); return g; },
  cone: (w, h, d) => { const g = new THREE.ConeGeometry(0.5, 1, 22); g.scale(w, h, d); return g; },
  torus: (w, h, d) => { const g = new THREE.TorusGeometry(0.38, 0.13, 12, 28); g.scale(w, h, d); return g; },
  plane: (w, h, d) => { const g = new THREE.PlaneGeometry(w, d); g.rotateX(-Math.PI / 2); return g; },
  prism: (w, h, d) => prismGeo(w, h, d),
  pyramid: (w, h, d) => pyramidGeo(w, h, d),
};
const rad = (d) => (d || 0) * Math.PI / 180;

function tagAnim(node, type) {
  if (!type) return;
  node.userData.anim = { type, base: { y: node.position.y, rz: node.rotation.z, ry: node.rotation.y }, phase: Math.random() * 6 };
}

/** Build the group for a design. Asset parts fill in as their models finish loading (`group.userData.ready` resolves when all have). */
export function buildDesign(design, objectColor) {
  const root = new THREE.Group(), inner = new THREE.Group();
  root.add(inner);
  inner.scale.setScalar(design.scale || 1);
  inner.rotation.y = rad(design.rot || 0);
  const pend = [];
  const tint = design.tint || null;
  for (const p of design.parts || []) {
    const node = new THREE.Group();
    node.position.set(p.x || 0, p.y || 0, p.z || 0);
    const r = p.r || [0, 0, 0];
    node.rotation.set(rad(r[0]), rad(r[1]), rad(r[2]));
    if (p.g) {                                                              // generator from the builder kit (already validated server-side)
      node.scale.setScalar(p.s || 1);
      node.add(buildGen(p.g, p.pp || {}));
    } else if (p.a || p.gf) {                                               // model from the asset library, or a 3D gift
      node.scale.setScalar(p.s || 1);
      const ph = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), new THREE.MeshStandardMaterial({ color: 0xcfc6b0, transparent: true, opacity: 0.35 }));
      ph.position.y = 0.4; node.add(ph);                                    // placeholder until the model arrives
      pend.push(template(p.a || 'g' + p.gf, p.f, p.gf ? `/gift/${p.gf}/file` : undefined).then((t) => {
        node.remove(ph);
        const inst = skClone(t.holder);
        const col = p.c || tint;
        if (col && HEX.test(col)) tintMaterials(inst, col);
        else if (p.anim === 'blink' || design.anim === 'blink') tintMaterials(inst, '#ffffff', 0);   // own materials so only this one blinks
        node.add(inst);
        if (t.clips.length) { const mx = new THREE.AnimationMixer(inst); mx.clipAction(t.clips[0]).play(); mixers.add(mx); root.userData.mixer = mx; }
      }).catch(() => { ph.material.color.set(0xd88); }));
    } else {                                                                // primitive part
      const m = new THREE.Mesh(GEO[p.p] ? GEO[p.p](p.w || 1, p.h || 1, p.d || 1) : GEO.box(1, 1, 1), materialFor(p.m, p.c || tint || objectColor));
      m.castShadow = true; m.receiveShadow = true;
      node.add(m);
    }
    inner.add(node);
    tagAnim(node, p.anim);
  }
  tagAnim(inner, design.anim);
  root.userData.ready = Promise.all(pend);
  root.userData.animNodes = [];
  root.traverse((o) => { if (o.userData.anim) root.userData.animNodes.push(o); });
  return root;
}

/** Apply the fixed animations (spin, bob, sway, blink). Called every frame for each design group. */
export function animateDesign(root, t, dt) {
  for (const n of root.userData.animNodes || []) {
    const a = n.userData.anim, ph = a.phase;
    if (a.type === 'spin') n.rotation.y += dt * 1.2;
    else if (a.type === 'bob') n.position.y = a.base.y + Math.sin(t * 2 + ph) * 0.18;
    else if (a.type === 'sway') n.rotation.z = a.base.rz + Math.sin(t * 1.4 + ph) * 0.12;
    else if (a.type === 'blink') {
      const on = Math.sin(t * 5 + ph) > 0 ? 0.9 : 0.05;
      n.traverse((o) => {
        if (!o.isMesh) return;
        for (const m of Array.isArray(o.material) ? o.material : [o.material]) if (m.emissive) { m.emissive.set(0xffe9a0); m.emissiveIntensity = on; }
      });
    }
  }
}
