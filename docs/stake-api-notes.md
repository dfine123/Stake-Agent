# Stake.com API Notes

Running log of confirmed and unconfirmed GraphQL operations. Update this file
every time a query/mutation is verified against a live Stake account.

---

## Endpoint

| URL | Status | Source |
|-----|--------|--------|
| `https://api.stake.com/graphql` | **CONFIRMED** | Seuntjie900/DiceBot Stake.cs |
| `https://stake.com/_api/graphql` | Reported (alt) | Community forums |

Use `https://api.stake.com/graphql`. Both appear to work but the `api.` subdomain
is referenced in real reverse-engineered code.

## Required headers

```
Content-Type: application/json
x-access-token: <your token>
```

Token is obtained from browser DevTools (see below). Stake will never ask for it;
don't share it.

---

## How to capture queries from DevTools

1. Log into stake.com in Chrome/Firefox.
2. Open DevTools → **Network** tab.
3. Filter requests by `graphql` in the search box.
4. Perform the action you want to capture (check balance, move to vault, etc.).
5. Click the matching network request.
6. **Request** tab → copy the full JSON body (it has `query`, `variables`).
7. **Response** tab → copy the JSON response.
8. Paste both here and update the corresponding query constant in `engine/stake/client.py`.

---

## Operations

### `get_balance` — UserBalances

**Status: CONFIRMED** (Seuntjie900/DiceBot PD.cs, `DiceBotGetBalance`)

```graphql
query GambleAgentBalance {
  user {
    id
    balances {
      available {
        amount
        currency
      }
    }
    activeClientSeed { seed }
    activeServerSeed  { seedHash nonce }
  }
}
```

Response shape (abridged):
```json
{
  "data": {
    "user": {
      "id": "...",
      "balances": {
        "available": [
          { "amount": 0.00123456, "currency": "btc" },
          { "amount": 0.0, "currency": "eth" }
        ]
      },
      "activeClientSeed": { "seed": "abc123..." },
      "activeServerSeed":  { "seedHash": "def456...", "nonce": 42 }
    }
  }
}
```

Notes:
- `currency` is a plain string (lowercase), not a nested object.
- All currencies appear in the `available` array even when balance is 0.
- Verify the exact currency string casing on first live run.

---

### `set_client_seed` — changeClientSeed

**Status: CONFIRMED** (Seuntjie900/DiceBot PD.cs, `DiceBotRotateSeed`)

```graphql
mutation GambleAgentRotateSeed($seed: String!) {
  rotateServerSeed { seed seedHash nonce }
  changeClientSeed(seed: $seed) { seed }
}
```

Notes:
- `rotateServerSeed` and `changeClientSeed` are called together so the
  server/client pair is always fresh at session start.
- The vibe seed feature calls this before any bets are placed.
- Confirmed field name: `changeClientSeed`, argument: `seed: String!`.

---

### `get_currency_rate` — CurrencyRates

**Status: UNVERIFIED** — query shape guessed. Will fail on first use if wrong.

```graphql
query GambleAgentCurrencyRates {
  info {
    currencies {
      name
      usdPrice
    }
  }
}
```

**TODO:** To verify and fix this query:
1. Log into stake.com, open DevTools → Network → filter `graphql`.
2. The rate is likely fetched on page load — watch for a request that
   returns USD prices for btc, eth, etc.
3. Copy the query body and paste the confirmed version here.
4. Update `_CURRENCY_RATE_QUERY` and `get_currency_rate()` parsing in
   `engine/stake/client.py` to match the real field names.

Note: `usdt` always returns `Decimal("1")` without a network call.

---

### `vault_deposit` — VaultDeposit

**Status: UNVERIFIED** — mutation shape guessed. Will fail on first use if wrong.

```graphql
mutation GambleAgentVaultDeposit($currency: CurrencyEnum!, $amount: Float!) {
  vaultDeposit(currency: $currency, amount: $amount) {
    id
  }
}
```

**TODO:** To verify and fix this mutation:
1. Log into stake.com, open DevTools → Network → filter `graphql`.
2. Transfer any small amount to your vault.
3. Copy the mutation body and response.
4. Update `_VAULT_DEPOSIT_MUTATION` and `vault_deposit()` parsing in
   `engine/stake/client.py`.

---

## Dice bet mutation

**Status: CONFIRMED** (Seuntjie900/DiceBot PD.cs, `DiceBotDiceBet`)

This lives in `engine/stake/games/dice.py`, not the client. Documented here for reference.

```graphql
mutation DiceBet(
  $amount: Float!
  $target: Float!
  $condition: CasinoGameDiceConditionEnum!
  $currency: CurrencyEnum!
  $identifier: String!
) {
  diceRoll(
    amount: $amount
    target: $target
    condition: $condition
    currency: $currency
    identifier: $identifier
  ) {
    id
    nonce
    currency
    amount
    payout
    state {
      ... on CasinoGameDice {
        result
        target
        condition
      }
    }
    createdAt
    serverSeed { seedHash seed nonce }
    clientSeed { seed }
    user {
      balances { available { amount currency } }
    }
  }
}
```

`CasinoGameDiceConditionEnum` values: `above` | `below` (verify casing on first run).
`identifier`: client-generated UUID per bet (used for idempotency).

---

## Keno bet mutation

**Status: UNVERIFIED** — best-guess shape, mirrors confirmed diceRoll pattern.
Lives in `engine/stake/games/keno.py` (`_KENO_BET_MUTATION`).

```graphql
mutation KenoBet(
  $amount: Float!
  $currency: CurrencyEnum!
  $identifier: String!
  $risk: CasinoGameKenoRiskEnum!
  $selected: [Float!]!
) {
  kenoBet(...) {
    id nonce currency amount payout
    state { ... on CasinoGameKeno { drawnNumbers selectedNumbers risk } }
    ...
  }
}
```

**TODO:** Capture from DevTools — place a Keno bet, copy the request/response.
Things most likely to differ from the guess:
- Mutation field name (`kenoBet` vs `kenoMultiplier` vs `kenoPlay`)
- Risk enum name (`CasinoGameKenoRiskEnum`) and value casing (`classic` vs `CLASSIC`)
- Whether `selected` is `[Float!]!` or `[Int!]!`
- State inline type name (`CasinoGameKeno`) and its field names

---

## Limbo bet mutation

**Status: UNVERIFIED** — best-guess shape, mirrors confirmed diceRoll pattern.
Lives in `engine/stake/games/limbo.py` (`_LIMBO_BET_MUTATION`).

```graphql
mutation LimboBet(
  $amount: Float!
  $currency: CurrencyEnum!
  $identifier: String!
  $multiplierTarget: Float!
) {
  limboBet(...) {
    id nonce currency amount payout
    state { ... on CasinoGameLimbo { result multiplierTarget } }
    ...
  }
}
```

**TODO:** Capture from DevTools — place a Limbo bet, copy the request/response.
Things most likely to differ from the guess:
- Mutation field name (`limboBet` vs `limboGame` vs `limbo`)
- Variable name (`multiplierTarget` vs `target` vs `targetMultiplier`)
- State inline type name (`CasinoGameLimbo`) and its field names

---

## CurrencyEnum values

**Status: PARTIALLY CONFIRMED**

From DiceBot Stake.cs `sCurrencies`: `Btc, Eth, Ltc, Doge, Bch, Xrp, Trx, Eos`
(These are display names; actual GraphQL enum values may differ in case.)

Working assumption: enum values are lowercase (`btc`, `eth`, etc.) matching
the currency strings returned by the balance query. Verify on first live call.
