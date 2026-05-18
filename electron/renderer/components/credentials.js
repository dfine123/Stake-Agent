'use strict';

// Credentials view — Task 2.3 will wire Keychain. Scaffolding only here.
window.CredentialsComponent = {
  mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Credentials</h1>
        <p>Your credentials are stored locally in macOS Keychain — never sent anywhere except the services they authenticate.</p>
      </div>

      <div class="card">
        <div class="card-title">Stake.com Access Token</div>
        <div class="field">
          <label>x-access-token</label>
          <input type="password" id="cred-stake-token" placeholder="Paste from DevTools → Network → any graphql request header" autocomplete="off">
          <div class="field-hint">
            Open Stake.com → F12 → Network → filter "graphql" → click any request → Headers → find x-access-token
          </div>
        </div>
        <div class="row">
          <button class="btn btn-ghost btn-sm" id="btn-test-stake">Test connection</button>
          <span class="badge badge-muted" id="stake-test-result" style="display:none"></span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Anthropic API Key</div>
        <div class="field">
          <label>API Key</label>
          <input type="password" id="cred-anthropic-key" placeholder="sk-ant-..." autocomplete="off">
          <div class="field-hint">
            Get yours at console.anthropic.com — used for session commentary (Phase 3)
          </div>
        </div>
        <div class="row">
          <button class="btn btn-ghost btn-sm" id="btn-test-anthropic">Test connection</button>
          <span class="badge badge-muted" id="anthropic-test-result" style="display:none"></span>
          <button class="btn btn-ghost btn-sm" id="btn-open-anthropic">Open console ↗</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title" style="cursor:pointer" id="telegram-toggle">
          Telegram Notifications <span style="float:right;font-size:11px;font-weight:400;color:var(--text-muted)">optional ▸</span>
        </div>
        <div id="telegram-fields" style="display:none">
          <div class="field">
            <label>Bot Token</label>
            <input type="password" id="cred-telegram-token" placeholder="110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" autocomplete="off">
          </div>
          <div class="field">
            <label>Chat ID</label>
            <input type="text" id="cred-telegram-chat" placeholder="-1001234567890" autocomplete="off">
          </div>
        </div>
      </div>

      <div class="row" style="margin-top:8px">
        <button class="btn btn-primary" id="btn-save-creds" disabled>Save &amp; Continue →</button>
        <span class="text-muted" style="font-size:12px">IPC not yet wired — save will enable in Task 2.3</span>
      </div>
    `;

    // Telegram accordion
    document.getElementById('telegram-toggle').addEventListener('click', () => {
      const fields = document.getElementById('telegram-fields');
      fields.style.display = fields.style.display === 'none' ? 'block' : 'none';
    });

    // Anthropic console link
    document.getElementById('btn-open-anthropic').addEventListener('click', () => {
      window.gambleAgent.openExternal('https://console.anthropic.com');
    });

    // Placeholder: enable save once both required fields have content
    const stakeInput = document.getElementById('cred-stake-token');
    const anthropicInput = document.getElementById('cred-anthropic-key');
    const saveBtn = document.getElementById('btn-save-creds');

    function checkFields() {
      saveBtn.disabled = !(stakeInput.value.trim() && anthropicInput.value.trim());
    }

    stakeInput.addEventListener('input', checkFields);
    anthropicInput.addEventListener('input', checkFields);
  }
};
