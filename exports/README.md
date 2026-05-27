# Exported Session Data

Runtime data exported from `~/Library/Application Support/GambleAgent/sessions.db`. This database is created and written to by the GambleAgent engine at runtime — it is not static data checked into the repo. These exports are snapshots for inspection and sharing.

**Exported:** 2026-05-27

## Files

- **sessions.json** — Full structured export. Sessions with nested bets and vault events, including raw Stake API responses.
- **bets.csv** — Flat table, one row per bet with session context joined in. Easy to open in Excel / Google Sheets / pandas.

## Data summary

| Metric | Value |
|--------|-------|
| Sessions | 1 |
| Total bets | 98 |
| Duration | ~7.5 minutes (05:35–05:42 UTC) |
| Currency | SOL |
| Persona | Steady |
| Start balance | 0.1022 SOL (~$8.55 USD) |
| End balance | 0.1305 SOL (~$10.92 USD) |
| Net P&L | +0.0283 SOL (~$2.37 USD) |
| End reason | user_halt |

### Game breakdown

| Game | Bets | Wins | Losses | Win Rate |
|------|------|------|--------|----------|
| Dice | 39 | 25 | 14 | 64.1% |
| Keno | 35 | 27 | 8 | 77.1% |
| Limbo | 24 | 14 | 10 | 58.3% |
| **Total** | **98** | **66** | **32** | **67.3%** |

### Payout multipliers observed

| Game | Multipliers seen |
|------|-----------------|
| Dice | 0.00x (loss), 2.00x (win) |
| Keno | 0.00x (loss), 0.25x (partial), 1.40x, 4.10x |
| Limbo | 0.00x (loss), 2.00x (win) |

## Field reference

### Session fields

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment primary key |
| started_at | ISO8601 | Session start timestamp (UTC) |
| ended_at | ISO8601 | Session end timestamp (UTC) |
| currency | string | Betting currency (e.g. `sol`) |
| persona | string | Betting persona used (`steady`) |
| top_target_usd | string | Primary profit target in USD |
| secondary_target_usd | string | Secondary profit target in USD |
| start_balance | string | Balance at session start (in `currency`) |
| end_balance | string | Balance at session end (in `currency`) |
| end_reason | string | Why the session ended: `user_halt`, `top_target_hit`, `secondary_target_hit`, `stop_loss_hit`, `error` |
| vibe_seed | string | Client seed derived from vibe settings (SHA-256) |
| config | object | Full session configuration snapshot |

### Bet fields

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment primary key |
| session_id | int | FK to session |
| placed_at | ISO8601 | When the bet was sent to Stake |
| settled_at | ISO8601 | When the result came back |
| game | string | Game adapter name: `dice`, `keno`, or `limbo` |
| amount | string | Bet size as decimal string (in `currency`) |
| currency | string | Bet currency |
| won | 0/1 | 1 = win, 0 = loss |
| payout | string | Amount returned as decimal string (0 on loss) |
| multiplier | float | Payout multiplier (e.g. 2.0 for even money) |
| stake_bet_id | string | Bet ID from Stake's API response (UUID) |
| params | object | Game-specific parameters sent to Stake |
| raw_response | object | Full Stake GraphQL response for this bet |

### Game-specific params

**Dice:** `{"target": 50.5, "condition": "above"}` — roll above/below a target number.

**Keno:** `{"selected": [7, 14, 21, 28, 35], "risk": "classic"}` — pick 1-10 numbers from 0-39.

**Limbo:** `{"multiplier_target": 2.0}` — target a payout multiplier, win if RNG >= target.

### CSV columns

The CSV joins session data onto each bet row. Session fields are prefixed with `session_` (e.g. `session_currency`, `session_persona`). The `params_json` column contains the raw JSON params for each bet.
