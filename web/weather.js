// Weather you can see: rain, snow, drifting leaves, fog, overcast sky and the odd flash of lightning.
// It only reads the weather name the server already sends (world.weather) and never changes anything in the world.
// Soft and cozy on purpose: gentle particles, muted greys, the light never goes fully dark.
// ?wx=<name> forces a weather (e.g. ?wx=snow), ?wx=0 turns it off, window.__setWeather(name) does the same from the console.
import * as THREE from 'three';

const GREY = 0xb4bcc6;
// sky: [colour the sky/fog/clouds drift toward, how far]; dim: how much the sun is softened; fog: view-distance multiplier;
// rain/snow/leaves: particle amount 0..1; wind: sideways drift; bolt: lightning.
const PRESETS = {
  'clear': {},
  'clear and cold': { sky: [0xaec4e0, 0.1], fog: 0.9 },
  'cloudy': { sky: [GREY, 0.55], dim: 0.18, fog: 0.95 },
  'light rain': { sky: [0xaab4c0, 0.65], dim: 0.22, rain: 0.45, fog: 0.8, wind: 0.12 },
  'drizzle': { sky: [0xb0b9c3, 0.55], dim: 0.18, rain: 0.2, fog: 0.85, wind: 0.08 },
  'thunderstorm': { sky: [0x8e98a6, 0.8], dim: 0.35, rain: 1, fog: 0.9, wind: 0.3, bolt: true },
  'foggy': { sky: [0xc4cacf, 0.7], dim: 0.12, fog: 0.8 },
  'breezy': { sky: [GREY, 0.1], wind: 0.5 },
  'falling leaves': { sky: [0xb9b4a8, 0.2], leaves: 0.9, wind: 0.4 },
  'light snow': { sky: [0xc2c8d0, 0.5], dim: 0.15, snow: 0.45, fog: 0.85 },
  'snow': { sky: [0xcdd2d8, 0.6], dim: 0.15, snow: 1, fog: 0.9 },
  'frosty': { sky: [0xbcd0e6, 0.25], fog: 0.8 },
  'warm and hazy': { sky: [0xf0dfb8, 0.3], fog: 0.75 },
};
const FALLBACKS = [[/thunder|storm/, 'thunderstorm'], [/drizzle/, 'drizzle'], [/rain|shower/, 'light rain'], [/snow|blizzard/, 'snow'], [/fog|mist/, 'foggy'], [/leaves/, 'falling leaves'], [/frost|cold/, 'frosty'], [/haze|hazy/, 'warm and hazy'], [/cloud|overcast/, 'cloudy'], [/wind|breez/, 'breezy']];
export const presetFor = (name) => { const n = String(name || '').toLowerCase(); return PRESETS[n] || PRESETS[(FALLBACKS.find(([re]) => re.test(n)) || [])[1]] || PRESETS.clear; };

const rnd = (seed) => () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };

// A fixed cloud of random points that wraps around `center`, so the particles stay in the world while the camera moves and the shader does all the animation.
function seeds(n, s) { const r = rnd(s), a = new Float32Array(n * 4); for (let i = 0; i < a.length; i++) a[i] = r(); return a; }

function makeRain(count) {
  const g = new THREE.BufferGeometry(), s = seeds(count, 7), seed = new Float32Array(count * 8), tip = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) { for (let k = 0; k < 2; k++) { seed.set(s.subarray(i * 4, i * 4 + 4), (i * 2 + k) * 4); tip[i * 2 + k] = k; } }
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 6), 3));
  g.setAttribute('seed', new THREE.BufferAttribute(seed, 4)); g.setAttribute('tip', new THREE.BufferAttribute(tip, 1));
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, fog: false,
    uniforms: { t: { value: 0 }, amount: { value: 0 }, W: { value: 60 }, center: { value: new THREE.Vector3() }, wind: { value: new THREE.Vector2(0.12, 0.04) }, tone: { value: new THREE.Color(0xcfdcec) } },
    vertexShader: `attribute vec4 seed; attribute float tip; uniform float t, amount, W; uniform vec3 center; uniform vec2 wind; varying float vA;
      const float H = 30.0;
      void main(){
        float fall = 20.0 + fract(seed.x * 13.7) * 6.0;
        float y = mod(seed.y * H - t * fall, H);
        vec2 rel = mod(seed.xz * W + wind * t * fall - center.xz + W * 0.5, W) - W * 0.5;
        vec3 p = vec3(center.x + rel.x, y, center.z + rel.y);
        p += tip * vec3(wind.x, 1.0, wind.y) * (0.9 + seed.w * 0.5);
        float edge = 1.0 - smoothstep(0.5, 1.0, length(rel) / (W * 0.5));
        float near = smoothstep(2.0, 6.0, length(p - cameraPosition));
        vA = step(seed.w, amount) * edge * near * mix(0.55, 0.12, tip);
        gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0); }`,
    fragmentShader: 'uniform vec3 tone; varying float vA; void main(){ if (vA < 0.01) discard; gl_FragColor = vec4(tone, vA); }',
  });
  const o = new THREE.LineSegments(g, m); o.frustumCulled = false; o.renderOrder = 5; o.visible = false; return o;
}

// leaf = false: soft white flakes; leaf = true: warm coloured leaves that tumble more and fall slower.
function makePoints(count, { size, leaf }) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  g.setAttribute('seed', new THREE.BufferAttribute(seeds(count, leaf ? 29 : 13), 4));
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, fog: false, defines: leaf ? { LEAF: '' } : {},
    uniforms: { t: { value: 0 }, amount: { value: 0 }, W: { value: 60 }, center: { value: new THREE.Vector3() }, wind: { value: new THREE.Vector2(0.12, 0.04) }, pxScale: { value: 600 }, size: { value: size } },
    vertexShader: `attribute vec4 seed; uniform float t, amount, pxScale, size, W; uniform vec3 center; uniform vec2 wind; varying float vA; varying vec3 vC; varying float vRot, vFlip;
      const float H = 28.0;
      void main(){
        #ifdef LEAF
          float fall = 0.9 + fract(seed.x * 13.7) * 0.7; float sw = 1.6;
        #else
          float fall = 1.1 + fract(seed.x * 13.7) * 0.9; float sw = 0.6;
        #endif
        float y = mod(seed.y * H - t * fall, H);
        vec2 sway = vec2(sin(t * 0.7 + seed.x * 40.0), cos(t * 0.6 + seed.z * 40.0)) * sw;
        vec2 rel = mod(seed.xz * W + sway + wind * t * (1.0 + fall) - center.xz + W * 0.5, W) - W * 0.5;
        vec4 mv = viewMatrix * vec4(center.x + rel.x, y, center.z + rel.y, 1.0);
        gl_Position = projectionMatrix * mv;
        #ifdef LEAF
          gl_PointSize = clamp(size * (0.6 + seed.w * 0.8) * pxScale / max(0.5, -mv.z), 9.0, 90.0);        // big enough to read as a leaf
        #else
          gl_PointSize = max(2.0, size * (0.6 + seed.w * 0.8) * pxScale / max(0.5, -mv.z));
        #endif
        float edge = 1.0 - smoothstep(0.5, 1.0, length(rel) / (W * 0.5));
        vA = step(fract(seed.w * 7.31), amount) * edge * smoothstep(1.5, 4.0, -mv.z);
        vRot = 0.0; vFlip = 1.0;
        #ifdef LEAF
          vRot = seed.z * 6.2832 + t * (0.4 + seed.x * 1.2);
          vFlip = 0.3 + 0.7 * abs(cos(t * (0.9 + seed.y * 1.4) + seed.w * 6.2832));
          vC = mix(vec3(0.85, 0.5, 0.17), vec3(0.62, 0.26, 0.1), fract(seed.z * 5.1)) + vec3(0.1, 0.12, -0.05) * fract(seed.x * 3.3);
        #else
          vC = vec3(0.97, 0.98, 1.0);
        #endif
      }`,
    fragmentShader: `varying float vA; varying vec3 vC; varying float vRot, vFlip;
      void main(){ if (vA < 0.01) discard; vec2 c = gl_PointCoord - 0.5;
        #ifdef LEAF
          float cs = cos(vRot), sn = sin(vRot);
          vec2 q = vec2(cs * c.x + sn * c.y, -sn * c.x + cs * c.y) * 1.45;               // along the leaf, then across it; tumbling squashes it sideways
          q.y /= vFlip;
          float u = q.x + 0.5;                                                              // 0 at the stem end, 1 at the tip
          float hw = 0.34 * pow(max(sin(3.14159 * clamp(u, 0.0, 1.0)), 0.0), 0.75) * (1.15 - 0.45 * u);     // broad leaf narrowing to a point
          float blade = (u > 0.0 && u < 1.0) ? smoothstep(hw + 0.045, hw - 0.01, abs(q.y)) : 0.0;
          float stem = (u > -0.14 && u <= 0.0) ? smoothstep(0.05, 0.015, abs(q.y)) : 0.0;
          float a = max(blade, stem);
          float rib = smoothstep(0.035, 0.0, abs(q.y)) * step(0.0, u) * step(u, 0.9);      // a darker midrib
          vec3 col = vC * (1.0 - 0.28 * rib);
        #else
          float a = smoothstep(0.5, 0.15, length(c));
        #endif
        #ifdef LEAF
          gl_FragColor = vec4(col, a * vA * 0.95); }
        #else
          gl_FragColor = vec4(vC, a * vA * 0.9); }
        #endif`,
  });
  const o = new THREE.Points(g, m); o.frustumCulled = false; o.renderOrder = 5; o.visible = false; return o;
}

export function createWeather({ scene, camera, renderer, sun, hemi, REAL, getCenter }) {
  const q = new URLSearchParams(location.search).get('wx');
  const W = { enabled: q !== '0', name: q && q !== '0' ? q : 'clear', forced: !!q && q !== '0' };
  const rain = makeRain(5500), snow = makePoints(4500, { size: 0.16, leaf: false }), leaves = makePoints(500, { size: 0.7, leaf: true });
  for (const o of [rain, snow, leaves]) scene.add(o);
  const cur = { rain: 0, snow: 0, leaves: 0, dim: 0, fog: 1, skyAmt: 0, skyCol: new THREE.Color(GREY), wind: 0.1, bolt: 0 };
  const tg = { ...cur, skyCol: new THREE.Color(GREY) };
  const grey = new THREE.Color();
  const fogBase = { near: scene.fog.near, far: scene.fog.far }, applied = { near: scene.fog.near, far: scene.fog.far };
  let nextBolt = 8, boltAt = -9, flash = 0;

  W.set = (name) => { W.name = String(name || 'clear'); const p = presetFor(W.name); Object.assign(tg, { rain: p.rain || 0, snow: p.snow || 0, leaves: p.leaves || 0, dim: p.dim || 0, fog: p.fog || 1, skyAmt: p.sky ? p.sky[1] : 0, wind: p.wind ?? 0.1, bolt: p.bolt ? 1 : 0 }); if (p.sky) tg.skyCol.set(p.sky[0]); };
  W.fromServer = (name) => { if (!W.forced && name && name !== W.name) W.set(name); };       // a forced weather (?wx= / __setWeather) wins over the server's
  W.set(W.name);
  window.__setWeather = (name) => { W.forced = name !== null && name !== undefined; W.set(W.forced ? name : 'clear'); return W.name; };

  W.update = (dt, t, nightness) => {
    if (!W.enabled) { rain.visible = snow.visible = leaves.visible = false; return; }
    const k = 1 - Math.exp(-dt * 0.8);                                            // weather eases in and out over a few seconds
    for (const key of ['rain', 'snow', 'leaves', 'dim', 'fog', 'skyAmt', 'wind', 'bolt']) cur[key] += (tg[key] - cur[key]) * k;
    cur.skyCol.lerp(tg.skyCol, k);

    // the particles
    const c = getCenter();
    const span = Math.max(60, camera.position.distanceTo(c) * 1.8);                 // zoomed out, the weather covers the whole view instead of a bubble round the target
    const px = renderer.domElement.height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
    for (const [o, v, wf] of [[rain, cur.rain, 1], [snow, cur.snow, 0.5], [leaves, cur.leaves, 1.5]]) {
      o.visible = v > 0.01; if (!o.visible) continue;
      const u = o.material.uniforms; u.W.value = span; u.t.value = t; u.amount.value = v; u.center.value.copy(c); u.wind.value.set(cur.wind * wf, cur.wind * wf * 0.35);
      if (u.pxScale) u.pxScale.value = px;
    }
    rain.material.uniforms.tone.value.set(0xcfdcec).multiplyScalar(1 - nightness * 0.6);

    // the sky, the fog and the light (these are reset every frame by the day/night code, so this runs after it)
    const dark = 1 - nightness * 0.7;
    if (REAL.on) { REAL.tint.amount = cur.skyAmt; REAL.tint.color.copy(cur.skyCol); }
    else if (cur.skyAmt > 0.005) { grey.copy(cur.skyCol).multiplyScalar(dark); scene.background.lerp(grey, cur.skyAmt); scene.fog.color.lerp(grey, cur.skyAmt); }
    if (scene.fog.near !== applied.near) fogBase.near = scene.fog.near;           // the map code resizes the fog with the world: follow it
    if (scene.fog.far !== applied.far) fogBase.far = scene.fog.far;
    scene.fog.near = applied.near = fogBase.near * (0.4 + 0.6 * cur.fog); scene.fog.far = applied.far = fogBase.far * cur.fog;
    sun.intensity *= 1 - cur.dim;

    // lightning: a short double flash every so often in a storm
    if (cur.bolt > 0.5 && t > nextBolt) { boltAt = t; nextBolt = t + 7 + Math.random() * 10; }
    const b = t - boltAt; flash = b < 0 ? 0 : b < 0.08 ? 1 : b < 0.16 ? 0.15 : b < 0.24 ? 0.8 : b < 0.6 ? 0.8 * (1 - (b - 0.24) / 0.36) : 0;
    if (flash > 0) { sun.intensity += flash * 2.2; hemi.intensity += flash * 0.9; }
  };
  return W;
}
