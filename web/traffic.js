// Ambient traffic: a few Kenney cars drive along the map's road tiles (ground type 'r'). They are scenery made by the engine from the roads you painted;
// they are not objects on the map, so nothing here places, moves or removes anything of yours. Otto can ride one (see main.js 'ride').
import * as THREE from 'three';
import { buildDesign } from './models.js';
import { heightAt } from './terrain.js';

export function createTraffic({ scene }) {
  const root = new THREE.Group(); root.name = 'traffic'; scene.add(root);
  let cars = [], nodes = new Map(), cell = 4, half = 40, curDoc = null;
  const key = (i, j) => i + ',' + j;
  const pos = (i, j) => [-half + (i + 0.5) * cell, -half + (j + 0.5) * cell];

  function clear() { for (const c of cars) root.remove(c.g); cars = []; }
  function rebuild(doc, models, count = 3) {
    clear(); nodes = new Map(); curDoc = doc; if (!doc || !models?.length) return;
    cell = doc.cell; half = (doc.n * doc.cell) / 2;
    for (let j = 0; j < doc.n; j++) for (let i = 0; i < doc.n; i++) if (doc.ground[j][i] === 'r') nodes.set(key(i, j), [i, j]);
    const nb = (i, j) => [[1, 0], [-1, 0], [0, 1], [0, -1]].map(([a, b]) => [i + a, j + b]).filter(([a, b]) => nodes.has(key(a, b)));
    const usable = [...nodes.values()].filter(([i, j]) => nb(i, j).length >= 2);
    if (usable.length < 6) return;
    const n = Math.min(count, Math.floor(usable.length / 10) || 1);
    for (let k = 0; k < n; k++) {
      const [i, j] = usable[Math.floor(((k + 0.5) / n) * usable.length)], m = models[k % models.length];
      const g = buildDesign({ parts: [{ a: m.aid, f: m.fit, x: 0, y: 0, z: 0, s: 1, r: [0, 0, 0] }], scale: 1, rot: 0 });
      const w = new THREE.Group(); w.add(g); root.add(w);
      const next = nb(i, j)[0], [x0, z0] = pos(i, j), [x1, z1] = pos(...next);
      cars.push({ g: w, from: [i, j], to: next, prev: null, t: 0, speed: 3.6 + k * 0.5, x: x0, z: z0, yaw: Math.atan2(x1 - x0, z1 - z0), nb });
    }
  }
  function step(dt) {
    for (const c of cars) {
      const [fx, fz] = pos(...c.from), [tx, tz] = pos(...c.to), len = Math.hypot(tx - fx, tz - fz) || 1;
      c.t += (c.speed * dt) / len;
      if (c.t >= 1) {                                   // arrived at the next road tile: carry on straight if possible, else turn, else turn around
        const opts = c.nb(...c.to).filter(([a, b]) => !(a === c.from[0] && b === c.from[1]));
        const dir = [c.to[0] - c.from[0], c.to[1] - c.from[1]];
        const straight = opts.find(([a, b]) => a - c.to[0] === dir[0] && b - c.to[1] === dir[1]);
        c.prev = c.from; c.from = c.to; c.to = straight || opts[Math.floor(Math.random() * opts.length)] || c.prev; c.t = 0;
        continue;
      }
      const [ax, az] = pos(...c.from), [bx, bz] = pos(...c.to), dx = bx - ax, dz = bz - az, L = Math.hypot(dx, dz) || 1;
      const rx = dz / L, rz = -dx / L, lane = 0.9;                     // keep to the right-hand side of the road
      const px = ax + dx * c.t + rx * lane, pz = az + dz * c.t + rz * lane;
      const yaw = Math.atan2(dx, dz); let d = yaw - c.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); c.yaw += d * Math.min(1, dt * 6);
      c.x = px; c.z = pz; c.g.position.set(px, 0.05 + heightAt(curDoc, px, pz), pz); c.g.rotation.y = c.yaw;
    }
  }
  return { root, rebuild, step, get cars() { return cars; } };
}
