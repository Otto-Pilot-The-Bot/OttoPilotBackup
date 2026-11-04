// Client-side art store: asks the server for each piece's content once, turns it into a canvas
// (pixel grid / sanitized SVG / sandboxed canvas JS) and tells listeners. Sculptures are built in main.js.
const SIZE = 256;
let frame = null, ready = null, nextId = 1;
const waiting = new Map();

function ensureSandbox() {
  if (frame) return ready;
  frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts');       // opaque origin: cannot touch this page, its storage or the server
  frame.style.cssText = 'position:absolute;width:0;height:0;border:0;visibility:hidden';
  frame.src = '/art-sandbox.html';
  ready = new Promise((res) => {
    addEventListener('message', function onMsg(e) {
      if (e.source !== frame.contentWindow || !e.data) return;
      if (e.data.ready) return res();
      const w = waiting.get(e.data.id); if (!w) return;
      waiting.delete(e.data.id);
      if (typeof e.data.png === 'string' && e.data.png.startsWith('data:image/png;base64,')) w.res(e.data.png);
      else w.rej(new Error(String(e.data.error || 'could not draw').slice(0, 160)));
    });
  });
  document.body.appendChild(frame);
  return ready;
}

async function runJs(code) {
  await ensureSandbox();
  const id = nextId++;
  return new Promise((res, rej) => {
    waiting.set(id, { res, rej });
    frame.contentWindow.postMessage({ id, code, size: SIZE }, '*');
    setTimeout(() => { if (waiting.delete(id)) rej(new Error('drawing took too long')); }, 6000);
  });
}

const loadImg = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('image would not load')); i.src = src; });
function newCanvas() { const c = document.createElement('canvas'); c.width = c.height = SIZE; const g = c.getContext('2d'); g.fillStyle = '#fffaf0'; g.fillRect(0, 0, SIZE, SIZE); return [c, g]; }

async function draw(piece) {
  const [c, g] = newCanvas();
  if (piece.mode === 'pixel') {
    const d = JSON.parse(piece.content), cell = Math.floor(SIZE / Math.max(d.w, d.h));
    const ox = Math.floor((SIZE - cell * d.w) / 2), oy = Math.floor((SIZE - cell * d.h) / 2);
    d.rows.forEach((row, y) => [...row].forEach((ch, x) => { const col = d.palette[ch]; if (col && /^#[0-9a-f]{6}$/i.test(col)) { g.fillStyle = col; g.fillRect(ox + x * cell, oy + y * cell, cell, cell); } }));
  } else if (piece.mode === 'image') {                   // a picture the engine already drew in marker style
    g.drawImage(await loadImg(piece.content), 0, 0, SIZE, SIZE);
  } else if (piece.mode === 'svg') {
    g.drawImage(await loadImg('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(piece.content)), 0, 0, SIZE, SIZE);
  } else if (piece.mode === 'js') {
    g.drawImage(await loadImg(await runJs(piece.content)), 0, 0, SIZE, SIZE);
  } else return null;                                    // sculpture: 3D, no flat picture
  return c;
}

export class ArtStore {
  constructor(send) { this.send = send; this.meta = new Map(); this.canvas = new Map(); this.thumbs = new Map(); this.asked = new Map(); this.done = new Set(); this.listeners = []; this.chain = Promise.resolve(); }
  onChange(cb) { this.listeners.push(cb); }
  update(list) {
    const want = [], now = Date.now();
    for (const a of list) {
      this.meta.set(a.id, a);
      if (a.status === 'broken' || this.done.has(a.id)) continue;
      if (!this.asked.has(a.id) || now - this.asked.get(a.id) > 20000) { this.asked.set(a.id, now); want.push(a.id); }   // asked again if the answer never came (e.g. the server restarted meanwhile)
    }
    for (let i = 0; i < want.length; i += 12) this.send({ type: 'get_art', ids: want.slice(i, i + 12) });
  }
  receive(msg) {
    this.chain = this.chain.then(async () => {
      try {
        const c = await draw(msg);
        this.done.add(msg.id);
        if (c) { this.canvas.set(msg.id, c); this.thumbs.set(msg.id, c.toDataURL('image/png')); }
        this.listeners.forEach((cb) => cb());
      } catch (err) {
        this.send({ type: 'art_result', id: msg.id, ok: false, error: String(err.message || err).slice(0, 150) });
      }
    });
  }
}
