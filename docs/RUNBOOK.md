# Runbook — running with real Alpaca + Telegram

Everything below runs on the paper/dry-run path: **zero real dollars**.
Real trading needs the separate triple gate (bottom).

## 0. Credentials

Copy `.env.example` to `.env` at the repo root and fill in the five values.
The engines auto-load it (Python via python-dotenv, Rust via dotenvy); a real
exported env var always overrides the file. `.env` is gitignored — never
commit it.

```sh
cp .env.example .env && $EDITOR .env
```

Variable names the code expects (exactly): `ALPACA_API_KEY`,
`ALPACA_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`. If your
existing `.env` uses different names, rename them to these.

Quick check that the values load:

```sh
cd sandbox/backtest && uv run python -c "from backtest.env import load_env; load_env(); import os; print('alpaca key tail:', os.environ['ALPACA_API_KEY'][-4:])"
```

## 1. Telegram bridge

```sh
cd infra/telegram && uv run telegram-bridge
```

Then from your phone: `/status` should reply (and only to your account —
messages from any other id are dropped). Drop a test event to confirm
outbound delivery:

```sh
echo '{"schema_version":"1.0.0","id":"evt-smoke-1","source_agent":"manual","severity":"high","kind":"promotion_request","payload":{"text":"smoke test"},"requires_reply":true,"ts":"2026-01-01T00:00:00Z"}' > infra/telegram/queue/evt-smoke-1.json
```

## 2. Backtest on real Alpaca data (IEX daily bars)

Downloads + pins a parquet snapshot, then reruns are offline & reproducible:

```sh
cd sandbox/backtest
uv run backtest --manifest ../../tests/integration/sma-cross-demo.manifest.json \
  --start 2018-01-01 --end 2024-12-31
```

(For a real strategy, point `--manifest` at its wiki-embedded manifest.)

## 3. Paper engine against the live Alpaca data stream

```sh
cargo run -p paper-engine -- \
  --manifest <manifest.json> \
  --ruleset data/results/<id>/ruleset.json \
  --feed alpaca
```

## 4. Live engine — DRY RUN (Alpaca paper endpoint, real order path, $0 risk)

Requires an approved live promotion (ranker issues it; you `/approve` +
`CONFIRM` it in Telegram). Dry-run is the default mode:

```sh
cargo run -p live -- \
  --manifest <manifest.json> \
  --ruleset data/results/<id>/ruleset.json \
  --mode dry-run
```

This exercises real Alpaca auth, order submission, and startup
reconciliation against the paper account — no real money.

## 5. Real trading (only when you truly mean it)

All three must be true or the engine refuses:

1. `QP_REAL_TRADING=1` in the environment,
2. `--real` on the command line,
3. `environment = "real"` in `live/guardrails.toml`.

Do the paper→real checklist first (fund the account, re-review guardrails,
ramp sizing). The live trading key should live ONLY in this process's
environment — not in the `.env` that agents can read.
```
