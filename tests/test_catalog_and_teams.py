from pathlib import Path

import yaml

from aurai_gateway.catalog import (
    load_catalog,
    load_teams,
    validate_catalog,
    validate_teams,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "config" / "model-catalog.yaml"
TEAMS = ROOT / "teams" / "teams.yaml"
VALUES = ROOT / "charts" / "aurai-gateway" / "values.yaml"


def test_catalog_is_valid():
    assert validate_catalog(load_catalog(CATALOG)) == []


def test_teams_are_valid_against_catalog():
    catalog = load_catalog(CATALOG)
    assert validate_teams(load_teams(TEAMS), catalog) == []


def test_t3_team_cannot_use_a_model_not_approved_for_t3():
    catalog = load_catalog(CATALOG)
    teams = load_teams(TEAMS)
    guest = next(t for t in teams if t.risk_tier == "T3")
    bad = type(guest)(**{**guest.__dict__, "models": ("aurai-openai-mini",)})
    errors = validate_teams([bad], catalog)
    assert any("not approved for T3" in e for e in errors)


def test_fallback_must_permit_same_tiers():
    catalog = load_catalog(CATALOG)
    broken = dict(catalog)
    broken["aurai-fast"] = type(catalog["aurai-fast"])(
        alias="aurai-fast",
        provider="anthropic",
        tiers=frozenset({"T0", "T1", "T2", "T3"}),
        fallback="aurai-local",
        optional=False,
    )
    assert any("does not permit" in e for e in validate_catalog(broken))


def test_chart_models_match_catalog():
    """Every model the gateway serves is approved in the catalog, and the reverse."""
    values = yaml.safe_load(VALUES.read_text(encoding="utf-8"))
    served = {m["alias"] for m in values["litellm"]["models"]}
    assert served == set(load_catalog(CATALOG))


def test_chart_fallbacks_match_catalog():
    values = yaml.safe_load(VALUES.read_text(encoding="utf-8"))
    catalog = load_catalog(CATALOG)
    chart_fallbacks = {k: v[0] for entry in values["litellm"]["fallbacks"] for k, v in entry.items()}
    catalog_fallbacks = {a: m.fallback for a, m in catalog.items() if m.fallback}
    assert chart_fallbacks == catalog_fallbacks
