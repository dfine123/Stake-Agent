'use strict';

window.SettingsComponent = (() => {
  const ACCT = {
    stakeToken:     'stake_access_token',
    anthropicKey:   'anthropic_api_key',
    telegramToken:  'telegram_bot_token',
    telegramChatId: 'telegram_chat_id',
  };

  // ── Helpers ───────────────────────────────────────────────────────────────

  async function _keychainGet(account) {
    try { return await window.gambleAgent.keychain.get(account); } catch { return null; }
  }
  async function _keychainDelete(account) {
    try { await window.gambleAgent.keychain.delete(account); } catch { /* already gone */ }
  }

  function _mask(value) {
    if (!value) return null;
    // Show last 4 characters: ••••••ab12
    const suffix = value.slice(-4);
    return `${'•'.repeat(8)}${suffix}`;
  }

  // ── Credential row rendering ──────────────────────────────────────────────

  function _credRow(container, { label, account, value, hint }) {
    const saved = !!value;
    const row = container.querySelector(`[data-cred="${account}"]`);
    if (!row) return;

    row.innerHTML = `
      <div>
        <div style="font-size:13px;font-weight:500;margin-bottom:2px">${label}</div>
        ${hint ? `<div class="text-muted" style="font-size:11px">${hint}</div>` : ''}
      </div>
      <div class="row" style="gap:8px;align-items:center">
        ${saved
          ? `<span class="mono text-muted" style="font-size:12px">${_mask(value)}</span>
             <span class="badge badge-green">saved</span>
             <button class="btn btn-ghost btn-sm" data-delete="${account}">Delete</button>`
          : `<span class="badge badge-muted">not set</span>`
        }
        <button class="btn btn-ghost btn-sm" data-edit="${account}">
          ${saved ? 'Replace' : 'Set'} →
        </button>
      </div>
    `;
  }

  // ── Mount ─────────────────────────────────────────────────────────────────

  function mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Settings</h1>
        <p>Credentials, engine control, and data management.</p>
      </div>

      <!-- ── Credentials ────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title" style="margin-bottom:16px">Stored Credentials
          <span style="float:right;font-size:11px;font-weight:400;text-transform:none;letter-spacing:0;color:var(--text-muted)">macOS Keychain · com.gambleagent.app</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:0">
          <div class="settings-cred-row" data-cred="stake_access_token"></div>
          <div class="divider" style="margin:10px 0"></div>
          <div class="settings-cred-row" data-cred="anthropic_api_key"></div>
          <div class="divider" style="margin:10px 0"></div>
          <div class="settings-cred-row" data-cred="telegram_bot_token"></div>
          <div class="divider" style="margin:10px 0"></div>
          <div class="settings-cred-row" data-cred="telegram_chat_id"></div>
        </div>
      </div>

      <!-- ── Engine ─────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Python Engine</div>
        <div class="row-between">
          <div>
            <div style="font-size:13px;margin-bottom:3px">Sidecar process</div>
            <div class="text-muted mono" style="font-size:11px" id="engine-alive-label">checking…</div>
          </div>
          <div class="row" style="gap:8px">
            <button class="btn btn-ghost btn-sm" id="btn-check-engine">Check</button>
            <button class="btn btn-ghost btn-sm" id="btn-restart-engine">Restart</button>
          </div>
        </div>
      </div>

      <!-- ── Data ───────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Data</div>
        <div class="row-between" style="margin-bottom:12px">
          <div>
            <div style="font-size:13px;margin-bottom:2px">App data folder</div>
            <div class="text-muted mono" style="font-size:11px">~/Library/Application Support/GambleAgent/</div>
          </div>
          <button class="btn btn-ghost btn-sm" id="btn-open-data-dir">Open in Finder ↗</button>
        </div>
        <div class="row-between">
          <div>
            <div style="font-size:13px;margin-bottom:2px">Session config</div>
            <div class="text-muted" style="font-size:11px">Stored in browser localStorage — personas, targets, games, vibes</div>
          </div>
          <button class="btn btn-ghost btn-sm" id="btn-clear-config">Clear saved config</button>
        </div>
      </div>

      <!-- ── About ──────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">About</div>
        <div style="font-size:13px;color:var(--text-secondary);line-height:1.8">
          <div class="row-between">
            <span>Version</span>
            <span class="mono" id="settings-version">—</span>
          </div>
          <div class="divider" style="margin:10px 0"></div>
          <div class="row-between">
            <span>Phase 1 — Engine prototype (CLI)</span>
            <span class="badge badge-green">complete</span>
          </div>
          <div class="row-between" style="margin-top:8px">
            <span>Phase 2 — Electron UI + Packaging</span>
            <span class="badge badge-gold">in progress</span>
          </div>
          <div class="row-between" style="margin-top:8px">
            <span>Phase 3 — Full engine (all games, all personas, commentary)</span>
            <span class="badge badge-muted">upcoming</span>
          </div>
          <div class="row-between" style="margin-top:8px">
            <span>Phase 4 — Avatar</span>
            <span class="badge badge-muted">upcoming</span>
          </div>
        </div>
      </div>

      <!-- ── Danger zone ─────────────────────────────────────────────────── -->
      <div class="card" style="border-color:var(--red-dim)">
        <div class="card-title" style="color:var(--red)">Danger Zone</div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="row-between">
            <div>
              <div style="font-size:13px;margin-bottom:2px">Remove all credentials</div>
              <div class="text-muted" style="font-size:11px">Deletes all four Keychain entries. Cannot be undone.</div>
            </div>
            <button class="btn btn-ghost btn-sm" id="btn-delete-all-creds"
              style="border-color:var(--red-dim);color:var(--red)">Delete all</button>
          </div>
        </div>
      </div>

      <!-- ── Inline status ───────────────────────────────────────────────── -->
      <div id="settings-status" style="display:none;margin-top:4px">
        <span id="settings-status-text" class="badge"></span>
      </div>

      <style>
        .settings-cred-row {
          display:flex; justify-content:space-between; align-items:center;
          min-height:48px; gap:12px;
        }
      </style>
    `;

    // ── Load and render credentials ─────────────────────────────────────────
    async function refreshCreds() {
      const [stake, anthropic, tgToken, tgChat] = await Promise.all([
        _keychainGet(ACCT.stakeToken),
        _keychainGet(ACCT.anthropicKey),
        _keychainGet(ACCT.telegramToken),
        _keychainGet(ACCT.telegramChatId),
      ]);

      _credRow(container, { label: 'Stake.com Access Token', account: ACCT.stakeToken,    value: stake,    hint: 'x-access-token header from Stake GraphQL requests' });
      _credRow(container, { label: 'Anthropic API Key',      account: ACCT.anthropicKey,   value: anthropic,hint: 'sk-ant-… — used for commentary in Phase 3' });
      _credRow(container, { label: 'Telegram Bot Token',     account: ACCT.telegramToken,  value: tgToken,  hint: 'optional — push notifications' });
      _credRow(container, { label: 'Telegram Chat ID',       account: ACCT.telegramChatId, value: tgChat,   hint: 'optional — target chat for notifications' });
    }
    refreshCreds();

    // ── Credential row buttons (delegated) ──────────────────────────────────
    container.addEventListener('click', async e => {
      // Edit / Replace → navigate to Credentials view
      const editBtn = e.target.closest('[data-edit]');
      if (editBtn) {
        window.App?.navigateTo('credentials');
        return;
      }

      // Delete single credential
      const deleteBtn = e.target.closest('[data-delete]');
      if (deleteBtn) {
        const account = deleteBtn.dataset.delete;
        if (!confirm(`Delete "${account}" from Keychain?`)) return;
        await _keychainDelete(account);
        _showStatus('ok', `✓ Deleted ${account}`);
        refreshCreds();
        return;
      }
    });

    // ── Engine controls ─────────────────────────────────────────────────────
    async function checkEngine() {
      const alive = await window.gambleAgent.engineAlive();
      const label = container.querySelector('#engine-alive-label');
      if (label) {
        label.textContent  = alive ? 'running' : 'offline';
        label.style.color  = alive ? 'var(--green)' : 'var(--red)';
      }
    }
    checkEngine();

    container.querySelector('#btn-check-engine').addEventListener('click', checkEngine);

    container.querySelector('#btn-restart-engine').addEventListener('click', async () => {
      const btn = container.querySelector('#btn-restart-engine');
      btn.disabled = true;
      btn.textContent = '⋯ Restarting…';
      await window.gambleAgent.engineRestart();
      setTimeout(async () => {
        await checkEngine();
        btn.disabled = false;
        btn.textContent = 'Restart';
        _showStatus('ok', '✓ Engine restarted');
      }, 1500);
    });

    // ── Data controls ───────────────────────────────────────────────────────
    container.querySelector('#btn-open-data-dir').addEventListener('click', () => {
      window.gambleAgent.openDataDir();
    });

    container.querySelector('#btn-clear-config').addEventListener('click', () => {
      if (!confirm('Clear saved session config? Defaults will be restored.')) return;
      localStorage.removeItem('gambleagent:session-config');
      _showStatus('ok', '✓ Session config cleared — defaults restored on next visit');
    });

    // ── Danger zone ─────────────────────────────────────────────────────────
    container.querySelector('#btn-delete-all-creds').addEventListener('click', async () => {
      if (!confirm('Delete ALL credentials from Keychain? You will need to re-enter them.')) return;
      await Promise.all(Object.values(ACCT).map(_keychainDelete));
      _showStatus('ok', '✓ All credentials removed');
      refreshCreds();
    });

    // ── Version ─────────────────────────────────────────────────────────────
    window.gambleAgent.getVersion().then(v => {
      const el = container.querySelector('#settings-version');
      if (el) el.textContent = `v${v}`;
    });

    // ── Status flash ─────────────────────────────────────────────────────────
    let _statusTimer = null;
    function _showStatus(kind, text) {
      const wrap = container.querySelector('#settings-status');
      const el   = container.querySelector('#settings-status-text');
      if (!wrap || !el) return;
      el.className   = `badge badge-${kind === 'ok' ? 'green' : 'red'}`;
      el.textContent = text;
      wrap.style.display = '';
      clearTimeout(_statusTimer);
      _statusTimer = setTimeout(() => { wrap.style.display = 'none'; }, 3000);
    }

    // Refresh on view activation
    document.addEventListener('view:activated', e => {
      if (e.detail.viewId === 'settings') {
        refreshCreds();
        checkEngine();
      }
    });
  }

  return { mount };
})();
