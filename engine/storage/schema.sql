-- GambleAgent local storage schema.
-- Decimal money values are stored as TEXT (never REAL) to preserve precision.

CREATE TABLE IF NOT EXISTS sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at            TEXT    NOT NULL,    -- ISO8601 UTC
    ended_at              TEXT,
    currency              TEXT    NOT NULL,
    persona               TEXT    NOT NULL,
    top_target_usd        TEXT,                -- Decimal as string
    secondary_target_usd  TEXT,
    start_balance         TEXT,                -- Decimal in `currency`
    end_balance           TEXT,
    end_reason            TEXT,                -- top_target_hit | secondary_target_hit
                                               -- | stop_loss_hit | user_halt | error
    vibe_seed             TEXT,
    config_json           TEXT                 -- snapshot of full session config
);

CREATE TABLE IF NOT EXISTS bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    placed_at       TEXT    NOT NULL,
    settled_at      TEXT,
    game            TEXT    NOT NULL,
    amount          TEXT    NOT NULL,          -- Decimal as string
    currency        TEXT    NOT NULL,
    params_json     TEXT    NOT NULL,
    won             INTEGER,                   -- 0/1, NULL until settled
    payout          TEXT,                      -- Decimal as string
    multiplier      REAL,
    stake_bet_id    TEXT,                      -- Stake's response id
    raw_json        TEXT                       -- full Stake response for replay/audit
);

CREATE INDEX IF NOT EXISTS idx_bets_session ON bets(session_id);

CREATE TABLE IF NOT EXISTS vault_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    executed_at  TEXT    NOT NULL,
    currency     TEXT    NOT NULL,
    amount       TEXT    NOT NULL              -- Decimal as string
);
