'use strict';

window.CredentialsComponent = (() => {
  // Keychain account names — these are the keys stored under com.gambleagent.app
  const ACCT = {
    stakeToken:      'stake_access_token',
    anthropicKey:    'anthropic_api_key',
    telegramToken:   'telegram_bot_token',
    telegramChatId:  'telegram_chat_id',
  };

  // ── Keychain helpers ──────────────────────────────────────────────────────

  async function _keychainGet(account) {
    try { return await window.gambleAgent.keychain.get(account); }
    catch { return null; }
  }

  async function _keychainSet(account, value) {
    if (value) {
      await window.gambleAgent.keychain.set(account, value);
    } else {
      try { await window.gambleAgent.keychain.delete(account); } catch { /* already absent */ }
    }
  }

  // ── Test helpers ──────────────────────────────────────────────────────────

  function _setTestResult(el, state, text) {
    // state: 'loading' | 'ok' | 'error' | 'warn' | 'idle'
    el.style.display = state === 'idle' ? 'none' : '';
    el.className = 'badge ' + ({
      loading: 'badge-muted',
      ok:      'badge-green',
      error:   'badge-red',
      warn:    'badge-gold',
    }[state] ?? 'badge-muted');
    el.textContent = text;
  }

  async function _testStake(token, resultEl, btnEl) {
    if (!token) {
      _setTestResult(resultEl, 'error', '✗ enter a token first');
      return;
    }
    btnEl.disabled = true;
    _setTestResult(resultEl, 'loading', '⋯ connecting…');

    const res = await window.gambleAgent.engineSend('preflight', {
      stake_access_token: token,
      currency: 'usdt',
    }, 20_000);

    btnEl.disabled = false;
    if (res.ok) {
      const bal = parseFloat(res.payload.balance ?? 0).toFixed(4);
      const usd = parseFloat(res.payload.balance_usd ?? 0).toFixed(2);
      _setTestResult(resultEl, 'ok', `✓ connected — ${bal} USDT ($${usd})`);
    } else {
      const msg = res.error ?? 'unknown error';
      _setTestResult(resultEl, 'error', `✗ ${msg.slice(0, 80)}`);
    }
  }

  function _testAnthropic(key, resultEl) {
    if (!key) {
      _setTestResult(resultEl, 'error', '✗ enter a key first');
      return;
    }
    // Format check only — live test happens in Phase 3 when commentary is used
    if (key.startsWith('sk-ant-')) {
      _setTestResult(resultEl, 'warn', '✓ format ok — live test in Phase 3');
    } else {
      _setTestResult(resultEl, 'error', '✗ expected sk-ant-… prefix');
    }
  }

  // ── Mount ─────────────────────────────────────────────────────────────────

  function mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Credentials</h1>
        <p>Stored in macOS Keychain — never logged, never sent anywhere except the services they authenticate.</p>
      </div>

      <div id="cred-first-launch-banner" style="display:none;margin-bottom:20px">
        <div style="background:var(--green-glow);border:1px solid var(--green-dim);border-radius:var(--radius-lg);padding:14px 18px;font-size:13px;color:var(--green)">
          <strong>Welcome to GambleAgent.</strong>
          Enter your Stake access token below to get started. You can get it from your browser's DevTools on any Stake GraphQL request.
        </div>
      </div>

      <!-- ── Stake token ───────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Stake.com Access Token <span id="stake-saved-pill" style="display:none;margin-left:8px;font-size:10px;font-weight:500;color:var(--green);letter-spacing:0;text-transform:none">● saved</span></div>
        <div class="field">
          <label>x-access-token</label>
          <div style="position:relative">
            <input type="password" id="cred-stake-token"
              placeholder="Paste from DevTools → Network → any graphql request → Headers"
              autocomplete="off" spellcheck="false">
            <button class="btn btn-ghost btn-sm" id="btn-stake-reveal"
              style="position:absolute;right:6px;top:50%;transform:translateY(-50%);padding:3px 8px;font-size:11px"
              title="Show / hide">👁</button>
          </div>
          <div class="field-hint">
            Stake.com → F12 → Network → filter "graphql" → any request → Headers tab → x-access-token
          </div>
        </div>
        <div class="row" style="gap:8px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" id="btn-test-stake">Test connection</button>
          <span class="badge badge-muted" id="stake-test-result" style="display:none"></span>
        </div>
      </div>

      <!-- ── Anthropic key ─────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Anthropic API Key <span style="font-size:10px;font-weight:400;color:var(--text-muted);text-transform:none;letter-spacing:0">used for session commentary</span> <span id="anthropic-saved-pill" style="display:none;margin-left:8px;font-size:10px;font-weight:500;color:var(--green);letter-spacing:0;text-transform:none">● saved</span></div>
        <div class="field">
          <label>API Key</label>
          <div style="position:relative">
            <input type="password" id="cred-anthropic-key"
              placeholder="sk-ant-api03-…"
              autocomplete="off" spellcheck="false">
            <button class="btn btn-ghost btn-sm" id="btn-anthropic-reveal"
              style="position:absolute;right:6px;top:50%;transform:translateY(-50%);padding:3px 8px;font-size:11px"
              title="Show / hide">👁</button>
          </div>
          <div class="field-hint">
            Get yours at console.anthropic.com — leave blank for now, required in Phase 3
          </div>
        </div>
        <div class="row" style="gap:8px">
          <button class="btn btn-ghost btn-sm" id="btn-test-anthropic">Validate format</button>
          <span class="badge badge-muted" id="anthropic-test-result" style="display:none"></span>
          <button class="btn btn-ghost btn-sm" id="btn-open-anthropic" style="margin-left:auto">Open console ↗</button>
        </div>
      </div>

      <!-- ── Telegram (optional) ───────────────────────────────────────────── -->
      <div class="card" style="padding-bottom:0">
        <div class="card-title" id="telegram-toggle" style="cursor:pointer;margin-bottom:0;padding-bottom:16px">
          Telegram Notifications
          <span id="telegram-saved-pill" style="display:none;margin-left:8px;font-size:10px;font-weight:500;color:var(--green);letter-spacing:0;text-transform:none">● saved</span>
          <span style="float:right;font-size:11px;font-weight:400;color:var(--text-muted);text-transform:none;letter-spacing:0" id="telegram-chevron">optional ▸</span>
        </div>
        <div id="telegram-fields" style="display:none;padding-top:8px;border-top:1px solid var(--border)">
          <div class="field" style="margin-top:16px">
            <label>Bot Token</label>
            <input type="password" id="cred-telegram-token"
              placeholder="110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
              autocomplete="off">
          </div>
          <div class="field">
            <label>Chat ID</label>
            <input type="text" id="cred-telegram-chat"
              placeholder="-1001234567890"
              autocomplete="off">
            <div class="field-hint">Get chat ID by messaging @userinfobot on Telegram</div>
          </div>
          <div style="padding-bottom:16px"></div>
        </div>
      </div>

      <!-- ── Save ──────────────────────────────────────────────────────────── -->
      <div class="row" style="margin-top:20px;gap:12px">
        <button class="btn btn-primary" id="btn-save-creds" disabled>Save to Keychain →</button>
        <span id="save-status" class="badge" style="display:none"></span>
      </div>
    `;

    // ── Element refs ────────────────────────────────────────────────────────
    const stakeInput     = container.querySelector('#cred-stake-token');
    const anthropicInput = container.querySelector('#cred-anthropic-key');
    const telegramToken  = container.querySelector('#cred-telegram-token');
    const telegramChat   = container.querySelector('#cred-telegram-chat');
    const saveBtn        = container.querySelector('#btn-save-creds');
    const saveStatus     = container.querySelector('#save-status');
    const stakeResult    = container.querySelector('#stake-test-result');
    const anthropicResult= container.querySelector('#anthropic-test-result');
    const stakeSavedPill = container.querySelector('#stake-saved-pill');
    const anthropicSavedPill = container.querySelector('#anthropic-saved-pill');
    const telegramSavedPill  = container.querySelector('#telegram-saved-pill');
    const banner         = container.querySelector('#cred-first-launch-banner');

    // ── Save button gating ──────────────────────────────────────────────────
    function _updateSaveBtn() {
      saveBtn.disabled = !stakeInput.value.trim();
    }
    stakeInput.addEventListener('input', _updateSaveBtn);

    // ── Reveal toggles ──────────────────────────────────────────────────────
    function _wireReveal(btnId, inputEl) {
      container.querySelector(btnId).addEventListener('click', () => {
        inputEl.type = inputEl.type === 'password' ? 'text' : 'password';
      });
    }
    _wireReveal('#btn-stake-reveal',    stakeInput);
    _wireReveal('#btn-anthropic-reveal', anthropicInput);

    // ── Telegram accordion ──────────────────────────────────────────────────
    container.querySelector('#telegram-toggle').addEventListener('click', () => {
      const fields   = container.querySelector('#telegram-fields');
      const chevron  = container.querySelector('#telegram-chevron');
      const open = fields.style.display === 'none';
      fields.style.display  = open ? 'block' : 'none';
      chevron.textContent   = open ? 'optional ▾' : 'optional ▸';
    });

    // ── Test buttons ────────────────────────────────────────────────────────
    const testStakeBtn = container.querySelector('#btn-test-stake');
    testStakeBtn.addEventListener('click', () =>
      _testStake(stakeInput.value.trim(), stakeResult, testStakeBtn));

    container.querySelector('#btn-test-anthropic').addEventListener('click', () =>
      _testAnthropic(anthropicInput.value.trim(), anthropicResult));

    // ── Anthropic console link ───────────────────────────────────────────────
    container.querySelector('#btn-open-anthropic').addEventListener('click', () =>
      window.gambleAgent.openExternal('https://console.anthropic.com'));

    // ── Save ────────────────────────────────────────────────────────────────
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      _setTestResult(saveStatus, 'loading', '⋯ saving…');

      try {
        await _keychainSet(ACCT.stakeToken,     stakeInput.value.trim());
        await _keychainSet(ACCT.anthropicKey,   anthropicInput.value.trim());
        await _keychainSet(ACCT.telegramToken,  telegramToken.value.trim());
        await _keychainSet(ACCT.telegramChatId, telegramChat.value.trim());

        _setTestResult(saveStatus, 'ok', '✓ saved to Keychain');
        _showSavedPills(stakeInput.value.trim(), anthropicInput.value.trim(),
                        telegramToken.value.trim() && telegramChat.value.trim());

        // Navigate to session config after a brief pause
        setTimeout(() => window.App?.navigateTo('session-config'), 800);
      } catch (err) {
        _setTestResult(saveStatus, 'error', `✗ ${err.message}`);
        saveBtn.disabled = false;
      }
    });

    // ── Saved-pill helper ───────────────────────────────────────────────────
    function _showSavedPills(hasStake, hasAnthropic, hasTelegram) {
      stakeSavedPill.style.display    = hasStake    ? '' : 'none';
      anthropicSavedPill.style.display= hasAnthropic? '' : 'none';
      telegramSavedPill.style.display = hasTelegram ? '' : 'none';
    }

    // ── Load from Keychain on mount ─────────────────────────────────────────
    (async () => {
      const [stake, anthropic, tgToken, tgChat] = await Promise.all([
        _keychainGet(ACCT.stakeToken),
        _keychainGet(ACCT.anthropicKey),
        _keychainGet(ACCT.telegramToken),
        _keychainGet(ACCT.telegramChatId),
      ]);

      const isFirstLaunch = !stake;
      banner.style.display = isFirstLaunch ? '' : 'none';

      if (stake)    stakeInput.value     = stake;
      if (anthropic)anthropicInput.value = anthropic;
      if (tgToken)  telegramToken.value  = tgToken;
      if (tgChat)   telegramChat.value   = tgChat;

      // Show "saved" pills next to each section header
      _showSavedPills(!!stake, !!anthropic, !!(tgToken && tgChat));

      _updateSaveBtn();

      if (stake) {
        // Credentials already exist — change button label and let user continue
        saveBtn.textContent = 'Update & Continue →';
      }
    })();
  }

  return { mount };
})();
