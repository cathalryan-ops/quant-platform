"""Pins the Rust golden fixture to the Python side: the committed fixture's
expected_weights must still equal what the Python strategy produces for its
bars. If this fails after an intentional strategy change, regenerate the
fixture (see the generator in the P-shift commit) and update the Rust side."""

import importlib.util
import json
from pathlib import Path

import pandas as pd

from backtest.signal import BarFrame

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "engine-core/tests/fixtures/ms_shift_golden.json"

_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy", REPO_ROOT / "sandbox/backtest/strategies/ms_shift_spy.py"
)
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)


def test_python_matches_committed_golden_fixture():
    fx = json.loads(FIXTURE.read_text())
    high = [b["high"] for b in fx["bars"]]
    low = [b["low"] for b in fx["bars"]]
    close = [b["close"] for b in fx["bars"]]
    idx = pd.RangeIndex(len(close))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    bars = BarFrame(open=mk(close), high=mk(high), low=mk(low), close=mk(close))

    p = fx["params"]
    sig = ms.Signal(
        swing_lookback=p["swing_lookback"],
        atr_period=p["atr_period"],
        displacement_mult=p["displacement_mult"],
    )
    got = sig.generate(bars)["SPY"].tolist()
    assert got == fx["expected_weights"], "Python drifted from the golden fixture"
