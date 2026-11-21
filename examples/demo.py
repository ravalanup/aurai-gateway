"""Shows the gateway enforcing risk tiers with the same prompt.

Prerequisites: the gateway is port-forwarded to localhost:4000, teams are applied
(`aurai-teamctl apply teams/teams.yaml`) and LITELLM_MASTER_KEY is set in this shell.

  python examples/demo.py

The prompt contains synthetic data only. For each demo team the script issues a short-lived key,
sends the prompt through the gateway and prints what happened. Keys are not printed.
"""

from __future__ import annotations

import os
import sys

import httpx

BASE_URL = os.environ.get("AURAI_GATEWAY_URL", "http://localhost:4000")
ADMIN_KEY = os.environ.get("LITELLM_MASTER_KEY")
MODEL = os.environ.get("AURAI_DEMO_MODEL", "aurai-fast")

PROMPT = (
    "Summarize this note in one sentence: Alex Rivera (alex.rivera@example.com, 555-123-4567) "
    "paid with card 4111 1111 1111 1111 and asked about weekend hours."
)

TEAMS = [("sandbox", "T0"), ("internal-help", "T1"), ("ops-insights", "T2"), ("guest-assistant", "T3")]


def main() -> int:
    if not ADMIN_KEY:
        print("Set LITELLM_MASTER_KEY first.", file=sys.stderr)
        return 1
    admin = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {ADMIN_KEY}"}, timeout=60)
    print(f"Prompt: {PROMPT}\n")

    for team_id, tier in TEAMS:
        issued = admin.post(
            "/key/generate",
            json={
                "team_id": team_id,
                "key_alias": f"demo-{team_id}",
                "duration": "1h",
                "metadata": {"risk_tier": tier},
            },
        )
        if issued.status_code >= 300:
            print(f"[{tier}] {team_id}: could not issue key ({issued.status_code}). Apply teams first.")
            continue
        key = issued.json()["key"]
        response = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 120},
            timeout=120,
        )
        if response.status_code == 200:
            text = response.json()["choices"][0]["message"]["content"].strip()
            print(f"[{tier}] {team_id}: allowed\n    reply: {text}\n")
        else:
            detail = response.json().get("error", response.json())
            print(f"[{tier}] {team_id}: HTTP {response.status_code}\n    {detail}\n")
    print("Traces in Langfuse or Phoenix (aurai-eval-governance) show the masked prompts and aurai_pii metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
