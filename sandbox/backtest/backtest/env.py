"""Load the repo-root .env into the process environment, once.

Called by entrypoints that need Alpaca credentials. Real environment
variables always win over .env (so systemd/CI overrides are respected);
missing python-dotenv is non-fatal (env may already be exported)."""

from __future__ import annotations

from pathlib import Path


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for parent in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent]:
        candidate = parent / ".env"
        if (parent / "CLAUDE.md").is_file() and candidate.is_file():
            load_dotenv(candidate, override=False)
            return
