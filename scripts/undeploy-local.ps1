# Removes the gateway release and its Secret from the local cluster. The database is kept.
param([string]$Namespace = "aurai-gateway")
helm uninstall aurai-gateway --namespace $Namespace
kubectl delete secret litellm-secrets -n $Namespace --ignore-not-found
