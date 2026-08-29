"""The mission-control single-page UI (pure HTML/CSS/JS, no external assets).

The page polls the JSON API every few seconds and renders:

* a live equity curve (canvas, neon gradient),
* broker venue cards with mode pills (demo / live / blocked),
* the peer-AI council panel with a deliberate box,
* the mistake-lesson feed from the learning loop,
* a trade ticket (dry-run by default) and the kill switch.

No external assets, no CDN, no build step — everything ships inline.
"""

from __future__ import annotations

_CSS = """
:root {
  --bg: #05060f;
  --panel: rgba(16, 20, 40, 0.55);
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
}
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -2;
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(108, 92, 231, 0.28), transparent 60%),
    radial-gradient(900px 500px at 90% 0%, rgba(0, 229, 255, 0.16), transparent 55%),
    radial-gradient(800px 600px at 50% 110%, rgba(255, 92, 122, 0.12), transparent 60%),
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
  background-image: linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 42px 42px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%);
  mask-image: radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%);
}
header { display: flex; align-items: center; gap: 18px; padding: 22px 34px 14px; }
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
main { display: grid; gap: 18px; padding: 10px 34px 40px; grid-template-columns: repeat(12, 1fr); }
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
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-radius: 12px; margin-bottom: 8px;
  background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);
}
.venue .name { font-weight: 600; letter-spacing: 1px; }
.venue .mode { font-size: 10px; text-transform: uppercase; letter-spacing: 2px; }
.venue .mode.demo { color: var(--good); }
.venue .mode.live { color: var(--bad); }
.venue .mode.blocked { color: var(--muted); }
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
.log { font-family: Consolas, monospace; font-size: 12px; color: var(--muted); max-height: 140px; overflow-y: auto; }
.log div { padding: 3px 0; border-bottom: 1px dashed rgba(255,255,255,0.06); }
.statusline { color: var(--muted); font-size: 11px; letter-spacing: 1px; margin-top: 8px; }
.gauge { display: flex; gap: 14px; margin-top: 10px; }
.gauge .g { flex: 1; text-align: center; padding: 10px 6px; border-radius: 12px;
            background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); }
.gauge .v { font-size: 20px; font-weight: 700; }
.gauge .k { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; }
"""

_PAGE_BODY = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ORION — Mission Control</title>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="logo"></div>
  <div>
    <h1>ORION · Mission Control</h1>
    <div class="sub">autonomous financial intelligence — observe · decide · execute · learn</div>
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

  <section class="card span8">
    <h2>Broker venues (.env-discovered)</h2>
    <div id="venues" class="row">loading…</div>
  </section>

  <section class="card">
    <h2>Trade ticket</h2>
    <div class="row" style="gap:8px">
      <div class="field"><label>Symbol</label><input id="t-symbol" value="BTCUSDT" size="9"></div>
      <div class="field"><label>Side</label>
        <select id="t-side"><option>BUY</option><option>SELL</option></select></div>
      <div class="field"><label>Qty</label><input id="t-qty" value="0.01" size="6"></div>
      <div class="field"><label>Venue</label><select id="t-venue"><option value="">auto</option></select></div>
    </div>
    <div class="row" style="margin-top:12px">
      <label style="display:flex;gap:6px;align-items:center;text-transform:none;letter-spacing:0">
        <input type="checkbox" id="t-dry" checked style="width:auto"> dry-run
      </label>
      <button class="btn" id="btn-trade" style="margin-left:auto">Route order</button>
    </div>
    <div class="statusline">demo endpoints are default; live requires full unlock</div>
  </section>

  <section class="card span8">
    <h2>Peer-AI council</h2>
    <div class="row" style="margin-bottom:10px">
      <input id="p-q" placeholder="Ask every configured AI peer…" style="flex:1">
      <button class="btn" id="btn-ask">Deliberate</button>
    </div>
    <div id="peers" class="row">no peers configured — add API keys to .env</div>
    <div id="insights"></div>
  </section>

  <section class="card span4">
    <h2>Lessons learned</h2>
    <div id="lessons">no lessons yet — reflect on a trade below</div>
  </section>

  <section class="card span8">
    <h2>Reflect on a trade (learning loop)</h2>
    <div class="row" style="gap:8px">
      <div class="field"><label>Symbol</label><input id="r-symbol" value="AAPL" size="7"></div>
      <div class="field"><label>Side</label><select id="r-side"><option>buy</option><option>sell</option></select></div>
      <div class="field"><label>Entry</label><input id="r-entry" value="100" size="7"></div>
      <div class="field"><label>Exit</label><input id="r-exit" value="97" size="7"></div>
      <div class="field"><label>Predicted %</label><input id="r-pred" value="0.03" size="7"></div>
      <div class="field"><label>Equity</label><input id="r-eq" value="100000" size="8"></div>
    </div>
    <div class="row" style="margin-top:12px">
      <button class="btn" id="btn-reflect">Feed to mistake analyzer</button>
    </div>
  </section>

  <section class="card span4">
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
  while (el.children.length > 40) el.removeChild(el.lastChild);
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

function refreshStatus() {
  api('/api/status').then((s) => {
    $('execmode').innerHTML = esc(s.execution_mode) + ' <small>/ ' + esc(s.mode) + '</small>';
    $('g-pos').textContent = (s.limits.max_position_fraction * 100).toFixed(0) + '%';
    $('g-exp').textContent = (s.limits.max_portfolio_exposure * 100).toFixed(0) + '%';
    $('g-loss').textContent = (s.limits.max_daily_loss_fraction * 100).toFixed(0) + '%';
    drawEquity(s.equity_history);
    const pills = ['mode: ' + s.execution_mode,
                   s.live_trading_enabled ? 'LIVE UNLOCKED' : 'live locked',
                   'autonomy L' + s.autonomy_level];
    $('pills').innerHTML = pills.map((p, i) =>
      '<span class="pill ' + (s.live_trading_enabled && i === 1 ? 'live' : 'demo') + '">' + esc(p) + '</span>').join('');
    $('statusline').textContent = 'connected · ' + new Date().toLocaleTimeString();
  }).catch((e) => { $('statusline').textContent = 'error: ' + e.message; });
}

function refreshBrokers() {
  api('/api/brokers').then((s) => {
    const venues = s.venues || [];
    const el = $('venues');
    if (!venues.length) {
      el.innerHTML = '<span class="statusline">no venues configured — add API keys to .env (see .env.example)</span>';
    } else {
      el.innerHTML = venues.map((v) =>
        '<div class="venue" style="flex:1;min-width:170px"><div>' +
        '<div class="name">' + esc(v.name) + '</div>' +
        '<div class="mode ' + esc(v.mode.split(' ')[0]) + '">' + esc(v.mode) + '</div>' +
        '<div class="statusline">' + esc(v.detail || '') + '</div></div>' +
        '<div class="statusline">' + (v.available ? '●' : '○') + '</div></div>').join('');
    }
    $('t-venue').innerHTML = '<option value="">auto</option>' +
      venues.map((v) => '<option value="' + esc(v.name.split(':')[0]) + '">' + esc(v.name.split(':')[0]) + '</option>').join('');
    $('ksline').textContent = 'kill switch: ' + (s.kill_switch.engaged ? 'ENGAGED (' + s.kill_switch.reason + ')' : 'open');
  }).catch((e) => logLine('brokers: ' + e.message));
}

function refreshPeers() {
  api('/api/peers').then((s) => {
    const el = $('peers');
    if (!s.available) {
      el.innerHTML = '<span class="statusline">no peers configured — add OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY to .env</span>';
    } else {
      el.innerHTML = s.peers.map((p) =>
        '<div class="venue" style="flex:1;min-width:150px"><div>' +
        '<div class="name">' + esc(p.name) + '</div>' +
        '<div class="mode demo">' + esc(p.available ? 'ready · ' + p.model : 'no key') + '</div></div></div>').join('');
    }
    $('insights').innerHTML = (s.insights || []).slice(-6).reverse().map((i) =>
      '<div class="insight"><div class="meta">' + esc(i.provider) + ' · ' + esc(i.model) +
      ' · conf ' + Number(i.confidence).toFixed(2) + '</div>' + esc(i.thesis) + '</div>').join('');
  }).catch((e) => logLine('peers: ' + e.message));
}

function refreshLessons() {
  api('/api/lessons').then((s) => {
    const recent = s.recent || [];
    $('lessons').innerHTML = recent.length
      ? recent.map((l) =>
          '<div class="lesson sev-' + esc(l.severity) + '"><div class="meta">' +
          esc(l.kind) + ' · ' + esc(l.symbol) + ' · ' + esc(l.severity) + '</div>' +
          esc(l.description) + '</div>').join('')
      : 'no lessons yet — reflect on a trade below';
  }).catch((e) => logLine('lessons: ' + e.message));
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
$('btn-trade').onclick = () => {
  const body = {
    symbol: $('t-symbol').value.trim(), side: $('t-side').value,
    quantity: parseFloat($('t-qty').value) || 0,
    venue: $('t-venue').value || null, dry_run: $('t-dry').checked,
  };
  api('/api/trade', body).then((r) => {
    logLine('order ' + r.status + ' on ' + r.venue + ' (' + r.mode + ')');
  }).catch((e) => logLine('trade: ' + e.message));
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
$('btn-reflect').onclick = () => {
  api('/api/reflect', {
    symbol: $('r-symbol').value.trim(), side: $('r-side').value,
    entry_price: parseFloat($('r-entry').value) || 0,
    exit_price: parseFloat($('r-exit').value) || 0,
    predicted_return: parseFloat($('r-pred').value) || 0,
    equity: parseFloat($('r-eq').value) || 0,
    mode: 'simulation',
  }).then((r) => {
    (r.lessons || []).forEach((l) => logLine('lesson [' + l.kind + '] ' + l.symbol));
    refreshLessons();
  }).catch((e) => logLine('reflect: ' + e.message));
};

refreshStatus(); refreshBrokers(); refreshPeers(); refreshLessons();
setInterval(refreshStatus, 3000);
setInterval(refreshBrokers, 8000);
setInterval(refreshPeers, 10000);
setInterval(refreshLessons, 8000);
"""


def render_page() -> str:
    """Render the single-page dashboard (CSS/JS inlined, no external assets)."""
    return _PAGE_BODY.replace("__CSS__", _CSS).replace("__JS__", _JS)