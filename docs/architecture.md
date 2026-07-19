# Quant Platform — Architecture & Delegated Prompt Specification

> **Status:** v1.0 — decisions ratified 2026-07-19. This is the root
> specification for the `quant-platform` repo; every delegated prompt in §6
> builds against this document. P0's remaining scope is scaffolding the
> layout in §3 within this repo.

**Target:** WSL monorepo · US equities via Alpaca (Polymarket deferred to v2) ·
Rust engine focused on uptime + deterministic risk (not latency) · Python
backtesting · Obsidian second brain (Karpathy LLM Wiki pattern) · Paperclip
orchestration · Telegram two-way control · Opus orchestrators / Sonnet–Haiku
executors.

---

## 1. System overview

```
                    ┌─────────────────────────────────────────┐
                    │  BRAIN (Obsidian vault, Karpathy layout) │
                    │  raw/ → wiki/ + index.md + log.md        │
                    └──────▲──────────────────┬───────────────┘
        value backprop     │                  │ candidate strategies
   (post-mortems, scores)  │                  ▼
┌──────────────┐    ┌──────┴───────┐   ┌──────────────────────┐
│ LIVE (real $)│◄───┤ RANKER       │◄──┤ SANDBOX              │
│ Rust engine  │    │ (promotion   │   │ Python backtests →   │
│ + guardrails │    │  pipeline)   │   │ Rust paper trading   │
└──────▲───────┘    └──────────────┘   └──────────────────────┘
       │ approval gate
       ▼
   TELEGRAM  ◄──►  Paperclip dashboard (org chart, budgets, heartbeats)
```

**The compounding loop:** research agents grow the brain → orchestrator
surfaces candidates → sandbox implements + validates (backtest, then paper) →
ranker promotes top performers to live → live results and post-mortems are
written back into the wiki as updated strategy pages with revised scorecards.
That write-back is the "backpropagation of value."

---

## 2. Trading mandate (fixed parameters — the spine of the system)

These values are **decisions, not defaults**. Agents never modify them;
changes are human edits to `live/guardrails.toml` only.

### 2.1 Strategy mix & timescale

| Parameter | Decision |
|---|---|
| Strategy families (v1) | **Market Structure (MS) Shift** setups — directional breaks and displacement on daily charts — and classic **multi-day Swing Trading** rules. |
| Timescale | **Daily / swing interval only.** No intraday execution, ever, in v1. |
| Market | **US equities via Alpaca only.** Polymarket is cut from v1; the `market` enum in the contracts stays extensible so it can slot in later without schema surgery. |
| Data feed | Alpaca's free IEX feed is sufficient — daily bars are the unit of decision, so SIP is not needed in v1. |

**Consequence for the Rust engine:** its objective is **100% bulletproof
uptime, state tracking, and deterministic risk enforcement — not latency
reduction.** No latency budgets appear anywhere in this spec; any
"optimisation" that trades reliability for speed is out of mandate.

### 2.2 Capital & risk limits (`live/guardrails.toml`)

| Limit | Value | Meaning |
|---|---|---|
| Base capital | **$100,000** | Paper/simulated environment to start. |
| Max position size | **5% of capital ($5,000)** | Hard cap per trade, enforced inside the order path. |
| Max daily loss | **2% of capital ($2,000)** | Circuit breaker — see below. |

```toml
# live/guardrails.toml — HUMAN-EDITABLE ONLY. Agents read, never write.
[capital]
base_capital_usd = 100000
environment = "paper"          # "paper" | "real" — flipping this is a human act

[limits]
max_position_pct = 5.0         # $5,000 at base capital
max_daily_loss_pct = 2.0       # $2,000 — circuit breaker threshold
max_order_rate_per_min = 10    # sanity cap; swing trading never needs more
```

**Circuit breaker (max daily loss exceeded):** the live engine, in order:
1. **Auto-flattens** all open positions.
2. **Freezes execution** (no new orders accepted).
3. **Alerts Telegram** with a high-severity event (loss amount, positions
   flattened, triggering strategy).
4. **Drops the kill file** at repo root: `KILL`.

### 2.3 Kill switch (single, root-level)

The kill switch is one file: **`KILL` at the repo root.** If it exists, every
trading agent and engine halts and confirms the halt via an event. It is
created by: the circuit breaker (automatically), Telegram `/halt` (human), or
a human touching the file directly. Only a human `/resume` (or manual delete)
removes it. There is exactly one kill-file location — no per-component
variants.

---

## 3. Monorepo layout

```
quant-platform/
├── CLAUDE.md                     # root constitution — every agent reads this first
├── KILL                          # ← kill switch, EXISTS ONLY WHEN HALTED
├── brain/                        # Component 1 (this dir IS the Obsidian vault)
│   ├── raw/                      # unprocessed sources (inbox)
│   ├── wiki/
│   │   ├── strategies/           # one page per strategy (lifecycle tracked here)
│   │   ├── concepts/             # indicators, market structure, papers
│   │   └── postmortems/          # live/paper trade reviews
│   ├── index.md                  # catalog of every wiki page
│   ├── log.md                    # ingestion + event chronology
│   └── CLAUDE.md                 # vault-specific schema (ingest/query/lint rules)
├── contracts/                    # SHARED SCHEMAS — the parallelisation keystone
│   ├── strategy_manifest.schema.json
│   ├── backtest_result.schema.json
│   ├── paper_result.schema.json
│   ├── promotion.schema.json
│   ├── events.schema.json        # Telegram/dashboard event envelope
│   └── promotion_thresholds.toml # human-editable promotion criteria
├── sandbox/
│   ├── backtest/                 # Python (uv project): vectorbt + alpaca-py
│   └── paper-engine/             # Rust workspace member: paper execution
├── live/                         # Rust workspace member: real-stakes execution
│   └── guardrails.toml           # hard limits, human-editable only (§2.2)
├── engine-core/                  # Rust shared crate: order/position/risk types
├── agents/                       # one .md prompt file per role (from §6)
├── infra/
│   ├── paperclip/                # Paperclip company/org config
│   ├── telegram/                 # bot bridge (grammY or python-telegram-bot)
│   ├── cron/                     # market-open + maintenance schedules
│   └── dashboard/                # Paperclip is the dashboard; glue/webhooks here
├── data/                         # parquet snapshot cache (gitignored, hashed)
└── docs/                         # this file + ADRs
```

- **Obsidian on Windows** opens the vault at
  `\\wsl$\<distro>\home\<you>\quant-platform\brain` — native, no sync layer.
  File-watch lag on `\\wsl$` is cosmetic; the vault stays on WSL ext4 because
  agent I/O speed matters more.
- **Rust** is one cargo workspace (`engine-core`, `paper-engine`, `live`).
- **Python** is one uv-managed project under `sandbox/backtest`.

---

## 4. Shared contracts (write these FIRST — they unlock parallelism)

Every workstream codes against these schemas, never against another
workstream's internals. This is what makes P2–P5 fully parallel.

**`strategy_manifest.schema.json`** — the unit of exchange between
brain → sandbox → live:

```json
{
  "id": "ms-shift-spy-v1",
  "wiki_page": "brain/wiki/strategies/ms-shift-spy.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "one-paragraph falsifiable claim",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_spy.py:Signal" },
  "risk": { "max_position_pct": 5, "stop_loss_pct": 2 },
  "lifecycle": "research | backtest | paper | live | retired",
  "scorecard": {
    "sharpe_wf": null,
    "sortino_wf": null,
    "max_drawdown_bt": null,
    "sharpe_paper": null,
    "max_drawdown_paper": null,
    "pnl_live": null,
    "rank": null
  }
}
```

- `market` is an enum: `us_equities` in v1; `polymarket` is **reserved in the
  schema but rejected by every runtime component** until v2.
- `family` is an enum: `ms_shift | swing` in v1.
- `risk.max_position_pct` may never exceed the guardrail cap; validation
  rejects manifests that try.
- **Scorecard, not Elo.** Elo is dropped for v1 (no meaningful pairwise
  "match" exists between strategies). Ranking is a standard Performance
  Score Card on **walk-forward Sharpe, Sortino, and Max Drawdown**; the block
  stays extensible if a tournament structure ever justifies Elo.

**`backtest_result.schema.json` / `paper_result.schema.json`:** strategy id,
period, sharpe, sortino, max drawdown, turnover, slippage assumptions, equity
curve path, pass/fail against thresholds, notes — **plus a mandatory
`data_snapshot` block:**

```json
"data_snapshot": {
  "parquet_path": "data/us_equities/daily/SPY_QQQ_2018-2026.parquet",
  "content_hash": "sha256:…",
  "source_feed": "alpaca_iex_daily",
  "period": { "start": "2018-01-01", "end": "2026-06-30" }
}
```

Every result is reproducible bit-for-bit from its pinned snapshot. A result
whose snapshot hash no longer matches the file on disk is invalid and the
ranker must ignore it.

**`promotion.schema.json`:** strategy id, from→to lifecycle stage, evidence
(result refs), ranker rationale,
**`human_approval: {required: true, telegram_msg_id, confirmation_msg_id,
approved_at}`** — live promotion is impossible without this field populated,
and it requires **two** message ids (§6, P6: two-step confirmation).

**`events.schema.json`:** `{source_agent, severity, kind, payload,
requires_reply}` — one envelope for everything sent to Telegram or logged to
the dashboard.

---

## 5. Root `CLAUDE.md` (constitution all agents inherit)

```markdown
# Quant Platform — Agent Constitution

## Identity & scope
- You are one agent in a fan-out system. Do ONLY your delegated role. Never edit
  files owned by another workstream; communicate via contracts/ schemas.

## Non-negotiable safety rules
1. live/ NEVER executes without a promotion record containing a complete
   two-step human_approval.
2. guardrails.toml and promotion_thresholds.toml are read-only to all agents.
   Flag needed changes via Telegram.
3. Key separation is absolute: live production keys exist EXCLUSIVELY in the
   runtime environment of the live/ process. Agents are sandboxed to
   paper-trading and data API keys only. No agent environment ever contains a
   live trading credential. No API keys in code or the vault; read from
   environment / .env (gitignored).
4. Kill switch: if <repo-root>/KILL exists, all trading agents and engines
   halt and confirm halt. Only a human removes it.
5. Budget freeze: if any agent exhausts its monthly token budget, the ENTIRE
   loop freezes (no agent runs) and an emergency alert goes to Telegram.
   Resumption is a human act.

## Brain protocol (Karpathy LLM Wiki)
- New knowledge enters via brain/raw/. Processing = read, extract atomic notes
  into brain/wiki/ with [[wikilinks]], update index.md, append to log.md.
- Every strategy has exactly one page in wiki/strategies/ that is the single
  source of truth for its lifecycle and scorecard.
- Never delete wiki content; supersede it and note why.

## Engineering rules
- Prefer existing libraries over bespoke logic: vectorbt, alpaca-py,
  pandas/polars, tokio, barter-rs, serde, teloxide/grammY. Hand-roll only glue
  and domain-specific signal logic.
- All cross-component data flows validate against contracts/*.schema.json.
- All backtest/paper results pin their data via parquet path + content hash.
- Small commits, conventional messages, one workstream per branch.

## Model discipline
- Orchestrator roles: Opus. Implementation/executor roles: Sonnet. Bulk/routine
  (linting, summarising, ingest triage): Haiku. Do not escalate yourself.
```

---

## 6. Delegated prompts

Notation: **[model]** · **deps** = must finish first · same **group** letter =
run in parallel.

### P0 — Repo Scaffolder · [Sonnet] · deps: none · group: —
> **Role:** Initialise this repo exactly per the layout in §3 (the repo
> itself and this spec already exist — scaffolding is the remaining scope).
> **Rules:** Create the cargo workspace (`engine-core`, `paper-engine`, `live`
> members), the uv Python project in `sandbox/backtest`, empty vault skeleton
> in `brain/`, `.gitignore` (env files, `target/`, `.venv`, `data/`, Obsidian
> workspace files), root `CLAUDE.md` verbatim from §5, `guardrails.toml`
> verbatim from §2.2, and CI stub (fmt + clippy + pytest on push). Do NOT
> implement any logic.
> **Done when:** `cargo check` and `uv run pytest` pass on empty projects;
> repo pushed.

### P1 — Contracts Author · [Opus] · deps: P0 · group: —
> **Role:** Author all five JSON Schemas in `contracts/` per §4, plus
> generated types: Rust structs via `schemars`/`serde` in `engine-core`,
> Python models via `pydantic` in `sandbox/backtest/contracts.py`.
> **Rules:** Schemas are versioned (`$id` with semver). Breaking changes
> require a new version, never mutation. `market` enum includes `polymarket`
> as reserved-but-rejected. Scorecard block per §4 (no Elo). `data_snapshot`
> block mandatory in both result schemas. `human_approval` requires both
> message ids. Write one example instance per schema in `contracts/examples/`.
> **Done when:** Both languages round-trip every example file; documented in
> `contracts/README.md`.
> ⚠️ **This is the only bottleneck. Everything below fans out after P1.**

### P2 — Vault Architect (Brain) · [Sonnet] · deps: P1 · group: A
> **Role:** Build the brain per Karpathy's pattern: `brain/CLAUDE.md` schema
> defining the four operations as Claude Code skills — `/capture` (ingest raw
> → wiki with wikilinks), `/sync` (batch-process raw/), `/lint` (fix orphan
> links, stale index entries, index.md drift), `/digest` (periodic synthesis
> of what changed).
> **Rules:** Strategy pages must embed a fenced `strategy_manifest` JSON block
> validating against the contract — this is how the sandbox discovers
> candidates. Ingest is idempotent; log every operation to `log.md`.
> Templates for strategy/concept/postmortem pages in `brain/wiki/_templates/`
> (strategy template pre-filled for the two v1 families: `ms_shift`, `swing`).
> **Done when:** Dropping a sample PDF + article into raw/ and running /sync
> produces linked wiki pages, an updated index, and a log entry; /lint on a
> deliberately broken vault repairs it.

### P3 — Research Orchestrator + Researchers (Brain) · [Opus orchestrator, Haiku/Sonnet executors] · deps: P2 · group: B
> **Role (orchestrator):** On each heartbeat, decide research direction from
> gaps in the wiki (untested hypotheses, stale strategy pages, unreviewed
> postmortems), then fan out: Haiku agents triage/summarise sources into
> raw/; Sonnet agents deep-read and propose NEW strategy pages with
> falsifiable hypotheses and draft manifests (`lifecycle: research`).
> **Rules:** Research scope is the v1 mandate only: MS Shift and swing
> strategies on daily US-equity charts. Every claim in a wiki page cites its
> raw/ source. Proposals must state the hypothesis, the edge's suspected
> mechanism, and a cheap falsification test. Cap: max 3 new strategy
> proposals per day (quality over volume). Send a one-paragraph daily digest
> event to Telegram.
> **Done when:** A dry run produces ≥1 well-formed strategy proposal from
> seeded sources, with digest delivered.

### P4 — Backtest Engineer (Sandbox/Python) · [Sonnet] · deps: P1 · group: A
> **Role:** Build the Python backtest harness in `sandbox/backtest`.
> **Rules:** Use **vectorbt** for vectorised backtests and **alpaca-py**
> (IEX feed, daily bars — sufficient for the swing timescale) for data; do
> not hand-roll portfolio accounting. A strategy is a class implementing the
> `Signal` protocol referenced by the manifest's `signal_spec`. Enforce:
> walk-forward splits, realistic fees/slippage models, and a hard rule that
> any lookahead access raises. **Reproducibility is mandatory:** downloaded
> bars are cached to parquet under `data/`, content-hashed (sha256), and the
> `data_snapshot` block is written into every result; a run against a
> snapshot whose hash doesn't match must abort. Emit `backtest_result.json`
> per contract + equity curve PNG. CLI: `uv run backtest --manifest <path>`.
> **Done when:** A trivial SMA-cross manifest runs end-to-end twice and
> produces byte-identical, threshold-checked result metrics from the pinned
> snapshot.

### P5 — Rust Engine Core + Paper Engine · [Sonnet] · deps: P1 · group: A
> **Role:** Build `engine-core` (order/position/fill/risk types, mirrors
> contracts) and `paper-engine`: an async tokio service that subscribes to
> Alpaca market data and simulates execution against real-time quotes with
> configurable slippage, running strategies promoted to `lifecycle: paper`.
> **Rules:** Engineering objective is **uptime, state tracking, and
> deterministic risk enforcement — explicitly NOT latency**; the daily/swing
> timescale means seconds are fine, lost state is not. Maintain a persistent
> state journal so a restart resumes exactly where it left off. Evaluate
> **barter-rs** first for the engine loop; build on it if it fits, wrap or
> replace only with justification in an ADR. Signals for paper stage are
> executed from the manifest's compiled ruleset (keep Python out of the
> execution path: the backtest stage exports the fitted signal as parameters
> the Rust engine interprets — define this export format in an ADR under
> `docs/`, covering at minimum the `ms_shift` and `swing` families).
> Structured `tracing` logs; results appended as `paper_result.json` daily
> with the `data_snapshot` provenance of the strategy's fitted parameters.
> No network writes to any broker order endpoint from this crate — enforce at
> type level (no order-submission client dependency). Halt on root `KILL`.
> **Done when:** SMA-cross paper-trades against live Alpaca paper data for a
> session, survives a mid-session restart without state loss, and emits
> valid results.

### P6 — Telegram Bridge · [Sonnet] · deps: P1 · group: A
> **Role:** Two-way Telegram bot in `infra/telegram` (grammY/TypeScript or
> python-telegram-bot — pick one, justify in README).
> **Rules:** **Auth is an allowlist of one:** the bot hard-pins the owner's
> numeric Telegram user ID (from env, e.g. `TELEGRAM_OWNER_ID`); every
> update from any other ID is dropped and logged, never processed. Inbound:
> `/status`, `/halt` (creates root `KILL`), `/resume` (removes it),
> `/approve <promotion-id>`, `/reject <id>`, and free-text messages routed
> to the on-duty orchestrator as tasks. **Live promotions use a strict
> two-step interactive confirmation:** `/approve <id>` on a paper→live
> promotion makes the bot echo back the strategy, size, scorecard, and
> evidence links, and the approval is only written when the owner replies
> `CONFIRM <id>`; both message ids are recorded in `human_approval`.
> Anything else cancels. Outbound: consumes `events.schema.json` from a
> simple file-queue; batches low-severity events into digests, sends
> high-severity (circuit breaker, budget freeze) immediately. Approval
> replies write `human_approval` into the promotion record atomically.
> **Done when:** Round trip works — a fake promotion event pings the phone,
> the two-step `/approve` → `CONFIRM` updates the record, a message from a
> non-owner ID is provably ignored, and `/halt` stops a running paper engine.

### P7 — Ranker & Promotion Pipeline · [Opus] · deps: P4, P5 · group: C
> **Role:** The gatekeeper between lifecycle stages. Reads all result files +
> wiki strategy pages, maintains each strategy's **Performance Score Card**
> (walk-forward Sharpe, Sortino, Max Drawdown — no Elo in v1), and issues
> promotion records: research → backtest (auto), backtest → paper (auto if
> thresholds met), **paper → live (ALWAYS requires the two-step Telegram
> approval)**, any → retired.
> **Rules:** Promotion criteria live in `contracts/promotion_thresholds.toml`
> (min walk-forward Sharpe, min Sortino, max drawdown, min paper days) —
> human-editable, agent-readable, never agent-writable. Results with a
> broken `data_snapshot` hash are ignored. Every promotion/demotion gets a
> rationale written to the strategy's wiki page (this is half the value
> backprop). Demote aggressively; capital is finite.
> **Done when:** Given seeded results, it ranks and promotes/demotes
> correctly and blocks a live promotion until a complete two-step approval
> exists.

### P8 — Live Engine · [Sonnet, reviewed by Opus] · deps: P5, P6, P7 · group: D
> **Role:** `live/` crate reusing engine-core + the paper engine's strategy
> runtime, but submitting real orders through the Alpaca trading API.
> **Rules:**
> - **Startup refuses unless:** valid approved promotion records exist (with
>   complete two-step `human_approval`), `guardrails.toml` parses, and no
>   root `KILL` exists.
> - **Crash recovery is a first-class requirement:** on every startup the
>   engine reconciles local position state against Alpaca's account ledger
>   before accepting any signal; every order carries an **idempotent client
>   order ID** (deterministic function of strategy id + signal + trading
>   day) so a crash mid-submit can never double-order; orphaned open orders
>   found during reconciliation are cancelled and reported.
> - **Guardrails enforced inside the order path** (§2.2): max position size,
>   max order rate, and the max-daily-loss circuit breaker → auto-flatten,
>   freeze execution, Telegram alert, drop root `KILL`.
> - **Key separation:** this process's runtime environment is the ONLY place
>   live production keys exist. It is launched from a dedicated environment
>   file readable by no agent.
> - **Dry-run is the default and targets Alpaca's paper-trading endpoints**
>   — the full order path (auth, order types, error handling, reconciliation)
>   is exercised end-to-end with zero risk. Real mode requires an env var
>   AND a CLI flag AND `environment = "real"` in guardrails.toml.
> - Every fill and every guardrail trigger emits an event.
> **Done when:** In dry-run against the Alpaca paper account: it refuses to
> start without approvals, places and reconciles a real paper order with an
> idempotent client order ID, survives a kill-and-restart without
> double-ordering, trips the circuit breaker on a simulated loss (flatten +
> freeze + alert + KILL), and alerts Telegram.

### P9 — Post-Mortem Analyst (value backprop) · [Sonnet] · deps: P8 · group: E
> **Role:** After each paper/live session: write a postmortem wiki page
> (expected vs realised edge, slippage vs model, guardrail events), update
> the strategy page's scorecard block, and file follow-up research questions
> into the Research Orchestrator's queue.
> **Rules:** Postmortems link the strategy page, the result files, and any
> relevant concept pages. Quantify, don't narrate. This closes the loop — its
> outputs are P3's inputs.
> **Done when:** A completed paper session yields a linked postmortem and an
> updated scorecard visible in Obsidian's graph.

### P10 — Paperclip + Scheduling · [Sonnet] · deps: P3, P6 · group: C
> **Role:** Stand up **Paperclip** (the 2026 open-source Node/React
> agent-orchestration platform, self-hosted) in `infra/paperclip` as the
> management dashboard, using its **native company/budget layout and
> standard containerized execution environment**: define the org chart
> mirroring this prompt set (Opus orchestrators as managers, Sonnet/Haiku
> executors reporting to them), per-agent monthly budgets, and heartbeat
> schedules.
> **Rules:** Heartbeats: research orchestrator daily pre-US-open (compute
> from the exchange calendar via `pandas_market_calendars`, don't hardcode
> UTC hours); vault `/lint` + `/digest` + index/CLAUDE.md hygiene nightly.
> Mirror critical schedules as plain WSL cron entries in `infra/cron/` so
> trading-critical jobs don't depend on the dashboard being up. All agent
> runs must appear in Paperclip's audit trail with cost. **Budget overrun
> policy: if any agent exhausts its monthly token budget, freeze the entire
> loop (no agent runs) and push an emergency high-severity alert to
> Telegram; resumption is a human act.**
> **Done when:** Dashboard shows the org chart, a heartbeat fires the
> research orchestrator, token spend per agent is visible, and a simulated
> budget exhaustion freezes the loop and alerts Telegram.

### P11 — Integration Test Conductor · [Opus] · deps: all · group: —
> **Role:** Script one full loop on a toy strategy: seed a source → research
> proposes → backtest passes (with pinned snapshot) → paper runs (short
> simulated session, including a restart) → ranker requests live promotion →
> two-step Telegram approve → live dry-run executes against the Alpaca paper
> account → postmortem lands in the vault. Document every seam that leaked.
> **Done when:** The loop runs unattended except for the Telegram
> approve-and-confirm taps.

---

## 7. Parallel execution plan

| Wave | Runs in parallel | Prompts |
|------|------------------|---------|
| 0 | sequential | P0 → P1 |
| 1 | group A (4 agents) | P2, P4, P5, P6 |
| 2 | groups B + C | P3, P7, P10 |
| 3 | group D | P8 |
| 4 | group E | P9 |
| 5 | sequential | P11 |

Wave 1 is fully independent because every prompt codes only against
`contracts/` — that's the whole reason P1 exists.

## 8. Library summary (prefer these; hand-roll only glue + signals)

| Concern | Library |
|---|---|
| Backtesting | vectorbt (fallback: backtrader for event-driven cases) |
| Equities data + broker | alpaca-py (paper + live on the same API; IEX daily bars in v1) |
| Rust engine | tokio, barter-rs (evaluate), serde, schemars, tracing |
| Telegram | grammY (TS) or python-telegram-bot |
| Scheduling/calendar | Paperclip heartbeats + cron; pandas_market_calendars |
| Dataframes | polars (Python side) |
| Orchestration/dashboard | Paperclip (self-hosted, containerized execution) |

*(py-clob-client / Polymarket tooling: deferred with the rest of Polymarket
to v2.)*

## 9. Open risks to keep in view

- **Real-capital autonomy:** the two-step Telegram approval gate +
  guardrails.toml + root KILL file are the system's spine. Never let an
  agent "temporarily" relax them — the constitution makes them read-only,
  and reviews should treat any diff touching them as a red flag.
- **Python↔Rust signal handoff (P5's ADR):** the trickiest seam. Start with
  parameterised rulesets (Rust interprets fitted params) covering the
  `ms_shift` and `swing` families; only consider embedding (PyO3) if
  strategies outgrow that.
- **barter-rs fit:** it's built with latency-sensitive designs in mind; if
  its abstractions fight the uptime/state-journal priority, wrapping or
  replacing (with an ADR) is acceptable — the mandate is reliability.
- **Paper→real transition:** v1 runs entirely on the $100k paper
  environment. Flipping `environment = "real"` is a human decision that
  deserves its own checklist (broker funding, guardrail re-review, sizing
  ramp-up) — write that checklist before the flip, not during.
- **WSL file-watching:** if Obsidian feels laggy on `\\wsl$`, that's
  cosmetic; don't move the vault out of ext4 — agents' I/O speed matters
  more.

---

## Appendix A — Decision log (2026-07-19)

| Question | Decision |
|---|---|
| Strategy mix & timescale | MS Shift + multi-day swing, daily interval only; Rust = uptime/state/risk, not latency |
| Capital & limits | $100k paper start; 5% ($5k) max position; 2% ($2k) daily-loss circuit breaker → flatten + freeze + Telegram + root KILL |
| Polymarket | Cut from v1; schema enums stay extensible |
| Elo | Dropped for v1; Performance Score Card on walk-forward Sharpe, Sortino, Max Drawdown |
| Paperclip | Official 2026 open-source Node/React platform; native company/budget layout, containerized execution |
| Crash recovery | P8: startup reconciliation vs Alpaca ledger + idempotent client order IDs |
| Key separation | Live keys exclusively in the live/ process runtime; agents sandboxed to paper/data keys |
| Telegram security | Bot pinned to owner's numeric user ID; two-step interactive confirmation for live promotions |
| Reproducibility | Parquet snapshot caching + content hash inside result schemas |
| Budget overruns | Exhausted budget freezes the entire loop + emergency Telegram alert |
| Dry-run definition | Live engine dry-run targets Alpaca paper-trading endpoints end-to-end |
| Repo separation | `quant-platform` is its own private repo, fully independent of any other project (done 2026-07-19) |
