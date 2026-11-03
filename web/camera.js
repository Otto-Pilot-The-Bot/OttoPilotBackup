// Camera modes: 1 overhead (the original orbit view), 2 follow-Otto low view, 3 ground-level walk (look around only).
// Walk mode never edits anything: it only moves the camera. Esc leaves it.
import * as THREE from 'three';

const EYE = 1.55;                 // Otto is 1.7 m tall; his eyes are about here
const WALK = 5.0, RUN = 11.0, RADIUS = 0.45;

export function createCameraModes({ camera, controls, dom, getRobot, getHalf, getColliders, onChange, getGround = () => 0 }) {
  let mode = 'overhead', detached = false;
  const saved = { pos: new THREE.Vector3(), target: new THREE.Vector3() };
  const keys = new Set(), look = { yaw: 0, pitch: 0 }, me = new THREE.Vector3(0, EYE, 0);
  const fpos = new THREE.Vector3(), ftarget = new THREE.Vector3(), tmp = new THREE.Vector3();
  let fyaw = 0, locked = false, dragging = false, hintEl = null;

  // ---------- UI: three buttons + current mode label
  const bar = document.createElement('div'); bar.id = 'camBar';
  bar.innerHTML = `<button data-m="overhead" title="Overhead view (1)">1 · Overhead</button><button data-m="follow" title="Low view behind Otto (2)">2 · Follow Otto</button><button data-m="walk" title="Walk around at eye level (3). Esc to leave.">3 · Walk</button><button data-a="detach" id="camDetach" title="Let go of Otto and look around freely" hidden>🔓 Detach</button><span id="camMode"></span>`;
  document.body.appendChild(bar);
  hintEl = document.createElement('div'); hintEl.id = 'camHint'; hintEl.hidden = true;
  hintEl.textContent = 'WASD move · mouse look · Shift run · Esc back to overhead (look only, nothing can be edited here)';
  document.body.appendChild(hintEl);
  bar.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.m) setMode(b.dataset.m); else if (b.dataset.a === 'detach') setDetached(!detached);
  });
  const paint = () => {
    for (const b of bar.querySelectorAll('button[data-m]')) b.classList.toggle('on', b.dataset.m === mode);
    bar.querySelector('#camMode').textContent = mode === 'overhead' ? 'Overhead' : mode === 'follow' ? (detached ? 'Follow (detached)' : 'Following Otto') : 'Walking';
    const d = bar.querySelector('#camDetach'); d.hidden = mode !== 'follow'; d.textContent = detached ? '🔒 Re-attach' : '🔓 Detach';
    hintEl.hidden = mode !== 'walk';
    document.body.dataset.cam = mode;
  };

  function setDetached(v) {
    detached = v;
    if (mode === 'follow') {
      controls.enabled = v;
      if (v) { const r = getRobot(); controls.target.set(r.pos.x, EYE, r.pos.z); controls.update(); }
    }
    paint();
  }

  function setMode(m) {
    if (m === mode) return;
    if (mode === 'overhead') { saved.pos.copy(camera.position); saved.target.copy(controls.target); }
    if (mode === 'walk' && document.pointerLockElement === dom) document.exitPointerLock();
    mode = m; detached = false; keys.clear(); dragging = false;
    controls.enabled = m === 'overhead';
    if (m === 'overhead') { camera.position.copy(saved.pos); controls.target.copy(saved.target); camera.up.set(0, 1, 0); controls.update(); }
    if (m === 'follow') { const r = getRobot(); fyaw = r.yaw; placeBehind(r, true); }
    if (m === 'walk') {
      const r = getRobot(); me.set(r.pos.x + Math.sin(r.yaw) * 1.5, EYE, r.pos.z + Math.cos(r.yaw) * 1.5); look.yaw = r.yaw + Math.PI; look.pitch = 0;
      pushOut(me); applyWalkView();
      try { dom.requestPointerLock?.()?.catch?.(() => {}); } catch (_) { /* no pointer lock (headless): drag to look instead */ }
    }
    paint(); onChange?.(m);
  }

  // ---------- follow
  function placeBehind(r, snap) {
    const d = 4.2;
    tmp.set(r.pos.x - Math.sin(fyaw) * d, EYE + 0.15 + getGround(r.pos.x, r.pos.z), r.pos.z - Math.cos(fyaw) * d);
    const half = getHalf() + 3; tmp.x = Math.max(-half, Math.min(half, tmp.x)); tmp.z = Math.max(-half, Math.min(half, tmp.z));
    if (snap) fpos.copy(tmp); else fpos.lerp(tmp, 0.12);
    ftarget.set(r.pos.x + Math.sin(fyaw) * 2.5, EYE - 0.1 + getGround(r.pos.x, r.pos.z), r.pos.z + Math.cos(fyaw) * 2.5);
    camera.position.copy(fpos); camera.lookAt(ftarget);
  }

  // ---------- walk
  function applyWalkView() {
    me.y = EYE + getGround(me.x, me.z);                          // eyes stay about 1.55 m above the hills and dips
    camera.position.copy(me);
    const cp = Math.cos(look.pitch);
    camera.lookAt(me.x + Math.sin(look.yaw) * cp, me.y + Math.sin(look.pitch), me.z + Math.cos(look.yaw) * cp);
  }
  /** Push a point out of every solid footprint (oriented boxes {x,z,hw,hd,rot}) and keep it inside the world. */
  function pushOut(p) {
    const half = getHalf() - 0.6; p.x = Math.max(-half, Math.min(half, p.x)); p.z = Math.max(-half, Math.min(half, p.z));
    for (const c of getColliders()) {
      if (Math.abs(p.x - c.x) > Math.max(c.hw, c.hd) * 1.5 + RADIUS + 1 || Math.abs(p.z - c.z) > Math.max(c.hw, c.hd) * 1.5 + RADIUS + 1) continue;
      const cs = Math.cos(c.rot || 0), sn = Math.sin(c.rot || 0), dx = p.x - c.x, dz = p.z - c.z;
      const lx = dx * cs - dz * sn, lz = dx * sn + dz * cs;                       // into the box's own axes
      const qx = Math.max(-c.hw, Math.min(c.hw, lx)), qz = Math.max(-c.hd, Math.min(c.hd, lz));
      let ox = lx - qx, oz = lz - qz, dist = Math.hypot(ox, oz);
      if (dist >= RADIUS) continue;
      if (dist < 1e-4) { const px = c.hw - Math.abs(lx), pz = c.hd - Math.abs(lz); if (px < pz) { ox = Math.sign(lx || 1); oz = 0; } else { ox = 0; oz = Math.sign(lz || 1); } dist = 0; }
      else { ox /= dist; oz /= dist; }
      const nx = qx + ox * RADIUS * 1.001 + (dist === 0 ? ox * (c.hw - Math.abs(lx) + 0) : 0), nz = qz + oz * RADIUS * 1.001 + (dist === 0 ? oz * (c.hd - Math.abs(lz)) : 0);
      p.x = c.x + nx * cs + nz * sn; p.z = c.z - nx * sn + nz * cs;
    }
  }
  function walkStep(dt) {
    const f = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
    const s = (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) - (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0);
    if (f || s) {
      const sp = (keys.has('ShiftLeft') || keys.has('ShiftRight') ? RUN : WALK) * dt, len = Math.hypot(f, s);
      const fx = Math.sin(look.yaw), fz = Math.cos(look.yaw);
      // move on each axis separately so you slide along walls instead of sticking
      me.x += ((fx * f - fz * s) / len) * sp; pushOut(me);
      me.z += ((fz * f + fx * s) / len) * sp; pushOut(me);
    }
    applyWalkView();
  }

  // ---------- input
  const typing = (e) => /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '') || e.target?.isContentEditable;
  addEventListener('keydown', (e) => {
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === 'Digit1') setMode('overhead'); else if (e.code === 'Digit2') setMode('follow'); else if (e.code === 'Digit3') setMode('walk');
    else if (e.code === 'Escape' && mode === 'walk') setMode('overhead');
    else if (mode === 'walk') { keys.add(e.code); if (e.code.startsWith('Arrow') || e.code === 'Space') e.preventDefault(); }
  });
  addEventListener('keyup', (e) => keys.delete(e.code));
  addEventListener('blur', () => keys.clear());
  document.addEventListener('pointerlockchange', () => {
    locked = document.pointerLockElement === dom;
    if (!locked && mode === 'walk' && !dragging) setMode('overhead');           // Esc releases the lock: that is "exit walk mode"
  });
  dom.addEventListener('mousedown', () => { if (mode === 'walk' && !locked) dragging = true; });
  addEventListener('mouseup', () => { dragging = false; });
  addEventListener('mousemove', (e) => {
    if (mode !== 'walk' || (!locked && !dragging)) return;
    look.yaw -= e.movementX * 0.0025; look.pitch = Math.max(-1.35, Math.min(1.35, look.pitch - e.movementY * 0.0025));
  });

  paint();
  return {
    get mode() { return mode; }, get pos() { return me.clone(); }, setMode, setDetached,
    /** debugging / screenshots: ?cam=walk&at=x,z&yaw=deg */
    pose(x, z, yawDeg, pitchDeg = 0) { me.set(x, EYE, z); look.yaw = (yawDeg * Math.PI) / 180; look.pitch = (pitchDeg * Math.PI) / 180; pushOut(me); },
    update(dt) {
      if (mode === 'follow' && !detached) {
        const r = getRobot(); fyaw += Math.atan2(Math.sin(r.yaw - fyaw), Math.cos(r.yaw - fyaw)) * Math.min(1, dt * 1.6);
        placeBehind(r, false);
      } else if (mode === 'follow' && detached) controls.update();
      else if (mode === 'walk') walkStep(dt);
    },
  };
}
