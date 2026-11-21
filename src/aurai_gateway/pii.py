"""Apply the tiered PII policy to chat messages or embedding input.

This module has no dependency on LiteLLM so it can be tested on its own. The LiteLLM hook in
`guardrail.py` is a thin wrapper around `apply_policy`.

Only counts and entity types are ever recorded. Detected values are never logged or traced.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .policy import TierPolicy
from .presidio_client import AnalyzerUnavailable, Finding, PresidioAnalyzerClient


class PiiBlocked(Exception):
    """The request contains entities that the tier does not allow."""

    def __init__(self, tier: str, entity_types: list[str]) -> None:
        super().__init__(f"{tier} policy blocks: {', '.join(entity_types)}")
        self.tier = tier
        self.entity_types = entity_types


class PiiUnavailable(Exception):
    """The analyzer was unreachable and the tier fails closed."""


@dataclass
class PiiResult:
    tier: str
    masked: Counter[str] = field(default_factory=Counter)
    analyzer_error: bool = False

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "masked": dict(self.masked),
            "masked_total": sum(self.masked.values()),
            "analyzer_error": self.analyzer_error,
        }


def mask_text(text: str, findings: list[Finding]) -> str:
    """Replace each finding with `<ENTITY_TYPE>`. Overlaps keep the higher-scoring, longer span."""
    ordered = sorted(findings, key=lambda f: (-f.score, -(f.end - f.start), f.start))
    kept: list[Finding] = []
    for candidate in ordered:
        if all(candidate.end <= k.start or candidate.start >= k.end for k in kept):
            kept.append(candidate)
    for f in sorted(kept, key=lambda f: f.start, reverse=True):
        text = text[: f.start] + f"<{f.entity_type}>" + text[f.end :]
    return text


async def _process_text(
    text: str, policy: TierPolicy, client: PresidioAnalyzerClient, language: str, result: PiiResult
) -> str:
    findings = await client.analyze(text, policy.entities, language=language, score_threshold=policy.score_threshold)
    blocked = sorted({f.entity_type for f in findings if f.entity_type in policy.block})
    if blocked:
        raise PiiBlocked(policy.tier, blocked)
    to_mask = [f for f in findings if f.entity_type in policy.mask]
    for f in to_mask:
        result.masked[f.entity_type] += 1
    return mask_text(text, to_mask) if to_mask else text


async def apply_policy(
    data: dict[str, Any],
    policy: TierPolicy,
    client: PresidioAnalyzerClient,
    language: str = "en",
) -> PiiResult:
    """Mask (or reject) PII in `data["messages"]` and `data["input"]` in place."""
    result = PiiResult(tier=policy.tier)
    try:
        messages = data.get("messages")
        if isinstance(messages, list):
            for message in messages:
                content = message.get("content") if isinstance(message, dict) else None
                if isinstance(content, str):
                    message["content"] = await _process_text(content, policy, client, language, result)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                            part["text"] = await _process_text(part["text"], policy, client, language, result)

        embedding_input = data.get("input")
        if isinstance(embedding_input, str):
            data["input"] = await _process_text(embedding_input, policy, client, language, result)
        elif isinstance(embedding_input, list) and all(isinstance(i, str) for i in embedding_input):
            data["input"] = [await _process_text(i, policy, client, language, result) for i in embedding_input]
    except AnalyzerUnavailable as exc:
        if policy.on_error == "block":
            raise PiiUnavailable(f"PII analyzer unavailable and {policy.tier} fails closed") from exc
        result.analyzer_error = True
    return result
