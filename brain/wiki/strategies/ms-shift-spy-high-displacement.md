---
type: strategy
created: 2026-07-20
---

# MS Shift SPY — High Displacement (v2)

Single-variable follow-up to [[ms-shift-spy]] (v1, retired 2026-07-20). Not
a new mechanism — a stricter version of the same one, isolating a single
question the v1 postmortem raised.

## Hypothesis

v1's real 12-fold walk-forward result (see [[ms-shift-spy]]'s Lifecycle
history and `brain/raw/ms-shift-spy-v1-fold-regime-hypothesis.md`) showed
its edge concentrated in 3 of 12 folds — all clean, sustained continuation
windows (COVID crash+recovery, the following 2020-21 recovery, the 2023-24
AI rally) — while the other 9 folds sat in a mediocre 0.0-0.82 Sharpe
band. v1's displacement filter (range ≥ 1.5× 14-day ATR) may be too loose,
letting through low-conviction structure breaks that dilute the average
with noise trades rather than concentrating on the high-conviction breaks
that actually predict continuation.

**Hypothesis:** raising the displacement threshold to 2.0× ATR (v1's 1.5×
→ 2.0×, everything else unchanged) will act as a crude conviction filter,
pruning weak entries and raising walk-forward Sharpe versus v1's 0.674
(12-fold) / 0.657 (5-fold) — even at the cost of materially fewer trades.

**Killed if:** walk-forward Sharpe with mult=2.0 is not clearly better
than v1 (say, doesn't clear ≥0.85) — a wash or a decline would mean
displacement magnitude isn't distinguishing good entries from noise, and
the mediocre folds are mediocre for some other reason. **Also killed if**
trade count collapses to a handful of trades over the 9-year period —
that would make any Sharpe reading statistically meaningless rather than
a real result, and needs to be checked before the Sharpe number is
trusted at all (see Falsification test).

## Mechanism

Identical to v1 — see [[market-structure-shift]] and [[displacement]].
The only added claim here is that displacement *magnitude* is a
reasonable proxy for entry conviction, so filtering harder on it should
improve selectivity without abandoning the underlying premise.

## Calibration (why 2.0, not 3.0)

Before picking a value, candidate multipliers (1.5, 1.75, 2.0, 2.25, 2.5,
3.0) were sanity-checked against synthetic i.i.d.-noise OHLC series
(offline, no live data needed — this only tests firing frequency, not
performance). Result: 3.0 fired **zero times** over a synthetic
9-year-equivalent series across 5 seeds; even 2.0 was sparse (~0.4
position changes per run). Real markets cluster volatility far more than
independent Gaussian draws (autocorrelated true range, fat tails), so
this systematically *underestimates* real firing frequency — it's a lower
bound, not a prediction — but it was enough to rule out 3.0 as almost
certainly too aggressive for a statistically meaningful test, and to
choose 2.0 as a genuine-but-not-reckless step up from v1's 1.5.

## Falsification test

Run the existing harness against the same manifest shape as v1
(SPY+QQQ, 2016-01-01 to 2024-12-31, `folds=12` to match the resolution
that produced v1's fold breakdown). Before trusting the Sharpe number,
check the trade count / turnover first — if it's too sparse to be
meaningful (single digits of trades over 9 years), that alone falsifies
the "2.0 is a usable threshold" premise regardless of what the Sharpe
says. If trade count is reasonable, compare the fold-by-fold Sharpes
directly against v1's 12-fold breakdown: the hypothesis predicts the
weak/mediocre folds should either drop out (fewer or no trades in those
windows) or improve, while the 3 strong folds (2019-10→2020-07,
2020-07→2021-04, 2023-07→2024-04) should be preserved.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-spy-v2",
  "wiki_page": "brain/wiki/strategies/ms-shift-spy-high-displacement.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "Raising the displacement threshold from 1.5x to 2.0x 14-day ATR (v1's only other parameters unchanged) filters out low-conviction structure breaks and raises walk-forward Sharpe versus v1's 0.674 (12-fold); killed if Sharpe does not clear 0.85 or if trade count collapses to a statistically meaningless handful of trades over 2016-2024.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_spy_high_displacement.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0 },
  "lifecycle": "research",
  "scorecard": {
    "sharpe_wf": null, "sortino_wf": null, "max_drawdown_bt": null,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Not yet backtested — this is the next command to run in the operator's
environment (real Alpaca data required, same as v1):

```sh
cd sandbox/backtest
uv run python -c "
import json, re
from pathlib import Path
page = Path('../../brain/wiki/strategies/ms-shift-spy-high-displacement.md').read_text()
manifest = json.loads(re.search(r'\`\`\`strategy_manifest\n(.*?)\`\`\`', page, re.S).group(1))
manifest['lifecycle'] = 'backtest'
Path('/tmp/ms_shift_v2_manifest.json').write_text(json.dumps(manifest, indent=2))
"
uv run backtest --manifest /tmp/ms_shift_v2_manifest.json --start 2016-01-01 --end 2024-12-31 --folds 12
```

Same reproducibility caveat as v1 applies: `data/` is gitignored, so this
result will need to be manually recorded in this page once run, the same
way [[ms-shift-spy]]'s retirement was.

## Lifecycle history

- 2026-07-20 — created at `research` — proposed as a single-variable
  follow-up to [[ms-shift-spy]]'s (v1) retirement postmortem; parameter
  choice calibrated against synthetic firing-frequency checks (see
  Calibration section above) rather than picked arbitrarily.
