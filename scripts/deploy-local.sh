#!/usr/bin/env bash
# Build the gateway image, load it into kind, create the Secret and install the chart.
# Requires: docker, kind, kubectl, helm, and ANTHROPIC_API_KEY (or GEMINI_API_KEY) in the environment.
set -euo pipefail

CLUSTER="${CLUSTER:-aurai}"
NAMESPACE="${NAMESPACE:-aurai-gateway}"
IMAGE="${IMAGE:-aurai-gateway:0.1.0}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

for tool in docker kind kubectl helm openssl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: $tool" >&2; exit 1; }
done
[ -n "${ANTHROPIC_API_KEY:-}${GEMINI_API_KEY:-}" ] || { echo "Set ANTHROPIC_API_KEY (or GEMINI_API_KEY) first." >&2; exit 1; }

kubectl config use-context "kind-$CLUSTER" >/dev/null
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || { echo "Namespace $NAMESPACE not found. Start aurai-infra first." >&2; exit 1; }

docker build -t "$IMAGE" "$REPO"
kind load docker-image "$IMAGE" --name "$CLUSTER"

existing() { kubectl get secret litellm-secrets -n "$NAMESPACE" -o "jsonpath={.data.$1}" 2>/dev/null | base64 -d 2>/dev/null || true; }
MASTER="$(existing master-key)"; MASTER="${MASTER:-sk-aurai-local-$(openssl rand -hex 16)}"
SALT="$(existing salt-key)";     SALT="${SALT:-sk-salt-$(openssl rand -hex 16)}"
PG_HOST="postgres.aurai-system.svc.cluster.local:5432"
PG_CRED="aurai:aurai-local-dev-only"

kubectl apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Secret
metadata:
  name: litellm-secrets
  namespace: $NAMESPACE
type: Opaque
stringData:
  master-key: "$MASTER"
  salt-key: "$SALT"
  database-url: "postgresql://$PG_CRED@$PG_HOST/litellm"
  database-admin-url: "postgresql://$PG_CRED@$PG_HOST/postgres"
  anthropic-api-key: "${ANTHROPIC_API_KEY:-}"
  gemini-api-key: "${GEMINI_API_KEY:-}"
  openai-api-key: "${OPENAI_API_KEY:-}"
YAML

EXTRA=()
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then EXTRA+=(--set litellm.models[0].enabled=false --set litellm.models[1].enabled=false --set litellm.models[2].enabled=false); fi
if [ -z "${GEMINI_API_KEY:-}" ]; then EXTRA+=(--set litellm.models[3].enabled=false --set litellm.models[4].enabled=false); fi

helm upgrade --install aurai-gateway "$REPO/charts/aurai-gateway" \
  --namespace "$NAMESPACE" -f "$REPO/charts/aurai-gateway/values-local.yaml" \
  --set image.repository=aurai-gateway --set image.tag=0.1.0 \
  "${EXTRA[@]}" --wait --timeout 10m

echo "Gateway installed. Run: kubectl port-forward -n $NAMESPACE svc/litellm 4000:4000"
