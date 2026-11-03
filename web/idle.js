// Idle life: between decisions Otto does not freeze. He looks around, nods, shrugs, hops, sits when tired and tilts his head at things.
// It only moves the robot's body/head on the page (never the world, never the server's idea of where he is). A walk or any real action interrupts it at once.

const shortest = (a) => Math.atan2(Math.sin(a), Math.cos(a));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

/** getRobot() -> THREE.Object3D | null; getHead() -> bone | null; canFidget() -> bool (standing still, nothing else playing);
 *  emote(name) plays a one-shot or looping clip; getMood() -> string; getNeeds() -> { energy, battery, boredom }; getPoints() -> [{x,z}] things worth looking at. */
export function createIdle({ getRobot, getHead, canFidget, emote, getMood, getNeeds, getPoints }) {
  const I = { enabled: true, can: canFidget };
  let timer = 4 + Math.random() * 4, turn = null, head = { yaw: 0, pitch: 0, ty: 0, tp: 0, until: 0 }, applied = { y: 0, x: 0 }, sat = false, idleFor = 0;

  I.lookUp = (secs = 4) => { head.tp = -0.55; head.ty = (Math.random() - 0.5) * 0.4; head.until = performance.now() + secs * 1000; };     // watching the sky: the head tips back
  I.glance = (x, z) => { const r = getRobot(); if (r) turn = { to: Math.atan2(x - r.position.x, z - r.position.z) }; };

  I.debug = () => ({ timer, idleFor, sat, turning: !!turn });
  I.update = (dt) => {
    const r = getRobot(); if (!r || !I.enabled) return;
    if (!canFidget()) { timer = 3 + Math.random() * 5; idleFor = 0; if (sat) sat = false; turn = null; return; }
    idleFor += dt;
    if (turn) { r.rotation.y += shortest(turn.to - r.rotation.y) * Math.min(1, dt * 3.2); if (Math.abs(shortest(turn.to - r.rotation.y)) < 0.04) turn = null; }
    timer -= dt;
    if (timer > 0) return;
    const mood = getMood(), n = getNeeds(), pts = getPoints();
    timer = 5 + Math.random() * 9;
    if (!sat && (n.energy < 35 || mood === 'tired') && idleFor > 10) { sat = true; emote('Sitting'); return; }
    if (sat) return;                                                      // sitting until something real happens
    const roll = Math.random();
    if (roll < 0.40) {                                                    // look around: at something interesting if there is something, else a random way
      if (pts.length && Math.random() < 0.7) { const p = pick(pts); turn = { to: Math.atan2(p.x - r.position.x, p.z - r.position.z) }; }
      else turn = { to: r.rotation.y + (Math.random() - 0.5) * 2.2 };
      head.ty = (Math.random() - 0.5) * 0.5; head.tp = (Math.random() - 0.5) * 0.2; head.until = performance.now() + 2500;
    } else if (roll < 0.62) {                                             // a mood-flavoured gesture
      const by = { happy: ['Yes', 'ThumbsUp', 'Yes'], excited: ['Jump', 'Yes', 'Dance'], proud: ['ThumbsUp', 'Yes'], curious: ['Yes', 'No'], surprised: ['Jump'], bored: ['No', 'No', 'Yes'],
        content: ['Yes', 'ThumbsUp'], sad: ['No'], scared: ['No'], angry: ['Punch'], tired: ['No'] };
      emote(pick(by[mood] || ['Yes']));
    } else if (roll < 0.80) {                                             // tilts his head at something
      head.tp = 0.25 + Math.random() * 0.2; head.ty = (Math.random() < 0.5 ? -1 : 1) * 0.5; head.until = performance.now() + 2200;
    } else if (roll < 0.84 && n.boredom > 60) {                           // restless: a little hop
      emote('Jump');
    } else if (pts.length) {                                              // wanders his gaze back to the nearest interesting thing
      const p = pts[0]; turn = { to: Math.atan2(p.x - r.position.x, p.z - r.position.z) };
    }
  };

  /** Call just BEFORE the animation mixer each frame: takes last frame's head offset back off. If the clip rewrites the head bone this changes nothing;
   *  if it does not, the offset would otherwise be added again every frame and the head would spin. */
  I.clearHead = () => {
    const h = getHead(); if (!h) return;
    h.rotation.y -= applied.y; h.rotation.x -= applied.x; applied.y = applied.x = 0;
  };
  /** Call after the animation mixer has run each frame: eases the head toward the current offset (the mixer would otherwise overwrite it). */
  I.applyHead = (dt) => {
    const h = getHead(); if (!h) return;
    if (performance.now() > head.until) { head.ty = 0; head.tp = 0; }
    const k = Math.min(1, dt * 5); head.yaw += (head.ty - head.yaw) * k; head.pitch += (head.tp - head.pitch) * k;
    h.rotation.y += head.yaw; h.rotation.x += head.pitch; applied.y = head.yaw; applied.x = head.pitch;
  };
  return I;
}
