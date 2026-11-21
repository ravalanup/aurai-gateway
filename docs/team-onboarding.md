# Team onboarding

## 1. Classify the use case
Use the risk-tier questions in `aurai-docs/docs/governance/risk-tiers.md`. Record the tier and an accountable owner.

## 2. Add the team
Add an entry to `teams/teams.yaml`:

```yaml
- team_id: park-ops-planner
  alias: Park Operations Planner
  risk_tier: T2
  owner: Operations planning lead
  cost_center: CC-3300
  models: [aurai-balanced, aurai-reasoning]
  max_budget_usd: 800
  rpm: 100
  tpm: 150000
```

Choose models approved for the tier (see `config/model-catalog.yaml`). Budgets reset every `budget_duration` (default 30 days).

## 3. Validate and review
```bash
aurai-teamctl validate teams/teams.yaml
pytest
```
Open a pull request. The platform team reviews the tier, models, budget and limits. T2 and T3 additionally need the reviews listed in the governance doc.

## 4. Apply
```bash
export LITELLM_MASTER_KEY=<admin key>
aurai-teamctl apply teams/teams.yaml --base-url http://localhost:4000 --dry-run
aurai-teamctl apply teams/teams.yaml --base-url http://localhost:4000
```
In AWS, run this from CI or a bastion with the admin key from Secrets Manager.

## 5. Issue a key
```bash
aurai-teamctl issue-key park-ops-planner --alias planner-service --days 30
```
The key prints once. Store it in the team's secret manager and rotate before expiry. Use one key per application so spend and traces can be attributed.

## 6. Call the gateway
```bash
curl http://<gateway>/chat/completions \
  -H "Authorization: Bearer $AURAI_KEY" -H "Content-Type: application/json" \
  -d '{"model":"aurai-balanced","messages":[{"role":"user","content":"Hello"}]}'
```
Any OpenAI-compatible client works with the gateway URL as the base URL and the alias as the model.

## Offboarding or pausing
Remove or reduce the team's budget and apply, or revoke keys in the LiteLLM admin API. The platform team can disable a model route or key immediately in an incident (see the runbook).
