# Phase 2 Handoff — sandbox → local Mac

This doc is the bridge between the cloud sandbox sessions (Phase 1 + Phase 2
through Task 2.8) and continuing the work on a local Mac with Claude Code.

---

## Current state

- **Phase**: 2 (Electron UI + Packaging)
- **Branch**: `claude/add-claude-context-file-PaRYw`
- **Latest commit before handoff**: Task 2.8 — see `git log -1` on push.
- **Next task**: **2.9 — End-to-end integration test in dev mode**

---

## Phase 2 — done

- **2.1** Electron scaffolding, design system, router shell, view stubs.
- **2.2** Python sidecar IPC layer (stdio newline-delimited JSON, EngineClient,
  Test IPC button in Debug Console).
- **2.3** Credentials screen + macOS Keychain via `keytar`. Stake "Test
  connection" button does a real `preflight` IPC round-trip.
- **2.4** Session config form — currency, targets, persona cards, game grid
  (12 games; 9 disabled with `.coming-soon` Phase 3 overlay), stop-loss,
  vibes, dry-run. Auto-saves to localStorage.
- **2.5** Dashboard — full state machine (idle → starting → running → paused →
  stopping → ended), live bet feed driven by engine events, stats sidebar
  with USD balance + P&L + target progress bar, GO / PAUSE / STOP / PANIC
  controls.
- **2.6** Debug console v2 — filter pills (All / Events / Responses / GraphQL /
  Errors) with live counts, search box, auto-scroll toggle, Copy-as-cURL
  buttons on every GraphQL request, session export to JSON file.
- **2.7** Settings — credential list with masked values + per-credential
  delete, engine restart, data folder open, danger zone (delete-all).
- **2.8** Wired engine config types to UI — added `validate_config` and
  `get_config_schema` IPC commands; Launch button now consults the engine's
  pydantic validation before navigating to dashboard; structured field-level
  errors surface in the UI.

**Tests**: 150 passing (`python -m pytest engine/tests/`).

---

## Phase 2 — remaining

- **2.9** End-to-end integration test in dev mode (this is where you start).
- **2.10** Packaging via electron-builder (unsigned universal macOS DMG).
- **2.11** Smoke test the packaged DMG.

---

## Decisions and gotchas from this session

Items not already in `CLAUDE.md` that the next session needs to know:

1. **Stake API was never live-verified.** Phase 1 engine code was written but
   the sandbox blocks egress to `api.stake.com` (`x-deny-reason:
   host_not_allowed`). The first real round-trip will happen in Task 2.9. The
   Debug Console (Task 2.6) was specifically built to surface every raw
   request/response so the first run can be post-mortemed. Expect to find at
   least one bug in `engine/stake/client.py` request shape or response
   parsing — be patient with it.

2. **Decimal-as-string over the wire.** The orchestrator emits `Decimal`
   objects in event payloads (`start_balance`, `payout`, `amount`, etc.). The
   IPC server's `_send` uses `json.dumps(..., default=str)`, so they arrive
   in the renderer as strings. The dashboard uses `parseFloat()` to parse
   them for display. This is deliberate — no precision loss in the engine,
   conversion only at the display boundary. Do not change this without
   reading `engine/ipc/server.py:_send` carefully.

3. **The x-access-token is never in debug payloads.** `StakeClient` does not
   include the auth header in the data it passes to `debug_hook`. The "Copy
   as cURL" button uses `<YOUR_TOKEN>` as a placeholder. This means debug
   console exports are safe to share for bug reports.

4. **Engine restart kills running sessions silently.** The dashboard does not
   currently subscribe to `engine_crash` events for reconnect logic — it
   just shows the error in the feed. If you hit Restart in Settings during
   a live session, the orchestrator task is cancelled with no graceful
   shutdown. Vault state is unaffected (each bet is committed to Stake
   independently), but the SQLite session row won't be marked ended.

5. **Lucky numbers serialization.** UI stores `vibes.lucky_numbers` as a
   comma-separated string in localStorage (so the input field round-trips
   verbatim). `window.SessionConfig.toEnginePayload()` parses it to
   `int[]` before sending — empty string yields `[]`.

6. **`session.yaml` is CLI-only.** When running via Electron, all config
   comes from `localStorage` + Keychain. The YAML file is only used by
   `python -m engine.main run --config session.yaml`. Do not try to keep
   them in sync.

7. **`anthropic` is in `pyproject.toml` but not imported yet.** Added during
   handoff so the local env is fully provisioned before Phase 3 begins.
   Currently zero imports — `pip install -e ./engine` will pull it but
   nothing uses it.

8. **`stake_token` vs `stake_access_token` was a real bug.** The IPC server
   originally used the key `stake_token` while the renderer sent
   `stake_access_token`. Fixed in 2.5 (`engine/ipc/server.py`). Mention this
   if anyone wonders why the older debug console screenshots show a
   different shape.

9. **`session_start` event includes `start_balance_usd` and `rate`.** Added
   in Task 2.5 to `engine/brain/orchestrator.py`. The dashboard relies on
   these for USD-denominated P&L tracking without extra API calls.

10. **DMG will be unsigned.** Locked decision — user accepted the
    "unidentified developer" Gatekeeper warning to skip the $99/yr Apple
    cost. `mac.identity: null`, `hardenedRuntime: false` in
    `electron/package.json`.

---

## Local Mac prerequisites

Install before resuming:

| Tool       | Version             | Notes                                                       |
|------------|---------------------|-------------------------------------------------------------|
| Node       | **20.x** (LTS)      | Electron 28 supports Node 18+, but 20 is what we test on   |
| npm        | 10.x                | Comes with Node 20                                          |
| Python     | **3.11+**           | Pydantic v2, asyncio TaskGroups, modern type syntax        |
| pip        | latest              | `python3 -m pip install --upgrade pip`                      |
| Xcode CLT  | latest              | `xcode-select --install` — keytar needs native compilation |

After cloning:

```bash
# 1. Python engine deps (editable install + dev deps for pytest)
python3 -m pip install -e "./engine[dev]"

# 2. Electron deps (electron, electron-builder, keytar)
cd electron && npm install && cd ..

# 3. Verify tests
python3 -m pytest engine/tests/   # expect 150 passed

# 4. Run dev mode (spawns Python sidecar + opens Electron window)
npm run dev                       # from repo root
```

**First-run check:** the Credentials view should open by default. Paste a real
Stake `x-access-token`, click "Test connection" — this exercises the full
IPC → Python → Stake API path. **Watch the Debug Console** (⌘⇧D) while it
runs; expect at least one quirk in the GraphQL shape.

---

## Starter prompt for local Claude Code

Paste this verbatim into a fresh Claude Code session on the Mac:

```
Resuming GambleAgent Phase 2 from a sandbox handoff.

Read these files first, in this order:
  1. CLAUDE.md            — overall project spec + current phase
  2. docs/HANDOFF.md      — the bridge doc you wrote in the sandbox

Current task is 2.9 — end-to-end integration test in dev mode. The goal
is to prove the full flow works on real macOS hardware against the real
Stake.com API for the first time:

  1. `npm run dev` from the repo root — confirm the Electron window opens
     and the Python sidecar spawns cleanly (check Debug Console pill).
  2. Enter Stake access token via Credentials screen, "Test connection".
     Watch the Debug Console for the preflight GraphQL traffic.
  3. Save credentials, configure a tiny session in Session Config
     (small targets, USDT, dry-run ON).
  4. Click Launch Session → expect dashboard to populate with starting
     balance + session_start event.
  5. With dry-run on, bets are simulated — confirm the bet feed
     populates, stats sidebar updates, no real money moves.
  6. Repeat with dry-run OFF and a $5–$10 target — confirm the engine
     actually places a real Stake bet end-to-end.

Expect bugs in the live Stake GraphQL round-trip — Phase 1 was never
verified against the real API. Use the Debug Console's "Copy as cURL"
button to retry any failing request from the terminal, then fix the
engine in `engine/stake/*`.

DO NOT proceed to Task 2.10 (packaging) until 2.9 is signed off by the user.
```

---

## File map — what changed in this session

```
electron/
  main.js                                    # IPC handlers + keytar
  preload.js                                 # contextBridge exposure
  ipc/client.js                              # EngineClient (NEW)
  renderer/app.js                            # router + initial nav
  renderer/index.html                        # sidebar shell
  renderer/styles.css                        # design system
  renderer/components/credentials.js         # Keychain UI
  renderer/components/session-config.js      # full form + validation
  renderer/components/dashboard.js           # live session view
  renderer/components/debug-console.js       # filters + cURL + export
  renderer/components/settings.js            # creds management
engine/
  ipc/__init__.py                            # (NEW)
  ipc/server.py                              # async stdio dispatcher (NEW)
  main.py                                    # added `serve` subcommand
  stake/client.py                            # added debug_hook
  stake/preflight.py                         # extracted get_preflight_data
  brain/orchestrator.py                      # bus/stop/pause/debug params
  tests/test_ipc_server.py                   # (NEW, 6 tests)
shared/schemas.json                          # IPC contract docs (NEW)
docs/HANDOFF.md                              # this file (NEW)
```
