"""Walk-forward backtest harness (P4).

Pipeline: strategy manifest -> pinned parquet snapshot -> lookahead-checked
signal -> vectorbt walk-forward simulation -> contract-valid
backtest_result.json + equity curve PNG.
"""
