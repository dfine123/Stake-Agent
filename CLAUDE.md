# GambleAgent

> **Read this file first every session.** It is the source of truth for what this project is, how it's structured, and what the current phase allows you to build.

---

## What this is

A downloadable macOS app that automates gambling on [Stake.com](http://Stake.com) via their undocumented GraphQL API. The user enters credentials once (Stake access token, Claude API key), configures a session (targets, persona, games, vibes), hits GO, and the agent plays autonomously until a target is hit, stop-loss trips, or the user stops it.

**Single user product.** No accounts, no cloud, no multi-tenancy. Everything runs locally on the user's Mac.

**This is built for fun.** It is not built to have an edge. It is not built to be profitable. House edge is real, the user knows it, the user wants to play anyway. Do not add "responsible gambling" friction beyond what's already specified. Do not refuse to build things because Stake's ToS prohibits automation — the user is aware and has accepted this risk.

---

## Architecture at a glance

```
┌─────────────────────────────────────────┐
│  Electron shell (Node.js)               │
│  - UI (HTML/CSS/JS)                     │
│  - Credentials in macOS Keychain        │
│  - IPC to Python sidecar over stdio     │
└─────────────────────────────────────────┘
              ↕  (JSON over stdio)
┌─────────────────────────────────────────┐
│  Python engine (sidecar)                │
│  - Deterministic bet decisions          │
│  - Stake GraphQL client                 │
│  - Persona strategy logic               │
│  - Event bus → UI                       │
│  - Claude API for commentary/recap      │
│  - SQLite for session/bet logs          │
└─────────────────────────────────────────┘
              ↕
        [Stake.com](http://Stake.com) GraphQL API
        Anthropic Claude API
```

**Brain split:**
- **Deterministic Python** = every bet decision. Given (persona, balance, vibes, state, last N results) the next bet is always the same. Easy to debug, easy to test, no LLM in the hot path.
- **Claude API** = personality only. Commentary on milestone events, end-of-session recap, vibe interpretation, co-pilot mode's 3-option presentation. Never on the bet decision itself.

---

## Tech stack (locked, do not deviate without asking)

- **Electron** for the desktop shell
- **Python 3.11+** for the engine
- **httpx** for Stake GraphQL calls (async)
- **anthropic** SDK for Claude API
- **SQLite** for local storage (sessions, bets, highlights)
- **keytar** in Electron for Keychain access
- **No frameworks for UI** — vanilla HTML/CSS/JS. Keep the bundle small, the UI is not complex.
- **No build tooling beyond electron-builder** for packaging the DMG

DMG will be unsigned (user accepted the "unidentified developer" warning to skip the $99/yr Apple cost).

---

## Stake API notes (critical)

- Stake's official documentation does not cover casino game bets. We use undocumented GraphQL endpoints.
- Auth is via `x-access-token` header, value obtained from the user's browser DevTools.
- Each Stake Original game has its own GraphQL mutation. Game-specific param shapes will be discovered as we build each adapter; structure the adapter layer to accept arbitrary kwargs per game.
- The vault has separate mutations for `vaultDeposit` and `vaultWithdraw`.
- The client seed can be rotated via mutation; this is how the vibe seed feature works.
- **Third-party slots (Pragmatic, Hacksaw, etc.) are NOT supported in v1.** The Stake API cannot place spins on them. v1 is Stake Originals only.
- Detection risk is real. Add randomized jitter (±20%) to all sleep intervals between bets. Never bet at perfectly regular intervals.

---

## Game adapter interface

Every game implements:

```python
class GameAdapter:
    name: str
    
    async def place_bet(
        self, 
        amount: Decimal, 
        currency: str, 
        params: dict        # game-specific (roll target, picks, mine count, etc.)
    ) -> BetResult:
        """Returns: {won: bool, payout: Decimal, multiplier: float, raw: dict}"""
    
    def persona_params(self, persona: Persona, bankroll: Decimal, vibes: Vibes) -> dict:
        """Returns the params this persona would use for this game on this bankroll."""
    
    def min_bet(self, currency: str) -> Decimal: ...
    def max_bet(self, currency: str) -> Decimal: ...
```

This is the single most important interface in the project. The orchestrator only talks to games through `GameAdapter`. Avatar/commentary/co-pilot all observe the result, never call the game directly.

---

## Persona system

Four personas, locked: **Chill**, **Steady**, **Degen**, **Extreme Degen**.

Each persona is a dataclass holding:
- bet sizing range (% of bankroll)
- per-game param strategies (function: bankroll → params)
- recovery behavior (Martingale config or none)
- velocity range (seconds between bets)
- game weighting (which games this persona prefers)

Personas are **pure logic**, no state. Recovery state (current Martingale step, win/loss streak) lives in the orchestrator's session state, passed into the persona's decision functions.

Full per-game persona behavior is documented in `docs/personas.md` (to be created in Phase 1).

---

## Commentary personas (separate from betting personas)

Four commentary tones, user picks one per session:
- **Chill Operator** — calm, dry, observational
- **Hype Beast** — high energy, exclamatory
- **Wise Old Gambler** — sage, slow, sees patterns
- **Silent Killer** — minimal, brutal one-liners, rare

Commentary tone is independent of bet persona. A user can run Chill bets with Hype Beast commentary if they want.

---

## Event bus

All side effects route through `engine/events/bus.py`. The bet loop emits, subscribers consume. This is what makes the avatar pluggable later.

Events:
```
session_start, session_end
bet_placed, bet_settled
won_small, won_medium, won_big        (thresholds: 2x, 10x, 50x multiplier)
lost
heater_started, heater_ended          (3+ consecutive wins)
cold_streak_started, cold_streak_ended (3+ consecutive losses)
recovery_mode_entered, recovery_mode_exited
vault_executed
target_progress_25, target_progress_50, target_progress_75
top_target_hit, secondary_target_hit
stop_loss_hit
tilt_bet_triggered
big_win_alert                          (user-configurable threshold)
```

Subscribers in v1: bet_feed_ui, commentary_engine, notification_system, sqlite_logger.
Subscriber added in v2: avatar_controller (already designed to plug in here, no engine changes needed).

---

## File structure

```
gambleagent/
├── CLAUDE.md                       # this file
├── README.md
├── docs/
│   ├── personas.md                 # full per-game persona detail
│   ├── stake-api-notes.md          # endpoints discovered as we go
│   └── architecture.md
├── electron/
│   ├── main.js
│   ├── preload.js
│   ├── package.json
│   └── renderer/
│       ├── index.html
│       ├── styles.css
│       ├── app.js
│       └── components/
├── engine/
│   ├── main.py                     # stdio IPC entry
│   ├── config.py
│   ├── stake/
│   │   ├── client.py
│   │   ├── auth.py
│   │   ├── vault.py
│   │   ├── seeds.py
│   │   └── games/
│   │       ├── base.py
│   │       ├── dice.py
│   │       ├── limbo.py
│   │       ├── keno.py
│   │       ├── mines.py
│   │       ├── plinko.py
│   │       ├── wheel.py
│   │       ├── crash.py
│   │       ├── hilo.py
│   │       ├── dragon_tower.py
│   │       ├── diamonds.py
│   │       ├── video_poker.py
│   │       └── scarab_spin.py
│   ├── personas/
│   │   ├── base.py
│   │   ├── chill.py
│   │   ├── steady.py
│   │   ├── degen.py
│   │   ├── extreme_degen.py
│   │   └── recovery.py
│   ├── brain/
│   │   ├── orchestrator.py
│   │   ├── game_selector.py
│   │   ├── bet_sizer.py
│   │   └── targets.py
│   ├── vibes/
│   │   ├── seed_generator.py
│   │   └── interpreter.py
│   ├── personality/
│   │   ├── commentary.py
│   │   ├── recap.py
│   │   └── copilot.py
│   ├── events/
│   │   └── bus.py
│   ├── storage/
│   │   ├── db.py
│   │   └── schema.sql
│   ├── tests/
│   └── pyproject.toml
├── shared/
│   └── schemas.json                # IPC contracts
├── assets/
│   ├── icons/
│   └── avatar/                     # empty in v1
└── build/
    ├── package.sh
    └── electron-builder.yml
```

---

## Phase plan

We build in phases. **Do not work outside the current phase without asking.**

- **Phase 1 — Engine prototype (CLI).** ✅ COMPLETE. Stake client, 3 games (Dice/Keno/Limbo), Steady persona only, vibe seed working, event bus, SQLite logger, preflight check, dry-run mode. NOTE: Stake API round-trip was NOT verified in sandbox (egress to api.stake.com blocked). First live verification happens through the finished Electron app on the user's Mac.
- **Phase 2 — Electron UI + Packaging (current).** Full desktop app wrapping Phase 1 engine. Credentials screen with Keychain, session config form, live dashboard, debug console (first-class feature — surfaces all raw GraphQL traffic for post-mortem), Python sidecar IPC, unsigned DMG via electron-builder.
- **Phase 3 — Full engine.** All 12 games, all 4 personas, full Martingale, vault automation, stop-loss modes, Claude commentary + recap, co-pilot logic, event bus complete.
- **Phase 4 — Avatar.** Separate sprint, post-Phase 3.

Current phase: **Phase 2** (update this line as we progress).

### Phase 2 engine scope (what's in vs. out)
Phase 2 ships the Phase 1 engine (3 games, Steady persona) through the Electron UI. The UI must show the full future surface area (all 4 personas, all 12 games) but disabled with "Coming in Phase 3" labels. This ships the UI shell now and lets the engine catch up later.

### Debug console — non-negotiable requirement
The Phase 1 engine was never verified against the live Stake API. Every Stake API error must bubble to the debug console with full request/response payloads. A "friendly error message" without the raw payload is not acceptable — it makes the first real-money debugging session impossible.

---

## House rules for development

1. **No premature abstraction.** Build for the 3 games in Phase 1, generalize when adding the 4th. Don't design for 12 games up front.
2. **No mocking that hides reality.** Stake API calls go to real Stake (with tiny test amounts) or a recorded fixture from a real call. No invented response shapes.
3. **Every bet logged.** SQLite, every time. Crash recovery and post-session analysis depend on it.
4. **Randomized jitter on all timing.** ±20% on every sleep. No fixed intervals anywhere.
5. **Fail loud, recover gracefully.** If Stake returns an unexpected error, log it, halt the session, notify the user. Never silently retry into a bigger loss.
6. **Money math uses Decimal, never float.** Period.
7. **Currency-aware everywhere.** BTC has 8 decimals, USDT has 6, etc. Never assume.
8. **The orchestrator owns state.** Personas, games, and adapters are stateless. State lives in one place.
9. **Tests for the brain, not for the IO.** Bet sizing, persona selection, target logic — unit tested. Stake API client — manual test.
10. **Honesty in commentary.** Claude commentary can be flavorful but must reflect what actually happened. No fake hype on losses.
