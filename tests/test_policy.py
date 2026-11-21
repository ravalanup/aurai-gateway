import pytest

from aurai_gateway.policy import PolicyError, load_policy, parse_policy, resolve_tier


def test_packaged_policy_loads_all_tiers():
    policy = load_policy()
    assert set(policy.tiers) == {"T0", "T1", "T2", "T3"}
    assert policy.default_tier == "T2"


def test_every_tier_masks_something():
    """The governance doc requires PII masking at every tier."""
    policy = load_policy()
    for tier in policy.tiers.values():
        assert tier.mask, f"{tier.tier} masks nothing"


def test_higher_tiers_never_remove_coverage():
    policy = load_policy()
    covered = [policy.tiers[t].mask | policy.tiers[t].block for t in ("T0", "T1", "T2", "T3")]
    for lower, higher in zip(covered, covered[1:], strict=False):
        assert lower <= higher


def test_t3_blocks_identifiers_and_fails_closed():
    t3 = load_policy().tiers["T3"]
    assert "US_SSN" in t3.block and "CREDIT_CARD" in t3.block
    assert t3.on_error == "block"
    assert t3.flag is True


def test_unknown_or_missing_tier_uses_default():
    policy = load_policy()
    assert policy.for_tier(None).tier == "T2"
    assert policy.for_tier("T9").tier == "T2"
    assert policy.for_tier("t3").tier == "T3"


def test_resolve_tier_prefers_key_over_team():
    assert resolve_tier({"risk_tier": "t1"}, {"risk_tier": "T3"}) == "T1"
    assert resolve_tier({}, {"risk_tier": "T3"}) == "T3"
    assert resolve_tier(None, None) is None


def test_overlapping_mask_and_block_rejected():
    raw = {
        "entity_groups": {},
        "tiers": {t: {"mask": ["US_SSN"], "block": ["US_SSN"]} for t in ("T0", "T1", "T2", "T3")},
    }
    with pytest.raises(PolicyError):
        parse_policy(raw)


def test_missing_tier_rejected():
    with pytest.raises(PolicyError):
        parse_policy({"tiers": {"T0": {}}})
