// VENDORED from the city project (TheFollowerCity), file src/assets/people.js, commit 302c013 ("Add robot character to People assets").
// Copied so Otto's project stays portable; reference/city is only a read-only reference and may change or be absent.
// Only change: import paths (palette.js and colors.js sit next to this file).
// Do not edit: Otto's own drawing code lives in ../otto.js.
import { PAL } from './palette.js';
import { shade } from './colors.js';

// Chibi walkers, drawn in screen space with feet at (0,0).
// dir: 0 = toward down-right, 1 = down-left, 2 = up-left (back), 3 = up-right (back)
// frame: 0 idle, 1/2 walk steps
export function person(ctx, r, { dir = 1, frame = 0 } = {}) {
  const skin = r.pick(PAL.skin), hair = r.pick(PAL.hair), shirt = r.pick(PAL.shirt), pants = r.pick(PAL.pants);
  const kid = r.chance(0.2), longHair = r.chance(0.4), hat = r.chance(0.15);
  const s = kid ? 0.78 : 1;
  const front = dir < 2;
  const sx = dir === 0 || dir === 3 ? 1 : -1;
  const swing = frame === 0 ? 0 : frame === 1 ? 1.8 : -1.8;
  const bob = frame === 0 ? 0 : -0.6;

  ctx.save();
  ctx.scale(s, s);
  ctx.fillStyle = 'rgba(45,55,30,.2)';
  ctx.beginPath();
  ctx.ellipse(0, 0.5, 6.5, 2.8, 0, 0, Math.PI * 2);
  ctx.fill();

  const rect = (x, y, w, h, c, rad = 0.8) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, rad);
    ctx.fillStyle = c;
    ctx.fill();
  };

  // legs + shoes (the back leg is drawn first)
  const legY = -6 + bob;
  rect(-2.6 - swing * sx * 0.5, legY, 2.5, 6 - Math.abs(swing) * 0.3, shade(pants, -0.08));
  rect(0.1 + swing * sx * 0.5, legY, 2.5, 6 - Math.abs(swing) * 0.3, pants);
  rect(-2.8 - swing * sx * 0.5, -1.2 + Math.abs(swing) * 0.3, 2.9, 1.5, '#3b3338');
  rect(-0.1 + swing * sx * 0.5, -1.2 + Math.abs(swing) * 0.3, 2.9, 1.5, '#3b3338');

  // arms behind torso when walking away
  const armY = -13.2 + bob;
  if (!front) {
    rect(-5 - swing * 0.4, armY, 1.9, 5.5, shade(shirt, -0.06));
    rect(3.1 + swing * 0.4, armY, 1.9, 5.5, shade(shirt, -0.06));
  }
  rect(-4, -14 + bob, 8, 8.6, shirt, 2);
  rect(-4, -9.2 + bob, 8, 3.8, shade(shirt, -0.07), 1.4);
  if (front) {
    rect(-5.2 + swing * 0.4, armY, 1.9, 5.5, shade(shirt, -0.05));
    rect(3.3 - swing * 0.4, armY, 1.9, 5.5, shade(shirt, -0.05));
    rect(-5.1 + swing * 0.4, armY + 4.8, 1.7, 1.5, skin, 0.7);
    rect(3.4 - swing * 0.4, armY + 4.8, 1.7, 1.5, skin, 0.7);
  }

  // head
  const hx = sx * 0.5, hy = -18.6 + bob;
  ctx.beginPath();
  ctx.arc(hx, hy, 4.3, 0, Math.PI * 2);
  ctx.fillStyle = skin;
  ctx.fill();
  ctx.fillStyle = hair;
  ctx.beginPath();
  if (front) {
    ctx.arc(hx, hy, 4.5, Math.PI * 1.02, Math.PI * 1.98);
    ctx.lineTo(hx + sx * 3.2, hy - 1.4);
    ctx.quadraticCurveTo(hx, hy - 3.2, hx - sx * 3.6, hy - 0.8);
    ctx.closePath();
    ctx.fill();
    if (longHair) rect(hx - 4.6, hy - 2, 2, 6.5, hair, 1);
    ctx.fillStyle = '#2b2a30';
    ctx.beginPath();
    ctx.arc(hx + sx * 1.2 - 1.3, hy + 0.5, 0.65, 0, Math.PI * 2);
    ctx.arc(hx + sx * 1.2 + 1.3, hy + 0.5, 0.65, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
    ctx.fill();
    if (longHair) rect(hx - 4.4, hy - 1, 8.8, 6.5, hair, 2);
  }
  if (hat) {
    const hc = r.pick(['#d2a03a', '#c4604b', '#6e8da3']);
    rect(hx - 5.4, hy - 3.2, 10.8, 1.8, hc, 0.9);
    rect(hx - 3.6, hy - 6.6, 7.2, 3.6, hc, 1.6);
  }
  ctx.restore();
}

// Helper bot: boxy chibi with a visor, antenna and chest light. Same screen-space frame as `person`.
const ROBOT_BODY = ['#c9d3da', '#e1b04a', '#7fb2c9', '#d0705c', '#8fc08a'];
const ROBOT_GLOW = ['#6fe3ff', '#ffd45e', '#8dff9a', '#ff8a6b'];
export function robot(ctx, r, { dir = 1, frame = 0 } = {}) {
  const body = r.pick(ROBOT_BODY), glow = r.pick(ROBOT_GLOW), joint = '#4a5058', dark = '#2d3136';
  const front = dir < 2;
  const sx = dir === 0 || dir === 3 ? 1 : -1;
  const swing = frame === 0 ? 0 : frame === 1 ? 1.8 : -1.8;
  const bob = frame === 0 ? 0 : -0.6;

  ctx.save();
  ctx.fillStyle = 'rgba(45,55,30,.2)';
  ctx.beginPath();
  ctx.ellipse(0, 0.5, 6.5, 2.8, 0, 0, Math.PI * 2);
  ctx.fill();

  const rect = (x, y, w, h, c, rad = 0.8) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, rad);
    ctx.fillStyle = c;
    ctx.fill();
  };
  const dot = (x, y, R, c) => { ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fillStyle = c; ctx.fill(); };

  // legs: short pistons with flat feet (back leg first)
  const legY = -5.6 + bob;
  rect(-2.6 - swing * sx * 0.5, legY, 2.4, 5, joint);
  rect(0.2 + swing * sx * 0.5, legY, 2.4, 5, shade(joint, 0.1));
  rect(-3.2 - swing * sx * 0.5, -1.4 + Math.abs(swing) * 0.3, 3.4, 1.7, dark, 0.6);
  rect(-0.2 + swing * sx * 0.5, -1.4 + Math.abs(swing) * 0.3, 3.4, 1.7, dark, 0.6);

  // arms behind torso when walking away
  const armY = -12.6 + bob;
  const arm = (x, c) => { rect(x, armY, 1.9, 5.2, c, 0.9); dot(x + 0.95, armY + 5.4, 1.15, joint); };
  if (!front) { arm(-5.3 - swing * 0.4, shade(body, -0.1)); arm(3.4 + swing * 0.4, shade(body, -0.1)); }

  // torso
  rect(-4, -13.4 + bob, 8, 8, body, 1.8);
  rect(-4, -9 + bob, 8, 3.6, shade(body, -0.09), 1.4);
  if (front) {
    rect(-2.4, -11.8 + bob, 4.8, 3.2, dark, 0.9);          // chest panel
    dot(0, -10.2 + bob, 1.05, glow);
    dot(0, -10.2 + bob, 1.9, glow + '40');
    arm(-5.5 + swing * 0.4, shade(body, -0.04));
    arm(3.6 - swing * 0.4, shade(body, -0.04));
  } else {
    rect(-2.6, -11.6 + bob, 5.2, 4.2, shade(body, -0.16), 0.9);   // back vent
    for (let i = 0; i < 3; i++) rect(-2, -11 + i * 1.3 + bob, 4, 0.5, dark, 0.2);
  }

  // head: wide rounded box, antenna with a glowing tip
  const hx = sx * 0.4, hy = -19 + bob;
  rect(hx - 0.35, hy - 8.6, 0.8, 3, joint, 0.3);
  dot(hx + 0.05, hy - 8.8, 1.2, glow);
  rect(hx - 4.8, hy - 4.6, 9.6, 8.8, body, 2.4);
  rect(hx - 5.5, hy - 1.4, 1, 2.8, joint, 0.4);                  // ear bolts
  rect(hx + 4.5, hy - 1.4, 1, 2.8, joint, 0.4);
  if (front) {
    rect(hx - 3.8 + sx * 0.5, hy - 2.4, 7.6, 4.2, dark, 1.8);    // visor
    dot(hx + sx * 0.5 - 1.7, hy - 0.3, 0.95, glow);
    dot(hx + sx * 0.5 + 1.7, hy - 0.3, 0.95, glow);
  } else {
    rect(hx - 3.4, hy - 3.4, 6.8, 1, shade(body, -0.14), 0.4);
    rect(hx - 3.4, hy - 1.4, 6.8, 1, shade(body, -0.14), 0.4);
  }
  ctx.restore();
}
