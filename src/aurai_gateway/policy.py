"""Load and resolve the tiered PII policy."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

VALID_TIERS = ("T0", "T1", "T2", "T3")
VALID_ON_ERROR = ("allow", "block")


class PolicyError(ValueError):
    """The policy file is malformed."""


@dataclass(frozen=True)
class TierPolicy:
    tier: str
    mask: frozenset[str]
    block: frozenset[str]
    flag: bool
    score_threshold: float
    on_error: str
    description: str = ""

    @property
    def entities(self) -> list[str]:
        """Every entity type the analyzer should look for in this tier."""
        return sorted(self.mask | self.block)


@dataclass(frozen=True)
class PiiPolicy:
    default_tier: str
    language: str
    tiers: dict[str, TierPolicy]

    def for_tier(self, tier: str | None) -> TierPolicy:
        """Return the policy for a tier. Unknown or missing tiers use the default tier."""
        if tier is not None and tier.upper() in self.tiers:
            return self.tiers[tier.upper()]
        return self.tiers[self.default_tier]


def _expand(names: list[str], groups: dict[str, list[str]]) -> frozenset[str]:
    out: set[str] = set()
    for name in names:
        out.update(groups[name] if name in groups else [name])
    return frozenset(out)


def parse_policy(raw: dict[str, Any]) -> PiiPolicy:
    groups = raw.get("entity_groups", {})
    tiers_raw = raw.get("tiers", {})
    missing = [t for t in VALID_TIERS if t not in tiers_raw]
    if missing:
        raise PolicyError(f"policy is missing tiers: {', '.join(missing)}")

    tiers: dict[str, TierPolicy] = {}
    for name in VALID_TIERS:
        t = tiers_raw[name]
        on_error = t.get("on_error", "block")
        if on_error not in VALID_ON_ERROR:
            raise PolicyError(f"{name}: on_error must be one of {VALID_ON_ERROR}")
        threshold = float(t.get("score_threshold", 0.5))
        if not 0.0 <= threshold <= 1.0:
            raise PolicyError(f"{name}: score_threshold must be between 0 and 1")
        mask = _expand(t.get("mask", []), groups)
        block = _expand(t.get("block", []), groups)
        if mask & block:
            raise PolicyError(f"{name}: entities cannot be both masked and blocked: {sorted(mask & block)}")
        tiers[name] = TierPolicy(
            tier=name,
            mask=mask,
            block=block,
            flag=bool(t.get("flag", False)),
            score_threshold=threshold,
            on_error=on_error,
            description=t.get("description", ""),
        )

    default_tier = raw.get("default_tier", "T2")
    if default_tier not in tiers:
        raise PolicyError(f"default_tier {default_tier!r} is not a valid tier")
    return PiiPolicy(default_tier=default_tier, language=raw.get("language", "en"), tiers=tiers)


def load_policy(path: str | Path | None = None) -> PiiPolicy:
    """Load the policy from `path`, or the packaged default."""
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = resources.files("aurai_gateway").joinpath("policies/pii.yaml").read_text(encoding="utf-8")
    return parse_policy(yaml.safe_load(text))


def resolve_tier(*metadata_sources: dict[str, Any] | None) -> str | None:
    """Find `risk_tier` in the first metadata dict that has it.

    Pass the most specific source first (key metadata), then team metadata. Callers cannot lower
    their own tier: it is set on the key or team by the platform team, never read from the request.
    """
    for source in metadata_sources:
        if source and isinstance(source.get("risk_tier"), str):
            return source["risk_tier"].upper()
    return None
