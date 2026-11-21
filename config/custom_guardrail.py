"""Entry point that LiteLLM loads (`guardrail: custom_guardrail.AuraiPIIGuardrail`).

LiteLLM expects this file next to config.yaml. The implementation lives in the `aurai_gateway`
package, which the Docker image installs.
"""

from aurai_gateway.guardrail import AuraiPIIGuardrail

__all__ = ["AuraiPIIGuardrail"]
