// Visual realism for the 3D world. Everything here is generated in code (no downloads, no image files):
// tone mapping, soft shadows, a gradient sky with sun glow and drifting clouds, a textured grass ground with swaying grass tufts,
// a far-away horizon that fades into the fog, and sky-based environment lighting. Set `?plain=1` in the URL to turn it off.
import * as THREE from 'three';

const rngSeed = (s) => () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;

// ---------------------------------------------------------------- textures
function grassTextures() {
  const N = 512, c = document.createElement('canvas'); c.width = c.height = N;
  const b = document.createElement('canvas'); b.width = b.height = N;
  const g = c.getContext('2d'), gb = b.getContext('2d'), r = rngSeed(7);
  g.fillStyle = '#6f9a45'; g.fillRect(0, 0, N, N); gb.fillStyle = '#808080'; gb.fillRect(0, 0, N, N);
  const wrap = (fn) => { for (const ox of [-N, 0, N]) for (const oy of [-N, 0, N]) fn(ox, oy); };       // tile seamlessly
  for (let i = 0; i < 260; i++) {                                                                       // big soft patches (light/dark)
    const x = r() * N, y = r() * N, R = 30 + r() * 70, d = r() < 0.5;
    wrap((ox, oy) => { const gr = g.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, R); const col = d ? '55,92,40' : '124,164,76'; gr.addColorStop(0, `rgba(${col},0.22)`); gr.addColorStop(1, `rgba(${col},0)`); g.fillStyle = gr; g.fillRect(x + ox - R, y + oy - R, R * 2, R * 2); });
  }
  for (let i = 0; i < 9000; i++) {                                                                      // blades and speckles
    const x = r() * N, y = r() * N, l = 3 + r() * 7, a = -Math.PI / 2 + (r() - 0.5) * 1.1, tone = r();
    const col = tone < 0.45 ? '70,112,44' : tone < 0.8 ? '104,148,60' : '150,172,84';
    wrap((ox, oy) => { g.strokeStyle = `rgba(${col},${0.35 + r() * 0.4})`; g.lineWidth = 0.8 + r() * 0.8; g.beginPath(); g.moveTo(x + ox, y + oy); g.lineTo(x + ox + Math.cos(a) * l, y + oy + Math.sin(a) * l); g.stroke(); });
    gb.strokeStyle = `rgba(${tone < 0.5 ? 60 : 200},${tone < 0.5 ? 60 : 200},${tone < 0.5 ? 60 : 200},0.5)`; gb.lineWidth = 1;
    wrap((ox, oy) => { gb.beginPath(); gb.moveTo(x + ox, y + oy); gb.lineTo(x + ox + Math.cos(a) * l, y + oy + Math.sin(a) * l); gb.stroke(); });
  }
  const map = new THREE.CanvasTexture(c), bump = new THREE.CanvasTexture(b);
  for (const t of [map, bump]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; }
  map.colorSpace = THREE.SRGBColorSpace;
  return { map, bump };
}

function tuftTexture() {
  const c = document.createElement('canvas'); c.width = 128; c.height = 128; const g = c.getContext('2d'), r = rngSeed(3);
  for (let i = 0; i < 16; i++) {
    const x = 14 + r() * 100, h = 50 + r() * 70, lean = (r() - 0.5) * 36, w = 3 + r() * 3.5;
    const gr = g.createLinearGradient(0, 128, 0, 128 - h); gr.addColorStop(0, '#4f7d33'); gr.addColorStop(1, '#a8c46a');
    g.fillStyle = gr; g.beginPath(); g.moveTo(x - w, 128); g.quadraticCurveTo(x - w * 0.3 + lean * 0.4, 128 - h * 0.6, x + lean, 128 - h); g.quadraticCurveTo(x + w * 0.3 + lean * 0.4, 128 - h * 0.6, x + w, 128); g.fill();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function cloudTexture() {
  const c = document.createElement('canvas'); c.width = 256; c.height = 128; const g = c.getContext('2d'), r = rngSeed(11);
  for (let i = 0; i < 26; i++) {
    const x = 50 + r() * 156, y = 48 + r() * 34 - (Math.abs(x - 128) / 128) * 14, R = 18 + r() * 26;
    const gr = g.createRadialGradient(x, y, 0, x, y, R); gr.addColorStop(0, 'rgba(255,255,255,0.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(x - R, y - R, R * 2, R * 2);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// ---------------------------------------------------------------- the setup
export function createRealism({ renderer, scene, camera, sun, hemi }) {
  const on = !new URLSearchParams(location.search).get('plain');
  const R = { on, update() {}, buildGround: null, tint: { amount: 0, color: new THREE.Color(0xb4bcc6) } };      // tint: the weather pulls the sky and clouds toward a colour
  if (!on) return R;

  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  sun.shadow.mapSize.set(4096, 4096); sun.shadow.radius = 3.5; sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.05;
  camera.far = 600; camera.updateProjectionMatrix();

  // ---- sky dome (follows the camera) with horizon glow, sun glow and a sun disc
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: { value: new THREE.Color(0x5b8fd0) }, horizon: { value: new THREE.Color(0xcfe3f2) }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunCol: { value: new THREE.Color(0xfff2d6) }, night: { value: 0 } },
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `varying vec3 vD; uniform vec3 top, horizon, sunDir, sunCol; uniform float night;
      void main(){ vec3 d = normalize(vD); float h = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(horizon, top, pow(h, 0.55));
        float s = max(dot(d, normalize(sunDir)), 0.0);
        col += sunCol * (pow(s, 6.0) * 0.28 + pow(s, 90.0) * 0.5 + smoothstep(0.9993, 0.9997, s) * 2.0) * (1.0 - night * 0.85);
        col = mix(col, horizon, smoothstep(0.0, -0.25, d.y) * 0.0);
        float st = step(0.9985, fract(sin(dot(floor(d.xz * 260.0 + d.y * 90.0), vec2(12.9898, 78.233))) * 43758.5453)) * night * smoothstep(0.1, 0.5, d.y);
        col += vec3(st);
        gl_FragColor = vec4(col, 1.0); }`,
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(500, 32, 18), skyMat); sky.renderOrder = -10; sky.frustumCulled = false; scene.add(sky);

  // ---- clouds
  const cloudTex = cloudTexture(), clouds = [];
  for (let i = 0; i < 14; i++) {
    const m = new THREE.SpriteMaterial({ map: cloudTex, transparent: true, depthWrite: false, fog: false, opacity: 0.9 });
    const s = new THREE.Sprite(m), a = (i / 14) * Math.PI * 2 + Math.sin(i * 7) * 0.3, d = 140 + (i % 5) * 45;
    s.position.set(Math.cos(a) * d, 70 + (i % 4) * 14, Math.sin(a) * d); const w = 90 + (i % 3) * 40; s.scale.set(w, w / 2, 1); s.userData.a = a; s.userData.d = d; s.userData.v = 0.0009 + (i % 4) * 0.0003;
    s.renderOrder = -9; scene.add(s); clouds.push(s);
  }

  // ---- ground: textured grass, a horizon plane that fades into the fog, and swaying grass tufts
  const { map, bump } = grassTextures(), tuftTex = tuftTexture();
  const groundMat = new THREE.MeshStandardMaterial({ map, bumpMap: bump, bumpScale: 1.4, roughness: 0.95, color: 0xffffff });
  const farMat = new THREE.MeshStandardMaterial({ map, roughness: 1, color: 0xdfe8d0 });
  const wind = { value: 0 };
  const tuftMat = new THREE.MeshStandardMaterial({ map: tuftTex, alphaTest: 0.5, roughness: 1 });
  tuftMat.onBeforeCompile = (sh) => {
    sh.uniforms.uWind = wind;
    sh.vertexShader = 'uniform float uWind;\n' + sh.vertexShader.replace('#include <begin_vertex>',
      `vec3 transformed = vec3(position);
       float sw = uv.y * uv.y; vec4 ip = instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
       transformed.x += sin(uWind * 1.6 + ip.x * 0.55 + ip.z * 0.35) * 0.09 * sw + sin(uWind * 3.1 + ip.z) * 0.025 * sw;`);
  };
  let tufts = null, farPlane = null, tuftsOn = true, farY = -0.06;
  R.setFarY = (y) => { farY = y; if (farPlane) farPlane.position.y = y; };      // a lake in the map needs the far ground well below it
  R.setTufts = (v) => { tuftsOn = v; if (tufts) tufts.visible = v; };      // off when a map's flat tiles (roads, plaza) lie on the ground

  R.buildGround = (half, ground) => {
    const size = half * 2 + 8, rep = size / 7;
    map.repeat.set(rep, rep); bump.repeat.set(rep, rep);
    ground.material = groundMat; ground.position.y = 0;
    if (farPlane) { scene.remove(farPlane); farPlane.geometry.dispose(); }
    const frep = 1200 / 14; const fm = farMat; fm.map = map.clone(); fm.map.repeat.set(frep, frep); fm.map.needsUpdate = true;
    farPlane = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200), fm); farPlane.rotation.x = -Math.PI / 2; farPlane.position.y = farY; farPlane.receiveShadow = false; scene.add(farPlane);
    if (tufts) { scene.remove(tufts); tufts.geometry.dispose(); tufts.dispose(); }
    const n = Math.min(14000, Math.round(half * half * 5.5)), g = new THREE.PlaneGeometry(0.62, 0.5); g.translate(0, 0.25, 0);
    const g2 = g.clone(); g2.rotateY(Math.PI / 2);
    const geo = mergeTwo(g, g2);
    tufts = new THREE.InstancedMesh(geo, tuftMat, n); tufts.frustumCulled = false;
    const rr = rngSeed(41), m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), sc = new THREE.Vector3(), col = new THREE.Color();
    for (let i = 0; i < n; i++) {
      p.set((rr() * 2 - 1) * (half + 3), 0, (rr() * 2 - 1) * (half + 3)); e.set(0, rr() * 3.14, 0); q.setFromEuler(e);
      const s = 0.6 + rr() * 0.9; sc.set(s, s * (0.7 + rr() * 0.7), s); m.compose(p, q, sc); tufts.setMatrixAt(i, m);
      col.setHSL(0.24 + rr() * 0.06, 0.35 + rr() * 0.2, 0.42 + rr() * 0.16); tufts.setColorAt(i, col);
    }
    tufts.visible = tuftsOn; scene.add(tufts);
  };

  // ---- sky-based environment light (rebuilt a few times a day)
  const pmrem = new THREE.PMREMGenerator(renderer); let lastEnv = -9, envTarget = null;
  const envScene = new THREE.Scene(); const envSky = new THREE.Mesh(sky.geometry, skyMat); envScene.add(envSky);
  scene.environmentIntensity = 0.35;

  const TOP = [[0, 0x0b1230], [5, 0x101a3d], [6.5, 0x5a7fb5], [8, 0x4f86cf], [17, 0x4f86cf], [18.5, 0x5a6fa8], [20, 0x141c44], [24, 0x0b1230]];
  const HOR = [[0, 0x1c2548], [5, 0x2a3358], [6.5, 0xf6c79a], [8, 0xcfe4f4], [17, 0xcfe4f4], [18.5, 0xf4b88a], [20, 0x3a4470], [24, 0x1c2548]];
  const lerpKey = (arr, h) => { for (let i = 1; i < arr.length; i++) if (h <= arr[i][0]) { const [h0, a] = arr[i - 1], [h1, b] = arr[i]; return new THREE.Color(a).lerp(new THREE.Color(b), (h - h0) / (h1 - h0 || 1)); } return new THREE.Color(arr.at(-1)[1]); };
  const tmpC = new THREE.Color();

  R.update = (hour, nightness, dt, t) => {
    const top = lerpKey(TOP, hour), hor = lerpKey(HOR, hour), wk = R.tint.amount;
    if (wk > 0.005) { tmpC.copy(R.tint.color).multiplyScalar(1 - nightness * 0.7); top.lerp(tmpC, Math.min(1, wk * 1.3)); hor.lerp(tmpC, wk * 0.9); }
    skyMat.uniforms.top.value.copy(top); skyMat.uniforms.horizon.value.copy(hor); skyMat.uniforms.night.value = nightness;
    skyMat.uniforms.sunDir.value.copy(sun.position).normalize(); skyMat.uniforms.sunCol.value.copy(sun.color);
    sky.position.copy(camera.position);
    scene.fog.color.copy(hor); scene.background.copy(hor);
    farMat.color.copy(tmpC.set(0xdfe8d0)).multiplyScalar(1 - nightness * 0.65);
    groundMat.color.setScalar(1 - nightness * 0.1);
    for (const c of clouds) { c.userData.a += c.userData.v * dt; const a = c.userData.a; c.position.x = Math.cos(a) * c.userData.d; c.position.z = Math.sin(a) * c.userData.d;
      c.material.color.copy(tmpC.set(0xffffff).lerp(sun.color, 0.35).multiplyScalar(1 - nightness * 0.75)); c.material.opacity = Math.min(1, 0.9 - nightness * 0.35 + wk * 0.12);
      if (wk > 0.005) c.material.color.lerp(tmpC.copy(R.tint.color).multiplyScalar(0.85 - nightness * 0.5), wk * 0.8); }
    wind.value = t;
    hemi.intensity *= 0.82;                                                       // the environment light adds to the hemisphere light
    if (Math.abs(hour - lastEnv) > 0.5 || hour < lastEnv) {                      // refresh reflections/ambient from the sky
      lastEnv = hour; if (envTarget) envTarget.dispose();
      envSky.position.set(0, 0, 0); envTarget = pmrem.fromScene(envScene, 0.02); scene.environment = envTarget.texture;
    }
  };
  return R;
}

function mergeTwo(a, b) {                                                          // two crossed quads in one geometry (no extra imports)
  const g = new THREE.BufferGeometry(), pa = a.attributes, pb = b.attributes;
  const cat = (x, y, n) => { const o = new Float32Array(x.array.length + y.array.length); o.set(x.array); o.set(y.array, x.array.length); return new THREE.BufferAttribute(o, n); };
  g.setAttribute('position', cat(pa.position, pb.position, 3)); g.setAttribute('normal', cat(pa.normal, pb.normal, 3)); g.setAttribute('uv', cat(pa.uv, pb.uv, 2));
  const ia = a.index.array, off = pa.position.count, idx = new Uint16Array(ia.length * 4);
  idx.set(ia); for (let i = 0; i < b.index.array.length; i++) idx[ia.length + i] = b.index.array[i] + off;
  for (let i = 0; i < ia.length * 2; i += 3) { idx[ia.length * 2 + i] = idx[i]; idx[ia.length * 2 + i + 1] = idx[i + 2]; idx[ia.length * 2 + i + 2] = idx[i + 1]; }   // reversed copies: both sides front-facing, normals stay up
  const nn = g.attributes.normal; for (let i = 0; i < nn.count; i++) nn.setXYZ(i, 0, 1, 0);          // light grass like the ground (normals up), not like flat cards
  g.setIndex(new THREE.BufferAttribute(idx, 1)); return g;
}
