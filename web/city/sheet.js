// Asset-Lab style sheets for Otto: ?view=style | motion | colors
import { drawOtto, BODY_COLORS, GLOW_COLORS, DEFAULT_LOOK, POSES, MOODS } from './otto.js';
import { person, robot } from './vendor/people.js';
import { rng } from './vendor/colors.js';

const q = new URLSearchParams(location.search), view = q.get('view') || 'style';
const look = { body: q.get('body') ? '#' + q.get('body') : DEFAULT_LOOK.body, glow: q.get('glow') ? '#' + q.get('glow') : DEFAULT_LOOK.glow };
const SC = 3.6, W = 120, H = 130, OY = 112;
const root = document.getElementById('root');

function section(title, note = '') {
  const s = document.createElement('section'); s.innerHTML = `<h2>${title}</h2>${note ? `<p>${note}</p>` : ''}<div class="row"></div>`;
  root.append(s); return s.querySelector('.row');
}
function cell(row, label, draw, sub = '') {
  const d = document.createElement('div'); d.className = 'cell';
  const c = document.createElement('canvas'); const dpr = 2; c.width = W * dpr; c.height = H * dpr; c.style.width = W + 'px'; c.style.height = H + 'px';
  const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.translate(W / 2, OY);
  g.save(); g.globalAlpha = 0.35; g.fillStyle = '#c9d6b0'; g.beginPath(); g.moveTo(0, -16 * SC / 3.6 * 0.5); g.lineTo(32 * 0.6, 0); g.lineTo(0, 16 * 0.6); g.lineTo(-32 * 0.6, 0); g.closePath(); g.fill(); g.restore();
  g.scale(SC, SC); draw(g);
  d.append(c); d.insertAdjacentHTML('beforeend', `<b>${label}</b>${sub ? `<i>${sub}</i>` : ''}`); row.append(d);
}
const O = (o) => (g) => drawOtto(g, { look, t: 0.3, ...o });

if (view === 'style') {
  const a = section('Style check: Otto next to the city repo\'s villagers and helper bot', 'Same renderer, same scale (4 villagers and the repo\'s own robot are the unmodified vendored city code).');
  for (let i = 0; i < 4; i++) cell(a, 'Villager ' + (i + 1), (g) => person(g, rng(131 + i * 17 + [0, 7, 19, 31][i]), { dir: 1, frame: 0 }), 'city repo');
  cell(a, 'City robot', (g) => robot(g, rng(131), { dir: 1, frame: 0 }), 'city repo');
  cell(a, 'Otto', O({ dir: 1, mood: 'neutral' }), 'new');
  cell(a, 'Otto', O({ dir: 0, mood: 'happy' }), 'new');
  const b = section('Walking away / toward (frames 0,1,2)', 'villager vs Otto, same frames');
  for (const dir of [0, 1, 2, 3]) cell(b, 'Villager dir ' + dir, (g) => person(g, rng(131 + 7), { dir, frame: 1 }), 'city repo');
  for (const dir of [0, 1, 2, 3]) cell(b, 'Otto dir ' + dir, O({ dir, frame: 1 }), 'new');
}
if (view === 'motion') {
  const a = section('4 directions x idle / walk frames');
  for (const dir of [0, 1, 2, 3]) for (const f of [0, 1, 2]) cell(a, `dir ${dir}`, O({ dir, frame: f }), f ? 'walk ' + f : 'idle');
  const b = section('Poses (front, both facings)');
  for (const dir of [1, 0]) {
    for (const p of POSES) cell(b, p, O({ dir, pose: p, frame: 1, mood: p === 'sleep' ? 'tired' : 'happy' }), 'dir ' + dir);
    cell(b, 'wave', O({ dir, pose: 'wave', frame: 2, mood: 'happy' }), 'arm up 2');
  }
  const c = section('Poses from behind');
  for (const p of ['stand', 'wave', 'sit', 'ride']) cell(c, p, O({ dir: 2, pose: p, frame: 1 }), 'dir 2');
}
if (view === 'mood') {
  const a = section('Mood faces on the visor (front, both facings)');
  for (const m of MOODS) cell(a, m, O({ dir: 1, mood: m }), 'dir 1');
  const b = section('Mood faces, facing down-right, plus asleep');
  for (const m of MOODS) cell(b, m, O({ dir: 0, mood: m }), 'dir 0');
  cell(b, 'asleep', O({ dir: 0, pose: 'sleep' }), 'visor closed');
}
if (view === 'colors') {
  const a = section('5 body colors x 4 glow colors', 'Pick one body and one glow. Names are shown under each robot; the suggested default is Amber + Cyan.');
  for (const [bn, bc] of BODY_COLORS) for (const [gn, gc] of GLOW_COLORS) cell(a, `${bn} / ${gn}`, (g) => drawOtto(g, { look: { body: bc, glow: gc }, dir: 1, mood: 'happy' }), bc + ' ' + gc);
}
