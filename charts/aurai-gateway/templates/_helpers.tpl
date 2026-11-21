{{/* Common labels */}}
{{- define "aurai-gateway.labels" -}}
app.kubernetes.io/part-of: aurai
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
aurai.io/environment: {{ .Values.global.environment | quote }}
{{- end -}}

{{- define "aurai-gateway.image" -}}
{{ required "image.repository must be set" .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}

{{/* Renders the LiteLLM config.yaml from values. */}}
{{- define "aurai-gateway.litellmConfig" -}}
{{- $models := list -}}
{{- range .Values.litellm.models -}}
{{- /* modelOverrides (keyed by alias) lets an overlay swap one model without repeating the whole list */ -}}
{{- $m := mergeOverwrite (deepCopy .) (index ($.Values.litellm.modelOverrides | default (dict)) .alias | default (dict)) -}}
{{- if $m.enabled -}}
{{- $params := dict "model" $m.model -}}
{{- if $m.apiKeyEnv -}}{{- $_ := set $params "api_key" (printf "os.environ/%s" $m.apiKeyEnv) -}}{{- end -}}
{{- if $m.apiBase -}}{{- $_ := set $params "api_base" $m.apiBase -}}{{- end -}}
{{- $models = append $models (dict "model_name" $m.alias "litellm_params" $params) -}}
{{- end -}}
{{- end -}}
{{- $settings := dict
  "num_retries" .Values.litellm.routing.numRetries
  "request_timeout" .Values.litellm.routing.requestTimeoutSeconds
  "fallbacks" .Values.litellm.fallbacks
  "drop_params" true
-}}
{{- if .Values.tracing.enabled -}}{{- $_ := set $settings "callbacks" (list "otel") -}}{{- end -}}
{{- $settings = mergeOverwrite $settings (.Values.litellm.extraSettings | default (dict)) -}}
{{- $general := dict "master_key" "os.environ/LITELLM_MASTER_KEY" "database_url" "os.environ/DATABASE_URL" "store_model_in_db" false -}}
{{- $general = mergeOverwrite $general (.Values.litellm.generalSettings | default (dict)) -}}
{{- if .Values.litellm.cache.enabled -}}
{{- $_ := set $settings "cache" true -}}
{{- $_ := set $settings "cache_params" (dict "type" "redis" "host" "os.environ/REDIS_HOST" "port" "os.environ/REDIS_PORT" "ttl" .Values.litellm.cache.ttlSeconds) -}}
{{- end -}}
{{- $cfg := dict
  "model_list" $models
  "litellm_settings" $settings
  "router_settings" (dict "routing_strategy" "simple-shuffle" "cooldown_time" .Values.litellm.routing.cooldownSeconds "redis_host" "os.environ/REDIS_HOST" "redis_port" "os.environ/REDIS_PORT")
  "general_settings" $general
  "guardrails" (list (dict "guardrail_name" "aurai-pii" "litellm_params" (dict "guardrail" "custom_guardrail.AuraiPIIGuardrail" "mode" "pre_call" "default_on" true)))
-}}
{{ toYaml $cfg }}
{{- end -}}
