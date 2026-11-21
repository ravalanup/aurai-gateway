"""LiteLLM guardrail that applies the tiered PII policy before a request leaves the platform.

LiteLLM loads this through `custom_guardrail.py` (see config/custom_guardrail.py), which re-exports
`AuraiPIIGuardrail`. Configuration is by environment variable:

  PRESIDIO_ANALYZER_URL   analyzer base URL (default http://presidio-analyzer:3000)
  AURAI_PII_POLICY        optional path to a policy file that replaces the packaged default
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException
from litellm.integrations.custom_guardrail import CustomGuardrail

from .pii import PiiBlocked, PiiUnavailable, apply_policy
from .policy import load_policy, resolve_tier
from .presidio_client import PresidioAnalyzerClient

_CALL_TYPES = {"completion", "acompletion", "text_completion", "embeddings", "aembedding"}


class AuraiPIIGuardrail(CustomGuardrail):
    def __init__(self, **kwargs: Any) -> None:
        self.policy = load_policy(os.environ.get("AURAI_PII_POLICY"))
        self.client = PresidioAnalyzerClient(os.environ.get("PRESIDIO_ANALYZER_URL", "http://presidio-analyzer:3000"))
        super().__init__(**kwargs)

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):  # noqa: ANN001
        if str(call_type) not in _CALL_TYPES:
            return data

        tier = resolve_tier(
            getattr(user_api_key_dict, "metadata", None),
            getattr(user_api_key_dict, "team_metadata", None),
        )
        tier_policy = self.policy.for_tier(tier)

        try:
            result = await apply_policy(data, tier_policy, self.client, self.policy.language)
        except PiiBlocked as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "pii_blocked",
                    "message": "The request contains data that this use case's risk tier does not allow.",
                    "tier": exc.tier,
                    "entity_types": exc.entity_types,
                },
            ) from exc
        except PiiUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "pii_check_unavailable", "message": str(exc)},
            ) from exc

        metadata = data.setdefault("metadata", {})
        if tier_policy.flag or result.analyzer_error:
            metadata["aurai_pii"] = result.trace_metadata()
        if result.masked:
            tags = metadata.setdefault("tags", [])
            tags.append("aurai:pii-masked")
        metadata["aurai_risk_tier"] = tier_policy.tier
        return data
