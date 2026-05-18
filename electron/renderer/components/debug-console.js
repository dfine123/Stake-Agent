'use strict';

// Debug Console — Task 2.6 builds the full implementation.
// Even in scaffolding, Cmd+Shift+D navigates here (wired in app.js).
window.DebugConsoleComponent = {
  mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <div class="row-between">
          <div>
            <h1>Debug Console</h1>
            <p>Raw IPC messages and Stake GraphQL traffic. Shortcut: <span class="mono">⌘⇧D</span></p>
          </div>
          <span class="badge badge-muted">Task 2.6</span>
        </div>
      </div>

      <div class="placeholder-view" style="margin-top:40px">
        <div class="placeholder-icon">🔬</div>
        <h2>Debug console — Task 2.6</h2>
        <p>
          Last 100 IPC messages, last 50 Stake GraphQL requests with full request/response bodies,
          latency, "Copy as cURL", and session log export.
          <br><br>
          <strong style="color:var(--text-primary)">This is a first-class feature</strong> —
          required for debugging the first live Stake API session.
        </p>
      </div>
    `;
  }
};
