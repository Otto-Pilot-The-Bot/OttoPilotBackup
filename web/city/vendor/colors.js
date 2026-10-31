// VENDORED from the city project (TheFollowerCity), file src/colors.js, commit 302c013 ("Add robot character to People assets").
// Copied so Otto's project stays portable; reference/city is only a read-only reference and may change or be absent.
// Do not edit: Otto's own drawing code lives in ../otto.js.
// Color helpers: every surface gets three tones (top / left / right) so lighting stays consistent.
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export function hexToHsl(hex) {
  const n = parseInt(hex.slice(1), 16);
  const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (mx + mn) / 2;
  if (mx !== mn) {
    const d = mx - mn;
    s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
    h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, l];
}

export const hsl = (h, s, l) =>
  `hsl(${h.toFixed(1)} ${(clamp(s, 0, 1) * 100).toFixed(1)}% ${(clamp(l, 0, 1) * 100).toFixed(1)}%)`;

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360;
  s = clamp(s, 0, 1);
  l = clamp(l, 0, 1);
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const x = (v) => Math.round(v * 255).toString(16).padStart(2, '0');
  return `#${x(f(0))}${x(f(8))}${x(f(4))}`;
}

// returns hex so the result can be fed back into tone()
export function shade(hex, dl = 0, dh = 0, ds = 0) {
  const [h, s, l] = hexToHsl(hex);
  return hslToHex(h + dh, s + ds, l + dl);
}

const cache = new Map();
// Light comes from the upper left: left faces mid, right faces dark, tops bright. Shadows lean cool.
export function tone(hex) {
  let t = cache.get(hex);
  if (!t) {
    const [h, s, l] = hexToHsl(hex);
    t = {
      base: hex,
      top: hsl(h + 2, s, Math.min(l + 0.09, 0.97)),
      left: hex,
      right: hsl(h - 8, s * 1.03, Math.max(l - 0.15, 0.05)),
    };
    cache.set(hex, t);
  }
  return t;
}

export function rng(seed) {
  let a = seed >>> 0;
  const r = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.pick = (arr) => arr[Math.floor(r() * arr.length)];
  r.range = (lo, hi) => lo + r() * (hi - lo);
  r.chance = (p) => r() < p;
  return r;
}
