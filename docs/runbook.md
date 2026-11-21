# Runbook

## Health
| Check | Command |
|---|---|
| Pods | `kubectl get pods -n aurai-gateway` |
| LiteLLM readiness | `kubectl exec -n aurai-gateway deploy/litellm -- python -c "import urllib.request as u; print(u.urlopen('http://localhost:4000/health/readiness').read())"` |
| Presidio | `kubectl logs -n aurai-gateway deploy/presidio-analyzer --tail=50` |
| Logs | `kubectl logs -n aurai-gateway deploy/litellm --tail=100` |

## Deploying to AWS
Prerequisites from `aurai-infra`: cluster, RDS, ElastiCache, ECR, the External Secrets Operator and the `aurai-aws-secrets` ClusterSecretStore.

1. Create the secrets in Secrets Manager (names follow `aurai-<env>/litellm/...`):
   - `master-key` and `salt-key`: random strings; keep the salt key stable forever (it encrypts stored credentials)
   - `provider-keys`: JSON `{"anthropic": "...", "gemini": "...", "openai": ""}`
   The infra Terraform creates containers for `litellm/master-key`; add `litellm/salt-key` and `litellm/provider-keys` there.
2. Build and push the image to the ECR repository, then set `image.repository` and `image.tag`.
3. Fill `values-aws.yaml`: Redis endpoint, RDS host, remote key names, ingress host and certificate annotations.
4. Install:
   ```bash
   helm upgrade --install aurai-gateway charts/aurai-gateway -n aurai-gateway \
     -f charts/aurai-gateway/values-aws.yaml --wait --timeout 10m
   ```
5. Apply teams (`aurai-teamctl apply`) from a host that can reach the gateway.

## Common problems

| Symptom | Likely cause | Action |
|---|---|---|
| Pod `CrashLoopBackOff`, log mentions database | `database-url` wrong or database missing | Check the Secret; confirm the init container created database `litellm` |
| `ImagePullBackOff` locally | Image not loaded into kind | Run `scripts/deploy-local.ps1` again |
| 401 from the gateway | Wrong or expired key | Issue a new key |
| 400 `pii_blocked` | T3 request contains identifiers | Remove or tokenize the identifier upstream |
| 503 `pii_check_unavailable` | Presidio not reachable (T2, T3) | Check Presidio pods and the network policy |
| 429 | Team rate limit or budget reached | Review spend in LiteLLM; raise limits through `teams.yaml` |
| Model call fails with provider auth error | Missing or invalid provider key | Update the Secret and restart: `kubectl rollout restart deploy/litellm -n aurai-gateway` |
| Fallback not used | Fallback provider has no key | Add the key, or disable the alias |

## Incident actions
- **Pause a team:** set `max_budget_usd` very low in `teams.yaml` and apply, or block its keys in the admin API.
- **Disable a model:** set `enabled: false` in chart values and redeploy.
- **Rotate a provider key:** update the secret value, wait for External Secrets (or re-run the local script), restart the Deployment.
- **Suspected PII leak:** find the request in traces by tag and tier, check `aurai_pii` metadata, and review the policy for the missed entity type.

## Rotation notes
Changing `salt-key` makes stored encrypted credentials unreadable. Do not rotate it without a migration plan.
