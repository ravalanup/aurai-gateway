#!/usr/bin/env bash
# One chat call through the gateway with a team key.
#   export AURAI_KEY=<virtual key from: aurai-teamctl issue-key sandbox --alias demo>
set -euo pipefail
curl -sS "${AURAI_GATEWAY_URL:-http://localhost:4000}/chat/completions" \
  -H "Authorization: Bearer ${AURAI_KEY:?set AURAI_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "aurai-fast", "messages": [{"role": "user", "content": "Say hello in five words."}]}'
