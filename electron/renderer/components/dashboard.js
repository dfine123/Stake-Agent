'use strict';

window.DashboardComponent = (() => {
  // ── Session state ─────────────────────────────────────────────────────────
  // Single object; mutated in place and re-rendered on each event.
  const S = {
    status:          'idle',  // idle|starting|running|paused|stopping|ended
    currency:        '',
    persona:         '',
    dryRun:          false,
    startBalanceUsd: 0,
    currentBalUsd:   0,
    topTargetUsd:    0,
    secondaryUsd:    0,
    rate:            1,
    sessionPnlUsd:   0,
    bets:            0,
    wins:            0,
    losses:          0,
    endReason:       '',
  };

  // ── Pending feed row (the bet_placed entry waiting for bet_settled) ───────
  let _pendingRowId = null;
  let _unsubscribe  = null;  // engine event unsubscribe fn
  let _container    = null;  // root element (set once in mount)

  // ── Config helpers ────────────────────────────────────────────────────────

  async function _buildStartPayload() {
    const cfg   = window.SessionConfig.get();
    const token = await window.gambleAgent.keychain.get('stake_access_token');
    if (!token) throw new Error('Stake token not found in Keychain — check Credentials.');
    return window.SessionConfig.toEnginePayload(cfg, token);
  }

  // ── DOM helpers ───────────────────────────────────────────────────────────

  function _q(sel)        { return _container?.querySelector(sel); }
  function _setText(sel, t){ const el = _q(sel); if (el) el.textContent = t; }
  function _setHtml(sel, h){ const el = _q(sel); if (el) el.innerHTML   = h; }
  function _show(sel)      { const el = _q(sel); if (el) el.style.display = ''; }
  function _hide(sel)      { const el = _q(sel); if (el) el.style.display = 'none'; }

  function _fmt(n, dec = 2) {
    return isNaN(n) ? '—' : Number(n).toFixed(dec);
  }
  function _fmtPnl(n) {
    const v = Number(n);
    if (isNaN(v)) return '—';
    return (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2);
  }
  function _pnlClass(n) {
    return Number(n) >= 0 ? 'text-green' : 'text-red';
  }

  // ── Controls rendering ────────────────────────────────────────────────────

  function _renderControls() {
    const s = S.status;
    const goBtn     = _q('#db-go');
    const pauseBtn  = _q('#db-pause');
    const stopBtn   = _q('#db-stop');
    const panicBtn  = _q('#db-panic');
    const newBtn    = _q('#db-new-session');

    if (!goBtn) return;

    goBtn.style.display    = s === 'idle' || s === 'ended'  ? '' : 'none';
    newBtn.style.display   = s === 'ended'                  ? '' : 'none';
    pauseBtn.style.display = s === 'running' || s === 'paused' ? '' : 'none';
    stopBtn.style.display  = s === 'running' || s === 'paused' ? '' : 'none';
    panicBtn.style.display = s === 'running' || s === 'paused' || s === 'stopping' ? '' : 'none';

    goBtn.disabled    = s === 'starting';
    goBtn.textContent = s === 'starting' ? '⋯ Starting…' : '▶ GO';
    pauseBtn.textContent = s === 'paused' ? '▶ Resume' : '⏸ Pause';
    stopBtn.disabled  = s === 'stopping';

    // Nav badge
    const badge = document.getElementById('session-status-badge');
    if (badge) {
      const labels = { idle:'idle', starting:'starting', running:'live', paused:'paused', stopping:'stopping', ended:'ended' };
      badge.textContent = labels[s] ?? s;
    }

    // Engine status dot
    const statusMap = { idle:'', starting:'running', running:'running', paused:'running', stopping:'running', ended:'' };
    window.App?.setEngineStatus(statusMap[s] ?? '', s === 'running' ? 'engine running' : s === 'paused' ? 'paused' : 'engine idle');
  }

  // ── Stats sidebar ─────────────────────────────────────────────────────────

  function _renderStats() {
    // Balance
    const balUsd = S.currentBalUsd;
    _setText('#db-balance-usd', `$${_fmt(balUsd)}`);

    // P&L
    const pnlEl = _q('#db-pnl');
    if (pnlEl) {
      pnlEl.textContent = _fmtPnl(S.sessionPnlUsd);
      pnlEl.className   = _pnlClass(S.sessionPnlUsd);
    }

    // Bet counts
    _setText('#db-bet-count', S.bets);
    const wr = S.bets > 0 ? ((S.wins / S.bets) * 100).toFixed(0) : '—';
    _setText('#db-win-rate', S.bets > 0 ? `${wr}%` : '—');
    _setText('#db-wins',   S.wins);
    _setText('#db-losses', S.losses);

    // Progress bar
    const start = S.startBalanceUsd;
    const top   = S.topTargetUsd;
    const range = top - start;
    let pct = range > 0 ? Math.min(100, Math.max(0, ((balUsd - start) / range) * 100)) : 0;
    const bar = _q('#db-progress-fill');
    if (bar) bar.style.width = pct.toFixed(1) + '%';

    // Secondary marker
    const sec = S.secondaryUsd;
    const secPct = range > 0 ? Math.min(100, Math.max(0, ((sec - start) / range) * 100)) : 0;
    const marker = _q('#db-secondary-marker');
    if (marker) marker.style.left = secPct.toFixed(1) + '%';

    _setText('#db-target-label', `$${_fmt(balUsd)} / $${_fmt(top)}`);
    _setText('#db-secondary-label', `secondary: $${_fmt(sec)}`);
  }

  // ── Bet feed ──────────────────────────────────────────────────────────────

  function _feedEl() { return _q('#db-feed'); }

  function _scrollFeed() {
    const wrap = _q('#db-feed-wrap');
    if (!wrap) return;
    const atBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 60;
    if (atBottom) wrap.scrollTop = wrap.scrollHeight;
  }

  function _addFeedRow(id, html, extraClass = '') {
    const feed = _feedEl();
    if (!feed) return null;
    const row = document.createElement('div');
    row.id        = 'feed-' + id;
    row.className = 'feed-row' + (extraClass ? ' ' + extraClass : '');
    row.innerHTML = html;
    feed.appendChild(row);
    _scrollFeed();
    return row;
  }

  function _addFeedEvent(text, cls = '') {
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
    _addFeedRow('evt-' + Date.now(), `
      <span class="feed-ts mono">${ts}</span>
      <span class="feed-event ${cls}">${text}</span>
    `);
  }

  // ── Event handlers ────────────────────────────────────────────────────────

  function _onEvent(msg) {
    if (!_container) return;

    // Hide the empty state
    _hide('#db-feed-empty');

    switch (msg.name) {

      case 'session_start': {
        const p = msg.payload;
        S.status          = 'running';
        S.currency        = p.currency ?? '';
        S.persona         = p.persona ?? '';
        S.startBalanceUsd = parseFloat(p.start_balance_usd) || 0;
        S.currentBalUsd   = S.startBalanceUsd;
        S.topTargetUsd    = parseFloat(p.top_target_usd)    || 0;
        S.secondaryUsd    = parseFloat(p.secondary_target_usd) || 0;
        S.rate            = parseFloat(p.rate) || 1;
        S.sessionPnlUsd   = 0;
        S.bets = S.wins = S.losses = 0;
        _setText('#db-currency-label', S.currency.toUpperCase());
        _setText('#db-persona-label',  S.persona);
        _addFeedEvent(`Session started — ${S.currency.toUpperCase()} · ${S.persona} persona · $${_fmt(S.startBalanceUsd)} starting`, 'feed-event-ok');
        _renderControls();
        _renderStats();
        break;
      }

      case 'bet_placed': {
        const p   = msg.payload;
        const id  = 'bp-' + Date.now();
        const ts  = new Date().toLocaleTimeString('en-US', { hour12: false });
        const amt = parseFloat(p.amount) || 0;
        const usd = amt * S.rate;
        const feed = _feedEl();
        if (!feed) break;
        const row = document.createElement('div');
        row.id        = 'feed-' + id;
        row.className = 'feed-row feed-pending';
        row.innerHTML = `
          <span class="feed-ts mono">${ts}</span>
          <span class="feed-pending-dot">⋯</span>
          <span class="feed-game mono">${p.game ?? '?'}</span>
          <span class="feed-amount mono">$${_fmt(usd)}</span>
          <span class="feed-result mono text-muted">—</span>
        `;
        feed.appendChild(row);
        _pendingRowId = id;
        _scrollFeed();
        break;
      }

      case 'bet_settled': {
        const p   = msg.payload;
        const won = p.result?.won;
        const amt = parseFloat(p.amount) || 0;
        const pay = parseFloat(p.result?.payout) || 0;
        const mul = parseFloat(p.result?.multiplier) || 0;
        const usd = amt * S.rate;
        const plUsd = won ? (pay - amt) * S.rate : -usd;

        S.sessionPnlUsd += plUsd;
        S.currentBalUsd  = S.startBalanceUsd + S.sessionPnlUsd;
        S.bets++;
        if (won) S.wins++; else S.losses++;

        // Update the pending row
        if (_pendingRowId) {
          const row = _q('#feed-' + _pendingRowId);
          if (row) {
            row.className = `feed-row ${won ? 'feed-won' : 'feed-lost'}`;
            const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
            row.innerHTML = `
              <span class="feed-ts mono">${ts}</span>
              <span class="feed-outcome">${won ? '✓' : '✗'}</span>
              <span class="feed-game mono">${p.game ?? '?'}</span>
              <span class="feed-amount mono">$${_fmt(usd)}</span>
              <span class="feed-result mono ${won ? 'text-green' : 'text-red'}">${_fmtPnl(plUsd)} <span style="color:var(--text-muted)">${mul.toFixed(2)}×</span></span>
            `;
          }
          _pendingRowId = null;
        }
        _renderStats();
        break;
      }

      case 'won_big': {
        // Highlight last row
        const feed = _feedEl();
        const last = feed?.lastElementChild;
        if (last) last.classList.add('feed-big-win');
        _addFeedEvent(`🔥 BIG WIN — ${parseFloat(msg.payload?.multiplier).toFixed(2)}×`, 'feed-event-gold');
        break;
      }

      case 'vault_executed': {
        const p = msg.payload;
        _addFeedEvent(`🏦 Vault — deposited ${parseFloat(p.amount).toFixed(6)} ${(p.currency ?? '').toUpperCase()}`, 'feed-event-gold');
        break;
      }

      case 'secondary_target_hit': {
        const usd = parseFloat(msg.payload?.balance_usd);
        S.currentBalUsd = isNaN(usd) ? S.currentBalUsd : usd;
        _addFeedEvent(`🎯 Secondary target hit — $${_fmt(usd)}`, 'feed-event-gold');
        _renderStats();
        break;
      }

      case 'top_target_hit': {
        const usd = parseFloat(msg.payload?.balance_usd);
        S.currentBalUsd = isNaN(usd) ? S.currentBalUsd : usd;
        _addFeedEvent(`🏆 Primary target hit — $${_fmt(usd)}`, 'feed-event-gold');
        _renderStats();
        break;
      }

      case 'stop_loss_hit': {
        const usd = parseFloat(msg.payload?.balance_usd);
        S.currentBalUsd = isNaN(usd) ? S.currentBalUsd : usd;
        _addFeedEvent(`🛑 Stop-loss triggered — $${_fmt(usd)}`, 'feed-event-error');
        _renderStats();
        break;
      }

      case 'session_completed': {
        S.status    = 'ended';
        S.endReason = msg.payload?.end_reason ?? 'unknown';
        const labels = {
          top_target_hit:    '🏆 Top target hit',
          secondary_target_hit: '🎯 Secondary target hit',
          stop_loss_hit:     '🛑 Stop-loss triggered',
          user_halt:         '⏹ Stopped by user',
          panic:             '🚨 Panic halt',
          error:             '⚠️ Engine error',
        };
        _addFeedEvent(`Session ended — ${labels[S.endReason] ?? S.endReason}`, 'feed-event-ok');
        _renderControls();
        _renderStats();
        break;
      }

      case 'engine_crash': {
        S.status = 'ended';
        S.endReason = 'crash';
        _addFeedEvent('⚠️ Engine crashed — check Debug Console', 'feed-event-error');
        _renderControls();
        break;
      }
    }
  }

  // ── Start session ─────────────────────────────────────────────────────────

  async function _startSession() {
    if (S.status !== 'idle' && S.status !== 'ended') return;

    S.status = 'starting';
    _pendingRowId = null;
    _renderControls();

    // Clear feed
    const feed = _feedEl();
    if (feed) feed.innerHTML = '';
    _show('#db-feed-empty');
    _setText('#db-feed-empty', '⋯ Starting session…');

    let payload;
    try {
      payload = await _buildStartPayload();
    } catch (err) {
      S.status = 'idle';
      _renderControls();
      _addFeedEvent(`✗ ${err.message}`, 'feed-event-error');
      _hide('#db-feed-empty');
      return;
    }

    // Show dry-run badge
    if (payload._dry_run) {
      _show('#db-dry-run-badge');
    } else {
      _hide('#db-dry-run-badge');
    }
    S.dryRun = payload._dry_run;

    const res = await window.gambleAgent.engineSend('start_session', payload, 10_000);
    if (!res.ok) {
      S.status = 'idle';
      _renderControls();
      _hide('#db-feed-empty');
      const detail = res.payload?.detail ?? [];
      if (detail.length > 0) {
        _addFeedEvent(`✗ Engine rejected config (${detail.length} error${detail.length > 1 ? 's' : ''}):`, 'feed-event-error');
        detail.forEach(e => _addFeedEvent(`    ${e.loc}: ${e.msg}`, 'feed-event-error'));
      } else {
        _addFeedEvent(`✗ Failed to start: ${res.error ?? 'unknown error'}`, 'feed-event-error');
      }
    }
    // Success: wait for 'session_start' event to set status='running'
  }

  // ── Mount ─────────────────────────────────────────────────────────────────

  function mount(container) {
    _container = container;

    container.innerHTML = `
      <div class="view-header">
        <div class="row-between" style="align-items:flex-start">
          <div>
            <h1>Dashboard</h1>
            <p>Live session view — controls, bet feed, and real-time stats.</p>
          </div>
          <div class="row" style="gap:8px;margin-top:4px;flex-wrap:wrap">
            <span id="db-dry-run-badge" class="badge badge-gold" style="display:none">DRY RUN</span>
            <span id="db-currency-label" class="badge badge-muted mono"></span>
            <span id="db-persona-label"  class="badge badge-muted mono"></span>
            <button class="btn btn-primary btn-sm" id="db-go">▶ GO</button>
            <button class="btn btn-ghost btn-sm"   id="db-pause" style="display:none">⏸ Pause</button>
            <button class="btn btn-ghost btn-sm"   id="db-stop"  style="display:none">■ Stop</button>
            <button class="btn btn-danger btn-sm"  id="db-panic" style="display:none">🚨 Panic</button>
            <button class="btn btn-ghost btn-sm"   id="db-new-session" style="display:none">↩ New Session</button>
          </div>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex:1;min-height:0">

        <!-- ── Stats sidebar ──────────────────────────────────────────────── -->
        <div style="width:220px;flex-shrink:0;display:flex;flex-direction:column;gap:12px">

          <div class="card" style="padding:16px">
            <div class="card-title" style="margin-bottom:8px">Balance</div>
            <div id="db-balance-usd" style="font-size:24px;font-weight:600;font-family:var(--font-mono)">$—</div>
            <div style="font-size:12px;margin-top:4px">
              Session P&L: <span id="db-pnl" class="mono">—</span>
            </div>
          </div>

          <div class="card" style="padding:16px">
            <div class="card-title" style="margin-bottom:10px">Target Progress</div>
            <div style="position:relative;height:8px;background:var(--bg-elevated);border-radius:4px;overflow:visible">
              <div id="db-progress-fill"
                style="height:100%;width:0%;background:var(--green);border-radius:4px;transition:width 0.3s"></div>
              <!-- Secondary target marker -->
              <div id="db-secondary-marker"
                style="position:absolute;top:-3px;width:2px;height:14px;background:var(--gold);border-radius:1px;left:50%"></div>
            </div>
            <div id="db-target-label"    style="font-size:11px;color:var(--text-muted);margin-top:6px;font-family:var(--font-mono)">$— / $—</div>
            <div id="db-secondary-label" style="font-size:10px;color:var(--gold);margin-top:2px;font-family:var(--font-mono)"></div>
          </div>

          <div class="card" style="padding:16px">
            <div class="card-title" style="margin-bottom:8px">Bets</div>
            <div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px;font-family:var(--font-mono)">
              <span style="color:var(--text-muted)">total</span>  <span id="db-bet-count">0</span>
              <span style="color:var(--text-muted)">win rate</span><span id="db-win-rate">—</span>
              <span style="color:var(--green)">wins</span>  <span id="db-wins">0</span>
              <span style="color:var(--red)">losses</span> <span id="db-losses">0</span>
            </div>
          </div>

          <!-- Avatar placeholder -->
          <div class="card coming-soon" style="padding:16px;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-height:80px">
            <div style="font-size:32px">🤖</div>
            <div style="font-size:11px;color:var(--text-muted);text-align:center">Avatar — Phase 4</div>
          </div>

        </div>

        <!-- ── Bet feed ───────────────────────────────────────────────────── -->
        <div style="flex:1;display:flex;flex-direction:column;min-width:0">
          <div id="db-feed-wrap"
            style="flex:1;overflow-y:auto;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:8px">
            <div id="db-feed"></div>
            <div id="db-feed-empty"
              style="padding:40px;text-align:center;color:var(--text-muted);font-size:13px">
              No session running — click <strong>GO</strong> to start
            </div>
          </div>
        </div>

      </div>

      <style>
        .feed-row {
          display:flex; gap:10px; align-items:baseline;
          padding:3px 6px; border-radius:4px; font-size:12px; line-height:1.6;
        }
        .feed-row.feed-won  { }
        .feed-row.feed-lost { opacity:0.8; }
        .feed-row.feed-pending { opacity:0.6; }
        .feed-row.feed-big-win { background:var(--gold-glow); border-radius:4px; }
        .feed-ts     { color:var(--text-muted); min-width:66px; flex-shrink:0 }
        .feed-game   { min-width:90px; flex-shrink:0; font-weight:500 }
        .feed-amount { min-width:60px; flex-shrink:0; color:var(--text-secondary) }
        .feed-result { flex:1 }
        .feed-outcome { min-width:14px; flex-shrink:0 }
        .feed-pending-dot { color:var(--text-muted); min-width:14px }
        .feed-event { flex:1; font-style:italic }
        .feed-event-ok    { color:var(--green); }
        .feed-event-gold  { color:var(--gold); }
        .feed-event-error { color:var(--red); }
      </style>
    `;

    // ── Subscribe to engine events (persists across view switches) ──────────
    if (_unsubscribe) _unsubscribe();
    _unsubscribe = window.gambleAgent.onEngineEvent(_onEvent);

    // ── Button wiring ───────────────────────────────────────────────────────
    _q('#db-go').addEventListener('click', _startSession);

    _q('#db-pause').addEventListener('click', async () => {
      if (S.status === 'paused') {
        await window.gambleAgent.engineSend('resume_session', {});
        S.status = 'running';
        _addFeedEvent('▶ Session resumed', '');
      } else {
        await window.gambleAgent.engineSend('pause_session', {});
        S.status = 'paused';
        _addFeedEvent('⏸ Session paused', '');
      }
      _renderControls();
    });

    _q('#db-stop').addEventListener('click', async () => {
      await window.gambleAgent.engineSend('stop_session', {});
      S.status = 'stopping';
      _addFeedEvent('⏹ Stopping after this bet…', '');
      _renderControls();
    });

    _q('#db-panic').addEventListener('click', async () => {
      await window.gambleAgent.engineSend('panic', {});
      S.status = 'ended';
      S.endReason = 'panic';
      _addFeedEvent('🚨 Panic — session halted immediately', 'feed-event-error');
      _renderControls();
    });

    _q('#db-new-session').addEventListener('click', () => {
      S.status = 'idle';
      S.bets = S.wins = S.losses = S.sessionPnlUsd = 0;
      S.startBalanceUsd = S.currentBalUsd = 0;
      const feed = _feedEl();
      if (feed) feed.innerHTML = '';
      _show('#db-feed-empty');
      _setText('#db-feed-empty', 'No session running — click GO to start');
      _renderControls();
      _renderStats();
      window.App?.navigateTo('session-config');
    });

    // ── Auto-launch when navigated here from "Launch Session →" ────────────
    document.addEventListener('view:activated', e => {
      if (e.detail.viewId !== 'dashboard') return;
      if (sessionStorage.getItem('gambleagent:launch') === '1') {
        sessionStorage.removeItem('gambleagent:launch');
        if (S.status === 'idle' || S.status === 'ended') _startSession();
      }
    });

    _renderControls();
    _renderStats();
  }

  return { mount };
})();
