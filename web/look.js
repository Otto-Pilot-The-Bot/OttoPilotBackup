// The "Look" toggle: Normal (the usual render) or Flat (a printed halftone picture of the same scene, in a small palette).
// Flat renders the scene into an offscreen target, then one full-screen pass picks, for every pixel, one of three colours from a ramp
// (dark / mid / light) and uses a rotated dot grid to decide which: dark areas get big dark dots on a lighter ground, light areas the reverse.
// The ramp depends on what the pixel is: blue things (sky, water) get blues, green things (grass, leaves) get pinks and purples,
// warm things get oranges, everything else lavender. Because the choice is made per pixel, edges and small details stay readable.
// Normal mode skips all of it (no cost). Dot size is in CSS pixels, so it looks the same at any pixel ratio. The choice is remembered in localStorage.
import * as THREE from 'three';

// Everything here is meant to be tweaked: window.__look.set({ dot: 8, contrast: 1.4, ... }) or edit the defaults. Ramps are [dark, mid, light].
const DEFAULTS = {
  dot: 5,                 // dot grid spacing in CSS pixels
  angle: 28,              // grid rotation in degrees
  contrast: 1.2,          // >1 pushes the picture toward its darkest and lightest colours
  exposure: 1.1,          // brightens the scene before it is printed
  ramps: {
    blue: ['#1d2f9c', '#4a6fe0', '#cfdcf7'],      // sky, water
    green: ['#4a1d7a', '#c15fd0', '#f6c9ee'],     // grass, leaves
    warm: ['#4b2336', '#e0884f', '#fbe3b8'],      // wood, roofs, skin, orange
    neutral: ['#2c2866', '#8a84cc', '#efe9f6'],   // roads, stone, everything else
  },
};
const RAMP_ORDER = ['blue', 'green', 'warm', 'neutral'];

const VERT = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
const FRAG = `
  uniform sampler2D tScene; uniform vec2 res; uniform float cell, angle, contrast, exposure; uniform vec3 ramp[12];
  varying vec2 vUv;
  vec3 pick(int base, int i){ vec3 c = ramp[base]; if (i == 1) c = ramp[base + 1]; else if (i == 2) c = ramp[base + 2]; return c; }
  void main(){
    vec3 c = pow(clamp(texture2D(tScene, vUv).rgb * exposure, 0.0, 1.0), vec3(0.4545));      // the target is linear, the screen wants sRGB
    float mx = max(max(c.r, c.g), c.b), mn = min(min(c.r, c.g), c.b), sat = mx - mn;
    float L = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float t = clamp((L - 0.5) * contrast + 0.5, 0.0, 0.999);

    // which ramp: by hue, only for colours that actually have some colour in them
    float hue = 0.0;
    if (sat > 0.001) {
      if (mx == c.r) hue = mod((c.g - c.b) / sat, 6.0); else if (mx == c.g) hue = (c.b - c.r) / sat + 2.0; else hue = (c.r - c.g) / sat + 4.0;
    }
    hue = mod(hue, 6.0);                                       // 0 red, 1 yellow, 2 green, 3 cyan, 4 blue, 5 magenta
    float k = smoothstep(0.04, 0.16, sat);                     // 0 = grey, 1 = coloured
    float wG = k * (1.0 - smoothstep(0.5, 1.3, abs(hue - 2.2)));
    float wB = k * (1.0 - smoothstep(0.6, 1.5, abs(hue - 3.8)));
    float wW = k * (1.0 - smoothstep(1.2, 2.0, min(hue, 6.0 - hue)));
    float wN = max(0.0, 1.0 - wG - wB - wW);
    float sum = wG + wB + wW + wN;

    // which of the two colours (dark/mid or mid/light) this pixel prints, by where it falls in its dot
    float cs = cos(angle), sn = sin(angle);
    mat2 R = mat2(cs, -sn, sn, cs);
    vec2 f = fract(R * gl_FragCoord.xy / cell) - 0.5;
    float p = length(f) * 1.4142;                              // 0 at the dot centre, 1 at the cell corners
    float u = t * 2.0, fl = floor(u), fr = u - fl, aa = 0.9 / cell + 0.05;
    float up = smoothstep(-aa, aa, p * p - (1.0 - fr));        // 1 = the upper colour, 0 = the lower one (dark dots grow as the picture darkens)
    int i0 = int(fl);
    vec3 col = vec3(0.0);
    for (int r = 0; r < 4; r++) {
      float w = (r == 0 ? wB : r == 1 ? wG : r == 2 ? wW : wN) / sum;
      if (w <= 0.0) continue;
      col += w * mix(pick(r * 3, i0), pick(r * 3, i0 + 1), up);
    }
    gl_FragColor = vec4(col, 1.0);
  }`;

export function createLook({ renderer, scene, camera }) {
  const L = { mode: 'normal', cfg: { ...DEFAULTS } };
  try { L.mode = localStorage.getItem('look') === 'flat' ? 'flat' : 'normal'; } catch { /* private window: stay Normal */ }
  const q = new URLSearchParams(location.search).get('look');
  if (q === 'flat' || q === 'normal') L.mode = q;

  let rt = null, quad = null, quadScene = null, quadCam = null, mat = null;
  const size = new THREE.Vector2();
  const build = () => {
    mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, depthTest: false, depthWrite: false,
      uniforms: { tScene: { value: null }, res: { value: new THREE.Vector2(1, 1) }, cell: { value: 5 }, angle: { value: 0 }, contrast: { value: 1 }, exposure: { value: 1 },
        ramp: { value: Array.from({ length: 12 }, () => new THREE.Color()) } },
    });
    quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); quad.frustumCulled = false;
    quadScene = new THREE.Scene(); quadScene.add(quad); quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    rt = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, samples: 4, depthBuffer: true });
    rt.texture.colorSpace = THREE.LinearSRGBColorSpace;
  };
  const free = () => { if (rt) rt.dispose(); if (mat) { mat.dispose(); mat.uniforms.tScene.value = null; } if (quad) quad.geometry.dispose(); rt = quad = quadScene = quadCam = mat = null; };

  // Colours as sRGB (what you typed is what you get): three's Color.set() converts hex to linear, so convert back with the colour-space flag off.
  const srgb = (c, hex) => { c.setStyle(hex, THREE.LinearSRGBColorSpace); return c; };
  function applyCfg() {
    const u = mat.uniforms, c = L.cfg, pr = renderer.getPixelRatio();
    u.cell.value = Math.max(2, c.dot * pr); u.angle.value = THREE.MathUtils.degToRad(c.angle); u.contrast.value = c.contrast; u.exposure.value = c.exposure;
    RAMP_ORDER.forEach((name, r) => { for (let i = 0; i < 3; i++) srgb(u.ramp.value[r * 3 + i], c.ramps[name][i]); });
  }

  L.set = (patch) => { Object.assign(L.cfg, patch); return L.cfg; };
  L.setMode = (m) => {
    L.mode = m === 'flat' ? 'flat' : 'normal';
    try { localStorage.setItem('look', L.mode); } catch { /* no storage: the choice just is not remembered */ }
    if (L.mode === 'normal') free();                           // nothing is kept while it is off
    document.body.dataset.look = L.mode; L.onChange?.(L.mode); return L.mode;
  };
  document.body.dataset.look = L.mode;

  // Called instead of renderer.render(scene, camera).
  L.render = () => {
    if (L.mode !== 'flat') { renderer.render(scene, camera); return; }
    if (!rt) build();
    renderer.getDrawingBufferSize(size);
    if (rt.width !== size.x || rt.height !== size.y) rt.setSize(size.x, size.y);     // follows the adaptive pixel ratio and window resizes
    mat.uniforms.res.value.copy(size); mat.uniforms.tScene.value = rt.texture; applyCfg();
    renderer.setRenderTarget(rt); renderer.render(scene, camera);
    renderer.setRenderTarget(null); renderer.render(quadScene, quadCam);
  };
  window.__look = L;
  return L;
}
