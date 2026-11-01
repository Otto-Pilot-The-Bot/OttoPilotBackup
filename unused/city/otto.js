// Otto's character for the city view.
// Drawn in code in the style of the city project's helper bot (vendor/people.js, commit 302c013): boxy chibi with a visor,
// antenna and chest light, screen-space, feet at (0,0), about 28 px tall at scale 1.
//   dir:   0 = toward down-right, 1 = down-left, 2 = up-left (back), 3 = up-right (back)   (same as the city kit)
//   frame: 0 idle, 1/2 walk steps (standing pose); wave uses frame 0/1/2 as arm positions; others ignore it
//   pose:  'stand' | 'wave' | 'sit' | 'sleep' | 'ride'
//   mood:  'neutral' | 'happy' | 'sad' | 'surprised' | 'tired' | 'angry'   (drawn on the visor; see moodFace())
import { shade } from './vendor/colors.js';

export const BODY_COLORS = [['Silver', '#c9d3da'], ['Amber', '#e1b04a'], ['Sky blue', '#7fb2c9'], ['Coral', '#d0705c'], ['Sage green', '#8fc08a']];
export const GLOW_COLORS = [['Cyan', '#6fe3ff'], ['Gold', '#ffd45e'], ['Mint', '#8dff9a'], ['Ember', '#ff8a6b']];
export const DEFAULT_LOOK = { body: '#e1b04a', glow: '#6fe3ff' };           // amber body, cyan glow
export const POSES = ['stand', 'wave', 'sit', 'sleep', 'ride'];
export const MOODS = ['neutral', 'happy', 'sad', 'surprised', 'tired', 'angry'];

/** The game's feelings (and his mood word) -> the face drawn on the visor. */
export function moodFace(feeling) {
  return ({ happy: 'happy', excited: 'happy', proud: 'happy', content: 'happy', sad: 'sad', scared: 'surprised', surprised: 'surprised',
    tired: 'tired', bored: 'tired', angry: 'angry' })[feeling] || 'neutral';
}

/** Game animation name (what the old 3D robot played) + context -> pose. */
export function poseFor(anim, { energy = 100, night = false, riding = false } = {}) {
  if (riding) return 'ride';
  if (anim === 'Sitting') return energy < 35 || night ? 'sleep' : 'sit';
  if (anim === 'Death') return 'sleep';
  if (anim === 'Wave' || anim === 'ThumbsUp' || anim === 'Yes' || anim === 'Dance') return 'wave';
  return 'stand';
}

const JOINT = '#4a5058', DARK = '#2d3136';

export function drawOtto(ctx, { dir = 1, frame = 0, pose = 'stand', mood = 'neutral', look = DEFAULT_LOOK, t = 0 } = {}) {
  const body = look.body, glow = look.glow, joint = JOINT, dark = DARK;
  const front = dir < 2;
  const sx = dir === 0 || dir === 3 ? 1 : -1;
  const standing = pose === 'stand' || pose === 'wave';
  const swing = pose === 'stand' ? (frame === 0 ? 0 : frame === 1 ? 1.8 : -1.8) : 0;
  const seated = pose === 'sit' || pose === 'sleep' || pose === 'ride';
  const bob = pose === 'stand' ? (frame === 0 ? 0 : -0.6) : seated ? (pose === 'ride' ? 0.2 : 4.4) : 0;   // seated: body sits lower
  const asleep = pose === 'sleep';
  const g = asleep ? shade(glow, -0.32) : glow;

  const rect = (x, y, w, h, c, rad = 0.8) => { ctx.beginPath(); ctx.roundRect(x, y, w, h, rad); ctx.fillStyle = c; ctx.fill(); };
  const dot = (x, y, R, c) => { ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fillStyle = c; ctx.fill(); };

  ctx.save();
  ctx.fillStyle = 'rgba(45,55,30,.2)';
  ctx.beginPath(); ctx.ellipse(0, 0.5, pose === 'ride' ? 9.5 : 6.5, pose === 'ride' ? 3.2 : 2.8, 0, 0, Math.PI * 2); ctx.fill();

  // ---- vehicle (ride): a little cart in the same flat style, drawn behind and in front of him
  const cartBack = () => {
    rect(-8.5, -4.6, 17, 3.6, shade(body, -0.22), 1.4);                // chassis
    dot(-5.2 * sx, -1.1, 2.1, dark); dot(5.2 * sx, -1.1, 2.1, dark); dot(-5.2 * sx, -1.1, 0.9, joint); dot(5.2 * sx, -1.1, 0.9, joint);
    rect(-2.3, -6.1, 4.6, 1.8, shade(body, -0.3), 0.8);                // seat
  };
  if (pose === 'ride') cartBack();

  // ---- legs
  if (standing) {
    const legY = -5.6 + bob;
    rect(-2.6 - swing * sx * 0.5, legY, 2.4, 5, joint);
    rect(0.2 + swing * sx * 0.5, legY, 2.4, 5, shade(joint, 0.1));
    rect(-3.2 - swing * sx * 0.5, -1.4 + Math.abs(swing) * 0.3, 3.4, 1.7, dark, 0.6);
    rect(-0.2 + swing * sx * 0.5, -1.4 + Math.abs(swing) * 0.3, 3.4, 1.7, dark, 0.6);
  } else if (pose === 'ride') {
    rect(-2.6, -6.8, 2.4, 2.4, joint); rect(0.2, -6.8, 2.4, 2.4, shade(joint, 0.1));   // thighs on the seat
    rect(-3.4 + sx * 1.2, -4.6, 2.6, 1.7, dark, 0.6); rect(0.6 + sx * 1.2, -4.6, 2.6, 1.7, dark, 0.6);
  } else {                                                                              // sit on the ground, knees up
    rect(-3.6, -3.6, 2.8, 3.0, joint); rect(0.8, -3.6, 2.8, 3.0, shade(joint, 0.1));
    rect(-4.2, -1.1, 3.6, 1.6, dark, 0.6); rect(0.6, -1.1, 3.6, 1.6, dark, 0.6);
  }

  // ---- arms (pivot at the shoulder; ang 0 = hanging down, as in the city bot)
  const armY = -12.6 + bob;
  const arm = (x, c, ang = 0, len = 5.2) => {
    ctx.save(); ctx.translate(x + 0.95, armY + 0.8); ctx.rotate(ang);
    rect(-0.95, -0.8, 1.9, len, c, 0.9); dot(0, len - 0.6, 1.15, joint);
    ctx.restore();
  };
  const wv = pose === 'wave' ? (frame === 0 ? 0 : frame === 1 ? 0.35 : -0.35) : 0;
  const lowSide = pose === 'ride' ? 1.9 : 0.0;                          // ride: hands forward on the wheel
  const angR = pose === 'wave' ? -(2.45 + wv) : pose === 'ride' ? -0.8 : asleep ? 0.12 : 0;
  const angL = pose === 'ride' ? 0.8 : asleep ? -0.12 : 0;
  if (!front) { arm(-5.3 - swing * 0.4, shade(body, -0.1), angL); arm(3.4 + swing * 0.4, shade(body, -0.1), angR); }

  // ---- torso
  rect(-4, -13.4 + bob, 8, 8, body, 1.8);
  rect(-4, -9 + bob, 8, 3.6, shade(body, -0.09), 1.4);
  if (front) {
    rect(-2.4, -11.8 + bob, 4.8, 3.2, dark, 0.9);                        // chest panel
    dot(0, -10.2 + bob, 1.05, g);
    dot(0, -10.2 + bob, 1.9, g + '40');
    arm(-5.5 + swing * 0.4, shade(body, -0.04), angL);
    arm(3.6 - swing * 0.4, shade(body, -0.04), angR);
  } else {
    rect(-2.6, -11.6 + bob, 5.2, 4.2, shade(body, -0.16), 0.9);          // back vent
    for (let i = 0; i < 3; i++) rect(-2, -11 + i * 1.3 + bob, 4, 0.5, dark, 0.2);
  }
  void lowSide;

  // ---- head: wide rounded box, antenna with a glowing tip
  const tilt = asleep ? 1.4 : 0;                                         // sleeping: head dips
  const hx = sx * 0.4 + (asleep ? sx * 0.8 : 0), hy = -19 + bob + tilt;
  rect(hx - 0.35, hy - 8.6, 0.8, 3, joint, 0.3);
  dot(hx + 0.05, hy - 8.8, mood === 'surprised' ? 1.7 : 1.2, g);
  rect(hx - 4.8, hy - 4.6, 9.6, 8.8, body, 2.4);
  rect(hx - 5.5, hy - 1.4, 1, 2.8, joint, 0.4);                          // ear bolts
  rect(hx + 4.5, hy - 1.4, 1, 2.8, joint, 0.4);
  if (front) {
    rect(hx - 3.8 + sx * 0.5, hy - 2.4, 7.6, 4.2, dark, 1.8);            // visor
    face(ctx, hx + sx * 0.5, hy, asleep ? 'asleep' : mood, g, dark);
  } else {
    rect(hx - 3.4, hy - 3.4, 6.8, 1, shade(body, -0.14), 0.4);
    rect(hx - 3.4, hy - 1.4, 6.8, 1, shade(body, -0.14), 0.4);
  }
  if (asleep) {                                                           // drifting "z"
    ctx.fillStyle = '#5b6a78'; ctx.font = 'bold 5px system-ui'; ctx.textAlign = 'center';
    for (let i = 0; i < 2; i++) { const p = ((t * 0.5 + i * 0.5) % 1); ctx.globalAlpha = 1 - p; ctx.fillText('z', hx + 6 + p * 4, hy - 7 - p * 7 - i); }
    ctx.globalAlpha = 1;
  }
  if (pose === 'ride') cartFront(ctx, rect, body, sx);
  ctx.restore();
}

function cartFront(ctx, rect, body, sx) {
  rect(-8.5, -3.2, 17, 2.3, shade(body, -0.12), 1.2);                    // front skirt covers the legs a little
  rect(sx > 0 ? 4.2 : -6.4, -9.6, 2.2, 5.2, '#4a5058', 0.5);            // steering column
}

/** Mood faces on the visor (cx, cy = eye line centre). Same dot-and-stroke vocabulary as the city bot's two glowing eyes. */
function face(ctx, cx, cy, mood, glow) {
  const ex = 1.7, ey = cy - 0.3;
  const dot = (x, y, R) => { ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fillStyle = glow; ctx.fill(); };
  const stroke = (fn, w = 0.75) => { ctx.beginPath(); fn(); ctx.strokeStyle = glow; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.stroke(); };
  if (mood === 'happy') {
    for (const s of [-1, 1]) stroke(() => ctx.arc(cx + s * ex, ey + 0.55, 1.05, Math.PI * 1.1, Math.PI * 1.9));      // ^ ^
    stroke(() => ctx.arc(cx, ey + 1.0, 0.95, Math.PI * 0.15, Math.PI * 0.85), 0.6);                                   // small smile
  } else if (mood === 'sad') {
    for (const s of [-1, 1]) { dot(cx + s * ex, ey + 0.4, 0.8); stroke(() => { ctx.moveTo(cx + s * (ex + 1.2), ey - 1.0); ctx.lineTo(cx + s * (ex - 1.1), ey - 1.6); }, 0.6); }
    stroke(() => ctx.arc(cx, ey + 2.1, 0.9, Math.PI * 1.15, Math.PI * 1.85), 0.55);                                   // frown
  } else if (mood === 'surprised') {
    for (const s of [-1, 1]) { stroke(() => ctx.arc(cx + s * ex, ey - 0.1, 1.15, 0, Math.PI * 2), 0.65); dot(cx + s * ex, ey - 0.1, 0.35); }
    stroke(() => ctx.arc(cx, ey + 1.5, 0.5, 0, Math.PI * 2), 0.5);                                                    // little "o"
  } else if (mood === 'tired') {
    for (const s of [-1, 1]) { ctx.fillStyle = glow; ctx.fillRect(cx + s * ex - 0.95, ey + 0.1, 1.9, 0.75); }          // half-closed bars
  } else if (mood === 'angry') {
    for (const s of [-1, 1]) { dot(cx + s * ex, ey + 0.35, 0.85); stroke(() => { ctx.moveTo(cx + s * (ex + 1.2), ey - 1.5); ctx.lineTo(cx + s * (ex - 1.1), ey - 0.55); }, 0.7); }
  } else if (mood === 'asleep') {
    for (const s of [-1, 1]) stroke(() => ctx.arc(cx + s * ex, ey - 0.2, 1.0, Math.PI * 0.15, Math.PI * 0.85), 0.7);   // closed eyes
  } else {
    dot(cx - ex, ey, 0.95); dot(cx + ex, ey, 0.95);                                                                    // neutral: as in the city bot
  }
}
