#!/usr/bin/env bash
# Heartbeat wrapper: every scheduled agent run goes through here so the
# freeze/kill gates apply uniformly and every run lands in the audit log.
# Usage: run_agent.sh <role> <command...>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROLE="$1"; shift
AUDIT="$ROOT/infra/paperclip/audit.log"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -f "$ROOT/infra/paperclip/FROZEN" ]]; then
  echo "$TS $ROLE SKIPPED (loop frozen)" >> "$AUDIT"; exit 0
fi
if [[ -f "$ROOT/KILL" && "$ROLE" != "vault-ops" ]]; then
  echo "$TS $ROLE SKIPPED (KILL present)" >> "$AUDIT"; exit 0
fi

echo "$TS $ROLE START $*" >> "$AUDIT"
if "$@"; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $ROLE OK" >> "$AUDIT"
else
  rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $ROLE FAILED rc=$rc" >> "$AUDIT"
  exit $rc
fi
