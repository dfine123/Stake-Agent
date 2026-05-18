'use strict';

// Debug Console — live IPC message log + GraphQL traffic viewer.
// Full implementation (export, cURL copy) in Task 2.6.
// Task 2.2 goal: prove IPC works end-to-end.

window.DebugConsoleComponent = (() => {
  const MAX_MESSAGES = 200;
  let _messages = [];
  let _unsubscribe = null;
  let _listEl = null;
  let _countEl = null;
  let _engineAlive = false;

  function _addMessage(msg) {
    _messages.push(msg);
    if (_messages.length > MAX_MESSAGES) _messages.shift();
    window.App?.setDebugCount(_messages.length);
    _renderMessage(msg);
  }

  function _colorForMsg(msg) {
    if (msg.name === 'engine_crash' || msg.name === 'error') return 'var(--red)';
    if (msg.name?.startsWith('debug_request'))  return 'var(--blue)';
    if (msg.name?.startsWith('debug_response')) return '#9e9e9e';
    if (msg.type === 'response' && msg.ok === false) return 'var(--red)';
    if (msg.type === 'response') return 'var(--green)';
    if (msg.name === 'bet_settled') return msg.payload?.result?.won ? 'var(--green)' : 'var(--red)';
    if (msg.name === 'won_big')     return 'var(--gold)';
    return 'var(--text-secondary)';
  }

  function _renderMessage(msg) {
    if (!_listEl) return;

    const ts = new Date(msg.ts).toLocaleTimeString('en-US', { hour12: false });
    const color = _colorForMsg(msg);
    const typeTag = msg.type === 'response'
      ? `<span style="color:${msg.ok ? 'var(--green)' : 'var(--red)'}">▶ ${msg.ok ? 'ok' : 'err'}</span>`
      : `<span style="color:var(--text-muted)">◆ ${msg.type}</span>`;

    const row = document.createElement('div');
    row.className = 'dc-row';
    row.innerHTML = `
      <span class="dc-ts mono">${ts}</span>
      ${typeTag}
      <span class="dc-name mono" style="color:${color}">${msg.name ?? '?'}</span>
      <span class="dc-payload mono">${_summarise(msg.payload)}</span>
    `;

    // Click to expand full JSON
    row.addEventListener('click', () => {
      const existing = row.nextElementSibling;
      if (existing && existing.classList.contains('dc-detail')) {
        existing.remove();
        return;
      }
      const detail = document.createElement('pre');
      detail.className = 'dc-detail mono';
      detail.textContent = JSON.stringify(msg, null, 2);
      row.insertAdjacentElement('afterend', detail);
    });

    _listEl.appendChild(row);
    // Auto-scroll to bottom unless user has scrolled up
    const parent = _listEl.parentElement;
    const atBottom = parent.scrollHeight - parent.scrollTop - parent.clientHeight < 60;
    if (atBottom) parent.scrollTop = parent.scrollHeight;
  }

  function _summarise(payload) {
    if (!payload) return '';
    const s = JSON.stringify(payload, null, 0);
    return s.length > 120 ? s.slice(0, 120) + '…' : s;
  }

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

  function mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <div class="row-between" style="align-items:flex-start">
          <div>
            <h1>Debug Console</h1>
            <p>Raw IPC messages and Stake GraphQL traffic. Shortcut: <span class="mono">⌘⇧D</span></p>
          </div>
          <div class="row" style="gap:8px;margin-top:4px">
            <span class="status-pill" id="dc-engine-pill">
              <span class="status-dot" id="dc-engine-dot"></span>
              <span id="dc-engine-label" class="mono" style="font-size:11px">checking…</span>
            </span>
            <button class="btn btn-ghost btn-sm" id="dc-test-btn">Test IPC (get_status)</button>
            <button class="btn btn-ghost btn-sm" id="dc-clear-btn">Clear</button>
          </div>
        </div>
      </div>

      <div id="dc-log-wrap" style="flex:1;overflow-y:auto;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:8px">
        <div id="dc-log"></div>
        <div id="dc-empty" style="padding:40px;text-align:center;color:var(--text-muted);font-size:13px">
          No messages yet — waiting for engine events…
        </div>
      </div>

      <style>
        .dc-row {
          display: flex; gap: 10px; align-items: baseline;
          padding: 3px 6px; border-radius: 4px; cursor: pointer;
          font-size: 12px; line-height: 1.5;
        }
        .dc-row:hover { background: var(--bg-elevated); }
        .dc-ts    { color: var(--text-muted); min-width: 78px; flex-shrink:0 }
        .dc-name  { min-width: 160px; flex-shrink:0; font-weight:500 }
        .dc-payload { color: var(--text-muted); overflow:hidden; white-space:nowrap; text-overflow:ellipsis }
        .dc-detail {
          background: var(--bg-base); border-left: 2px solid var(--border-strong);
          margin: 0 6px 4px 6px; padding: 10px 14px; font-size: 11px;
          color: var(--text-secondary); overflow-x: auto; white-space: pre;
          border-radius: 0 0 4px 4px;
        }
        #dc-engine-pill { display:flex; align-items:center; gap:6px; padding:4px 8px;
          background:var(--bg-elevated); border-radius:10px; }
      </style>
    `;

    _listEl  = container.querySelector('#dc-log');
    _countEl = container.querySelector('#dc-count');

    // Buttons
    container.querySelector('#dc-test-btn').addEventListener('click', _testIPC);
    container.querySelector('#dc-clear-btn').addEventListener('click', () => {
      _messages = [];
      _listEl.innerHTML = '';
      container.querySelector('#dc-empty').style.display = '';
      window.App?.setDebugCount(0);
    });

    // Subscribe to engine events and display them
    if (_unsubscribe) _unsubscribe();
    _unsubscribe = window.gambleAgent.onEngineEvent(msg => {
      container.querySelector('#dc-empty').style.display = 'none';
      _addMessage(msg);
    });

    // Check engine alive status
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

    // Replay buffered messages (from before this view was opened)
    if (_messages.length > 0) {
      container.querySelector('#dc-empty').style.display = 'none';
      _messages.forEach(_renderMessage);
    }

    // Refresh status when view is activated
    document.addEventListener('view:activated', e => {
      if (e.detail.viewId === 'debug-console') refreshStatus();
    });
  }

  return { mount };
})();
