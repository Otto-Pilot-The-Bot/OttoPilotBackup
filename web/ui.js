// All DOM / panels. main.js feeds it snapshots and events; it never touches the 3D scene directly.
const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = (u) => (/^https?:\/\/[^\s"'<>]+$/i.test(u || '') ? u : '');
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };

const MOOD = { happy: '😊', excited: '🤩', proud: '😎', content: '🙂', curious: '🧐', surprised: '😮', tired: '😴', bored: '🥱', scared: '😨', sad: '😢', angry: '😠' };
const TOOL_ICON = { move_to: '🚶', eat: '🔋', rest: '💤', search_web: '🔎', read_page: '📄', write_journal: '📓', interact_with: '🤝', shop: '🛍️', build: '🔨', make_art: '🎨', publish_page: '📰', system: '⚠️' };
const TOOL_LABEL = { move_to: 'Walking', eat: 'Refueling', rest: 'Resting', search_web: 'Searching', read_page: 'Reading a page', write_journal: 'Journaling', interact_with: 'Exploring', shop: 'Shopping', build: 'Building', make_art: 'Making art', publish_page: 'Drafting a page', system: 'System' };
const KIND_ICON = { tree: '🌳', rock: '🪨', flower: '🌸', ball: '⚽', box: '📦', lamp: '💡', house: '🏠', fountain: '⛲', statue: '🗿', bench: '🪑', creature: '🐾', other: '✨' };
const STAGES = ['blueprint', 'gather', 'build', 'finished'];
const SWATCH = ['#e53935', '#fb8c00', '#fdd835', '#43a047', '#00897b', '#1e88e5', '#8e24aa', '#ec407a', '#f5f5f5', '#6d4c41'];

let short = 'Otto', api, snap = null, skew = 0, openId = null, art = null, lastCaption = '';
const openPrev = new Set();
let confirmLive = false;
let thingsTab = 'gallery', browseFilter = 'all', draggingSpeed = false, killArmed = false, logRows = null, showLog = false;
const gift = { kind: 'tree', color: '#43a047' };

export const rel = (ts) => {
  const s = Math.max(0, Date.now() / 1000 + skew - ts);
  if (s < 10) return 'just now';
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};
const ago = (ts) => `<span class="ago" data-ts="${ts}">${rel(ts)}</span>`;

// ------------------------------------------------------------------ panels
const PANELS = [
  { id: 'diary', icon: '📖', label: 'His diary', title: 'His diary', build() {}, update(el, s) {
    el.innerHTML = s.journal.length ? s.journal.map((j) => { const th = j.obj_id ? api.thumb(j.obj_id) : null; return `<article class="note k-${esc(j.kind)}"><header>${ago(j.ts)}<span class="chip">${({ entry: 'journal', reflection: 'reflection', learning: 'learned', art: 'art', build: 'built' })[j.kind] || esc(j.kind)}</span><span title="${esc(j.mood)}">${MOOD[j.mood] || ''}</span></header><div class="row">${th ? `<img class="thumb" alt="" src="${th}">` : ''}<p>${esc(j.text)}</p></div></article>`; }).join('')
      : '<div class="empty">His diary is still blank. He will write soon.</div>';
  } },

  { id: 'doing', icon: '🎯', label: "What he's doing", title: "What he's doing", build() {}, update(el, s) {
    const goal = s.goals[0], others = s.goals.slice(1);
    const act = s.projects.filter((p) => p.status === 'active');
    const last = s.projects.find((p) => p.status === 'done');
    const stepper = (p) => { const done = STAGES.indexOf(p.stage) + 1; return `<div class="steps">${STAGES.map((n, i) => `<span class="${i < done ? 'done' : i === done ? 'next' : ''}">${n === 'finished' ? 'finish' : n}</span>`).join('')}</div>`; };
    el.innerHTML = `<h3>Right now</h3><div class="card">${esc(lastCaption || 'Thinking…')}${s.state.inside ? `<div class="meta">📍 inside the ${esc(s.places[s.state.inside].label)}</div>` : ''}</div>
      <h3>Current goal</h3>${goal ? `<div class="card goal">#${goal.id} ${esc(goal.text)}</div>` : '<div class="empty">No goal yet.</div>'}
      ${others.length ? `<div class="chips">${others.map((g) => `<span class="chip" title="${esc(g.text)}">${esc(g.text.slice(0, 38))}${g.text.length > 38 ? '…' : ''}</span>`).join('')}</div>` : ''}
      <h3>Project in progress</h3>${act.length ? act.map((p) => `<div class="card"><div class="t"><span class="sw" style="background:${esc(p.color)}"></span>${esc(p.name)}</div><div class="meta">${esc(p.description || '')}</div>${stepper(p)}</div>`).join('')
        : `<div class="empty">Nothing on the workbench${last ? ` · last finished: “${esc(last.name)}”` : ''}.</div>`}
      ${s.interests.length ? `<h3>Curious about</h3><div class="chips">${s.interests.map((i) => `<span class="chip">${esc(i.topic)}</span>`).join('')}</div>` : ''}
      <h3>Recent actions</h3>${s.recent.map((r) => `<div class="act"><span class="ico">${TOOL_ICON[r.tool] || '•'}</span><span class="x2" title="${esc(r.result)}"><b>${esc(TOOL_LABEL[r.tool] || r.tool)}</b> ${esc(r.args)} <span class="dim">${esc(r.result)}</span></span><span class="small dim">${ago(r.ts)}</span></div>`).join('')}`;
  } },

  { id: 'things', icon: '🧺', label: 'His things', title: 'His things', build(el) {
    el.innerHTML = `<div class="tabs"></div><div class="tb"></div>`;
    el.querySelector('.tabs').onclick = (e) => { const b = e.target.closest('button[data-t]'); if (b) { thingsTab = b.dataset.t; refresh(); } };
    el.querySelector('.tb').onclick = (e) => { const b = e.target.closest('[data-art]'); if (b) openArt(+b.dataset.art); };
  }, update(el, s) {
    const tabs = [['gallery', '🖼️ Gallery'], ['built', '🔧 Built'], ['wear', '🎩 Wardrobe'], ['sketch', '✏️ Sketchbook']];
    el.querySelector('.tabs').innerHTML = tabs.map(([k, l]) => `<button data-t="${k}" class="${k === thingsTab ? 'on' : ''}">${l}</button>`).join('');
    const tb = el.querySelector('.tb');
    if (thingsTab === 'gallery') {
      const list = s.art.filter((a) => a.status !== 'broken');
      tb.innerHTML = list.length ? `<div class="grid">${list.map((a) => {
        const th = art.thumbs.get(a.id) || (a.kind === 'sculpture' ? api.thumbArt(a.id) : null);
        return `<button class="art-card" data-art="${a.id}"><div class="pic">${th ? `<img class="${a.mode === 'pixel' ? 'px' : ''}" alt="" src="${th}">` : a.kind === 'sculpture' ? '🗿' : '…'}</div><div class="cap">${esc(a.title)}</div><div class="small dim">${esc(a.kind)} · ${ago(a.ts)}</div></button>`;
      }).join('')}</div>` : '<div class="empty">No art yet. He may start when he feels creative.</div>';
    } else if (thingsTab === 'built') {
      tb.innerHTML = s.built.length ? s.built.map((b) => { const th = b.obj_id ? api.thumb(b.obj_id) : null; return `<div class="card row">${th ? `<img class="thumb" alt="" src="${th}">` : `<span class="sw" style="background:${esc(b.color || '#ccc')}"></span>`}<div><div class="t">${esc(b.name)}</div><div class="meta">${esc(b.description || '')} · ${ago(b.ts)}</div></div></div>`; }).join('')
        : '<div class="empty">He has not finished a build yet.</div>';
      if (s.designs && s.designs.length) tb.innerHTML += `<h3>Designs he scripted &amp; saved</h3>` + s.designs.map((d) => `<div class="card"><div class="t">📐 ${esc(d.name)} <span class="chip">reused ${d.uses}×</span></div><details><summary class="small">Show his script</summary><pre class="log" style="max-height:160px">${esc(d.script)}</pre></details><div class="meta">${ago(d.ts)}</div></div>`).join('');
    } else if (thingsTab === 'wear') {
      const slots = [['hat', 'Hat'], ['goggles', 'Goggles'], ['scarf', 'Scarf'], ['antenna', 'Antenna'], ['body', 'Paint']];
      const fav = s.prefs.filter((p) => p.subject.endsWith(' color') && p.score > 0.3).slice(0, 5);
      tb.innerHTML = `<h3>Wearing now</h3>` + slots.map(([k, l]) => `<div class="card"><span class="sw" style="background:${esc(s.outfit[k] || 'transparent')}"></span>${l}: <span class="dim">${s.outfit[k] ? 'yes' : 'nothing'}</span></div>`).join('')
        + `<h3>Favorite colors</h3>${fav.length ? `<div class="chips">${fav.map((p) => `<span class="chip">${esc(p.subject.replace(' color', ''))}</span>`).join('')}</div>` : '<div class="empty">Still deciding.</div>'}`;
    } else {
      tb.innerHTML = s.sketches.length ? s.sketches.map((k) => `<div class="card" style="${k.used ? 'opacity:.55;text-decoration:line-through' : ''}">✏️ ${esc(k.idea)} <div class="meta">${ago(k.ts)}${k.used ? ' · used' : ''}</div></div>`).join('')
        : '<div class="empty">The sketchbook is empty. Ideas come from reading and reflecting.</div>';
    }
  } },

  { id: 'browse', icon: '🌐', label: 'Browsing', title: 'Browsing', build(el) {
    el.innerHTML = `<div class="tabs"></div><div class="tb"></div>`;
    el.querySelector('.tabs').onclick = (e) => { const b = e.target.closest('button[data-f]'); if (b) { browseFilter = b.dataset.f; refresh(); } };
  }, update(el, s) {
    el.querySelector('.tabs').innerHTML = [['all', 'All'], ['pages', '📄 Pages'], ['searches', '🔎 Searches']].map(([k, l]) => `<button data-f="${k}" class="${k === browseFilter ? 'on' : ''}">${l}</button>`).join('');
    const items = [];
    if (browseFilter !== 'searches') for (const r of s.reads) items.push({ ts: r.ts, html: r.ok
      ? `<div class="card"><div class="t">📄 ${safeUrl(r.url) ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title || host(r.url))}</a>` : esc(r.title || r.url)}</div><div class="meta">${esc(host(r.url))} · ${ago(r.ts)}</div>${r.summary ? `<div style="margin-top:4px">“${esc(r.summary)}”</div>` : ''}</div>`
      : `<div class="card" style="opacity:.8"><div class="t">🚫 Could not read</div><div class="meta">${esc(r.url.slice(0, 70))} · ${ago(r.ts)}</div><div class="small">${esc(r.error)}</div></div>` });
    if (browseFilter !== 'pages') for (const q of s.searches) items.push({ ts: q.ts, html: `<div class="card"><div class="t">🔎 ${esc(q.query)}</div><div class="meta">${ago(q.ts)}${q.error ? ' · failed' : ''}</div>${q.results.map((r) => `<div class="small">${safeUrl(r.url) ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title || host(r.url))}</a>` : esc(r.title)} <span class="dim">${esc(host(r.url))}</span></div>`).join('')}</div>` });
    items.sort((a, b) => b.ts - a.ts);
    el.querySelector('.tb').innerHTML = items.length ? items.map((i) => i.html).join('') : '<div class="empty">He has not browsed yet.</div>';
  } },

  { id: 'site', icon: '🌍', label: 'My site', title: 'My site', build(el) {
    el.innerHTML = `<div id="siteNotice"></div><div id="siteStatus"></div><div id="siteQueue"></div><div id="siteHistory"></div>`;
    el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-site]'); if (!b) return;
      const a = b.dataset.site;
      if (a === 'approve' || a === 'reject') api.send({ type: a + '_page', id: +b.dataset.id });
      else if (a === 'mode-dry') { confirmLive = false; api.send({ type: 'set_publish_mode', mode: 'dry_run' }); }
      else if (a === 'mode-live') { confirmLive = true; refresh(); }
      else if (a === 'mode-live-yes') { confirmLive = false; api.send({ type: 'set_publish_mode', mode: 'live' }); }
      else if (a === 'mode-live-no') { confirmLive = false; refresh(); }
      else if (a === 'check') api.send({ type: 'check_site' });
    });
    el.addEventListener('change', (e) => { if (e.target.id === 'sitePub') api.send({ type: 'toggle_publish', on: e.target.checked }); });
    el.addEventListener('toggle', (e) => { const d = e.target; if (d.dataset && d.dataset.prev) { d.open ? openPrev.add(d.dataset.prev) : openPrev.delete(d.dataset.prev); } }, true);
  }, update(el, s) {
    const S = s.site, live = S.mode === 'live', st = S.status || {};
    const n = S.notice;
    $('#siteNotice', el).innerHTML = n && Date.now() / 1000 + skew - n.ts < 600 ? `<div class="card" style="background:${n.ok ? '#e4f1dc' : '#f6d7cf'};border-color:${n.ok ? '#b6d6a4' : '#e3a89b'}">${n.ok ? '✅' : '⚠️'} ${esc(n.text)} <span class="small dim">${ago(n.ts)}</span></div>` : '';
    const chip = !S.enabled ? '<span class="chip" style="background:#e8dfcc">Publishing is OFF</span>'
      : live ? '<span class="chip" style="background:#cfe8c4">ON · LIVE (uploads to GitHub)</span>' : '<span class="chip" style="background:#fbe0c4">ON · dry run (nothing is uploaded)</span>';
    $('#siteStatus', el).innerHTML = `<div class="card"><div>${chip}</div>
      <div style="margin-top:8px">🌐 <a href="${esc(S.url)}" target="_blank" rel="noopener noreferrer">${esc(S.url.replace('https://', ''))}</a></div>
      <div class="meta">repo ${esc(S.repo)} · commits as ${esc(S.author)}</div></div>
      <label class="switch" style="margin:10px 2px"><input type="checkbox" id="sitePub" ${S.enabled ? 'checked' : ''}><span>Let him write pages for his site.<br><span class="small dim">Off by default. Nothing ever goes out without you pressing Approve.</span></span></label>
      <h3>How approved pages are sent</h3>
      <div class="tabs" style="margin-bottom:6px"><button data-site="mode-dry" class="${!live ? 'on' : ''}">🧪 Dry run (safe)</button><button data-site="mode-live" class="${live ? 'on' : ''}">🚀 Live</button></div>
      ${confirmLive ? `<div class="card" style="background:#f6d7cf;border-color:#e3a89b"><b>Go live?</b> Pages you approve will be pushed to the public website above.<div class="field"><button class="btn danger" data-site="mode-live-yes">Yes, switch to live</button><button class="btn" data-site="mode-live-no">Cancel</button></div></div>` : ''}
      <div class="small dim">${live ? 'Live: approving a page commits and pushes it to GitHub Pages.' : 'Dry run: approving writes the files to <b>site_dryrun/</b> on this Mac and shows what would be pushed. Nothing is uploaded.'}</div>
      <div class="small" style="margin-top:6px">${st.token_present === undefined ? 'Checking setup…' : st.token_present ? '🔑 GitHub token found in .env (value never shown)' : '⚠️ No GitHub token found in .env'} <button class="btn" style="padding:1px 8px;font-size:11px" data-site="check">Re-check</button></div>
      <div class="small dim">Limit: ${S.used_today} of ${S.per_day} pages published in the last 24 h.</div>`;
    $('#siteQueue', el).innerHTML = `<h3>Waiting for your approval</h3>` + (S.pending.length ? S.pending.map((p) => {
      const busy = p.status === 'publishing', wait = p.retry_in > 0;
      return `<div class="card"><div class="t">${esc(p.title)}</div><div class="chips" style="margin:4px 0">${p.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join('')}</div>
        <div class="small">${esc(p.excerpt)}…</div>
        <details data-prev="${p.id}" ${openPrev.has(String(p.id)) ? 'open' : ''}><summary class="small">Preview</summary><iframe sandbox referrerpolicy="no-referrer" style="width:100%;height:180px;border:1px solid var(--line);border-radius:8px;background:#fffdf6" srcdoc="${esc('<style>body{font:14px/1.5 system-ui;color:#4b3b29;margin:10px}a{color:#c46a1f}h1{font-size:20px}h2,h3{font-size:16px}</style>' + p.html)}"></iframe></details>
        ${p.last_error ? `<div class="small" style="color:#a0521c;margin-top:4px">⚠️ Last try failed: ${esc(p.last_error)}${wait ? ` (you can retry in ${p.retry_in}s)` : ''}</div>` : ''}
        ${p.mode === 'dry_run' && !p.last_error ? '<div class="small dim" style="margin-top:4px">🧪 A dry run of this page was made. It is still waiting.</div>' : ''}
        <div class="field"><button class="btn primary" data-site="approve" data-id="${p.id}" ${busy || !S.enabled ? 'disabled' : ''}>${busy ? 'Publishing…' : live ? 'Approve & publish live' : (p.last_error ? 'Retry (dry run)' : 'Approve (dry run)')}</button><button class="btn" data-site="reject" data-id="${p.id}" ${busy ? 'disabled' : ''}>Reject</button></div></div>`;
    }).join('') : '<div class="empty">No pages waiting.</div>') + (S.enabled ? '' : '<div class="small dim">Publishing is off, so approvals are paused.</div>');
    $('#siteHistory', el).innerHTML = `<h3>Published history</h3>` + (S.history.length ? S.history.map((h) => `<div class="act"><span class="ico">${!h.ok ? '⚠️' : h.mode === 'live' ? '✅' : '🧪'}</span><span class="x2"><b>${h.ok && h.mode === 'live' && safeUrl(h.url) ? `<a href="${esc(h.url)}" target="_blank" rel="noopener noreferrer">${esc(h.title)}</a>` : esc(h.title)}</b>
      <span class="dim">${h.ok ? (h.mode === 'live' ? 'published' : 'dry run') : esc(h.error || 'failed')}</span> ${h.commit_url && safeUrl(h.commit_url) ? `<a href="${esc(h.commit_url)}" target="_blank" rel="noopener noreferrer">commit</a>` : ''}</span><span class="small dim">${ago(h.ts)}</span></div>`).join('') : '<div class="empty">Nothing published yet.</div>');
  } },

  { id: 'gift', icon: '🎁', label: 'Leave him something', title: 'Leave him something', build(el, s) {
    el.innerHTML = `<p class="dim small" style="margin-top:0">Place something in his world. He will notice it and decide what to do about it.</p>
      <h3>What is it?</h3><div class="kinds"></div>
      <h3>Name it (optional)</h3><div class="field"><input id="giftName" type="text" maxlength="24" placeholder="e.g. Old Oak"></div>
      <h3>Color</h3><div class="swatches"></div>
      <button class="btn primary wide" id="giftGo" style="margin-top:16px">Place in the world…</button>`;
    el.querySelector('.kinds').innerHTML = (s?.kinds || Object.keys(KIND_ICON)).map((k) => `<button data-k="${k}" class="${k === gift.kind ? 'on' : ''}"><span>${KIND_ICON[k] || '✨'}</span>${k}</button>`).join('');
    el.querySelector('.swatches').innerHTML = SWATCH.map((c) => `<button data-c="${c}" style="background:${c}" class="${c === gift.color ? 'on' : ''}"></button>`).join('') + `<input type="color" id="giftColor" value="${gift.color}" title="Custom color">`;
    el.querySelector('.kinds').onclick = (e) => { const b = e.target.closest('button[data-k]'); if (!b) return; gift.kind = b.dataset.k; el.querySelectorAll('.kinds button').forEach((x) => x.classList.toggle('on', x === b)); };
    const setColor = (c) => { gift.color = c; el.querySelectorAll('.swatches button').forEach((x) => x.classList.toggle('on', x.dataset.c === c)); $('#giftColor', el).value = c; };
    el.querySelector('.swatches').onclick = (e) => { const b = e.target.closest('button[data-c]'); if (b) setColor(b.dataset.c); };
    $('#giftColor', el).oninput = (e) => { gift.color = e.target.value; el.querySelectorAll('.swatches button').forEach((x) => x.classList.remove('on')); };
    $('#giftGo', el).onclick = () => { api.startPlace({ kind: gift.kind, name: $('#giftName', el).value, color: gift.color }); $('#giftName', el).value = ''; closePanel(); toast('Click the ground to place it · Esc to cancel', 6000); };
  }, update() {} },

  { id: 'you', icon: '🕹️', label: 'You', title: 'You', build(el) {
    el.innerHTML = `<button class="btn primary wide" id="pauseBtn"></button>
      <h3>How fast he thinks</h3><input type="range" id="speed" min="3" max="60" step="1"><div class="small dim" id="speedLbl"></div>
      <h3>Web pages</h3><label class="switch"><input type="checkbox" id="pubChk"><span>Let him draft web pages.<br><span class="small dim">Pages he writes wait for your approval (see <b>My site</b>). Nothing goes online unless you approve it.</span></span></label>
      <div id="pending"></div>
      <h3>Emergency</h3><button class="btn danger wide" id="killBtn">Kill switch — stop ${short}</button>
      <p class="small dim">You can also press Ctrl-C in the terminal or create a file named KILL in the project folder. His state is saved.</p>`;
    $('#pauseBtn', el).onclick = () => api.send({ type: snap.state.paused ? 'resume' : 'pause' });
    const sp = $('#speed', el);
    sp.oninput = () => { draggingSpeed = true; $('#speedLbl', el).textContent = `Thinks every ${sp.value}s`; };
    sp.onchange = () => { draggingSpeed = false; api.send({ type: 'set_interval', seconds: +sp.value }); };
    $('#pubChk', el).onchange = (e) => api.send({ type: 'toggle_publish', on: e.target.checked });
    $('#killBtn', el).onclick = (e) => {
      if (!killArmed) { killArmed = true; e.target.textContent = 'Really stop him? Click again to confirm'; setTimeout(() => { killArmed = false; e.target.textContent = `Kill switch — stop ${short}`; }, 4000); return; }
      api.send({ type: 'kill' });
    };
    $('#pending', el).onclick = (e) => { const b = e.target.closest('button[data-a]'); if (b) api.send({ type: b.dataset.a, id: +b.dataset.id }); };
  }, update(el, s) {
    const p = s.state.paused;
    $('#pauseBtn', el).textContent = p ? `▶ Resume ${short}` : `⏸ Pause ${short}`;
    if (!draggingSpeed) { $('#speed', el).value = Math.round(s.interval); $('#speedLbl', el).textContent = `Thinks every ${Math.round(s.interval)}s`; }
    $('#pubChk', el).checked = s.state.publish_enabled;
    $('#pending', el).innerHTML = s.pages.length ? '<h3>Drafts awaiting approval</h3>' + s.pages.map((pg) => `<div class="card"><div class="t">${esc(pg.title)}</div><div class="small">${esc(pg.body)}…</div><div class="field"><button class="btn primary" data-a="approve_page" data-id="${pg.id}">${s.site.mode === 'live' ? 'Approve & publish' : 'Approve (dry run)'}</button><button class="btn" data-a="reject_page" data-id="${pg.id}">Reject</button></div></div>`).join('') : '';
  } },

  { id: 'more', icon: '⋯', label: 'More', title: 'Settings & raw log', build(el) {
    el.innerHTML = `<div id="about"></div>
      <h3>Camera & labels</h3><label class="switch"><input type="checkbox" id="followChk" checked><span>Follow ${short}</span></label>
      <div class="field"><span class="small dim">Labels</span><select id="labelMode"><option value="smart">nearby only (no overlaps)</option><option value="all">all</option><option value="off">off</option></select><button class="btn" id="camReset">Reset camera</button></div>
      <div id="balance"></div><div id="world"></div><div id="packs"></div>
      <h3>Raw log</h3><div class="field"><button class="btn" id="logBtn">Show full log</button><button class="btn" id="logRefresh" hidden>Refresh</button></div><div id="logBox" class="log" hidden></div>`;
    $('#followChk', el).onchange = (e) => api.setFollow(e.target.checked);
    $('#labelMode', el).onchange = (e) => api.setLabelMode(e.target.value);
    $('#camReset', el).onclick = () => api.resetCamera();
    $('#logBtn', el).onclick = () => { showLog = !showLog; if (showLog) api.send({ type: 'get_log', limit: 200 }); refresh(); };
    $('#logRefresh', el).onclick = () => api.send({ type: 'get_log', limit: 200 });
    el.addEventListener('click', (e) => { if (e.target.id === 'rescan') { api.send({ type: 'rescan_assets' }); toast('Scanning asset folders…'); } });
  }, update(el, s) {
    $('#about', el).innerHTML = `<div class="card"><div class="t">${esc(s.name)}</div><div class="meta">model: ${esc(s.model)} · tick ${s.state.tick} · day ${s.world.day}</div><div class="meta">Everything he thinks, does, reads and searches is stored in <b>data/sprocket.db</b>.</div></div>`;
    const B = s.balance, kv = (o) => Object.entries(o).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${Array.isArray(v) ? v.join(' / ') : esc(v)}</td></tr>`).join('');
    $('#balance', el).innerHTML = `<h3>Energy balance <span class="dim" style="text-transform:none;letter-spacing:0">(edit in sprocket/config.py)</span></h3>
      <div class="card"><b>Run time at ${Math.round(B.tick_seconds)}s per tick</b><table class="kv">${Object.entries(B.estimates_minutes).map(([k, v]) => `<tr><td>${esc(k)}</td><td>~${v} min</td></tr>`).join('')}</table></div>
      <details><summary class="small">Rates (per tick)</summary><table class="kv">${kv(B.rates)}</table></details>
      <details><summary class="small">Recharging</summary><table class="kv">${kv(B.restore)}</table></details>
      <details><summary class="small">Thresholds</summary><table class="kv">${kv(B.thresholds)}</table></details>
      <details><summary class="small">Pacing (so he doesn't only build)</summary><table class="kv">${kv(B.pacing)}</table></details>`;
    $('#world', el).innerHTML = `<h3>World</h3><div class="card">Buildable area: <b>${Math.round(s.world_half * 2)} × ${Math.round(s.world_half * 2)}</b> · ${s.objects.length} objects<div class="meta">The engine places every new object, avoids overlaps, and grows the area when it gets crowded.</div></div>`
      + (s.blocked_sites.length ? `<h3>Sites that blocked him</h3>${s.blocked_sites.map((b) => `<div class="small">🚫 ${esc(b.host)} <span class="dim">${esc(b.reason)}</span></div>`).join('')}` : '');
    const need = s.packs.some((p) => p.attribution_required);
    $('#packs', el).innerHTML = `<h3>Asset library &amp; credits</h3><div class="card">${s.assets_total.u} usable of ${s.assets_total.n} models <button class="btn" id="rescan" style="float:right;padding:3px 10px">Rescan</button>
      <div class="meta">Drop packs into <b>assets/</b> (one folder each). Add a <b>credits.json</b> or LICENSE.txt per pack to record its license. Models are treated as data only.</div></div>`
      + s.packs.map((p) => `<div class="card"><div class="t">${esc(p.pack)} <span class="chip">${p.usable}/${p.n} models</span></div>
        <div class="meta">License: <b>${esc(p.license)}</b>${p.attribution_required ? ' · <b>attribution required</b>' : ''}${p.credit ? `<br>Credit: ${esc(p.credit)}` : ''}${p.source ? `<br>Source: ${esc(p.source)}` : ''}</div>
        ${p.license === 'unknown' ? `<div class="small" style="color:#a0521c">⚠ ${esc(p.notes)}</div>` : ''}</div>`).join('')
      + (need ? '<div class="small">Some packs need attribution; keep the credit lines above when sharing screenshots or builds.</div>' : '');
    $('#logBtn', el).textContent = showLog ? 'Hide log' : 'Show full log';
    $('#logRefresh', el).hidden = !showLog;
    const box = $('#logBox', el); box.hidden = !showLog;
    if (showLog && logRows) { const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 40 || !box.firstChild; box.innerHTML = logRows.map((r) => `<div><span class="k">t${r.tick} ${esc(r.kind)}</span>${esc(r.text)}</div>`).join(''); if (atEnd) box.scrollTop = 1e9; }
  } },
];

// ------------------------------------------------------------------ chrome
function refresh() { if (!snap) return; const p = PANELS.find((x) => x.id === openId); if (p) { const body = $('#panelBody'); const st = body.scrollTop; p.update(body.querySelector('.pbody') || body, snap); body.scrollTop = st; } }
function openPanel(id) {
  openId = id; killArmed = false;
  const p = PANELS.find((x) => x.id === id);
  $('#panelTitle').textContent = p.title;
  const body = $('#panelBody'); body.innerHTML = '<div class="pbody"></div>'; p.build(body.firstChild, snap); $('#panel').hidden = false;
  document.querySelectorAll('.mb').forEach((b) => b.classList.toggle('on', b.dataset.id === id));
  refresh();
}
export function closePanel() { openId = null; $('#panel').hidden = true; document.querySelectorAll('.mb').forEach((b) => b.classList.remove('on')); }
export function toast(msg, ms = 3500) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(t._t); t._t = setTimeout(() => { t.hidden = true; }, ms); }

function openArt(id) {
  const a = art.meta.get(id); if (!a) return;
  const th = art.thumbs.get(id) || (a.kind === 'sculpture' ? api.thumbArt(id) : null);
  $('#lbBody').innerHTML = `${th ? `<img class="${a.mode === 'pixel' ? 'px' : ''}" alt="${esc(a.title)}" src="${th}">` : '<div style="font-size:80px;text-align:center">🗿</div>'}
    <h2 style="margin:4px 0">${esc(a.title)}</h2><div class="small dim">${esc(a.kind)} · ${ago(a.ts)}</div>
    ${a.statement ? `<p>“${esc(a.statement)}”</p>` : ''}${a.inspiration ? `<p class="small dim">Inspired by ${esc(a.inspiration)}</p>` : ''}
    <div>${(a.colors || []).map((c) => `<span class="sw" style="background:${esc(c)}"></span>`).join('')}</div>${a.kind === 'sculpture' ? '<p class="small dim">This sculpture stands in the world, in front of the gallery.</p>' : ''}`;
  $('#lightbox').hidden = false;
}

export function init(a) {
  api = a; art = a.art;
  $('#menu').innerHTML = PANELS.map((p) => `<button class="mb" data-id="${p.id}" aria-label="${esc(p.label)}"><span class="lbl">${esc(p.label)}</span><span class="ic">${p.icon}</span></button>`).join('');
  $('#menu').onclick = (e) => { const b = e.target.closest('.mb'); if (!b) return; openId === b.dataset.id ? closePanel() : openPanel(b.dataset.id); };
  $('#panelClose').onclick = closePanel;
  $('#lbClose').onclick = () => { $('#lightbox').hidden = true; };
  $('#lightbox').onclick = (e) => { if (e.target.id === 'lightbox') $('#lightbox').hidden = true; };
  $('#meters').innerHTML = [['energy', '⚡', 'Energy', '#4fa8d8', true], ['battery', '🔋', 'Battery', '#7cb36a', true], ['creativity', '🎨', 'Creativity', '#c77dd1', true], ['boredom', '🥱', 'Boredom', '#e8a13a', false]]
    .map(([k, i, n, c, good]) => `<div class="m" data-k="${k}" data-good="${good}" title="${n}" style="--c:${c}">${i}<i><b style="width:0"></b></i></div>`).join('');
  addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!$('#lightbox').hidden) $('#lightbox').hidden = true; else if (document.body.classList.contains('placing')) api.cancelPlace(); else closePanel();
  });
  setInterval(() => document.querySelectorAll('[data-ts]').forEach((el) => { el.textContent = rel(+el.dataset.ts); }), 15000);
  art.onChange(() => refresh());
}

export function update(s) {
  const first = !snap; snap = s; skew = s.server_time - Date.now() / 1000;
  $('#name').textContent = s.name; short = s.short_name || short; document.title = `${s.name}'s World`;
  const m = s.state.mood;
  $('#moodEmoji').textContent = MOOD[m] || '🤖'; $('#moodChip').textContent = m + (s.state.inside ? ` · inside the ${s.places[s.state.inside].label}` : '');
  document.querySelectorAll('.m').forEach((el) => {
    const k = el.dataset.k, v = s.state[k], good = el.dataset.good === 'true';
    el.querySelector('b').style.width = Math.max(2, v) + '%'; el.title = `${el.title.split(' ')[0]} ${Math.round(v)}/100`;
    el.classList.toggle('low', good ? v < 25 : v > 80);
  });
  if (s.state.paused) setCaption('⏸', `Paused — ${short} is resting until you resume.`, true);
  else if (first && s.state.last_say) setCaption('💭', s.state.last_say);
  refresh();
}

function setCaption(icon, text, force) {
  if (!force && !text) return;
  $('#capIcon').textContent = icon; const t = $('#capText'); t.textContent = text; t.title = text;
  if (!force) lastCaption = text;
}
export function onAction(a) {
  if (!a.tool && !a.say) return;
  const text = a.say || a.result || '';
  setCaption(TOOL_ICON[a.tool] || '💭', text);
}
export function setClock(c) { $('#clockIcon').textContent = ({ dawn: '🌅', day: '☀️', dusk: '🌇', night: '🌙' })[c.phase]; $('#clockText').textContent = `${c.label} · Day ${c.day}`; }
export function setConn(ok, msg) { const c = $('#conn'); c.hidden = ok; if (!ok) c.textContent = msg; }
export function setLog(rows) { logRows = rows; refresh(); }
export function placed() { toast('Placed! He will notice it soon.', 2500); }

let _rt = null;
export function refreshSoon() { clearTimeout(_rt); _rt = setTimeout(() => { if (openId) refresh(); }, 200); }
