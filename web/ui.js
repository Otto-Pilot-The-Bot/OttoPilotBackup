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
let armedGift = 0;
let confirmLive = false;
let A = { data: null, tab: 'models', q: '', pack: '', page: 0, sel: null, pf: null, kitDesigns: {}, asked: false, count: -1 }, armedObj = 0;
let wishBanner = null, fulfilId = 0, assetFilter = '', pickedAsset = '';
let thingsTab = 'world', browseFilter = 'all', draggingSpeed = false, killArmed = false, logRows = null, showLog = false;
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
    el.innerHTML = s.journal.length ? s.journal.map((j) => { const th = j.obj_id ? api.thumb(j.obj_id) : null; return `<article class="note k-${esc(j.kind)}"><header>${ago(j.ts)}<span class="chip">${({ entry: 'journal', reflection: 'reflection', learning: 'learned', art: 'art', build: 'built', review: 'looking back' })[j.kind] || esc(j.kind)}</span><span title="${esc(j.mood)}">${MOOD[j.mood] || ''}</span></header><div class="row">${th ? `<img class="thumb" alt="" src="${th}">` : ''}<p>${esc(j.text)}</p></div></article>`; }).join('')
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
      ${s.interests.length ? `<h3>Interests</h3><div class="chips">${s.interests.map((i) => `<span class="chip" style="opacity:${Math.min(1, 0.45 + i.strength / 5)};font-weight:${i.strength >= 3 ? 700 : 500}" title="strength ${i.strength}">${esc(i.topic)} ${'●'.repeat(Math.min(5, Math.max(1, Math.round(i.strength))))}</span>`).join('')}</div>` : ''}
      ${s.mix && s.mix.n ? `<h3>Lately</h3>${Object.entries(s.mix.counts).sort((a, b) => b[1] - a[1]).map(([c, n]) => `<div class="mixrow"><span>${esc(c)}</span><i><b style="width:${Math.round(100 * n / s.mix.n)}%"></b></i><span class="small dim">${n}</span></div>`).join('')}` : ''}
      ${s.hobbies && s.hobbies.length ? `<h3>Logs &amp; series he keeps</h3>${s.hobbies.map((h) => `<div class="card"><div class="t">📒 ${esc(h.name)} <span class="chip">${h.n} ${h.n === 1 ? 'entry' : 'entries'}</span></div>${h.entries[0] ? `<div class="small dim">${esc(h.entries[0].text)}</div>` : ''}</div>`).join('')}` : ''}
      <h3>Recent actions</h3>${s.recent.map((r) => `<div class="act"><span class="ico">${TOOL_ICON[r.tool] || '•'}</span><span class="x2" title="${esc(r.result)}"><b>${esc(TOOL_LABEL[r.tool] || r.tool)}</b> ${esc(r.args)} <span class="dim">${esc(r.result)}</span></span><span class="small dim">${ago(r.ts)}</span></div>`).join('')}`;
  } },

  { id: 'things', icon: '🌍', label: 'In his world', title: 'In his world', build(el) {
    el.innerHTML = `<div class="tabs"></div><div class="tb"></div>`;
    el.querySelector('.tabs').onclick = (e) => { const b = e.target.closest('button[data-t]'); if (b) { thingsTab = b.dataset.t; refresh(); } };
    el.querySelector('.tb').onclick = (e) => { const b = e.target.closest('[data-art]'); if (b) openArt(+b.dataset.art); const t = e.target.closest('[data-tune]'); if (t) playTune(snap.tunes.find((x) => x.id === +t.dataset.tune)); const oe = e.target.closest('[data-oe]'); if (oe) { const id = +oe.dataset.id, k = oe.dataset.oe;
        if (k === 'move') { api.startPlace({ move: true, id }); closePanel(); toast('Click the ground to move it · Esc to cancel', 5000); }
        else if (k === 'rot') api.send({ type: 'object_rotate', id, deg: -45 }); else if (k === 'rotr') api.send({ type: 'object_rotate', id, deg: 45 });
        else if (k === 'smaller') api.send({ type: 'object_scale', id, factor: 0.9 }); else if (k === 'bigger') api.send({ type: 'object_scale', id, factor: 1.1 });
        else if (k === 'rm') { if (armedObj === id) { api.send({ type: 'object_remove', id }); armedObj = 0; } else { armedObj = id; setTimeout(() => { armedObj = 0; refresh(); }, 4000); refresh(); } } }
      const d = e.target.closest('[data-gdel]'); if (d) { const id = +d.dataset.gdel; if (armedGift === id) { api.send({ type: 'delete_gift', id }); armedGift = 0; } else { armedGift = id; setTimeout(() => { armedGift = 0; refresh(); }, 4000); } refresh(); } };
  }, update(el, s) {
    const tabs = [['world', '🌍 In his world'], ['gifts', '🎁 Gifts'], ['gallery', '🖼️ Gallery'], ...(s.building_enabled ? [['built', '🔧 Built']] : []), ['sounds', '🎵 Sounds'], ['collect', '🐚 Collection'], ['logs', '📒 Logs'], ['wear', '🎩 Wardrobe'], ['sketch', '✏️ Sketchbook']];
    el.querySelector('.tabs').innerHTML = tabs.map(([k, l]) => `<button data-t="${k}" class="${k === thingsTab ? 'on' : ''}">${l}</button>`).join('');
    const tb = el.querySelector('.tb');
    if (thingsTab === 'world') {
      const mine = (s.objects || []).filter((o) => o.source === 'user' || o.source === 'gift');
      tb.innerHTML = mine.length ? mine.map((o) => { const w = o.meta && o.meta.wish_id, th = o.kind === 'gift_picture' ? `/gift/${o.meta.gift_id}/file` : api.thumb(o.id);
        return `<div class="card row">${th ? `<img class="thumb" alt="" src="${th}">` : '<div class="thumb" style="display:grid;place-items:center;font-size:28px">📦</div>'}<div><div class="t">${esc(o.name)}</div>
          <div class="chips" style="margin-top:3px"><span class="chip">${w ? '💫 granted wish' : o.source === 'gift' ? '🎁 gift' : 'placed by you'}</span><span class="chip">${esc(o.kind.replace('gift_', ''))}</span></div>
          <div class="field" style="gap:4px;margin:6px 0 0;flex-wrap:wrap"><button class="btn ob" data-oe="move" data-id="${o.id}">Move…</button>${o.meta && o.meta.design ? `<button class="btn ob" data-oe="rot" data-id="${o.id}" title="rotate">⟲</button><button class="btn ob" data-oe="rotr" data-id="${o.id}" title="rotate">⟳</button><button class="btn ob" data-oe="smaller" data-id="${o.id}">−</button><button class="btn ob" data-oe="bigger" data-id="${o.id}">+</button>` : ''}<button class="btn ob" data-oe="rm" data-id="${o.id}">${armedObj === o.id ? 'Really remove?' : 'Remove'}</button></div></div></div>`; }).join('')
        : '<div class="empty">Nothing yet. Place something with “Leave him something”, give him a gift, or grant a wish.</div>';
    } else if (thingsTab === 'gallery') {
      const list = s.art.filter((a) => a.status !== 'broken');
      tb.innerHTML = list.length ? `<div class="grid">${list.map((a) => {
        const th = art.thumbs.get(a.id) || (a.kind === 'sculpture' ? api.thumbArt(a.id) : null);
        return `<button class="art-card" data-art="${a.id}"><div class="pic">${th ? `<img class="${a.mode === 'pixel' ? 'px' : ''}" alt="" src="${th}">` : a.kind === 'sculpture' ? '🗿' : '…'}</div><div class="cap">${esc(a.title)}</div><div class="small dim">${esc(a.kind)} · ${ago(a.ts)}</div></button>`;
      }).join('')}</div>` : '<div class="empty">No art yet. He may start when he feels creative.</div>';
    } else if (thingsTab === 'built') {
      tb.innerHTML = s.built.length ? s.built.map((b) => { const th = b.obj_id ? api.thumb(b.obj_id) : null; return `<div class="card row">${th ? `<img class="thumb" alt="" src="${th}">` : `<span class="sw" style="background:${esc(b.color || '#ccc')}"></span>`}<div><div class="t">${esc(b.name)}</div><div class="meta">${esc(b.description || '')} · ${ago(b.ts)}</div>${b.reason ? `<div class="small">Why: ${esc(b.reason)}</div>` : ''}${b.review ? `<div class="small dim">Looking back: ${esc(b.review)}</div>` : ''}</div></div>`; }).join('')
        : '<div class="empty">He has not finished a build yet.</div>';
      if (s.designs && s.designs.length) tb.innerHTML += `<h3>Designs he scripted &amp; saved</h3>` + s.designs.map((d) => `<div class="card"><div class="t">📐 ${esc(d.name)} <span class="chip">reused ${d.uses}×</span></div><details><summary class="small">Show his script</summary><pre class="log" style="max-height:160px">${esc(d.script)}</pre></details><div class="meta">${ago(d.ts)}</div></div>`).join('');
    } else if (thingsTab === 'gifts') {
      tb.innerHTML = s.gifts && s.gifts.length ? s.gifts.map((g) => `<div class="card row">${g.kind === 'picture' ? `<img class="thumb" alt="" src="/gift/${g.id}/file">` : '<div class="thumb" style="display:grid;place-items:center;font-size:30px">🧊</div>'}<div style="flex:1;min-width:0"><div class="t">${esc(g.name)} <span class="chip">${esc(({ new: 'waiting for ' + short, placed: 'in the world', displayed: 'on display', kept: 'kept safe' })[g.status] || g.status)}</span></div>
        <div class="meta">${g.kind === 'picture' ? `picture ${g.w}×${g.h}` : `3D model · ${Number(g.tris).toLocaleString()} triangles`} · from ${esc(g.giver)} · ${ago(g.ts)}</div>
        ${g.note ? `<div class="small">“${esc(g.note)}”</div>` : ''}${g.reaction ? `<div class="small dim">${esc(short)}: ${esc(g.reaction)}</div>` : ''}
        <button class="btn" style="padding:2px 10px;font-size:11px;margin-top:4px" data-gdel="${g.id}">${armedGift === g.id ? 'Really remove (deletes the file)?' : 'Remove'}</button></div></div>`).join('')
        : '<div class="empty">No gifts yet. Use “Leave him something” to give him a picture or a 3D model.</div>';
    } else if (thingsTab === 'sounds') {
      tb.innerHTML = s.tunes && s.tunes.length ? s.tunes.map((t) => `<div class="card"><div class="t">🎵 ${esc(t.title)} <button class="btn" style="float:right;padding:2px 10px" data-tune="${t.id}">▶ Play</button></div><div class="meta">${t.tempo} bpm · ${esc(t.wave)} · ${ago(t.ts)}</div><div class="small dim" style="word-break:break-word">${esc(t.notes)}</div></div>`).join('')
        : '<div class="empty">No tunes yet.</div>';
    } else if (thingsTab === 'collect') {
      tb.innerHTML = s.collection && s.collection.length ? `<div class="chips">${s.collection.map((c) => `<span class="chip" title="found in the ${esc(c.place)}"><span class="sw" style="background:${esc(c.color || '#ccc')};margin-right:4px"></span>${esc(c.item)}</span>`).join('')}</div>` : '<div class="empty">He has not collected anything yet. Small things turn up around the world.</div>';
    } else if (thingsTab === 'logs') {
      tb.innerHTML = s.hobbies && s.hobbies.length ? s.hobbies.map((h) => `<div class="card"><div class="t">📒 ${esc(h.name)} <span class="chip">${h.n}</span></div>${h.entries.map((e) => `<div class="small" style="margin-top:3px">${esc(e.text)} <span class="dim">${ago(e.ts)}</span></div>`).join('')}</div>`).join('') : '<div class="empty">No logs yet. He starts them when he spots, collects or composes things.</div>';
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

  { id: 'wishes', icon: '💫', label: 'Wishlist', title: 'Wishlist', build(el) {
    el.innerHTML = `<div id="wBanner"></div><p class="dim small" style="margin-top:0">Things he would like in his world. You decide: fulfil with a model from the library, say "not now", or hide the card.</p><div id="wOpen"></div><div id="wHist"></div>`;
    const opts = (s) => (s.assets_pick || []).filter((a) => !assetFilter || (a.name + ' ' + a.pack).toLowerCase().includes(assetFilter.toLowerCase())).slice(0, 80)
      .map((a) => `<option value="${a.id}" ${String(a.id) === String(pickedAsset) ? 'selected' : ''}>${esc(a.name)} · ${esc(a.pack)}</option>`).join('');
    el.addEventListener('input', (e) => { if (e.target.id === 'wFilter') { assetFilter = e.target.value; $('#wAsset', el).innerHTML = opts(snap); } });
    el.addEventListener('change', (e) => { if (e.target.id === 'wAsset') pickedAsset = e.target.value; });
    el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-w]'); if (!b) return; const a = b.dataset.w, id = +b.dataset.id;
      if (a === 'open') { fulfilId = id; const w = snap.wishes.find((x) => x.id === id); pickedAsset = w && w.asset_id ? String(w.asset_id) : ''; assetFilter = ''; refresh(true); }
      else if (a === 'cancel') { fulfilId = 0; refresh(true); }
      else if (a === 'decline' || a === 'hide') { api.send({ type: 'wish_' + a, id }); if (fulfilId === id) fulfilId = 0; }
      else if (a === 'place' || a === 'click') {
        const asset = $('#wAsset', el)?.value || pickedAsset; if (!asset) { wishBanner = { text: 'Choose a model from the list first.', ok: false, ts: Date.now() / 1000 }; refresh(true); return; }
        if (a === 'place') { api.send({ type: 'wish_fulfil', id, asset: +asset, zone: $('#wZone', el).value || undefined }); fulfilId = 0; }
        else { api.startPlace({ wish: true, id, asset: +asset }); closePanel(); toast('Click the ground to place it for him · Esc to cancel', 6000); }
      }
    });
    el._opts = opts;
  }, update(el, s) {
    const b = wishBanner && Date.now() / 1000 + skew - wishBanner.ts < 300 ? wishBanner : null;
    $('#wBanner', el).innerHTML = b ? `<div class="card" style="background:${b.ok ? '#e4f1dc' : '#f6d7cf'};border-color:${b.ok ? '#b6d6a4' : '#e3a89b'}">${b.ok ? '✅' : '⚠️'} ${esc(b.text)}</div>` : '';
    if (fulfilId && el.contains(document.activeElement) && /INPUT|SELECT/.test(document.activeElement.tagName)) return;     // do not disturb a form being filled in
    const open = (s.wishes || []).filter((w) => w.status === 'open'), done = (s.wishes || []).filter((w) => w.status !== 'open');
    $('#wOpen', el).innerHTML = `<h3>Open wishes</h3>` + (open.length ? open.map((w) => `<div class="card"><div class="t">${esc(w.item)}</div><div class="small">${esc(w.reason)}</div>
        <div class="meta">${ago(w.ts)}${w.interest ? ` · <span class="chip">${esc(w.interest)}</span>` : ''}${w.asset_name ? ` · suggests <span class="chip">${esc(w.asset_name)}</span>` : ''}</div>
        ${fulfilId === w.id ? `<div class="card" style="background:#fff8e8;margin-top:8px"><div class="small"><b>Choose a model</b></div><div class="field"><input type="text" id="wFilter" placeholder="search the library…" value="${esc(assetFilter)}"></div>
          <select id="wAsset" size="6" style="width:100%">${el._opts(s)}</select><div class="small" style="margin-top:6px"><b>Where?</b></div>
          <select id="wZone" style="width:100%"><option value="">Let the engine choose a fitting spot</option>${(s.zones || []).map((z) => `<option value="${z.key}">${esc(z.label)}</option>`).join('')}</select>
          <div class="field"><button class="btn primary" data-w="place" data-id="${w.id}">Place it</button><button class="btn" data-w="click" data-id="${w.id}">Click on the ground…</button><button class="btn" data-w="cancel" data-id="${w.id}">Cancel</button></div></div>`
          : `<div class="field"><button class="btn primary" data-w="open" data-id="${w.id}">Fulfil…</button><button class="btn" data-w="decline" data-id="${w.id}">Not now</button><button class="btn" data-w="hide" data-id="${w.id}">Hide</button></div>`}</div>`).join('')
      : '<div class="empty">No open wishes. He asks when something would make sense for his interests.</div>');
    $('#wHist', el).innerHTML = done.length ? `<h3>Answered</h3>` + done.map((w) => `<div class="act"><span class="ico">${w.status === 'granted' ? '✅' : '🕊️'}</span><span class="x2"><b>${esc(w.item)}</b> <span class="dim">${w.status === 'granted' ? 'granted' : 'not now'}${w.asset_name ? ' · ' + esc(w.asset_name) : ''}</span></span><span class="small dim">${ago(w.resolved_ts || w.ts)}</span><button class="btn" style="padding:0 8px;font-size:11px" data-w="hide" data-id="${w.id}">Hide</button></div>`).join('') : '';
  } },

  { id: 'assets', icon: '🧰', label: 'Assets', title: 'Asset library (yours)', build(el) {
    if (!A.asked || A.count !== (snap.assets_total || {}).n) { A.asked = true; A.count = (snap.assets_total || {}).n; api.send({ type: 'get_assets' }); }
    el.innerHTML = '<div id="aBody"></div>';
    const send = (kind) => {
      const pf = A.pf, base = { src: A.sel.src, asset: A.sel.id, gen: A.sel.gen, params: pf.params, name: pf.name, scale: pf.scale, rot: pf.rot, color: pf.tint ? pf.color : undefined, zone: pf.zone || undefined, exact: pf.exact, snap: pf.snap };
      if (kind === 'place') { api.send({ type: 'place_design', ...base }); } else { api.startPlace({ design: true, payload: base }); closePanel(); toast('Click the ground to place it · Esc to cancel', 6000); }
    };
    el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-a]'); if (!b) return; const a = b.dataset.a;
      if (a === 'tab') { A.tab = b.dataset.t; A.page = 0; A.sel = null; }
      else if (a === 'page') A.page = Math.max(0, A.page + +b.dataset.d);
      else if (a === 'pick') { const src = b.dataset.src, key = b.dataset.key; A.sel = src === 'kit' ? { src, gen: key } : { src, id: +key };
        const row = src === 'asset' ? A.data.rows.find((r) => r.id === +key) : null, spec = src === 'kit' ? A.data.kit[key] : [];
        A.pf = { name: row ? row.name : key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()), scale: 1, rot: 0, tint: false, color: '#c4604b', zone: '', exact: false, snap: '', params: Object.fromEntries((spec || []).map((p) => [p.name, p.default])) };
        if (src === 'kit') api.send({ type: 'design_preview', gen: key, params: A.pf.params, key: 'form' }); }
      else if (a === 'back' || a === 'cancel') A.sel = null;
      else if (a === 'place' || a === 'click') { send(a); if (a === 'place') A.sel = null; }
      render(el, snap);
    });
    const onChange = (e) => {
      const t = e.target, f = A.pf; if (!t.dataset) return;
      if (t.id === 'aQ') { A.q = t.value; A.page = 0; return render(el, snap, true); }
      if (t.id === 'aPack') { A.pack = t.value; A.page = 0; return render(el, snap); }
      if (!f) return;
      if (t.dataset.f) f[t.dataset.f] = t.type === 'checkbox' ? t.checked : (t.type === 'range' || t.dataset.num ? +t.value : t.value);
      if (t.dataset.p) { const sp = A.data.kit[A.sel.gen].find((x) => x.name === t.dataset.p); f.params[t.dataset.p] = t.type === 'checkbox' ? t.checked : (sp.kind === 'num' || sp.kind === 'int') ? +t.value : t.value;
        clearTimeout(A._t); A._t = setTimeout(() => api.send({ type: 'design_preview', gen: A.sel.gen, params: f.params, key: 'form' }), 350); }
      if (t.type === 'range') { const o = t.parentElement.querySelector('output'); if (o) o.textContent = t.value; }
    };
    el.addEventListener('input', (e) => { if (e.target.id === 'aQ') onChange(e); else if (e.target.type === 'range') onChange(e); });
    el.addEventListener('change', onChange);
    el._render = () => render(el, snap);
    function render(el, s, keepFocus) {
      if (!A.data) { $('#aBody', el).innerHTML = '<div class="empty">Loading the library…</div>'; return; }
      const host = $('#aBody', el);
      if (A.sel) return renderForm(host);
      const q = A.q.toLowerCase(), isKit = A.tab === 'kit';
      const rows = isKit ? Object.keys(A.data.kit).map((g) => ({ gen: g })) : A.data.rows.filter((r) => (!A.pack || r.pack === A.pack) && (!q || (r.name + ' ' + r.tags.join(' ') + ' ' + r.pack).toLowerCase().includes(q)));
      const per = 12, pages = Math.max(1, Math.ceil(rows.length / per)); A.page = Math.min(A.page, pages - 1);
      const view = rows.slice(A.page * per, A.page * per + per), packs = [...new Set(A.data.rows.map((r) => r.pack))];
      const prev = keepFocus ? document.activeElement : null, val = prev && prev.id === 'aQ' ? prev.selectionStart : null;
      host.innerHTML = `<div class="tabs"><button data-a="tab" data-t="models" class="${!isKit ? 'on' : ''}">🗂️ Model packs (${A.data.rows.length})</button><button data-a="tab" data-t="kit" class="${isKit ? 'on' : ''}">🏠 Buildings &amp; props</button></div>
        ${isKit ? '<p class="dim small" style="margin-top:0">Adjustable buildings, trees, lamps, ponds, cars… Pick one, tweak it, place it.</p>' : `<div class="field"><input type="text" id="aQ" placeholder="search ${A.data.rows.length} models…" value="${esc(A.q)}"><select id="aPack"><option value="">all packs</option>${packs.map((p) => `<option ${p === A.pack ? 'selected' : ''}>${esc(p)}</option>`).join('')}</select></div>`}
        <div class="grid">${view.map((r) => { const key = isKit ? r.gen : r.id, d = isKit ? A.kitDesigns['k:' + r.gen] : { parts: [{ a: r.id, f: r.fit, x: 0, y: 0, z: 0, s: 1, r: [0, 0, 0] }], scale: 1, rot: 0 };
          const th = d ? api.thumbDesign((isKit ? 'k:' : 'a:') + key, d, isKit ? r.gen : r.name) : null; if (isKit && !d && !A.kitDesigns['asked:' + r.gen]) { A.kitDesigns['asked:' + r.gen] = 1; api.send({ type: 'design_preview', gen: r.gen, params: {}, key: 'k:' + r.gen }); }
          return `<button class="art-card" data-a="pick" data-src="${isKit ? 'kit' : 'asset'}" data-key="${key}"><div class="pic">${th ? `<img alt="" src="${th}">` : '⏳'}</div><div class="cap">${esc(isKit ? r.gen.replace(/_/g, ' ') : r.name)}</div>
            <div class="small dim">${isKit ? 'adjustable' : `${(Math.max(r.sx, r.sz) * r.fit).toFixed(1)}×${(r.sy * r.fit).toFixed(1)} · ${esc(r.tags.slice(0, 2).join(', '))}`}</div></button>`; }).join('') || '<div class="empty">Nothing matches.</div>'}</div>
        <div class="field" style="justify-content:center"><button class="btn" data-a="page" data-d="-1" ${A.page ? '' : 'disabled'}>‹</button><span class="small dim">page ${A.page + 1} / ${pages}</span><button class="btn" data-a="page" data-d="1" ${A.page < pages - 1 ? '' : 'disabled'}>›</button></div>`;
      if (prev && prev.id === 'aQ') { const n = $('#aQ', el); n.focus(); n.setSelectionRange(val, val); }
    }
    function renderForm(host) {
      const f = A.pf, kit = A.sel.src === 'kit', spec = kit ? A.data.kit[A.sel.gen] : [], key = kit ? 'kitform' : null;
      const row = !kit ? A.data.rows.find((r) => r.id === A.sel.id) : null;
      const th = kit ? A.kitDesigns.form && api.thumbDesign('form:' + JSON.stringify(f.params), A.kitDesigns.form, f.name) : api.thumbDesign('a:' + A.sel.id, { parts: [{ a: row.id, f: row.fit, x: 0, y: 0, z: 0, s: 1, r: [0, 0, 0] }], scale: 1, rot: 0 }, row.name);
      const ctl = (p) => p.kind === 'num' || p.kind === 'int' ? `<label class="rng"><span>${esc(p.name.replace(/_/g, ' '))}</span><input type="range" data-p="${p.name}" min="${p.min}" max="${p.max}" step="${p.kind === 'int' ? 1 : 0.1}" value="${f.params[p.name]}"><output>${f.params[p.name]}</output></label>`
        : p.kind === 'choice' ? `<label class="rng"><span>${esc(p.name.replace(/_/g, ' '))}</span><select data-p="${p.name}">${p.options.map((o) => `<option ${o === f.params[p.name] ? 'selected' : ''}>${o}</option>`).join('')}</select></label>`
        : p.kind === 'color' ? `<label class="rng"><span>${esc(p.name.replace(/_/g, ' '))}</span><input type="color" data-p="${p.name}" value="${f.params[p.name]}"></label>`
        : p.kind === 'bool' ? `<label class="rng"><span>${esc(p.name.replace(/_/g, ' '))}</span><input type="checkbox" data-p="${p.name}" ${f.params[p.name] ? 'checked' : ''}></label>`
        : `<label class="rng"><span>${esc(p.name)}</span><input type="text" data-p="${p.name}" value="${esc(f.params[p.name] ?? '')}" maxlength="40"></label>`;
      host.innerHTML = `<button class="btn" data-a="back">← Back to the library</button>
        <div class="row" style="margin-top:10px"><img class="thumb" id="pvThumb" style="width:110px" alt="" ${th ? `src="${th}"` : ''}><div style="flex:1"><div class="field"><input type="text" data-f="name" value="${esc(f.name)}" maxlength="30"></div>
          ${row ? `<div class="small dim">${esc(row.pack)} · ${row.tris.toLocaleString()} triangles · ${row.tags.map(esc).join(', ')}</div>` : '<div class="small dim">adjustable kit item</div>'}</div></div>
        ${kit ? `<h3>Options</h3>${spec.filter((p) => p.name !== 'seed').map(ctl).join('')}` : ''}
        <h3>Placement</h3>
        <label class="rng"><span>scale</span><input type="range" data-f="scale" min="0.4" max="3" step="0.05" value="${f.scale}"><output>${f.scale}</output></label>
        <label class="rng"><span>rotation °</span><input type="range" data-f="rot" min="0" max="355" step="5" value="${f.rot}"><output>${f.rot}</output></label>
        <label class="rng"><span>tint</span><input type="checkbox" data-f="tint" ${f.tint ? 'checked' : ''}><input type="color" data-f="color" value="${f.color}"></label>
        <label class="rng"><span>where</span><select data-f="zone"><option value="">engine chooses a fitting spot</option>${A.data.zones.map((z) => `<option value="${z.key}" ${z.key === f.zone ? 'selected' : ''}>${esc(z.label)}</option>`).join('')}</select></label>
        <label class="rng"><span>exact spot</span><input type="checkbox" data-f="exact" ${f.exact ? 'checked' : ''}><span class="small dim">allow touching others (for assembling pieces)</span></label>
        <label class="rng"><span>snap to grid</span><select data-f="snap"><option value="">off</option>${['0.5', '1', '2'].map((v) => `<option ${v === f.snap ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
        <div class="field"><button class="btn primary" data-a="place">Place it</button><button class="btn" data-a="click">Click on the ground…</button><button class="btn" data-a="cancel">Cancel</button></div>
        <div class="small dim">“Place it” uses the zone above (or lets the engine choose). “Click on the ground” puts it exactly where you click.</div>`;
    }
  }, update(el, s) {
    if (A.count !== (s.assets_total || {}).n) { A.count = (s.assets_total || {}).n; api.send({ type: 'get_assets' }); }
    if (A.sel) { const im = $('#pvThumb', el); if (im && !im.getAttribute('src')) el._render && el._render(); return; }
    el._render && el._render();
  } },

  { id: 'gift', icon: '🎁', label: 'Leave him something', title: 'Leave him something', build(el, s) {
    el.innerHTML = `<p class="dim small" style="margin-top:0">Place something in his world. He will notice it and decide what to do about it.</p>
      <h3>What is it?</h3><div class="kinds"></div>
      <h3>Name it (optional)</h3><div class="field"><input id="giftName" type="text" maxlength="24" placeholder="e.g. Old Oak"></div>
      <h3>Color</h3><div class="swatches"></div>
      <button class="btn primary wide" id="giftGo" style="margin-top:16px">Place in the world…</button>`;
    const objHtml = el.innerHTML;
    el.innerHTML = `<div class="tabs"><button data-gt="obj" class="on">🌳 Objects</button><button data-gt="up">🖼️ Pictures &amp; 3D models</button></div><div id="objTab">${objHtml}</div>
      <div id="upTab" hidden><p class="dim small" style="margin-top:0">Give him your own picture or 3D model. He will notice it, look at it, and decide where it goes. Gifts stay private on this Mac and are never published.</p>
      <div id="drop" class="drop" tabindex="0">Drop a file here<br><span class="small dim">or click to choose · .png .jpg .webp (≤10 MB) · .glb (≤20 MB)</span></div>
      <input type="file" id="giftFile" accept=".png,.jpg,.jpeg,.webp,.glb" hidden><div id="picked" class="small" style="margin:6px 2px"></div>
      <h3>Name (optional)</h3><div class="field"><input id="gName" type="text" maxlength="40" placeholder="e.g. Sports car"></div>
      <h3>A note from you (optional)</h3><div class="field"><input id="gNote" type="text" maxlength="300" placeholder="I made this for you"></div>
      <button class="btn primary wide" id="gGo" style="margin-top:12px" disabled>Give it to him</button><div id="gMsg" class="small" style="margin-top:8px"></div></div>`;
    el.querySelector('.kinds').innerHTML = (s?.kinds || Object.keys(KIND_ICON)).map((k) => `<button data-k="${k}" class="${k === gift.kind ? 'on' : ''}"><span>${KIND_ICON[k] || '✨'}</span>${k}</button>`).join('');
    el.querySelector('.swatches').innerHTML = SWATCH.map((c) => `<button data-c="${c}" style="background:${c}" class="${c === gift.color ? 'on' : ''}"></button>`).join('') + `<input type="color" id="giftColor" value="${gift.color}" title="Custom color">`;
    el.querySelector('.kinds').onclick = (e) => { const b = e.target.closest('button[data-k]'); if (!b) return; gift.kind = b.dataset.k; el.querySelectorAll('.kinds button').forEach((x) => x.classList.toggle('on', x === b)); };
    const setColor = (c) => { gift.color = c; el.querySelectorAll('.swatches button').forEach((x) => x.classList.toggle('on', x.dataset.c === c)); $('#giftColor', el).value = c; };
    el.querySelector('.swatches').onclick = (e) => { const b = e.target.closest('button[data-c]'); if (b) setColor(b.dataset.c); };
    $('#giftColor', el).oninput = (e) => { gift.color = e.target.value; el.querySelectorAll('.swatches button').forEach((x) => x.classList.remove('on')); };
    let gf = null;
    const tabs = el.querySelector('.tabs');
    tabs.onclick = (e) => { const b = e.target.closest('button[data-gt]'); if (!b) return; tabs.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); $('#objTab', el).hidden = b.dataset.gt !== 'obj'; $('#upTab', el).hidden = b.dataset.gt !== 'up'; };
    const pick = (f) => {
      const msg = $('#gMsg', el); msg.textContent = ''; gf = null; $('#gGo', el).disabled = true;
      if (!f) return;
      if (!/\.(png|jpe?g|webp|glb)$/i.test(f.name)) { $('#picked', el).textContent = ''; msg.textContent = 'Only .png, .jpg/.jpeg, .webp pictures and .glb 3D models can be given.'; return; }
      const cap = /\.glb$/i.test(f.name) ? 20e6 : 10e6;
      if (f.size > cap) { msg.textContent = `That file is too big (${(f.size / 1e6).toFixed(1)} MB; limit ${cap / 1e6} MB).`; return; }
      gf = f; $('#picked', el).textContent = `📎 ${f.name} (${(f.size / 1e6).toFixed(2)} MB)`; $('#gGo', el).disabled = false;
    };
    const dz = $('#drop', el), inp = $('#giftFile', el);
    dz.onclick = () => inp.click(); inp.onchange = () => pick(inp.files[0]);
    dz.ondragover = (e) => { e.preventDefault(); dz.classList.add('over'); }; dz.ondragleave = () => dz.classList.remove('over');
    dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove('over'); pick(e.dataTransfer.files[0]); };
    $('#gGo', el).onclick = async () => {
      if (!gf) return; const msg = $('#gMsg', el); $('#gGo', el).disabled = true; msg.textContent = 'Sending…';
      const fd = new FormData(); fd.append('name', $('#gName', el).value); fd.append('note', $('#gNote', el).value); fd.append('file', gf);
      try {
        const r = await fetch('/gift', { method: 'POST', headers: { 'X-Gift-Upload': '1' }, body: fd }), j = await r.json();
        if (j.ok) { msg.textContent = `Given! ${short} will notice “${j.name}” soon.`; gf = null; $('#picked', el).textContent = ''; $('#gName', el).value = ''; $('#gNote', el).value = ''; inp.value = ''; }
        else { msg.textContent = '⚠️ ' + (j.error || 'That did not work.'); $('#gGo', el).disabled = false; }
      } catch (err) { msg.textContent = '⚠️ Could not reach the server.'; $('#gGo', el).disabled = false; }
    };
    $('#giftGo', el).onclick = () => { api.startPlace({ kind: gift.kind, name: $('#giftName', el).value, color: gift.color }); $('#giftName', el).value = ''; closePanel(); toast('Click the ground to place it · Esc to cancel', 6000); };
  }, update() {} },

  { id: 'you', icon: '🕹️', label: 'You', title: 'You', build(el) {
    el.innerHTML = `<button class="btn primary wide" id="pauseBtn"></button>
      <h3>How fast he thinks</h3><input type="range" id="speed" min="3" max="60" step="1"><div class="small dim" id="speedLbl"></div>
      <h3>Pace</h3><div class="tabs" id="paceBtns" style="margin-bottom:2px"></div><div class="small dim" id="paceNote"></div>
      <h3>Web pages</h3><label class="switch"><input type="checkbox" id="pubChk"><span>Let him draft web pages.<br><span class="small dim">Pages he writes wait for your approval (see <b>My site</b>). Nothing goes online unless you approve it.</span></span></label>
      <div id="pending"></div>
      <h3>Emergency</h3><button class="btn danger wide" id="killBtn">Kill switch — stop ${short}</button>
      <p class="small dim">You can also press Ctrl-C in the terminal or create a file named KILL in the project folder. His state is saved.</p>`;
    $('#pauseBtn', el).onclick = () => api.send({ type: snap.state.paused ? 'resume' : 'pause' });
    const sp = $('#speed', el);
    sp.oninput = () => { draggingSpeed = true; $('#speedLbl', el).textContent = `Thinks every ${sp.value}s`; };
    sp.onchange = () => { draggingSpeed = false; api.send({ type: 'set_interval', seconds: +sp.value }); };
    $('#pubChk', el).onchange = (e) => api.send({ type: 'toggle_publish', on: e.target.checked });
    $('#paceBtns', el).onclick = (e) => { const b = e.target.closest('button[data-pace]'); if (b) api.send({ type: 'set_pace', name: b.dataset.pace }); };
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
    $('#paceBtns', el).innerHTML = Object.entries(s.pace_presets || {}).map(([k, v]) => `<button data-pace="${k}" class="${s.state.pace === k ? 'on' : ''}">${({ calm: '🌿 Calm', normal: '🙂 Normal', lively: '⚡ Lively' })[k] || k} · ${v.interval}s</button>`).join('');
    $('#paceNote', el).textContent = `Thinking mode for decisions: ${s.think === 'False' ? 'off' : s.think}. Slower pace = longer actions and more quiet moments.`;
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
    const mm = s.memory || {};
    $('#world', el).innerHTML = `<h3>Memory</h3><div class="card"><div class="t">${mm.mode === 'embeddings' ? '🧠 Recall by meaning' : '⚠️ Simple recall'}</div><div class="meta">${esc(mm.note || '')}<br>${mm.embedded}/${mm.total} memories indexed</div></div><h3>World</h3><div class="card">Buildable area: <b>${Math.round(s.world_half * 2)} × ${Math.round(s.world_half * 2)}</b> · ${s.objects.length} objects<div class="meta">The engine places every new object, avoids overlaps, and grows the area when it gets crowded.</div></div>`
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
function refresh(force) { if (!snap) return; const p = PANELS.find((x) => x.id === openId); if (p) { const body = $('#panelBody'); const st = body.scrollTop; p.update(body.querySelector('.pbody') || body, snap); if (p.id === 'doing') postDoing(body, snap); body.scrollTop = st; } }
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

function postDoing(body, s) {
  if (!s.building_enabled) body.querySelectorAll('h3').forEach((h) => { if (h.textContent === 'Project in progress') { h.nextElementSibling && h.nextElementSibling.remove(); h.remove(); } });
  const wo = (s.wishes || []).filter((w) => w.status === 'open');
  if (wo.length) body.querySelector('.pbody, div').insertAdjacentHTML('beforeend', `<h3>Wishes he has made</h3>${wo.map((w) => `<div class="card"><div class="t">💫 ${esc(w.item)}</div><div class="meta">${esc(w.reason)}${w.interest ? ` · ${esc(w.interest)}` : ''}</div></div>`).join('')}`);
}

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
  const wxIcon = (w) => ({ clear: '☀️', 'clear and cold': '☀️', cloudy: '☁️', foggy: '🌫️', breezy: '🍃', 'falling leaves': '🍂', frosty: '❄️', 'light snow': '🌨️', snow: '❄️', thunderstorm: '⛈️' })[w] || (/rain|drizzle/.test(w || '') ? '🌧️' : '🌤️');
  $('#wx').textContent = `${wxIcon(s.weather)} ${s.weather} · ${s.season}`;
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
  const text = a.caption || a.say || a.result || '';
  setCaption(a.caption ? '📍' : (TOOL_ICON[a.tool] || '💭'), text);
}
export function setClock(c) { $('#clockIcon').textContent = ({ dawn: '🌅', day: '☀️', dusk: '🌇', night: '🌙' })[c.phase]; $('#clockText').textContent = `${c.label} · Day ${c.day}`; }
export function setConn(ok, msg) { const c = $('#conn'); c.hidden = ok; if (!ok) c.textContent = msg; }
export function setLog(rows) { logRows = rows; refresh(); }
export function placed() { toast('Placed! He will notice it soon.', 2500); }

let _rt = null;
export function refreshSoon() { clearTimeout(_rt); _rt = setTimeout(() => { if (openId) refresh(); }, 200); }

// ---- his tunes: simple oscillators, only when you press Play (browsers require a click)
let actx = null;
const SEMI = { C: -9, D: -7, E: -5, F: -4, G: -2, A: 0, B: 2 };
function freq(n) { const m = /^([A-G])([#b]?)(\d)$/.exec(n); if (!m) return 0; return 440 * 2 ** ((SEMI[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0) + (+m[3] - 4) * 12) / 12); }
export function playTune(t) {
  if (!t) return;
  actx = actx || new (window.AudioContext || window.webkitAudioContext)();
  const beat = 60 / (t.tempo || 100); let at = actx.currentTime + 0.05;
  for (const tok of String(t.notes).split(' ').slice(0, 48)) {
    const [n, d] = tok.split(':'); const dur = ({ w: 4, h: 2, q: 1, e: 0.5, s: 0.25 })[d || 'q'] * beat;
    if (n !== 'R' && freq(n)) {
      const o = actx.createOscillator(), g = actx.createGain(); o.type = t.wave === 'chime' ? 'sine' : t.wave; o.frequency.value = freq(n);
      g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(0.16, at + 0.02); g.gain.exponentialRampToValueAtTime(0.001, at + dur * 0.95);
      o.connect(g).connect(actx.destination); o.start(at); o.stop(at + dur);
      if (t.wave === 'chime') { const o2 = actx.createOscillator(), g2 = actx.createGain(); o2.frequency.value = freq(n) * 2.01; g2.gain.setValueAtTime(0.06, at); g2.gain.exponentialRampToValueAtTime(0.001, at + dur); o2.connect(g2).connect(actx.destination); o2.start(at); o2.stop(at + dur); }
    }
    at += dur;
  }
}

export function status(text) { setCaption('💭', `${short} is ${text}`, true); }

export function wishResult(m) { wishBanner = { text: m.text, ok: m.ok, ts: m.ts }; if (openId === 'wishes') refresh(true); }

export function assetsData(m) { A.data = m; if (openId === 'assets') { const b = $('#panelBody'); const el = b.querySelector('.pbody'); el && el._render && el._render(); } }
export function designPreview(m) { A.kitDesigns[m.key === 'form' ? 'form' : m.key] = m.design; if (openId === 'assets') { const el = $('#panelBody .pbody'); el && el._render && el._render(); } }
