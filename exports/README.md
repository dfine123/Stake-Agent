# Exported Session Data

Runtime data exported from `~/Library/Application Support/GambleAgent/sessions.db`. This database is created and written to by the GambleAgent engine at runtime — it is not static data checked into the repo. These exports are snapshots for inspection and sharing.

**Exported:** 2026-05-27

## Files

- **sessions.json** — Full structured export. Sessions with nested bets and vault events, including raw Stake API responses.
- **bets.csv** — Flat table, one row per bet with session context joined in. Easy to open in Excel / Google Sheets / pandas.

## Data summary

| Table | Rows | Notes |
|-------|------|-------|
| sessions | 8 | 2 USDT, 6 SOL. All Steady persona, all ended via user_halt. |
| bets | 15 | All dice. 14 in session 4, 1 in session 3. |
| vault_events | 0 | No vault operations executed. |

## Field reference

### Session fields

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment primary key |
| started_at | ISO8601 | Session start timestamp (UTC) |
| ended_at | ISO8601 | Session end timestamp (UTC) |
| currency | string | Betting currency (e.g. `usdt`, `sol`) |
| persona | string | Betting persona used (`steady`) |
| top_target_usd | string | Primary profit target in USD |
| secondary_target_usd | string | Secondary profit target in USD |
| start_balance | string | Balance at session start (in `currency`) |
| end_balance | string | Balance at session end (in `currency`) |
| end_reason | string | Why the session ended: `user_halt`, `top_target_hit`, `secondary_target_hit`, `stop_loss_hit`, `error` |
| vibe_seed | string | Client seed derived from vibe settings |
| config | object | Full session configuration snapshot |

### Bet fields

| Field | Type | Description |
|-------|------|-------------|
| id | int | Auto-increment primary key |
| session_id | int | FK to session |
| placed_at | ISO8601 | When the bet was sent to Stake |
| settled_at | ISO8601 | When the result came back |
| game | string | Game adapter name (e.g. `dice`) |
| amount | string | Bet size as decimal string (in `currency`) |
| currency | string | Bet currency |
| won | 0/1 | 1 = win, 0 = loss |
| payout | string | Amount returned as decimal string |
| multiplier | float | Payout multiplier (e.g. 2.0 for even money) |
| stake_bet_id | string | Bet ID from Stake's API response |
| params | object | Game-specific parameters (e.g. `{"target": 50.5, "condition": "above"}` for dice) |
| raw_response | object | Full Stake GraphQL response (JSON, for audit/replay) |

### CSV-specific columns

The CSV joins session data onto each bet row. Session fields are prefixed with `session_` (e.g. `session_currency`, `session_persona`). The `params_target` and `params_condition` columns are flattened from the params JSON for dice bets.
