#!/usr/bin/env bash
# P11 — Integration Test Conductor.
#
# Drives one full loop on the sma-cross-demo toy strategy through every seam:
#
#   research -> backtest -> ranker(->paper) -> paper engine -> ranker(live
#   request) -> Telegram two-step approve -> live dry-run (sim broker) ->
#   postmortem
#
# Runs unattended except that the Telegram approval is injected the way the
# bridge would write it (the human tap is simulated here so CI can run it).
# Every leaked seam is echoed with a >>> LEAK marker. Exit non-zero on any
# broken seam.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
STRAT="sma-cross-demo"
LEAKS=0
step() { echo; echo "=== $* ==="; }
leak() { echo ">>> LEAK: $*"; LEAKS=$((LEAKS + 1)); }
ok()   { echo "    ok: $*"; }

# Clean slate for a repeatable run.
rm -rf data/results/$STRAT data/live/$STRAT data/promotions \
       infra/telegram/queue/evt-* KILL
mkdir -p data infra/telegram/queue
# Reset the demo strategy page's manifest lifecycle to research + seed history.
python3 - << 'PY'
import re
from pathlib import Path
p = Path("brain/wiki/strategies/sma-cross-demo.md")
t = p.read_text()
t = re.sub(r'("lifecycle":\s*)"[a-z]+"', r'\1"research"', t, count=1)
t = re.sub(r'(## Lifecycle history\n\n).*', r'\1- 2026-07-19 — created at `research` — P11 integration test seed\n', t, flags=re.S)
p.write_text(t)
PY

# A pinned synthetic snapshot so the loop is deterministic and offline.
# Generated via uv (system python3 lacks pandas/pyarrow).
SNAP="$ROOT/data/us_equities/daily/${STRAT}_snapshot.parquet"
( cd "$ROOT/sandbox/backtest" && uv run python - "$SNAP" << 'PY'
import sys, numpy as np, pandas as pd
from pathlib import Path
path = Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)
dates = pd.bdate_range("2020-01-01", "2023-12-29").strftime("%Y-%m-%d")
# Gentle uptrend so the crossover actually trades and (usually) passes.
close = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.011, len(dates))))
df = pd.DataFrame({"symbol": "SPY", "date": dates, "open": close*0.999,
                   "high": close*1.005, "low": close*0.995, "close": close,
                   "volume": 1e6})
df.to_parquet(path, index=False)
print(f"snapshot: {path}")
PY
) || leak "snapshot generation failed"

# ---------------------------------------------------------------- 1. research
step "1. research -> backtest (ranker auto-promotes once the signal exists)"
cd "$ROOT/sandbox/backtest"
uv run ranker >/tmp/qp_rank1.txt 2>&1 || true
grep -q "$STRAT: research -> backtest" /tmp/qp_rank1.txt \
  && ok "ranker promoted research->backtest" \
  || leak "research->backtest not performed: $(cat /tmp/qp_rank1.txt)"

# ---------------------------------------------------------------- 2. backtest
step "2. backtest run -> contract-valid result + exported ruleset"
MANIFEST="$ROOT/tests/integration/${STRAT}.manifest.json"
uv run python - "$MANIFEST" << 'PY'
import sys, json, re
from pathlib import Path
page = Path("../../brain/wiki/strategies/sma-cross-demo.md").read_text()
manifest = re.search(r"```strategy_manifest\n(.*?)```", page, re.S).group(1)
m = json.loads(manifest); m["lifecycle"] = "backtest"
Path(sys.argv[1]).write_text(json.dumps(m, indent=2))
PY
uv run backtest --manifest "$MANIFEST" --start 2020-01-01 --end 2023-12-29 \
  --snapshot "$SNAP" --no-fetch \
  >/tmp/qp_bt.txt 2>&1 \
  && ok "backtest produced $(cat /tmp/qp_bt.txt)" \
  || { leak "backtest failed: $(cat /tmp/qp_bt.txt)"; }
[ -f "$ROOT/data/results/$STRAT/ruleset.json" ] \
  && ok "ruleset.json exported for the Rust engines" \
  || leak "ruleset.json missing (ADR 0002 handoff)"

# --------------------------------------------------- 3. ranker backtest->paper
step "3. ranker: backtest -> paper (if thresholds met)"
uv run ranker >/tmp/qp_rank2.txt 2>&1 || true
cat /tmp/qp_rank2.txt
LIFECYCLE=$(uv run python -c "import ranker,pathlib; print(ranker.read_manifest(pathlib.Path('../../brain/wiki/strategies/${STRAT}.md')).lifecycle)")
if [ "$LIFECYCLE" = "paper" ]; then
  ok "promoted to paper"
elif [ "$LIFECYCLE" = "retired" ]; then
  echo "    note: toy strategy retired at thresholds — loop behaved correctly."
  echo "    Forcing lifecycle=paper to exercise the remaining seams."
  uv run python - << 'PY'
import re, json, pathlib
p = pathlib.Path("../../brain/wiki/strategies/sma-cross-demo.md")
t = p.read_text()
block = re.search(r"(```strategy_manifest\n)(.*?)(```)", t, re.S)
m = json.loads(block.group(2)); m["lifecycle"] = "paper"
p.write_text(t[:block.start()] + block.group(1) + json.dumps(m, indent=2) + "\n" + block.group(3) + t[block.end():])
PY
else
  leak "unexpected lifecycle after ranker: $LIFECYCLE"
fi

# ---------------------------------------------------------------- 4. paper run
step "4. paper engine: sim session -> paper_result.json"
cp "$ROOT/data/results/$STRAT/ruleset.json" /tmp/qp_ruleset.json
uv run python - "$MANIFEST" << 'PY'
import sys, json
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text()); m["lifecycle"] = "paper"
Path(sys.argv[1]).write_text(json.dumps(m, indent=2))
PY
cd "$ROOT"
cargo run -q -p paper-engine -- --manifest "$MANIFEST" \
  --ruleset "data/results/$STRAT/ruleset.json" --feed sim --sessions 30 \
  >/tmp/qp_paper.txt 2>&1 \
  && ok "paper result: $(tail -1 /tmp/qp_paper.txt)" \
  || leak "paper engine failed: $(cat /tmp/qp_paper.txt)"

# ------------------------------------------------- 5. ranker requests live
step "5. ranker: paper -> live REQUEST (must block on approval)"
cd "$ROOT/sandbox/backtest"
# Ensure the paper result clears thresholds for the demo by checking; if not,
# the loop is still correct — we note it and still exercise the gate via a
# seeded pending promotion so the approval seam is tested regardless.
uv run ranker >/tmp/qp_rank3.txt 2>&1 || true
cat /tmp/qp_rank3.txt
PROMO=$(ls "$ROOT/data/promotions/"*live.json 2>/dev/null | head -1 || true)
if [ -z "$PROMO" ]; then
  echo "    note: paper thresholds not met by toy result; seeding a live"
  echo "    promotion request to exercise the approval + live-engine seams."
  PROMO="$ROOT/data/promotions/promo-$(date -u +%Y-%m-%d)-${STRAT}-live.json"
  mkdir -p "$ROOT/data/promotions"
  cat > "$PROMO" << EOF
{
  "schema_version": "1.0.0",
  "id": "promo-$(date -u +%Y-%m-%d)-${STRAT}-live",
  "strategy_id": "${STRAT}",
  "from_stage": "paper",
  "to_stage": "live",
  "evidence": ["data/results/${STRAT}/paper_result.json"],
  "rationale": "integration test",
  "issued_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "human_approval": { "required": true, "telegram_msg_id": null, "confirmation_msg_id": null, "approved_at": null }
}
EOF
fi
# Live engine MUST refuse while approval is incomplete.
cd "$ROOT"
if cargo run -q -p live -- --manifest "$MANIFEST" \
     --ruleset "data/results/$STRAT/ruleset.json" --mode sim --sessions 5 \
     >/tmp/qp_live_blocked.txt 2>&1; then
  leak "live engine STARTED without approval — safety gate failed"
else
  grep -q "refusing to start" /tmp/qp_live_blocked.txt \
    && ok "live engine correctly refused (no approval yet)" \
    || leak "live refused for the wrong reason: $(cat /tmp/qp_live_blocked.txt)"
fi

# --------------------------------------------- 6. Telegram two-step approval
step "6. Telegram two-step approval (simulated human tap)"
cd "$ROOT/infra/telegram"
PROMO_ID=$(basename "$PROMO" .json)
TELEGRAM_OWNER_ID=777000111 uv run python - "$PROMO_ID" << 'PY'
import sys
from pathlib import Path
from telegram_bridge import core
root = Path("../..").resolve()
pid = sys.argv[1]
text, pending = core.start_approval(root, pid, approve_msg_id=2001)
assert pending is not None, "live promotion must require confirmation"
msg = core.confirm_approval(root, pending, f"CONFIRM {pid}", confirm_msg_id=2002)
assert "approved" in msg, msg
appr = core.load_promotion(root, pid)["human_approval"]
assert appr["telegram_msg_id"] == 2001 and appr["confirmation_msg_id"] == 2002
print("    ok: two-step approval recorded", appr)
PY
[ $? -eq 0 ] && ok "approval written with both message ids" \
             || leak "two-step approval failed"

# ----------------------------------------------------- 7. live dry-run (sim)
step "7. live engine dry-run (sim broker) now that approval exists"
cd "$ROOT"
cargo run -q -p live -- --manifest "$MANIFEST" \
  --ruleset "data/results/$STRAT/ruleset.json" --mode sim --sessions 10 \
  >/tmp/qp_live.txt 2>&1 \
  && ok "live engine ran end-to-end in sim (approved)" \
  || leak "live engine failed after approval: $(cat /tmp/qp_live.txt)"
[ -f "data/live/$STRAT/live_journal.jsonl" ] \
  && ok "live journal written (crash-recoverable state)" \
  || leak "live journal missing"

# ----------------------------------------------------------- 8. postmortem
step "8. postmortem lands in the vault"
python3 "$ROOT/tests/integration/write_postmortem.py" "$ROOT" \
  && ok "postmortem generated from real session results" \
  || leak "postmortem generation failed"
[ -f "brain/wiki/postmortems/sma-cross-demo-p11.md" ] \
  && ok "postmortem present in vault" \
  || leak "postmortem not generated"

# --------------------------------------------------------------- summary
step "loop summary"
if [ "$LEAKS" -eq 0 ]; then
  echo "PASS — full loop ran unattended except the (simulated) approval tap."
  exit 0
else
  echo "FAIL — $LEAKS seam(s) leaked. See >>> LEAK markers above."
  exit 1
fi
