#!/usr/bin/env bash
# Budget overrun policy (architecture.md, decision log): freeze the ENTIRE
# agent loop and alert. Called by Paperclip's budget hook with the agent
# role as $1. Resumption is a human act: rm infra/paperclip/FROZEN.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT="${1:-unknown}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

touch "$ROOT/infra/paperclip/FROZEN"

EVT_ID="evt-budget-freeze-$(date -u +%Y%m%d%H%M%S)"
mkdir -p "$ROOT/infra/telegram/queue"
cat > "$ROOT/infra/telegram/queue/$EVT_ID.json" << EOF
{
  "schema_version": "1.0.0",
  "id": "$EVT_ID",
  "source_agent": "paperclip",
  "severity": "critical",
  "kind": "budget_freeze",
  "payload": { "text": "Agent '$AGENT' exhausted its monthly token budget. ENTIRE loop frozen (infra/paperclip/FROZEN). Delete the file to resume." },
  "requires_reply": true,
  "ts": "$TS"
}
EOF
echo "loop frozen by $AGENT at $TS"
