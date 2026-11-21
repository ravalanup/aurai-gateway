# Forwards the gateway to http://localhost:4000. Press Ctrl+C to stop.
param([string]$Namespace = "aurai-gateway", [int]$Port = 4000)
$ErrorActionPreference = "Stop"
kubectl port-forward -n $Namespace svc/litellm "${Port}:4000"
