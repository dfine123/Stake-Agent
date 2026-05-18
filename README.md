# GambleAgent

Autonomous Stake.com session runner — desktop app for macOS.

> **Status**: Phase 2 (Electron UI + Packaging) in progress. Phase 1 engine is
> complete. See `CLAUDE.md` for the full project spec and `docs/HANDOFF.md`
> for the current cross-session handoff state.

---

## Quickstart (fresh clone)

```bash
# Clone
git clone <your-fork-url> Stake-Agent
cd Stake-Agent

# Python engine (editable install + dev deps)
python3 -m pip install -e "./engine[dev]"

# Electron deps
cd electron && npm install && cd ..

# Run tests (expect 150 passed)
python3 -m pytest engine/tests/

# Run in dev mode — spawns the Python sidecar and opens the Electron window
npm run dev
```

The dev build opens DevTools attached to the renderer process. Use **⌘⇧D**
to jump to the Debug Console, which streams the raw IPC traffic and every
Stake GraphQL request/response.

---

## Requirements

- **Node** 20.x (LTS) with npm 10.x
- **Python** 3.11+
- **Xcode Command Line Tools** (`xcode-select --install`) — `keytar` needs
  native compilation for Keychain access
- macOS (Linux/Windows are not supported; the Electron build is Mac-only)

---

## CLI mode (engine only)

The Python engine also runs standalone, no Electron required:

```bash
# Validate a config file
python3 -m engine.main validate --config session.yaml

# Test Stake auth + show balance (no bets)
python3 -m engine.main preflight --config session.yaml

# Run a session (add --dry-run for simulation only)
python3 -m engine.main run --config session.yaml --dry-run

# IPC mode (used by Electron — reads JSON commands from stdin)
python3 -m engine.main serve
```

Copy `session.yaml` to `session.local.yaml` and fill in real credentials —
the `.local.yaml` is gitignored. You can also paste the token interactively
when prompted, or set `STAKE_ACCESS_TOKEN` in the environment.

---

## Packaging (Phase 2 Task 2.10)

```bash
npm run build          # universal macOS DMG, unsigned
```

Output lands in `electron/dist/`. The DMG is intentionally unsigned — first
launch will show "unidentified developer" until you right-click → Open.

---

## Repo layout

```
electron/             Electron shell — main process, preload, renderer
  ipc/                Sidecar process management + stdio framing
  renderer/           Vanilla HTML/CSS/JS UI; no framework
engine/               Python sidecar (also runs standalone as CLI)
  stake/              GraphQL client + per-game adapters
  brain/              Orchestrator, bet sizer, target tracker, game selector
  personas/           Strategy logic (stateless)
  vibes/              Seed generation + vibe interpreter
  events/             Pub/sub event bus
  storage/            SQLite session + bet logger
  ipc/                JSON-over-stdio server (talks to Electron)
shared/               IPC schema contract (shared/schemas.json)
docs/                 Project docs — HANDOFF, stake-api-notes, etc.
```

---

## Phase plan

- **Phase 1** ✅ Engine prototype (CLI) — Stake client, Dice/Keno/Limbo,
  Steady persona, vibe seeds, event bus, SQLite logger
- **Phase 2** 🚧 Electron UI + Packaging — current
- **Phase 3** — Full engine (12 games, 4 personas, Martingale, vault
  automation, Claude commentary, co-pilot mode)
- **Phase 4** — Avatar

---

## A note on this project

This is built for fun. House edge is real and well understood by the user —
the agent is not designed to have an edge. See `CLAUDE.md` for the full
context on the project's goals and constraints.
