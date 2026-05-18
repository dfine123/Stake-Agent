'use strict';

// ── Router ────────────────────────────────────────────────────────────────────
// Simple hash-free SPA router. Each nav link carries data-view="<id>" which
// maps to <div id="view-<id>">.

const views = ['credentials', 'session-config', 'dashboard', 'debug-console', 'settings'];

function navigateTo(viewId) {
  // Deactivate all views and nav links
  views.forEach(id => {
    document.getElementById(`view-${id}`)?.classList.remove('active');
    document.querySelector(`[data-view="${id}"]`)?.classList.remove('active');
  });

  // Activate target
  const view = document.getElementById(`view-${viewId}`);
  const link = document.querySelector(`[data-view="${viewId}"]`);
  if (view) view.classList.add('active');
  if (link) link.classList.add('active');

  // Notify component
  document.dispatchEvent(new CustomEvent('view:activated', { detail: { viewId } }));
}

// Wire nav links
document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    navigateTo(link.dataset.view);
  });
});

// ── Version stamp ─────────────────────────────────────────────────────────────
window.gambleAgent.getVersion().then(v => {
  const el = document.getElementById('app-version');
  if (el) el.textContent = `v${v}`;
});

// ── Engine status ─────────────────────────────────────────────────────────────
// Minimal global state — each component manages its own deeper state.
const AppState = {
  engineStatus: 'idle',   // idle | running | error
  sessionActive: false,
  debugCount: 0,
};

function setEngineStatus(status, label) {
  AppState.engineStatus = status;
  const dot  = document.getElementById('engine-status-dot');
  const text = document.getElementById('engine-status-text');
  if (dot)  { dot.className = `status-dot ${status}`; }
  if (text) { text.textContent = label ?? status; }
}

function setDebugCount(n) {
  AppState.debugCount = n;
  const badge = document.getElementById('debug-count-badge');
  if (badge) badge.textContent = n > 99 ? '99+' : n;
}

function setSessionBadge(label) {
  const badge = document.getElementById('session-status-badge');
  if (badge) badge.textContent = label;
}

// Expose to components
window.App = { navigateTo, setEngineStatus, setSessionBadge, setDebugCount, AppState };

// ── Mount components ──────────────────────────────────────────────────────────
// Each component exports a mount(containerEl) function.
document.querySelectorAll('[data-component]').forEach(el => {
  const name = el.dataset.component;
  const components = {
    'credentials':    window.CredentialsComponent,
    'session-config': window.SessionConfigComponent,
    'dashboard':      window.DashboardComponent,
    'debug-console':  window.DebugConsoleComponent,
    'settings':       window.SettingsComponent,
  };
  const component = components[name];
  if (component?.mount) component.mount(el);
});

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // Cmd+Shift+D → Debug Console
  if (e.metaKey && e.shiftKey && e.key === 'D') {
    e.preventDefault();
    navigateTo('debug-console');
  }
});

// ── Initial route ─────────────────────────────────────────────────────────────
// If Stake token already saved in Keychain, skip straight to session-config.
// Otherwise land on credentials (first-launch onboarding).
(async () => {
  try {
    const saved = await window.gambleAgent.keychain.get('stake_access_token');
    navigateTo(saved ? 'session-config' : 'credentials');
  } catch {
    navigateTo('credentials');
  }
})();
