'use strict';

// Settings view — Task 2.7.
window.SettingsComponent = {
  mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Settings</h1>
        <p>App configuration, credential management, and data access.</p>
      </div>

      <div class="card">
        <div class="card-title">Data</div>
        <div class="row-between">
          <div>
            <div style="font-size:13px;margin-bottom:3px">App data folder</div>
            <div class="text-muted mono" style="font-size:11px">~/Library/Application Support/GambleAgent/</div>
          </div>
          <button class="btn btn-ghost btn-sm" id="btn-open-data-dir">Open in Finder ↗</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">About</div>
        <div style="font-size:13px;color:var(--text-secondary);line-height:1.8">
          <div class="row-between"><span>Version</span><span class="mono" id="settings-version">—</span></div>
          <div class="divider" style="margin:10px 0"></div>
          <div class="row-between"><span>Phase 1 engine</span><span class="badge badge-green">complete</span></div>
          <div class="row-between" style="margin-top:6px"><span>Phase 2 UI</span><span class="badge badge-gold">in progress</span></div>
        </div>
      </div>

      <div class="card coming-soon">
        <div class="card-title">Credentials</div>
        <p class="text-muted" style="font-size:13px">View masked / replace / delete stored Keychain entries — Task 2.7</p>
      </div>
    `;

    document.getElementById('btn-open-data-dir').addEventListener('click', () => {
      window.gambleAgent.openDataDir();
    });

    window.gambleAgent.getVersion().then(v => {
      const el = document.getElementById('settings-version');
      if (el) el.textContent = `v${v}`;
    });
  }
};
