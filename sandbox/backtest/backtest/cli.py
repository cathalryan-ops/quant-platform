"""CLI: uv run backtest --manifest <path> --start YYYY-MM-DD --end YYYY-MM-DD"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contracts import StrategyManifest

from .engine import find_repo_root, run_backtest
from .env import load_env


def main(argv: list[str] | None = None) -> int:
    load_env()  # Alpaca keys from repo-root .env, if present
    parser = argparse.ArgumentParser(prog="backtest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--snapshot", type=Path, default=None, help="parquet override")
    parser.add_argument("--expected-hash", default=None, help="sha256:<hex> pin; abort on mismatch")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None, help="results dir (default data/results)")
    parser.add_argument(
        "--no-fetch", action="store_true", help="fail rather than fetch if snapshot is missing"
    )
    args = parser.parse_args(argv)

    manifest = StrategyManifest.model_validate(json.loads(args.manifest.read_text()))
    repo_root = find_repo_root(Path.cwd())
    result_path = run_backtest(
        manifest,
        start=args.start,
        end=args.end,
        repo_root=repo_root,
        snapshot_path=args.snapshot,
        expected_hash=args.expected_hash,
        folds=args.folds,
        out_dir=args.out,
        fetch=not args.no_fetch,
    )
    print(result_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
