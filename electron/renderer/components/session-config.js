'use strict';

// Session Config view — full implementation in Task 2.4.
window.SessionConfigComponent = {
  mount(container) {
    container.innerHTML = `
      <div class="view-header">
        <h1>Session Config</h1>
        <p>Configure your session parameters. Settings auto-save and reload on next launch.</p>
      </div>

      <div class="placeholder-view" style="margin-top:40px">
        <div class="placeholder-icon">⚙️</div>
        <h2>Full config form — Task 2.4</h2>
        <p>
          Currency, targets, stop-loss, persona, games, vibes, notifications —
          all inputs will live here as a real form (sliders, toggles, game cards).
        </p>
      </div>
    `;
  }
};
