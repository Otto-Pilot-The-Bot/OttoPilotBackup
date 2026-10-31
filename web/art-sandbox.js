// Runs the robot's canvas drawing code inside a Web Worker that can be killed, with no network (CSP) and no
// access to worker globals (shadowed). Only a PNG data URL is sent back to the parent page.
const parentWin = window.parent;
const TIMEOUT_MS = 3000;

addEventListener('message', (e) => {
  if (e.source !== parentWin) return;
  const { id, code, size } = e.data || {};
  if (typeof id !== 'number' || typeof code !== 'string') return;
  run(id, code.slice(0, 6000), Math.min(512, Math.max(32, size | 0 || 256)));
});

function reply(msg) { parentWin.postMessage(msg, '*'); }

function run(id, code, size) {
  const src =
    'let seed = ' + ((id * 2654435761) >>> 0) + ';\n' +
    'function rand(){ seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }\n' +
    'onmessage = async () => { try {\n' +
    '  const W = ' + size + ', H = ' + size + ';\n' +
    '  const canvas = new OffscreenCanvas(W, H); const ctx = canvas.getContext("2d");\n' +
    '  ctx.fillStyle = "#fffaf0"; ctx.fillRect(0, 0, W, H);\n' +
    '  (function (ctx, W, H, rand, self, postMessage, onmessage, fetch, importScripts, WebSocket, XMLHttpRequest, globalThis, Worker, eval, Function) {\n' +
    code + '\n' +
    '  })(ctx, W, H, rand);\n' +
    '  const blob = await canvas.convertToBlob({ type: "image/png" });\n' +
    '  postMessage({ blob });\n' +
    '} catch (err) { postMessage({ error: String((err && err.message) || err).slice(0, 200) }); } };';
  let url, worker, done = false;
  const finish = (msg) => { if (done) return; done = true; clearTimeout(timer); try { worker && worker.terminate(); } catch (_) {} if (url) URL.revokeObjectURL(url); reply({ id, ...msg }); };
  const timer = setTimeout(() => finish({ error: 'drawing took too long' }), TIMEOUT_MS);
  try {
    url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
    worker = new Worker(url);
  } catch (err) { return finish({ error: 'could not start: ' + err.message }); }
  worker.onerror = (ev) => { ev.preventDefault && ev.preventDefault(); finish({ error: (ev.message || 'syntax error in drawing code').slice(0, 200) }); };
  worker.onmessage = (ev) => {
    if (ev.data && ev.data.error) return finish({ error: ev.data.error });
    if (ev.data && ev.data.blob instanceof Blob && ev.data.blob.size < 2_000_000) {
      const fr = new FileReader();
      fr.onload = () => finish({ png: String(fr.result) });
      fr.onerror = () => finish({ error: 'could not read the image' });
      fr.readAsDataURL(ev.data.blob);
    } else finish({ error: 'no image produced' });
  };
  worker.postMessage(1);
}
reply({ ready: true });
