'use strict';

window.SessionConfigComponent = (() => {
  const STORAGE_KEY = 'gambleagent:session-config';

  // ── Default config ──────────────────────────────────────────────────────────
  const DEFAULTS = {
    currency:             'usdt',
    top_target_usd:       500,
    secondary_target_usd: 250,
    persona:              'steady',
    games_enabled:        ['dice', 'limbo', 'keno'],
    stop_loss: {
      enabled: false,
      mode:    'fixed_floor',
      value:   0,
    },
    vibes: {
      text:                '',
      lucky_numbers:       '',   // comma-separated string in UI, parsed on launch
      bake_into_seed:      true,
      influence_game_choice: true,
    },
    dry_run: false,
  };

  // ── Persistence ─────────────────────────────────────────────────────────────

  function _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
    } catch { return { ...DEFAULTS }; }
  }

  function _save(cfg) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)); } catch { /* quota */ }
  }

  // ── Expose config for other components (dashboard) ──────────────────────────
  // window.SessionConfig.get() returns the current saved config.
  window.SessionConfig = { get: _load };

  // ── Game catalogue ──────────────────────────────────────────────────────────
  const GAMES = [
    { id: 'dice',         label: 'Dice',         icon: '🎲', desc: 'Roll above/below a target',    phase3: false },
    { id: 'limbo',        label: 'Limbo',         icon: '📈', desc: 'Multiplier crash at target',   phase3: false },
    { id: 'keno',         label: 'Keno',          icon: '🔢', desc: 'Pick numbers, match the draw', phase3: false },
    { id: 'mines',        label: 'Mines',         icon: '💣', desc: 'Navigate the minefield',       phase3: true  },
    { id: 'plinko',       label: 'Plinko',        icon: '🪄', desc: 'Watch the ball drop',          phase3: true  },
    { id: 'wheel',        label: 'Wheel',         icon: '🎡', desc: 'Spin the wheel',               phase3: true  },
    { id: 'crash',        label: 'Crash',         icon: '🚀', desc: 'Cash out before it crashes',   phase3: true  },
    { id: 'hilo',         label: 'HiLo',          icon: '🃏', desc: 'Higher or lower',              phase3: true  },
    { id: 'dragon_tower', label: 'Dragon Tower',  icon: '🐉', desc: 'Climb the tower',              phase3: true  },
    { id: 'diamonds',     label: 'Diamonds',      icon: '💎', desc: 'Find the diamonds',            phase3: true  },
    { id: 'video_poker',  label: 'Video Poker',   icon: '♠️', desc: 'Classic poker hand',           phase3: true  },
    { id: 'scarab_spin',  label: 'Scarab Spin',   icon: '🪲', desc: 'Slot-style spins',             phase3: true  },
  ];

  // ── Persona catalogue ───────────────────────────────────────────────────────
  const PERSONAS = [
    { id: 'chill',        label: 'Chill',         desc: 'Small bets, long sessions, low variance',          phase3: true  },
    { id: 'steady',       label: 'Steady',        desc: 'Balanced — moderate bets, light recovery',         phase3: false },
    { id: 'degen',        label: 'Degen',         desc: 'Bigger swings, aggressive Martingale',             phase3: true  },
    { id: 'extreme_degen',label: 'Extreme Degen', desc: 'Max aggression — all-in energy, high variance',    phase3: true  },
  ];

  // ── Currencies ──────────────────────────────────────────────────────────────
  const CURRENCIES = ['usdt', 'btc', 'eth', 'sol', 'ltc', 'doge', 'trx'];

  // ── Stop-loss modes ─────────────────────────────────────────────────────────
  const SL_MODES = [
    { id: 'fixed_floor',      label: 'Fixed floor',             hint: 'Stop if balance drops below this USD amount' },
    { id: 'pct_of_start',     label: '% of starting balance',   hint: 'Stop after losing this % of starting balance' },
    { id: 'session_loss_cap', label: 'Session loss cap',        hint: 'Stop after losing this USD in one session' },
  ];

  // ── Render ──────────────────────────────────────────────────────────────────

  function _gameCards(cfg) {
    return GAMES.map(g => {
      const active  = cfg.games_enabled.includes(g.id);
      const p3class = g.phase3 ? 'coming-soon' : '';
      return `
        <div class="game-card ${active ? 'active' : ''} ${p3class}"
             data-game="${g.id}" ${g.phase3 ? '' : 'tabindex="0"'}>
          <div class="game-icon">${g.icon}</div>
          <div class="game-label">${g.label}</div>
          <div class="game-desc">${g.desc}</div>
          ${active && !g.phase3 ? '<div class="game-check">✓</div>' : ''}
        </div>`;
    }).join('');
  }

  function _personaCards(cfg) {
    return PERSONAS.map(p => {
      const active  = cfg.persona === p.id;
      const p3class = p.phase3 ? 'coming-soon' : '';
      return `
        <div class="persona-card ${active ? 'active' : ''} ${p3class}"
             data-persona="${p.id}" ${p.phase3 ? '' : 'tabindex="0"'}>
          <div class="persona-label">${p.label}</div>
          <div class="persona-desc">${p.desc}</div>
        </div>`;
    }).join('');
  }

  function _slValueLabel(mode) {
    return mode === 'pct_of_start' ? '%' : 'USD';
  }

  function mount(container) {
    const cfg = _load();

    container.innerHTML = `
      <div class="view-header">
        <div class="row-between">
          <div>
            <h1>Session Config</h1>
            <p>Configure your session. Settings auto-save — pick up exactly where you left off.</p>
          </div>
          <button class="btn btn-primary" id="sc-launch-btn">Launch Session →</button>
        </div>
      </div>

      <!-- ── Currency ──────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Currency</div>
        <div class="sc-pill-row" id="sc-currency-row">
          ${CURRENCIES.map(c => `
            <button class="pill-btn ${cfg.currency === c ? 'active' : ''}" data-currency="${c}">
              ${c.toUpperCase()}
            </button>`).join('')}
        </div>
        <div class="field-hint" style="margin-top:8px">
          Must match the currency of your Stake wallet balance. Targets are always denominated in USD.
        </div>
      </div>

      <!-- ── Targets ───────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Targets</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div class="field" style="margin-bottom:0">
            <label>Primary target (USD)</label>
            <div style="position:relative">
              <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:13px">$</span>
              <input type="number" id="sc-top-target" min="1" step="1"
                style="padding-left:24px"
                value="${cfg.top_target_usd}">
            </div>
            <div class="field-hint">Session ends when this is hit — vault triggered automatically</div>
          </div>
          <div class="field" style="margin-bottom:0">
            <label>Secondary target (USD)</label>
            <div style="position:relative">
              <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:13px">$</span>
              <input type="number" id="sc-secondary-target" min="1" step="1"
                style="padding-left:24px"
                value="${cfg.secondary_target_usd}">
            </div>
            <div class="field-hint">Partial vault at this balance — keeps you playing</div>
          </div>
        </div>
      </div>

      <!-- ── Persona ───────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Persona</div>
        <div class="persona-grid" id="sc-persona-grid">
          ${_personaCards(cfg)}
        </div>
      </div>

      <!-- ── Games ─────────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Games</div>
        <div class="game-grid" id="sc-game-grid">
          ${_gameCards(cfg)}
        </div>
        <div class="field-hint" style="margin-top:12px" id="sc-game-hint"></div>
      </div>

      <!-- ── Stop Loss ─────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Stop Loss</div>
        <div class="row" style="margin-bottom:16px">
          <label class="toggle-row">
            <input type="checkbox" id="sc-sl-enabled" ${cfg.stop_loss.enabled ? 'checked' : ''}>
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span class="toggle-label">Enable stop loss</span>
          </label>
        </div>
        <div id="sc-sl-fields" style="display:${cfg.stop_loss.enabled ? 'block' : 'none'}">
          <div style="display:grid;grid-template-columns:1fr auto;gap:16px;align-items:end">
            <div class="field" style="margin-bottom:0">
              <label>Mode</label>
              <select id="sc-sl-mode">
                ${SL_MODES.map(m => `
                  <option value="${m.id}" ${cfg.stop_loss.mode === m.id ? 'selected' : ''}>${m.label}</option>
                `).join('')}
              </select>
            </div>
            <div class="field" style="margin-bottom:0;min-width:120px">
              <label>Value <span id="sc-sl-unit" style="font-weight:400;color:var(--text-muted)">${_slValueLabel(cfg.stop_loss.mode)}</span></label>
              <input type="number" id="sc-sl-value" min="0" step="1"
                value="${cfg.stop_loss.value}">
            </div>
          </div>
          <div class="field-hint" style="margin-top:8px" id="sc-sl-hint">
            ${SL_MODES.find(m => m.id === cfg.stop_loss.mode)?.hint ?? ''}
          </div>
        </div>
      </div>

      <!-- ── Vibes ─────────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Vibes</div>
        <div class="field">
          <label>Vibe text <span style="font-weight:400;color:var(--text-muted)">optional — interpreted into client seed</span></label>
          <textarea id="sc-vibes-text" rows="2"
            placeholder="feeling lucky today, risky, full send, steady grind…"
            style="resize:vertical">${cfg.vibes.text}</textarea>
        </div>
        <div class="field">
          <label>Lucky numbers <span style="font-weight:400;color:var(--text-muted)">optional — comma separated</span></label>
          <input type="text" id="sc-lucky-numbers"
            placeholder="7, 13, 42, 88"
            value="${cfg.vibes.lucky_numbers}">
        </div>
        <div style="display:flex;flex-direction:column;gap:10px">
          <label class="toggle-row">
            <input type="checkbox" id="sc-bake-seed" ${cfg.vibes.bake_into_seed ? 'checked' : ''}>
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span class="toggle-label">Bake into client seed</span>
          </label>
          <label class="toggle-row">
            <input type="checkbox" id="sc-influence-game" ${cfg.vibes.influence_game_choice ? 'checked' : ''}>
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span class="toggle-label">Influence game selection weights</span>
          </label>
        </div>
      </div>

      <!-- ── Options ───────────────────────────────────────────────────────── -->
      <div class="card">
        <div class="card-title">Options</div>
        <label class="toggle-row">
          <input type="checkbox" id="sc-dry-run" ${cfg.dry_run ? 'checked' : ''}>
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
          <span class="toggle-label">
            Dry run — simulate bets without placing them
            <span style="font-size:11px;color:var(--gold);margin-left:6px">no real money at risk</span>
          </span>
        </label>
      </div>

      <!-- ── Validation banner ──────────────────────────────────────────────── -->
      <div id="sc-error-banner" style="display:none;margin-bottom:16px">
        <div style="background:var(--red-glow);border:1px solid var(--red-dim);border-radius:var(--radius-lg);padding:12px 16px;font-size:13px;color:var(--red)" id="sc-error-text"></div>
      </div>

      <style>
        /* ── Pill buttons (currency) ─── */
        .sc-pill-row { display:flex; flex-wrap:wrap; gap:8px; }
        .pill-btn {
          padding:5px 14px; border-radius:20px; font-size:12px; font-family:var(--font-mono);
          font-weight:600; cursor:pointer; border:1px solid var(--border-strong);
          background:transparent; color:var(--text-secondary);
          transition:background 0.12s,color 0.12s,border-color 0.12s;
        }
        .pill-btn:hover  { background:var(--bg-hover); color:var(--text-primary); }
        .pill-btn.active { background:var(--green-glow); color:var(--green); border-color:var(--green-dim); }

        /* ── Persona cards ─── */
        .persona-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
        .persona-card {
          padding:14px 12px; border-radius:var(--radius-md); border:1px solid var(--border-strong);
          cursor:pointer; transition:all 0.12s; position:relative;
        }
        .persona-card:hover:not(.coming-soon) { background:var(--bg-hover); border-color:var(--border-strong); }
        .persona-card.active { background:var(--green-glow); border-color:var(--green-dim); }
        .persona-label { font-size:13px; font-weight:600; margin-bottom:4px; }
        .persona-desc  { font-size:11px; color:var(--text-muted); line-height:1.4; }

        /* ── Game cards ─── */
        .game-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:8px; }
        .game-card {
          padding:12px 8px; border-radius:var(--radius-md); border:1px solid var(--border);
          cursor:pointer; transition:all 0.12s; text-align:center; position:relative;
        }
        .game-card:hover:not(.coming-soon) { background:var(--bg-hover); border-color:var(--border-strong); }
        .game-card.active  { background:var(--green-glow); border-color:var(--green-dim); }
        .game-icon  { font-size:20px; margin-bottom:4px; }
        .game-label { font-size:12px; font-weight:600; }
        .game-desc  { font-size:10px; color:var(--text-muted); margin-top:2px; line-height:1.3; }
        .game-check {
          position:absolute; top:6px; right:6px; font-size:10px;
          color:var(--green); font-weight:700;
        }

        /* ── Toggle ─── */
        .toggle-row { display:flex; align-items:center; gap:10px; cursor:pointer; user-select:none; }
        .toggle-track {
          width:32px; height:18px; border-radius:9px; background:var(--bg-elevated);
          border:1px solid var(--border-strong); position:relative; flex-shrink:0;
          transition:background 0.15s,border-color 0.15s;
        }
        .toggle-thumb {
          position:absolute; top:2px; left:2px; width:12px; height:12px;
          border-radius:50%; background:var(--text-muted); transition:transform 0.15s,background 0.15s;
        }
        input[type="checkbox"]:checked + .toggle-track { background:var(--green-glow); border-color:var(--green-dim); }
        input[type="checkbox"]:checked + .toggle-track .toggle-thumb { transform:translateX(14px); background:var(--green); }
        input[type="checkbox"] { display:none; }
        .toggle-label { font-size:13px; color:var(--text-secondary); }

        @media (max-width:1100px) {
          .game-grid    { grid-template-columns:repeat(4,1fr); }
          .persona-grid { grid-template-columns:repeat(2,1fr); }
        }
      </style>
    `;

    // ── Live state object (kept in sync with form, persisted on every change) ─
    let state = _load();

    function _persist() { _save(state); }

    function _showError(msg) {
      const banner = container.querySelector('#sc-error-banner');
      const text   = container.querySelector('#sc-error-text');
      if (msg) { banner.style.display = ''; text.textContent = msg; }
      else      { banner.style.display = 'none'; }
    }

    // ── Currency ────────────────────────────────────────────────────────────
    container.querySelector('#sc-currency-row').addEventListener('click', e => {
      const btn = e.target.closest('[data-currency]');
      if (!btn) return;
      state.currency = btn.dataset.currency;
      container.querySelectorAll('[data-currency]').forEach(b =>
        b.classList.toggle('active', b.dataset.currency === state.currency));
      _persist();
    });

    // ── Targets ────────────────────────────────────────────────────────────
    container.querySelector('#sc-top-target').addEventListener('input', e => {
      state.top_target_usd = parseFloat(e.target.value) || 0;
      _persist();
    });
    container.querySelector('#sc-secondary-target').addEventListener('input', e => {
      state.secondary_target_usd = parseFloat(e.target.value) || 0;
      _persist();
    });

    // ── Persona ────────────────────────────────────────────────────────────
    container.querySelector('#sc-persona-grid').addEventListener('click', e => {
      const card = e.target.closest('[data-persona]');
      if (!card || card.classList.contains('coming-soon')) return;
      state.persona = card.dataset.persona;
      container.querySelectorAll('[data-persona]').forEach(c =>
        c.classList.toggle('active', c.dataset.persona === state.persona));
      _persist();
    });

    // ── Games ──────────────────────────────────────────────────────────────
    function _updateGameHint() {
      const hint = container.querySelector('#sc-game-hint');
      const n    = state.games_enabled.length;
      hint.textContent = n === 0
        ? 'Select at least one game.'
        : `${n} game${n > 1 ? 's' : ''} enabled — the persona will rotate between them.`;
    }
    _updateGameHint();

    container.querySelector('#sc-game-grid').addEventListener('click', e => {
      const card = e.target.closest('[data-game]');
      if (!card || card.classList.contains('coming-soon')) return;
      const id = card.dataset.game;
      const idx = state.games_enabled.indexOf(id);
      if (idx === -1) {
        state.games_enabled.push(id);
        card.classList.add('active');
        // add check mark
        if (!card.querySelector('.game-check')) {
          const chk = document.createElement('div');
          chk.className = 'game-check';
          chk.textContent = '✓';
          card.appendChild(chk);
        }
      } else {
        if (state.games_enabled.length === 1) return; // keep at least one
        state.games_enabled.splice(idx, 1);
        card.classList.remove('active');
        card.querySelector('.game-check')?.remove();
      }
      _updateGameHint();
      _persist();
    });

    // ── Stop Loss ──────────────────────────────────────────────────────────
    const slEnabled = container.querySelector('#sc-sl-enabled');
    const slFields  = container.querySelector('#sc-sl-fields');
    const slMode    = container.querySelector('#sc-sl-mode');
    const slValue   = container.querySelector('#sc-sl-value');
    const slUnit    = container.querySelector('#sc-sl-unit');
    const slHint    = container.querySelector('#sc-sl-hint');

    slEnabled.addEventListener('change', () => {
      state.stop_loss.enabled = slEnabled.checked;
      slFields.style.display = slEnabled.checked ? 'block' : 'none';
      _persist();
    });
    slMode.addEventListener('change', () => {
      state.stop_loss.mode = slMode.value;
      slUnit.textContent   = _slValueLabel(slMode.value);
      slHint.textContent   = SL_MODES.find(m => m.id === slMode.value)?.hint ?? '';
      _persist();
    });
    slValue.addEventListener('input', () => {
      state.stop_loss.value = parseFloat(slValue.value) || 0;
      _persist();
    });

    // ── Vibes ──────────────────────────────────────────────────────────────
    container.querySelector('#sc-vibes-text').addEventListener('input', e => {
      state.vibes.text = e.target.value;
      _persist();
    });
    container.querySelector('#sc-lucky-numbers').addEventListener('input', e => {
      state.vibes.lucky_numbers = e.target.value;
      _persist();
    });
    container.querySelector('#sc-bake-seed').addEventListener('change', e => {
      state.vibes.bake_into_seed = e.target.checked;
      _persist();
    });
    container.querySelector('#sc-influence-game').addEventListener('change', e => {
      state.vibes.influence_game_choice = e.target.checked;
      _persist();
    });

    // ── Dry run ────────────────────────────────────────────────────────────
    container.querySelector('#sc-dry-run').addEventListener('change', e => {
      state.dry_run = e.target.checked;
      _persist();
    });

    // ── Launch ─────────────────────────────────────────────────────────────
    container.querySelector('#sc-launch-btn').addEventListener('click', () => {
      const err = _validate(state);
      if (err) { _showError(err); return; }
      _showError(null);
      _persist();
      window.App?.navigateTo('dashboard');
    });
  }

  // ── Validation ─────────────────────────────────────────────────────────────
  function _validate(cfg) {
    if (cfg.top_target_usd <= 0)
      return 'Primary target must be greater than $0.';
    if (cfg.secondary_target_usd <= 0)
      return 'Secondary target must be greater than $0.';
    if (cfg.secondary_target_usd >= cfg.top_target_usd)
      return 'Secondary target must be less than primary target.';
    if (cfg.games_enabled.length === 0)
      return 'Select at least one game.';
    if (cfg.stop_loss.enabled) {
      if (cfg.stop_loss.value <= 0)
        return 'Stop-loss value must be greater than 0 when enabled.';
      if (cfg.stop_loss.mode === 'pct_of_start' && cfg.stop_loss.value >= 100)
        return 'Stop-loss percent must be less than 100.';
    }
    return null;
  }

  return { mount };
})();
