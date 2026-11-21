<#
.SYNOPSIS
  Build the gateway image, load it into the local kind cluster, create the Secret and install the chart.

.DESCRIPTION
  Prerequisites: the local cluster from aurai-infra is running (local\scripts\up.ps1), with Docker,
  kind, kubectl and Helm installed.

  Provider keys are read from environment variables and written to a Kubernetes Secret through stdin,
  so they never appear in a file, in Helm values or on a command line:
    ANTHROPIC_API_KEY   required unless GEMINI_API_KEY is set
    GEMINI_API_KEY      optional
    OPENAI_API_KEY      optional (also set litellm.models aurai-openai-mini enabled=true)
#>
param(
  [string]$ClusterName = "aurai",
  [string]$Namespace = "aurai-gateway",
  [string]$Image = "aurai-gateway:0.1.0"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

foreach ($tool in "docker", "kind", "kubectl", "helm") {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing required tool: $tool" }
}
if (-not $env:ANTHROPIC_API_KEY -and -not $env:GEMINI_API_KEY) {
  throw "Set ANTHROPIC_API_KEY (or GEMINI_API_KEY) in this PowerShell session first."
}

kubectl config use-context "kind-$ClusterName" | Out-Null
kubectl get namespace $Namespace 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Namespace $Namespace not found. Start the platform first: aurai-infra\local\scripts\up.ps1" }

Write-Host "Building $Image"
docker build -t $Image $repo
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
kind load docker-image $Image --name $ClusterName
if ($LASTEXITCODE -ne 0) { throw "kind load failed" }

function New-RandomHex([int]$bytes) {
  $buffer = New-Object byte[] $bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
  -join ($buffer | ForEach-Object { $_.ToString("x2") })
}
function Get-ExistingSecretValue([string]$key) {
  $encoded = kubectl get secret litellm-secrets -n $Namespace -o "jsonpath={.data.$key}" 2>$null
  if ($LASTEXITCODE -eq 0 -and $encoded) { return [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded)) }
  return $null
}

# The salt key encrypts stored credentials. Keep it stable across re-deploys.
$masterKey = Get-ExistingSecretValue "master-key"; if (-not $masterKey) { $masterKey = "sk-aurai-local-" + (New-RandomHex 16) }
$saltKey   = Get-ExistingSecretValue "salt-key";   if (-not $saltKey)   { $saltKey = "sk-salt-" + (New-RandomHex 16) }

# Local Postgres credentials come from aurai-infra values-local.yaml (development only).
$pgHost = "postgres.aurai-system.svc.cluster.local:5432"
$pgCred = "aurai:aurai-local-dev-only"

$secretYaml = @"
apiVersion: v1
kind: Secret
metadata:
  name: litellm-secrets
  namespace: $Namespace
type: Opaque
stringData:
  master-key: "$masterKey"
  salt-key: "$saltKey"
  database-url: "postgresql://$pgCred@$pgHost/litellm"
  database-admin-url: "postgresql://$pgCred@$pgHost/postgres"
  anthropic-api-key: "$($env:ANTHROPIC_API_KEY)"
  gemini-api-key: "$($env:GEMINI_API_KEY)"
  openai-api-key: "$($env:OPENAI_API_KEY)"
"@
$secretYaml | kubectl apply -f - | Out-Null
Write-Host "Secret litellm-secrets applied"

# If a provider has no key, turn its models off so health checks stay green.
$extra = @()
if (-not $env:ANTHROPIC_API_KEY) { $extra += @("--set", "litellm.models[0].enabled=false", "--set", "litellm.models[1].enabled=false", "--set", "litellm.models[2].enabled=false") }
if (-not $env:GEMINI_API_KEY)    { $extra += @("--set", "litellm.models[3].enabled=false", "--set", "litellm.models[4].enabled=false") }

helm upgrade --install aurai-gateway "$repo\charts\aurai-gateway" `
  --namespace $Namespace `
  -f "$repo\charts\aurai-gateway\values-local.yaml" `
  --set "image.repository=aurai-gateway" --set "image.tag=0.1.0" `
  @extra --wait --timeout 10m
if ($LASTEXITCODE -ne 0) { throw "helm install failed" }

Write-Host ""
Write-Host "Gateway installed. Next:"
Write-Host "  .\scripts\port-forward.ps1                  # http://localhost:4000"
Write-Host "  kubectl get secret litellm-secrets -n $Namespace -o jsonpath='{.data.master-key}' | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(`$_)) }"
