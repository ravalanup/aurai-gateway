# Guardrails and risk tiers

Policy file: `src/aurai_gateway/policies/pii.yaml`. Governance background: `aurai-docs/docs/governance`.

## How the tier is chosen
The guardrail reads `risk_tier` from the key's metadata, then from the team's metadata. The platform team sets it through `teams/teams.yaml`. It is never read from the request body or headers, so callers cannot lower it. Keys without a tier use the default tier (T2), which masks broadly and fails closed.

## Policy by tier

| Tier | Mask | Block | Trace flag | Analyzer down |
|---|---|---|---|---|
| T0 | identifiers | - | no | allow, record error |
| T1 | identifiers, contact | - | no | allow, record error |
| T2 | identifiers, contact, personal | - | yes | block (503) |
| T3 | contact, personal | identifiers | yes | block (503) |

Entity groups:
- **identifiers**: credit card, US SSN, US ITIN, US passport, US driver license, US bank number, IBAN, crypto address
- **contact**: email, phone number, IP address
- **personal**: person name, location

The governance doc requires masking at every tier, so no tier is log-only. Higher tiers only add coverage; a test enforces that.

## What the caller sees
- Masked text goes to the model with placeholders such as `<EMAIL_ADDRESS>`.
- A blocked request returns HTTP 400 with `error: pii_blocked`, the tier and the entity types (never the values).
- If the check cannot run and the tier fails closed, HTTP 503 with `error: pii_check_unavailable`.

## What traces contain
For T2 and T3 (and whenever the analyzer fails), metadata includes `aurai_pii` with the tier, counts per entity type, the total, and whether the analyzer failed. Masked requests also get the tag `aurai:pii-masked`. Detected values are not logged or traced. Because masking happens before the model call, traces store masked prompts.

## Limits to know
- Presidio uses trained models and patterns; it can miss PII and flag false positives. Treat it as a control that reduces exposure, and measure it on labelled examples.
- Response content is not checked in this version. Output guardrails for T3 are listed under production gaps.
- Only text fields are analyzed: chat message text and embedding input. Images, files and tool-call arguments are not.
- Names and places depend on the analyzer's language model and score thresholds; tune thresholds per tier in the policy file.

## Changing the policy
Edit `pii.yaml`, run `pytest`, and open a pull request. To replace the packaged policy in a cluster, create a ConfigMap with a `pii.yaml` key and set `piiPolicyConfigMap` in the chart values.

## Extending the LiteLLM configuration

The chart renders LiteLLM's `config.yaml` from values. Four optional values let other repositories extend it without forking the chart; all default to empty:

| Value | Effect |
|---|---|
| `litellm.generalSettings` | Merged into `general_settings` (for example `user_header_mappings`, or JWT authentication) |
| `litellm.extraSettings` | Merged into `litellm_settings` (for example `extra_spend_tag_headers`) |
| `litellm.extraEnv` | Extra environment variables for the LiteLLM container |
| `litellm.modelOverrides` | Per-alias overrides merged over the matching entry in `litellm.models` (for example to point `aurai-embed` at a different embedding model) |

`aurai-workspace` uses them to attribute requests to individual users. Settings supplied this way are not checked by this repository's tests.
