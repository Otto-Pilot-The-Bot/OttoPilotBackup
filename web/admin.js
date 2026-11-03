// Admin dashboard: sliders and buttons for Otto's needs, character, omens, weather and mind. Talks to the same /ws as the world page (same sign-in).
// Every control sends one admin_* message; the server answers with a toast and a fresh admin view. The kill switch, pause and game mode use the normal messages.
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
let ws, view = null, wsOk = false, dragging = 0, quirks = [];

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.onopen = () => { wsOk = true; send({ type: 'admin_get' }); };
  ws.onclose = () => { wsOk = false; $('#who').textContent = 'reconnecting…'; setTimeout(connect, 2000); };
  ws.onmessage = (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.type === 'admin') render(m);
    else if (m.type === 'toast') toast(m.text, m.ok !== false);
  };
}
const send = (m) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); };
function toast(t, ok = true) { const x = $('#toast'); x.textContent = t; x.classList.toggle('bad', !ok); x.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => { x.hidden = true; }, 3500); }
setInterval(() => { if (wsOk && !dragging) send({ type: 'admin_get' }); }, 6000);

// ---- sliders: show the value while dragging, send when released
function slider(id, label, value, onSet, hint) {
  return `<label class="sl" title="${esc(hint || '')}"><span>${esc(label)}</span><input type="range" min="0" max="${id.startsWith('n_') ? 100 : 1}" step="${id.startsWith('n_') ? 1 : 0.05}" value="${value}" data-id="${id}"><b class="v">${id.startsWith('n_') ? Math.round(value) : (+value).toFixed(2)}</b></label>`;
}
document.addEventListener('input', (e) => { const t = e.target; if (t.type === 'range' && t.dataset.id) { dragging = Date.now(); t.parentElement.querySelector('.v').textContent = t.dataset.id.startsWith('n_') ? Math.round(t.value) : (+t.value).toFixed(2); }
  if (t.id === 'omenSec') $('#omenSecV').textContent = t.value; if (t.id === 'wipeText') $('#wipeBtn').disabled = t.value.trim() !== 'WIPE'; });
document.addEventListener('change', (e) => {
  const t = e.target; dragging = 0;
  if (t.type === 'range' && t.dataset.id) {
    if (t.dataset.id.startsWith('n_')) send({ type: 'admin_needs', [t.dataset.id.slice(2)]: +t.value });
    else if (t.dataset.id.startsWith('d_')) send({ type: 'admin_traits', dials: { [t.dataset.id.slice(2)]: +t.value } });
  }
  if (t.id === 'wx') send({ type: 'admin_weather', name: t.value });
});

function render(v) {
  view = v;
  $('#who').textContent = `tick ${v.tick} · ${v.world.label} day ${v.world.day} · feeling ${v.mood}`;
  $('#pauseBtn').textContent = v.paused ? 'Resume' : 'Pause'; $('#adGame').textContent = v.sleeping ? 'Wake up (game mode on)' : 'Game mode';
  if (!dragging || Date.now() - dragging > 2500) {
    $('#needs').innerHTML = Object.entries(v.needs).map(([k, n]) => slider('n_' + k, k, n)).join('');
    $('#dials').innerHTML = Object.entries(v.dials).map(([k, n]) => slider('d_' + k, k, n, `high: ${v.dial_info[k].high} · low: ${v.dial_info[k].low}`)).join('');
  }
  quirks = v.quirks.slice();
  $('#quirks').innerHTML = quirks.map((q, i) => `<span class="chip">${esc(q)} <button class="x" data-q="${i}" aria-label="Remove">✕</button></span>`).join('') || '<span class="dim small">none</span>';
  const have = new Set(quirks); $('#quirkAdd').innerHTML = v.quirk_pool.filter((q) => !have.has(q)).map((q) => `<option>${esc(q)}</option>`).join('');
  if (document.activeElement !== $('#wx')) $('#wx').innerHTML = v.weathers.map((w) => `<option value="${esc(w)}" ${w === v.weather_override ? 'selected' : ''}>${w || 'automatic (daily)'}</option>`).join('');
  $('#wxNow').textContent = `Right now: ${v.weather} (${v.season})${v.weather_override ? ' – forced by you' : ''}`;
  if (document.activeElement !== $('#goto')) $('#goto').innerHTML = Object.entries(v.places).map(([k, p]) => `<option value="${esc(k)}">${esc(p.label)}</option>`).join('');
  $('#omenNow').textContent = v.omen && v.tick <= v.omen.until ? `Active: “${v.omen.text}” (${v.omen.tone})` : '';
  $('#goals').innerHTML = v.goals.map((g) => `<div class="act"><span class="x2">${esc(g.text)}</span><button class="btn small" data-goal="${g.id}">Drop</button></div>`).join('') || '<div class="empty">No active goals.</div>';
  $('#interests').innerHTML = v.interests.map((i) => `<span class="chip">${esc(i.topic)} · ${i.strength} <button class="x" data-int="${esc(i.topic)}" aria-label="Remove">✕</button></span>`).join('') || '<span class="dim small">none</span>';
  $('#recent').innerHTML = v.recent.map((r) => `<div><span class="k">t${r.tick}</span> <b>${esc(r.tool)}</b> ${esc(r.result)}</div>`).join('');
  $('#printKey').textContent = v.print_ready ? '' : 'No printer key yet: add TRIPO_API_KEY to the .env file (or set it as an environment variable) and restart the server.';
  $('#prints').innerHTML = (v.prints || []).map((p) => `<div class="act"><span class="x2">${p.image ? `<img src="${p.image}" alt="" style="width:64px;height:64px;object-fit:cover;border-radius:8px;vertical-align:middle;margin-right:8px">` : ''}<b>${esc(p.title)}</b> <span class="dim small">${esc(p.prompt)} · ${p.tris} tris · ${p.status === 'ready' ? 'waiting' : 'on the tray'}</span></span>${p.status === 'ready' ? `<button class="btn small primary" data-pa="${p.id}">Approve</button><button class="btn small" data-pr="${p.id}">Reject</button>` : `<button class="btn small" data-prm="${p.id}">Remove</button>`}</div>`).join('') || '<div class="empty dim small">Nothing printed yet.</div>';
  $('#wipeCount').textContent = `Currently ${v.memories} memories and ${v.journal} diary entries.`;
}

document.addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.id === 'pauseBtn') send({ type: view && view.paused ? 'resume' : 'pause' });
  else if (b.id === 'adGame') send({ type: 'game_mode', on: !(view && view.sleeping) });
  else if (b.id === 'killBtn') { if (confirm('Kill switch: stop Otto and the server now?')) send({ type: 'kill' }); }
  else if (b.id === 'refill') send({ type: 'admin_refill' });
  else if (b.id === 'think') send({ type: 'admin_force_think' });
  else if (b.id === 'omenBtn') { send({ type: 'admin_omen', text: $('#omenText').value, tone: $('#omenTone').value, intensity: +$('#omenInt').value, seconds: +$('#omenSec').value }); $('#omenText').value = ''; }
  else if (b.id === 'gotoBtn') send({ type: 'admin_goto', place: $('#goto').value });
  else if (b.id === 'quirkBtn') { const q = $('#quirkAdd').value; if (q && quirks.length < 6) send({ type: 'admin_traits', quirks: [...quirks, q] }); }
  else if (b.id === 'wipeBtn') { if ($('#wipeText').value.trim() === 'WIPE' && confirm('Really wipe Otto\'s memory? A backup is saved first, but he will forget everything he has learned.')) { send({ type: 'admin_wipe_memory', confirm: $('#wipeText').value.trim() }); $('#wipeText').value = ''; $('#wipeBtn').disabled = true; } }
  else if (b.dataset.q !== undefined) send({ type: 'admin_traits', quirks: quirks.filter((_, i) => i !== +b.dataset.q) });
  else if (b.dataset.pa) send({ type: 'admin_print_approve', id: +b.dataset.pa });
  else if (b.dataset.pr) send({ type: 'admin_print_reject', id: +b.dataset.pr });
  else if (b.dataset.prm) { if (confirm('Remove this figurine from the tray?')) send({ type: 'admin_print_remove', id: +b.dataset.prm }); }
  else if (b.dataset.goal) send({ type: 'admin_goal_drop', id: +b.dataset.goal });
  else if (b.dataset.int) send({ type: 'admin_interest_drop', topic: b.dataset.int });
});
connect();
