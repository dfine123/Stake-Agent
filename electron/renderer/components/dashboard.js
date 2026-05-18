'use strict';

// Dashboard view — full implementation in Task 2.5.
window.DashboardComponent = {
  mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Dashboard</h1>
        <p>Live session view — start a session from Session Config to activate.</p>
      </div>

      <div class="placeholder-view" style="margin-top:40px">
        <div class="placeholder-icon">📊</div>
        <h2>Live dashboard — Task 2.5</h2>
        <p>
          Balance, vault, progress to target, live bet feed, GO/PAUSE/STOP/PANIC controls,
          avatar placeholder, session stats.
        </p>
      </div>
    `;
  }
};
