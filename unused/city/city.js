// Isometric city view for Otto (new page, next to the Three.js view at /). Same projection as the city kit: TW 64, TH 32,
// world x -> iso x (down-right), world z -> iso y (down-left). Otto is drawn by otto.js; his heading, pose and mood come from the server.
import { drawOtto, moodFace, poseFor, DEFAULT_LOOK } from './otto.js';
import { tone } from './vendor/colors.js';
import { PAL } from './vendor/palette.js';

const TW = 64, TH = 32, SC = 2.4;                               // Otto is drawn at 2.4x: about two tiles tall
const P = (x, y, z = 0) => [((x - y) * TW) / 2, ((x + y) * TH) / 2 - z];
const q = new URLSearchParams(location.search);
const look = { body: q.get('body') ? '#' + q.get('body') : DEFAULT_LOOK.body, glow: q.get('glow') ? '#' + q.get('glow') : DEFAULT_LOOK.glow };
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const $ = (id) => document.getElementById(id);
let dpr = 1, zoom = 0.9, cam = [0, 0], snap = null;
const otto = { x: 0, z: 0, tx: 0, tz: 0, dir: 1, moving: false, anim: 'Idle', mood: 'neutral', energy: 100, say: '' };
let objects = [], places = {}, half = 30, hour = 12, paused = false, forcePose = q.get('pose'), forceMood = q.get('mood');

function resize() { dpr = devicePixelRatio || 1; cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; }
addEventListener('resize', resize); resize();
addEventListener('wheel', (e) => { zoom = Math.max(0.4, Math.min(2.2, zoom * (e.deltaY < 0 ? 1.1 : 0.9))); });

// ---- websocket (same protocol as the 3D page)
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'snapshot') {
      const s = m.state; snap = m; objects = m.objects || []; places = m.places || {}; half = m.world_half || half; hour = m.world.hour; paused = s.paused;
      $('nm').textContent = m.name; $('mood').textContent = s.mood; $('st').textContent = paused ? 'paused' : `energy ${Math.round(s.energy)}%`;
      otto.tx = s.x; otto.tz = s.z; otto.mood = moodFace(s.mood); otto.energy = s.energy; otto.anim = s.last_anim || 'Idle';
      if (!otto.init) { otto.x = s.x; otto.z = s.z; otto.init = true; }
    } else if (m.type === 'action') {
      otto.anim = m.anim || 'Idle'; if (m.mood) otto.mood = moodFace(m.mood);
      const c = $('cap'); c.textContent = m.say || m.caption || ''; c.hidden = !c.textContent;
    }
  };
  ws.onclose = () => setTimeout(connect, 2500);
}
if (!q.get('static')) connect(); else { otto.init = true; }

// ---- drawing
function diamond(x0, y0, x1, y1, fill) {
  const pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)];
  ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
}
function isoBox(x0, y0, x1, y1, h, base) {                       // three-tone block: top bright, left mid, right dark (city kit lighting)
  const t = tone(base), p = (x, y, z) => P(x, y, z);
  const poly = (pts, c) => { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fillStyle = c; ctx.fill(); };
  poly([p(x0, y1, 0), p(x1, y1, 0), p(x1, y1, h), p(x0, y1, h)], t.left);
  poly([p(x1, y0, 0), p(x1, y1, 0), p(x1, y1, h), p(x1, y0, h)], t.right);
  poly([p(x0, y0, h), p(x1, y0, h), p(x1, y1, h), p(x0, y1, h)], t.top);
}
const KCOL = { poi: '#c9a97c', landscape: '#5f8f4a', find: '#e8c14a', creation: '#b0bec5', creature: '#58a37a', house: '#c4604b', gift_picture: '#8fb9cd', gift_model: '#7d6c92' };
function label(text, x, y) { ctx.save(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.font = '11px system-ui'; ctx.textAlign = 'center'; ctx.fillStyle = '#3b3a3fcc'; ctx.fillText(text, x, y); ctx.restore(); }

function frame(now) {
  const t = now / 1000, dt = Math.min(0.1, (frame.last ? t - frame.last : 0.016)); frame.last = t;
  // move toward the server position, face the way he walks
  const dx = otto.tx - otto.x, dz = otto.tz - otto.z, d = Math.hypot(dx, dz);
  otto.moving = d > 0.15;
  if (otto.moving) {
    const sp = Math.min(d, Math.max(1.8, d * 0.9) * dt); otto.x += (dx / d) * sp; otto.z += (dz / d) * sp;
    otto.dir = Math.abs(dx) >= Math.abs(dz) ? (dx > 0 ? 0 : 2) : (dz > 0 ? 1 : 3);
  }
  const [ox, oy] = P(otto.x, otto.z);
  cam[0] += (ox - cam[0]) * Math.min(1, dt * 3); cam[1] += (oy - cam[1]) * Math.min(1, dt * 3);

  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.setTransform(dpr * zoom, 0, 0, dpr * zoom, cv.width / 2 - cam[0] * dpr * zoom, cv.height / 2 - cam[1] * dpr * zoom + 60 * dpr);

  // ground: checker of soft greens inside the world edge
  const n = Math.round(half);
  for (let i = -n; i < n; i++) for (let j = -n; j < n; j++) diamond(i, j, i + 1, j + 1, (i + j) & 1 ? PAL.grass : '#a1c177');
  ctx.globalAlpha = 0.5; ctx.strokeStyle = '#6e8a4a'; ctx.lineWidth = 1.2; ctx.beginPath();
  for (const [x, y] of [P(-n, -n), P(n, -n), P(n, n), P(-n, n)]) ctx.lineTo(x, y); ctx.closePath(); ctx.stroke(); ctx.globalAlpha = 1;
  // pads for named places (home pad, fuel station)
  for (const [k, p] of Object.entries(places)) if (k === 'home' || k === 'fuel_station') { diamond(p.x - 2.2, p.z - 2.2, p.x + 2.2, p.z + 2.2, k === 'home' ? '#7e8fa8' : '#8c8c8c'); }

  // things in the world and Otto, back to front
  const items = objects.map((o) => ({ z: o.x + o.z, o })).concat([{ z: otto.x + otto.z + 0.3, otto: true }]).sort((a, b) => a.z - b.z);
  for (const it of items) {
    if (it.otto) {
      const [x, y] = P(otto.x, otto.z); ctx.save(); ctx.translate(x, y); ctx.scale(SC, SC);
      const night = hour >= 21 || hour < 6;
      const pose = forcePose || poseFor(otto.anim, { energy: otto.energy, night: night && otto.anim === 'Sitting' });
      const f = otto.moving ? [0, 1, 0, 2][Math.floor(t * 5) % 4] : pose === 'wave' ? [1, 0, 2, 0][Math.floor(t * 4) % 4] : 0;
      drawOtto(ctx, { dir: otto.dir, frame: f, pose, mood: forceMood || otto.mood, look, t });
      ctx.restore(); continue;
    }
    const o = it.o, r = Math.min(1.1, Math.max(0.3, (o.radius || 1) * 0.55)), col = KCOL[o.kind] || '#b0bec5';
    isoBox(o.x - r, o.z - r, o.x + r, o.z + r, o.kind === 'landscape' ? 0.9 * 22 : 0.7 * 22, o.color && /^#/.test(o.color) && o.kind !== 'poi' && o.kind !== 'landscape' ? o.color : col);
  }
  // names
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  for (const o of objects) { const [x, y] = P(o.x, o.z); label(o.name, (cv.width / 2 + (x - cam[0]) * dpr * zoom) / dpr, (cv.height / 2 + (y - cam[1]) * dpr * zoom + 60 * dpr) / dpr - 30 * zoom); }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
