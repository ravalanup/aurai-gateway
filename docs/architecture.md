# Architecture

## Role
The gateway is the only path from Aurai applications to model providers (ADR 0002). It authenticates callers with team virtual keys, enforces budgets and rate limits, applies the PII policy for the caller's risk tier, routes the alias to a provider model with retries and fallback, and emits traces and spend records.

## Components

| Component | Runs as | Purpose |
|---|---|---|
| LiteLLM proxy | Deployment (2+ replicas, HPA) | OpenAI-compatible API, key management, routing, spend tracking |
| `aurai_gateway` package | Installed in the LiteLLM image | Tiered PII guardrail and team tooling |
| Presidio analyzer | Deployment (2 replicas) | Detects PII entities in text over REST |
| PostgreSQL | Shared (`aurai-infra`) | Keys, teams, spend logs. Database `litellm` is created on first start |
| Redis | Shared (`aurai-infra`) | Response cache and router state |
| OpenTelemetry collector | Shared (`aurai-infra`) | Receives traces from the gateway |
| Secret `litellm-secrets` | Created by script (local) or External Secrets (AWS) | Master key, salt key, database URLs, provider keys |

## Request path
1. The caller sends a request to an alias such as `aurai-balanced` with a team virtual key.
2. LiteLLM validates the key, the allowed model list, budget and rate limits.
3. The `aurai-pii` guardrail reads the team's `risk_tier` from metadata, asks Presidio to analyze each text field, then masks or rejects according to the tier policy.
4. The router maps the alias to the provider model. On error it retries, then moves to the configured fallback.
5. LiteLLM records spend against the team and key, and sends a trace through OpenTelemetry. The trace carries counts of masked entities and the tier, never the detected values.

## Why these choices
- **Aliases over vendor names.** Applications stay unchanged when a provider model is swapped; changes are tested against golden sets first (`aurai-eval-governance`).
- **Policy as code.** Teams, budgets and tiers are reviewed in pull requests and applied by a script, not clicked in a console.
- **Analyzer as a separate service.** The language model for entity recognition is memory-heavy. Running it as its own Deployment keeps the gateway pods small and lets each scale on its own.
- **Masking in the gateway process.** Replacing spans with placeholders is a simple string operation; calling a second Presidio service for it would add a network hop without adding capability.
- **Fail closed for T2 and T3.** If PII cannot be checked, the request does not go out. T0 and T1 fail open and record the error so a PII outage does not stop personal productivity use.
- **Config rendered from chart values.** The chart is the single source for models and fallbacks; tests check it against the approved catalog.

## Network
- `aurai-gateway` namespace denies ingress by default.
- LiteLLM accepts traffic from namespaces labelled `aurai.io/platform-access=true` (set by `aurai-infra`).
- Presidio accepts traffic only from LiteLLM pods.
- Egress is open so the gateway can reach provider APIs. A production deployment would route egress through a proxy with an allow list.

## What production would add
- Per-model and per-region data residency routing, and contractual review evidence in the catalog
- SSO for the admin interface through Keycloak, with role mapping to platform and team administrators
- Egress allow list and private connectivity to providers
- Prompt and response retention controls by tier, with an audit store separate from traces
- Presidio custom recognizers for company identifiers, and evaluation of masking quality on a labelled set
- Output-side guardrails (post-call) for T3, and prompt-injection screening
- Load testing, capacity plans and per-team priority queues
- Multi-region failover and provider health-based routing
- Enterprise license features of LiteLLM where required (SSO, audit logs), after a build-vs-buy review
