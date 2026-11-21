# One chat call through the gateway with a team key.
#   $env:AURAI_KEY = "<virtual key from: aurai-teamctl issue-key sandbox --alias demo>"
$base = if ($env:AURAI_GATEWAY_URL) { $env:AURAI_GATEWAY_URL } else { "http://localhost:4000" }
if (-not $env:AURAI_KEY) { throw "Set AURAI_KEY first." }
$body = @{ model = "aurai-fast"; messages = @(@{ role = "user"; content = "Say hello in five words." }) } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$base/chat/completions" -Headers @{ Authorization = "Bearer $($env:AURAI_KEY)" } -ContentType "application/json" -Body $body
