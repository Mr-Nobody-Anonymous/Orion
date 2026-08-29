"""Mission Control P4-1 (the "cool" unified UI).

A richer single-page dashboard that consolidates every wired-in
ORION capability behind the same :class:`DashboardState`:

* a live equity curve + regime gauge,
* a per-venue broker grid (catalogue + missing-keys + health +
  kill switch + live registry state),
* a peer-AI council panel (deliberation form, recent insights,
  per-peer status with last error),
* a unified mistake-lesson timeline (per-kind counts, per-symbol
  bias, recent bias window),
* an immutable strategy registry view (lineage tree, version
  history, lifecycle pill),
* an experiment log (rolling window of tracked runs),
* the LocalModelRouter decision and hardware snapshot.

The page is stdlib-only HTML/JS, no CDN, no build. The JS uses
``fetch`` against the existing JSON API and renders via DOM
manipulation so refreshes don't require a page reload.
"""

from __future__ import annotations

_CSS = """
:root {
  --bg: #05060f;
  --panel: rgba(16, 20, 40, 0.55);
  --panel-strong: rgba(20, 24, 50, 0.75);
  --panel-border: rgba(120, 140, 255, 0.18);
  --text: #dbe4ff;
  --muted: #8b93b8;
  --accent: #6c5ce7;
  --accent2: #00e5ff;
  --good: #2ecc9a;
  --bad: #ff5c7a;
  --warn: #ffb454;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', Inter, system-ui, sans-serif;
  color: var(--text);
  background: var(--bg);
  overflow-x: hidden;
  min-height: 100vh;
  margin: 0;
  padding: 0;
}
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -2;
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(108, 92, 231, 0.30), transparent 60%),
    radial-gradient(900px 500px at 90% 0%, rgba(0, 229, 255, 0.18), transparent 55%),
    radial-gradient(800px 600px at 50% 110%, rgba(255, 92, 122, 0.14), transparent 60%),
    var(--bg);
  animation: drift 22s ease-in-out infinite alternate;
}
@keyframes drift {
  from { filter: hue-rotate(0deg) saturate(1); }
  to   { filter: hue-rotate(18deg) saturate(1.15); }
}
body::after {
  content: '';
  position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 42px 42px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%);
  mask-image: radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%);
}
header {
  display: flex; align-items: center; gap: 18px;
  padding: 22px 34px 14px;
}
.logo {
  width: 44px; height: 44px; border-radius: 12px;
  background: conic-gradient(from 180deg, var(--accent), var(--accent2), var(--accent));
  box-shadow: 0 0 24px rgba(108, 92, 231, 0.65), inset 0 0 12px rgba(0,0,0,0.4);
  position: relative;
}
.logo::after {
  content: ''; position: absolute; inset: 10px; border-radius: 50%;
  background: var(--bg); box-shadow: inset 0 0 8px rgba(0,229,255,0.8);
}
h1 {
  font-size: 20px; letter-spacing: 4px; font-weight: 700; text-transform: uppercase;
  background: linear-gradient(90deg, #fff, var(--accent2), var(--accent));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.sub { color: var(--muted); font-size: 12px; letter-spacing: 1px; }
.pillbar { margin-left: auto; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.pill {
  font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
  padding: 6px 12px; border-radius: 999px;
  border: 1px solid var(--panel-border); color: var(--muted);
  background: rgba(255,255,255,0.02);
}
.pill.live { color: var(--bad); border-color: rgba(255,92,122,0.5); box-shadow: 0 0 12px rgba(255,92,122,0.25); }
.pill.demo { color: var(--good); border-color: rgba(46,204,154,0.4); }
.pill.warn { color: var(--warn); border-color: rgba(255,180,84,0.4); }
.pill.ready { color: var(--accent2); border-color: rgba(0,229,255,0.45); }
main {
  display: grid; gap: 18px; padding: 10px 34px 40px;
  grid-template-columns: repeat(12, 1fr);
}
.card {
  grid-column: span 4;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  padding: 18px 20px;
  backdrop-filter: blur(14px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
  transition: transform .2s ease, box-shadow .2s ease;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(108,92,231,0.18); }
.card.span8 { grid-column: span 8; }
.card.span12 { grid-column: span 12; }
.card h2 {
  font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--muted); margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.card h2::before {
  content: ''; width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent2); box-shadow: 0 0 10px var(--accent2);
}
.big { font-size: 30px; font-weight: 700; letter-spacing: 1px; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.venue {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px 12px; border-radius: 12px;
  background: var(--panel-strong); border: 1px solid var(--panel-border);
  flex: 1; min-width: 150px;
}
.venue .name { font-weight: 600; letter-spacing: 1px; font-size: 13px; }
.venue .mode { font-size: 10px; text-transform: uppercase; letter-spacing: 2px; }
.venue .mode.demo { color: var(--good); }
.venue .mode.live { color: var(--bad); }
.venue .mode.blocked { color: var(--muted); }
.venue .detail { color: var(--muted); font-size: 10px; }
.venue .health { font-size: 10px; }
.venue .health.ok { color: var(--good); }
.venue .health.bad { color: var(--bad); }
.venue .health.unknown { color: var(--muted); }
.btn {
  cursor: pointer; border: 1px solid var(--panel-border);
  background: linear-gradient(180deg, rgba(108,92,231,0.25), rgba(108,92,231,0.08));
  color: var(--text); padding: 9px 16px; border-radius: 10px;
  font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase;
  transition: all .15s ease;
}
.btn:hover { box-shadow: 0 0 18px rgba(108,92,231,0.55); transform: translateY(-1px); }
.btn.danger { background: linear-gradient(180deg, rgba(255,92,122,0.3), rgba(255,92,122,0.08)); border-color: rgba(255,92,122,0.5); }
.btn.good { background: linear-gradient(180deg, rgba(46,204,154,0.3), rgba(46,204,154,0.08)); border-color: rgba(46,204,154,0.5); }
input, select {
  background: rgba(0,0,0,0.35); color: var(--text);
  border: 1px solid var(--panel-border); border-radius: 10px;
  padding: 9px 12px; font-size: 13px; outline: none; min-width: 0;
}
input:focus, select:focus { border-color: var(--accent2); box-shadow: 0 0 10px rgba(0,229,255,0.25); }
label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.lesson {
  padding: 10px 12px; border-left: 3px solid var(--warn);
  background: rgba(255,180,84,0.06); border-radius: 0 10px 10px 0;
  margin-bottom: 8px; font-size: 13px;
}
.lesson .meta { color: var(--muted); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 3px; }
.lesson.sev-high { border-left-color: var(--bad); background: rgba(255,92,122,0.06); }
.lesson.sev-low { border-left-color: var(--good); background: rgba(46,204,154,0.05); }
.insight {
  padding: 10px 12px; border-left: 3px solid var(--accent2);
  background: rgba(0,229,255,0.05); border-radius: 0 10px 10px 0; margin-bottom: 8px; font-size: 13px;
}
.insight .meta { color: var(--muted); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 3px; }
canvas { width: 100%; height: 180px; display: block; }
.statusline { color: var(--muted); font-size: 11px; letter-spacing: 1px; margin-top: 8px; }
.gauge { display: flex; gap: 14px; margin-top: 10px; }
.gauge .g { flex: 1; text-align: center; padding: 10px 6px; border-radius: 12px;
            background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); }
.gauge .v { font-size: 20px; font-weight: 700; }
.gauge .k { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; }
.log { font-family: Consolas, monospace; font-size: 12px; color: var(--muted); max-height: 200px; overflow-y: auto; }
.log div { padding: 3px 0; border-bottom: 1px dashed rgba(255,255,255,0.06); }
.lineage {
  font-family: Consolas, monospace; font-size: 12px;
  padding: 10px 12px; background: rgba(0,0,0,0.25);
  border-radius: 10px; color: var(--muted); line-height: 1.6;
}
.lineage .arrow { color: var(--accent2); margin: 0 6px; }
.lineage .key { color: var(--accent2); }
.lineage .hash { color: var(--good); }
.status-pulse {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: var(--good); margin-right: 6px;
  animation: pulse 1.5s ease-in-out infinite;
}
.status-pulse.bad { background: var(--bad); }
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px currentColor; }
  50% { opacity: 0.4; box-shadow: 0 0 2px currentColor; }
}
.pill.hot { color: var(--warn); border-color: rgba(255,180,84,0.5); }
.timeline-bar {
  display: flex; gap: 2px; height: 16px; border-radius: 4px; overflow: hidden;
  margin-top: 6px;
}
.timeline-bar span {
  display: block; height: 100%;
}
"""

_BODY = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ORION · Mission Control P4-1</title>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="logo"></div>
  <div>
    <h1>ORION · Mission Control</h1>
    <div class="sub">unified surface — observe · trade · learn · reflect</div>
  </div>
  <div class="pillbar" id="pills"></div>
</header>
<main>
  <section class="card span8">
    <h2>Equity curve (session)</h2>
    <canvas id="equity" width="900" height="200"></canvas>
    <div class="statusline" id="statusline">connecting…</div>
  </section>
  <section class="card">
    <h2>Risk posture</h2>
    <div class="big" id="execmode">—</div>
    <div class="gauge">
      <div class="g"><div class="v" id="g-pos">—</div><div class="k">max pos</div></div>
      <div class="g"><div class="v" id="g-exp">—</div><div class="k">max exposure</div></div>
      <div class="g"><div class="v" id="g-loss">—</div><div class="k">max daily loss</div></div>
    </div>
    <div style="margin-top:14px" class="row">
      <button class="btn danger" id="btn-engage">Engage kill switch</button>
      <button class="btn good" id="btn-disengage">Disengage</button>
    </div>
    <div class="statusline" id="ksline">kill switch: —</div>
  </section>

  <section class="card span12">
    <h2>Broker venues (catalogue · live · kill switch)</h2>
    <div id="brokers-grid" class="row">loading…</div>
  </section>

  <section class="card span8">
    <h2>Peer-AI council</h2>
    <div class="row" style="margin-bottom:10px">
      <input id="p-q" placeholder="Ask every configured AI peer…" style="flex:1">
      <button class="btn" id="btn-ask">Deliberate</button>
    </div>
    <div id="peers-strip" class="row">no peers configured — add API keys to .env</div>
    <div id="insights" style="margin-top:10px"></div>
  </section>

  <section class="card span4">
    <h2>Lessons (mistake timeline)</h2>
    <div id="lessons-summary" class="statusline">—</div>
    <div id="lessons-timeline"></div>
    <div id="lessons-list" style="margin-top:10px"></div>
  </section>

  <section class="card span8">
    <h2>Strategy registry (lineage)</h2>
    <div id="strategies" class="log">no strategies registered</div>
  </section>

  <section class="card span4">
    <h2>Experiments</h2>
    <div id="experiments" class="log">no experiments</div>
  </section>

  <section class="card span4">
    <h2>Model router</h2>
    <div class="row" style="gap:6px;margin-bottom:8px">
      <div class="field"><label>complexity</label>
        <select id="m-complexity">
          <option>cheap</option><option selected>standard</option><option>deep</option>
        </select>
      </div>
      <div class="field"><label>context tokens</label>
        <input id="m-context" type="number" value="0" size="6">
      </div>
    </div>
    <button class="btn" id="btn-model">Select model</button>
    <div id="model-result" class="statusline">—</div>
  </section>

  <section class="card span8">
    <h2>Activity log</h2>
    <div class="log" id="log"><div>booting…</div></div>
  </section>
</main>
<script>__JS__</script>
</body>
</html>
"""

_JS = """
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function logLine(msg) {
  const el = $('log');
  const div = document.createElement('div');
  div.textContent = new Date().toLocaleTimeString() + '  ' + msg;
  el.prepend(div);
  while (el.children.length > 60) el.removeChild(el.lastChild);
}

async function api(path, body) {
  const opts = body
    ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
    : {};
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function drawEquity(series) {
  const canvas = $('equity');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!series || series.length < 2) return;
  const min = Math.min(...series), max = Math.max(...series);
  const pad = (max - min) * 0.1 || 1;
  const lo = min - pad, hi = max + pad;
  const x = (i) => (i / (series.length - 1)) * (w - 20) + 10;
  const y = (v) => h - 14 - ((v - lo) / (hi - lo)) * (h - 28);
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, 'rgba(108,92,231,0.45)');
  grad.addColorStop(1, 'rgba(108,92,231,0.0)');
  ctx.beginPath();
  ctx.moveTo(x(0), y(series[0]));
  series.forEach((v, i) => ctx.lineTo(x(i), y(v)));
  ctx.lineTo(x(series.length - 1), h); ctx.lineTo(x(0), h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x(0), y(series[0]));
  series.forEach((v, i) => ctx.lineTo(x(i), y(v)));
  ctx.strokeStyle = '#00e5ff'; ctx.lineWidth = 2;
  ctx.shadowColor = '#00e5ff'; ctx.shadowBlur = 8;
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function renderStatus(s) {
  $('execmode').innerHTML = esc(s.execution_mode) + ' <small>/ ' + esc(s.mode) + '</small>';
  $('g-pos').textContent = (s.limits.max_position_fraction * 100).toFixed(0) + '%';
  $('g-exp').textContent = (s.limits.max_portfolio_exposure * 100).toFixed(0) + '%';
  $('g-loss').textContent = (s.limits.max_daily_loss_fraction * 100).toFixed(0) + '%';
  drawEquity(s.equity_history || []);
  const pills = [
    '<span class="pill ' + (s.live_trading_enabled ? 'live' : 'demo') + '">' + (s.live_trading_enabled ? 'LIVE UNLOCKED' : 'live locked') + '</span>',
    '<span class="pill">L' + esc(s.autonomy_level) + '</span>',
    '<span class="pill demo">mode ' + esc(s.execution_mode) + '</span>',
  ];
  $('pills').innerHTML = pills.join('');
  $('statusline').textContent = 'connected · ' + new Date().toLocaleTimeString();
}

function renderBrokers(b) {
  const liveVenues = b.venues || [];
  const liveMap = Object.fromEntries(liveVenues.map(v => [v.name, v]));
  const catalogue = (b.catalogue && b.catalogue.venues) || [];
  const missing = b.missing_keys || {};
  const ks = b.kill_switch || {};
  const ksPill = ks.engaged
    ? '<span class="pill live"><span class="status-pulse bad"></span>KILL SWITCH ENGAGED</span>'
    : '<span class="pill demo"><span class="status-pulse"></span>kill switch open</span>';
  $('pills').insertAdjacentHTML('beforeend', ' ' + ksPill);
  $('ksline').textContent = 'kill switch: ' + (ks.engaged ? 'ENGAGED (' + (ks.reason || '') + ')' : 'open');
  $('brokers-grid').innerHTML = catalogue.map((v) => {
    const live = liveMap[v.venue];
    const mode = live ? live.mode : 'not configured';
    const modeClass = mode.split(' ')[0];
    const detail = live ? (live.detail || '') : (missing[v.venue] ? 'missing: ' + missing[v.venue].join(', ') : '');
    const health = (b.health || []).find(h => h.venue === v.venue);
    const healthHtml = health
      ? '<div class="health ' + (health.ok ? 'ok' : 'bad') + '">' + (health.ok ? '● ping ok' : '○ ' + (health.detail || 'unreachable')) + '</div>'
      : '<div class="health unknown">○ health not probed</div>';
    return '<div class="venue">' +
      '<div class="name">' + esc(v.venue) + ' <span class="detail">(' + esc(v.adapter) + ')</span></div>' +
      '<div class="mode ' + esc(modeClass) + '">' + esc(mode) + '</div>' +
      '<div class="detail">' + esc(detail) + '</div>' +
      healthHtml +
      '</div>';
  }).join('') || '<span class="statusline">no catalogue available</span>';
}

function renderPeers(p) {
  const peers = p.peers || [];
  if (!peers.length) {
    $('peers-strip').innerHTML = '<span class="statusline">no peers configured — add OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY to .env</span>';
  } else {
    $('peers-strip').innerHTML = peers.map((peer) => {
      const status = peer.available ? 'ready' : 'no key';
      const dotClass = peer.available ? 'ok' : 'bad';
      const error = peer.last_error ? '<div class="statusline">err: ' + esc(peer.last_error.substring(0, 60)) + '</div>' : '';
      return '<div class="venue" style="min-width:140px">' +
        '<div class="name">' + esc(peer.provider) + '</div>' +
        '<div class="mode demo">' + esc(peer.model) + '</div>' +
        '<div class="health ' + dotClass + '">' + (peer.available ? '● ' : '○ ') + esc(status) + '</div>' +
        error +
        '</div>';
    }).join('');
  }
  $('insights').innerHTML = (p.insights || []).slice(-6).reverse().map((i) =>
    '<div class="insight"><div class="meta">' + esc(i.provider) + ' · ' + esc(i.model) +
    ' · conf ' + Number(i.confidence).toFixed(2) + '</div>' + esc(i.thesis) + '</div>'
  ).join('');
}

function renderLessons(payload) {
  const counts = payload.counts || {};
  const analysis = payload.analysis || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) {
    $('lessons-summary').textContent = 'no lessons yet';
    $('lessons-timeline').innerHTML = '';
    $('lessons-list').innerHTML = '';
    return;
  }
  $('lessons-summary').textContent = total + ' lessons · ' + (analysis.all_time && analysis.all_time.by_symbol ? Object.keys(analysis.all_time.by_symbol).length : 0) + ' symbols';
  // Timeline bars
  const kinds = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...kinds.map(k => k[1]));
  $('lessons-timeline').innerHTML = '<div class="timeline-bar">' +
    kinds.map(([kind, count]) => {
      const pct = (count / max) * 100;
      const color = kind === 'prediction_miss' ? 'var(--accent2)' : kind === 'oversized' ? 'var(--bad)' : kind === 'discipline' ? 'var(--warn)' : 'var(--good)';
      return '<span style="width:' + pct.toFixed(1) + '%;background:' + color + '" title="' + esc(kind) + ': ' + count + '"></span>';
    }).join('') + '</div>';
  $('lessons-list').innerHTML = (payload.recent || []).slice(0, 5).map((l) =>
    '<div class="lesson sev-' + esc(l.severity) + '"><div class="meta">' +
    esc(l.kind) + ' · ' + esc(l.symbol) + ' · ' + esc(l.severity) + '</div>' +
    esc(l.description) + '</div>'
  ).join('');
}

function renderStrategies(payload) {
  const strategies = payload.strategies || [];
  if (!strategies.length) {
    $('strategies').innerHTML = '<div>no strategies registered</div>';
    return;
  }
  $('strategies').innerHTML = strategies.map((s) => {
    const line = s.lineage || {};
    return '<div class="lineage">' +
      '<span class="key">' + esc(s.name) + '</span> · v' + esc(s.latest.version) + ' · <span class="hash">' + esc(s.latest.version_hash) + '</span> · ' + esc(s.latest.status) + '<br>' +
      '<span class="key">dataset</span> ' + esc(line.dataset || '—') +
      '<span class="arrow">→</span><span class="key">features</span> ' + esc(line.features || '—') +
      '<span class="arrow">→</span><span class="key">model</span> ' + esc(line.model || '—') +
      '<span class="arrow">→</span><span class="key">strategy</span> v' + esc(s.latest.version) +
      '<br><span class="key">backtest</span> ' + esc(s.latest.backtest_ref || '—') +
      ' · <span class="key">walk-forward</span> ' + esc(s.latest.walk_forward_ref || '—') +
      '</div>';
  }).join('');
}

function renderExperiments(payload) {
  const recent = payload.recent || [];
  $('experiments').innerHTML = recent.length
    ? recent.slice(-15).reverse().map((e) =>
        '<div>[' + esc(e.status) + '] ' + esc(e.experiment_id.substring(0, 12)) + ' · ' + esc(e.name) +
        (e.metrics && Object.keys(e.metrics).length ? ' · ' + Object.entries(e.metrics).map(([k, v]) => esc(k) + '=' + esc(v.toFixed(3))).join(', ') : '') +
        '</div>'
      ).join('')
    : '<div>no experiments tracked</div>';
}

async function refreshStatus() {
  try { renderStatus(await api('/api/status')); } catch (e) { $('statusline').textContent = 'error: ' + e.message; }
}
async function refreshBrokers() {
  try { renderBrokers(await api('/api/brokers')); } catch (e) { logLine('brokers: ' + e.message); }
}
async function refreshPeers() {
  try { renderPeers(await api('/api/peers')); } catch (e) { logLine('peers: ' + e.message); }
}
async function refreshLessons() {
  try { renderLessons(await api('/api/lessons')); } catch (e) { logLine('lessons: ' + e.message); }
}
async function refreshStrategies() {
  try { renderStrategies(await api('/api/strategies')); } catch (e) { logLine('strategies: ' + e.message); }
}
async function refreshExperiments() {
  try { renderExperiments(await api('/api/experiments')); } catch (e) { logLine('experiments: ' + e.message); }
}

$('btn-engage').onclick = () => {
  api('/api/killswitch', {engaged: true, reason: 'operator (web)'}).then(() => {
    logLine('kill switch ENGAGED'); refreshBrokers();
  }).catch((e) => logLine('killswitch: ' + e.message));
};
$('btn-disengage').onclick = () => {
  api('/api/killswitch', {engaged: false}).then(() => {
    logLine('kill switch disengaged'); refreshBrokers();
  }).catch((e) => logLine('killswitch: ' + e.message));
};
$('btn-ask').onclick = () => {
  const q = $('p-q').value.trim();
  if (!q) return;
  logLine('consulting peers…');
  api('/api/deliberate', {question: q}).then((r) => {
    logLine('peers answered: ' + (r.insights || []).length +
            ' · failures: ' + (r.failures || []).length);
    refreshPeers();
  }).catch((e) => logLine('deliberate: ' + e.message));
};
$('btn-model').onclick = () => {
  api('/api/select-model', {
    complexity: $('m-complexity').value,
    context_tokens: parseInt($('m-context').value || '0', 10),
  }).then((r) => {
    $('model-result').innerHTML = '→ <span class="health ok">' + esc(r.tier.model) + '</span> · ctx=' + r.tier.context_window + ' · reason: ' + esc(r.tier.reason);
  }).catch((e) => logLine('model: ' + e.message));
};

refreshStatus(); refreshBrokers(); refreshPeers(); refreshLessons();
refreshStrategies(); refreshExperiments();
setInterval(refreshStatus, 3000);
setInterval(refreshBrokers, 6000);
setInterval(refreshPeers, 10000);
setInterval(refreshLessons, 8000);
setInterval(refreshStrategies, 12000);
setInterval(refreshExperiments, 12000);
"""


def render_p4_page() -> str:
    """Render the P4-1 unified mission-control page."""
    return _BODY.replace("__CSS__", _CSS).replace("__JS__", _JS)
