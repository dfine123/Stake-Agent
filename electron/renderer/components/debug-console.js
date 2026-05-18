'use strict';

// Debug Console — live IPC message log + GraphQL traffic viewer.
// First-class feature: every Stake API call's raw request + response is logged
// here, so the user can post-mortem any error with full context.

window.DebugConsoleComponent = (() => {
  const MAX_MESSAGES = 500;
  let _messages = [];
  let _unsubscribe = null;
  let _listEl = null;
  let _engineAlive = false;

  // Filter state
  let _filter = 'all';      // all | event | response | gql | errors
  let _search = '';
  let _autoScroll = true;

  // ── Filter logic ────────────────────────────────────────────────────────

  function _matchesFilter(msg) {
    if (_filter === 'all')      return true;
    if (_filter === 'event')    return msg.type === 'event' && !msg.name?.startsWith('debug_');
    if (_filter === 'response') return msg.type === 'response';
    if (_filter === 'gql')      return msg.name?.startsWith('debug_');
    if (_filter === 'errors') {
      if (msg.name === 'engine_crash' || msg.name === 'engine_stderr' || msg.name === 'error') return true;
      if (msg.type === 'response' && msg.ok === false) return true;
      if (msg.name === 'debug_response' && msg.payload?.status && msg.payload.status >= 400) return true;
      return false;
    }
    return true;
  }

  function _matchesSearch(msg) {
    if (!_search) return true;
    const haystack = (msg.name ?? '') + ' ' + JSON.stringify(msg.payload ?? {});
    return haystack.toLowerCase().includes(_search.toLowerCase());
  }

  // ── State helpers ───────────────────────────────────────────────────────

  function _addMessage(msg) {
    _messages.push(msg);
    if (_messages.length > MAX_MESSAGES) _messages.shift();
    window.App?.setDebugCount(_messages.length);
    if (_matchesFilter(msg) && _matchesSearch(msg)) _renderMessage(msg);
  }

  // ── Rendering ───────────────────────────────────────────────────────────

  function _colorForMsg(msg) {
    if (msg.name === 'engine_crash' || msg.name === 'error' || msg.name === 'engine_stderr') return 'var(--red)';
    if (msg.name === 'debug_request')  return 'var(--blue)';
    if (msg.name === 'debug_response') {
      const status = msg.payload?.status;
      if (status && status >= 400) return 'var(--red)';
      return '#9e9e9e';
    }
    if (msg.type === 'response' && msg.ok === false) return 'var(--red)';
    if (msg.type === 'response') return 'var(--green)';
    if (msg.name === 'bet_settled') return msg.payload?.result?.won ? 'var(--green)' : 'var(--red)';
    if (msg.name === 'won_big' || msg.name === 'top_target_hit') return 'var(--gold)';
    return 'var(--text-secondary)';
  }

  function _typeTag(msg) {
    if (msg.type === 'response') {
      return `<span style="color:${msg.ok ? 'var(--green)' : 'var(--red)'}">▶ ${msg.ok ? 'ok' : 'err'}</span>`;
    }
    if (msg.name === 'debug_request')  return `<span style="color:var(--blue)">→ req</span>`;
    if (msg.name === 'debug_response') {
      const s = msg.payload?.status;
      const color = s && s >= 400 ? 'var(--red)' : '#9e9e9e';
      return `<span style="color:${color}">← ${s ?? 'res'}</span>`;
    }
    return `<span style="color:var(--text-muted)">◆ ${msg.type}</span>`;
  }

  function _summarise(msg) {
    if (msg.name === 'debug_request') {
      const op = _extractOperationName(msg.payload?.query);
      return op ? `${op} → ${msg.payload?.endpoint ?? ''}` : (msg.payload?.endpoint ?? '');
    }
    if (msg.name === 'debug_response') {
      const ms = msg.payload?.latency_ms;
      return ms != null ? `${ms} ms` : '';
    }
    const p = msg.payload;
    if (!p) return '';
    const s = JSON.stringify(p, null, 0);
    return s.length > 140 ? s.slice(0, 140) + '…' : s;
  }

  function _extractOperationName(query) {
    if (!query || typeof query !== 'string') return null;
    // Match `mutation FooBar(` / `query FooBar(` / `mutation FooBar {`
    const m = query.match(/^\s*(query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)/);
    return m ? m[2] : null;
  }

  function _renderMessage(msg) {
    if (!_listEl) return;

    const ts = new Date(msg.ts).toLocaleTimeString('en-US', { hour12: false });
    const color = _colorForMsg(msg);

    const row = document.createElement('div');
    row.className = 'dc-row';
    row.innerHTML = `
      <span class="dc-ts mono">${ts}</span>
      ${_typeTag(msg)}
      <span class="dc-name mono" style="color:${color}">${msg.name ?? '?'}</span>
      <span class="dc-payload mono">${_escapeHtml(_summarise(msg))}</span>
    `;

    // Click to expand
    row.addEventListener('click', () => _toggleDetail(row, msg));

    _listEl.appendChild(row);
    _maybeScrollToBottom();
  }

  function _escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function _maybeScrollToBottom() {
    if (!_autoScroll) return;
    const parent = _listEl.parentElement;
    if (!parent) return;
    parent.scrollTop = parent.scrollHeight;
  }

  function _toggleDetail(row, msg) {
    const existing = row.nextElementSibling;
    if (existing && existing.classList.contains('dc-detail')) {
      existing.remove();
      return;
    }

    const detail = document.createElement('div');
    detail.className = 'dc-detail';

    // For GraphQL request messages, add a "Copy as cURL" button
    const isGqlReq = msg.name === 'debug_request' && msg.payload?.endpoint && msg.payload?.query;
    if (isGqlReq) {
      const btnRow = document.createElement('div');
      btnRow.style.cssText = 'display:flex;gap:6px;padding:8px 14px 0;flex-wrap:wrap';
      btnRow.innerHTML = `
        <button class="btn btn-ghost btn-sm dc-copy-curl">📋 Copy as cURL</button>
        <button class="btn btn-ghost btn-sm dc-copy-query">📋 Copy query</button>
        <button class="btn btn-ghost btn-sm dc-copy-vars">📋 Copy variables</button>
      `;
      btnRow.querySelector('.dc-copy-curl').addEventListener('click', e => {
        e.stopPropagation();
        _copyToClipboard(_buildCurl(msg.payload), e.currentTarget);
      });
      btnRow.querySelector('.dc-copy-query').addEventListener('click', e => {
        e.stopPropagation();
        _copyToClipboard(msg.payload.query, e.currentTarget);
      });
      btnRow.querySelector('.dc-copy-vars').addEventListener('click', e => {
        e.stopPropagation();
        _copyToClipboard(JSON.stringify(msg.payload.variables ?? {}, null, 2), e.currentTarget);
      });
      detail.appendChild(btnRow);
    }

    // For GraphQL response messages, add "Copy JSON" button
    if (msg.name === 'debug_response') {
      const btnRow = document.createElement('div');
      btnRow.style.cssText = 'display:flex;gap:6px;padding:8px 14px 0;flex-wrap:wrap';
      btnRow.innerHTML = `<button class="btn btn-ghost btn-sm dc-copy-body">📋 Copy response JSON</button>`;
      btnRow.querySelector('.dc-copy-body').addEventListener('click', e => {
        e.stopPropagation();
        _copyToClipboard(JSON.stringify(msg.payload?.body ?? {}, null, 2), e.currentTarget);
      });
      detail.appendChild(btnRow);
    }

    const pre = document.createElement('pre');
    pre.className = 'dc-detail-json mono';
    pre.textContent = JSON.stringify(msg, null, 2);
    detail.appendChild(pre);

    row.insertAdjacentElement('afterend', detail);
  }

  // ── cURL builder ────────────────────────────────────────────────────────

  function _buildCurl({ endpoint, query, variables }) {
    const body = JSON.stringify({ query, variables: variables ?? {} });
    const escaped = body.replace(/'/g, "'\\''");
    return [
      `curl -X POST '${endpoint}' \\`,
      `  -H 'Content-Type: application/json' \\`,
      `  -H 'x-access-token: <YOUR_TOKEN>' \\`,
      `  -d '${escaped}'`,
    ].join('\n');
  }

  function _copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      if (btn) {
        const original = btn.textContent;
        btn.textContent = '✓ Copied';
        setTimeout(() => { btn.textContent = original; }, 1200);
      }
    });
  }

  // ── Re-render (after filter change) ─────────────────────────────────────

  function _rerenderAll() {
    if (!_listEl) return;
    _listEl.innerHTML = '';
    const filtered = _messages.filter(m => _matchesFilter(m) && _matchesSearch(m));
    filtered.forEach(_renderMessage);
    const empty = document.getElementById('dc-empty');
    if (empty) empty.style.display = filtered.length === 0 ? '' : 'none';
  }

  // ── Export ──────────────────────────────────────────────────────────────

  function _exportSession() {
    if (_messages.length === 0) return;
    const blob = new Blob([JSON.stringify(_messages, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.download = `gambleagent-debug-${ts}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Test IPC ────────────────────────────────────────────────────────────

  async function _testIPC() {
    const msg = {
      id: 'test-' + Date.now(),
      type: 'event',
      name: 'ipc_test_sent',
      payload: { command: 'get_status' },
      ts: new Date().toISOString(),
    };
    _addMessage(msg);

    const res = await window.gambleAgent.engineSend('get_status');
    _addMessage({
      id: res.payload?.id || 'test-resp',
      type: 'response',
      name: 'get_status',
      ok: res.ok,
      payload: res.ok ? res.payload : { error: res.error },
      ts: new Date().toISOString(),
    });
  }

  // ── Mount ───────────────────────────────────────────────────────────────

  function mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <div class="row-between" style="align-items:flex-start">
          <div>
            <h1>Debug Console</h1>
            <p>Raw IPC messages + Stake GraphQL traffic. Shortcut: <span class="mono">⌘⇧D</span></p>
          </div>
          <div class="row" style="gap:8px;margin-top:4px;flex-wrap:wrap">
            <span class="status-pill" id="dc-engine-pill">
              <span class="status-dot" id="dc-engine-dot"></span>
              <span id="dc-engine-label" class="mono" style="font-size:11px">checking…</span>
            </span>
            <button class="btn btn-ghost btn-sm" id="dc-test-btn">Test IPC</button>
            <button class="btn btn-ghost btn-sm" id="dc-export-btn">⇩ Export</button>
            <button class="btn btn-ghost btn-sm" id="dc-clear-btn">Clear</button>
          </div>
        </div>
      </div>

      <!-- ── Filter bar ───────────────────────────────────────────────────── -->
      <div id="dc-filter-bar" style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
        <div class="dc-pill-row">
          <button class="pill-btn active" data-filter="all">All <span id="cnt-all" class="dc-cnt">0</span></button>
          <button class="pill-btn"        data-filter="event">Events <span id="cnt-event" class="dc-cnt">0</span></button>
          <button class="pill-btn"        data-filter="response">Responses <span id="cnt-response" class="dc-cnt">0</span></button>
          <button class="pill-btn"        data-filter="gql">GraphQL <span id="cnt-gql" class="dc-cnt">0</span></button>
          <button class="pill-btn"        data-filter="errors">Errors <span id="cnt-errors" class="dc-cnt">0</span></button>
        </div>
        <input type="text" id="dc-search" placeholder="search name or payload…"
          style="flex:1;min-width:200px;background:var(--bg-base);border:1px solid var(--border-strong);border-radius:var(--radius-md);padding:6px 10px;font-size:12px;font-family:var(--font-mono);color:var(--text-primary);outline:none">
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-muted);cursor:pointer">
          <input type="checkbox" id="dc-autoscroll" checked style="display:none">
          <span class="toggle-track" style="width:28px;height:16px"><span class="toggle-thumb"></span></span>
          auto-scroll
        </label>
      </div>

      <!-- ── Log viewport ─────────────────────────────────────────────────── -->
      <div id="dc-log-wrap" style="flex:1;overflow-y:auto;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:8px;min-height:0">
        <div id="dc-log"></div>
        <div id="dc-empty" style="padding:40px;text-align:center;color:var(--text-muted);font-size:13px">
          No messages yet — waiting for engine events…
        </div>
      </div>

      <style>
        .dc-row {
          display:flex; gap:10px; align-items:baseline;
          padding:3px 6px; border-radius:4px; cursor:pointer;
          font-size:12px; line-height:1.5;
        }
        .dc-row:hover { background:var(--bg-elevated); }
        .dc-ts      { color:var(--text-muted); min-width:78px; flex-shrink:0 }
        .dc-name    { min-width:160px; flex-shrink:0; font-weight:500 }
        .dc-payload { color:var(--text-muted); overflow:hidden; white-space:nowrap; text-overflow:ellipsis }

        .dc-detail {
          background:var(--bg-base); border-left:2px solid var(--border-strong);
          margin:0 6px 4px 6px; padding:0; font-size:11px;
          color:var(--text-secondary); border-radius:0 0 4px 4px;
        }
        .dc-detail-json {
          padding:10px 14px; margin:0;
          overflow-x:auto; white-space:pre;
          font-size:11px;
        }

        #dc-engine-pill { display:flex; align-items:center; gap:6px; padding:4px 8px;
          background:var(--bg-elevated); border-radius:10px; }

        .dc-pill-row { display:flex; gap:6px; }
        .dc-cnt {
          font-size:10px; padding:1px 5px; margin-left:4px;
          background:var(--bg-elevated); color:var(--text-muted);
          border-radius:8px; font-family:var(--font-mono);
        }
        .pill-btn.active .dc-cnt { background:var(--bg-base); }
      </style>
    `;

    _listEl = container.querySelector('#dc-log');

    const search = container.querySelector('#dc-search');
    const empty  = container.querySelector('#dc-empty');

    // ── Filter pills ────────────────────────────────────────────────────────
    container.querySelector('#dc-filter-bar').addEventListener('click', e => {
      const btn = e.target.closest('[data-filter]');
      if (!btn) return;
      _filter = btn.dataset.filter;
      container.querySelectorAll('[data-filter]').forEach(b =>
        b.classList.toggle('active', b.dataset.filter === _filter));
      _rerenderAll();
    });

    // ── Search ──────────────────────────────────────────────────────────────
    let _searchTimer = null;
    search.addEventListener('input', () => {
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => {
        _search = search.value.trim();
        _rerenderAll();
      }, 120);
    });

    // ── Auto-scroll toggle ──────────────────────────────────────────────────
    const autoScrollCb = container.querySelector('#dc-autoscroll');
    autoScrollCb.addEventListener('change', () => { _autoScroll = autoScrollCb.checked; });

    // Also disable auto-scroll if user scrolls up manually
    container.querySelector('#dc-log-wrap').addEventListener('scroll', e => {
      const w = e.currentTarget;
      const atBottom = w.scrollHeight - w.scrollTop - w.clientHeight < 60;
      if (!atBottom && _autoScroll) {
        _autoScroll = false;
        autoScrollCb.checked = false;
      }
    });

    // ── Buttons ─────────────────────────────────────────────────────────────
    container.querySelector('#dc-test-btn').addEventListener('click', _testIPC);
    container.querySelector('#dc-export-btn').addEventListener('click', _exportSession);
    container.querySelector('#dc-clear-btn').addEventListener('click', () => {
      _messages = [];
      _listEl.innerHTML = '';
      empty.style.display = '';
      window.App?.setDebugCount(0);
      _updateCounts();
    });

    // ── Subscribe to engine events ──────────────────────────────────────────
    if (_unsubscribe) _unsubscribe();
    _unsubscribe = window.gambleAgent.onEngineEvent(msg => {
      empty.style.display = 'none';
      _addMessage(msg);
      _updateCounts();
    });

    // ── Engine alive status ─────────────────────────────────────────────────
    async function refreshStatus() {
      _engineAlive = await window.gambleAgent.engineAlive();
      const dot   = container.querySelector('#dc-engine-dot');
      const label = container.querySelector('#dc-engine-label');
      if (dot && label) {
        dot.className   = `status-dot ${_engineAlive ? 'online' : 'error'}`;
        label.textContent = _engineAlive ? 'engine running' : 'engine offline';
      }
    }
    refreshStatus();

    // ── Count badges ────────────────────────────────────────────────────────
    function _updateCounts() {
      const cnt = { all: _messages.length, event: 0, response: 0, gql: 0, errors: 0 };
      for (const m of _messages) {
        if (m.type === 'event' && !m.name?.startsWith('debug_')) cnt.event++;
        if (m.type === 'response') cnt.response++;
        if (m.name?.startsWith('debug_')) cnt.gql++;
        if (m.name === 'engine_crash' || m.name === 'engine_stderr' || m.name === 'error') cnt.errors++;
        else if (m.type === 'response' && m.ok === false) cnt.errors++;
        else if (m.name === 'debug_response' && m.payload?.status >= 400) cnt.errors++;
      }
      for (const k of Object.keys(cnt)) {
        const el = container.querySelector('#cnt-' + k);
        if (el) el.textContent = cnt[k];
      }
    }
    _updateCounts();

    // ── Replay buffered messages ────────────────────────────────────────────
    if (_messages.length > 0) {
      empty.style.display = 'none';
      _rerenderAll();
    }

    // Refresh status whenever view re-activates
    document.addEventListener('view:activated', e => {
      if (e.detail.viewId === 'debug-console') refreshStatus();
    });
  }

  return { mount };
})();
