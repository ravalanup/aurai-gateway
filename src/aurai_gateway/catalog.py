"""Model catalog and team definitions, with the governance checks CI relies on."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TIERS = ("T0", "T1", "T2", "T3")
TEAM_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DURATION = re.compile(r"^\d+(s|m|h|d|mo)$")


@dataclass(frozen=True)
class CatalogModel:
    alias: str
    provider: str
    tiers: frozenset[str]
    fallback: str | None
    optional: bool


@dataclass(frozen=True)
class Team:
    team_id: str
    alias: str
    risk_tier: str
    owner: str
    cost_center: str
    models: tuple[str, ...]
    max_budget_usd: float
    budget_duration: str
    rpm: int
    tpm: int


def load_catalog(path: str | Path) -> dict[str, CatalogModel]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    catalog: dict[str, CatalogModel] = {}
    for item in raw.get("models", []):
        catalog[item["alias"]] = CatalogModel(
            alias=item["alias"],
            provider=item["provider"],
            tiers=frozenset(item["tiers"]),
            fallback=item.get("fallback"),
            optional=bool(item.get("optional", False)),
        )
    return catalog


def load_teams(path: str | Path) -> list[Team]:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    teams = []
    for item in raw.get("teams", []):
        teams.append(
            Team(
                team_id=item["team_id"],
                alias=item["alias"],
                risk_tier=item["risk_tier"],
                owner=item["owner"],
                cost_center=item["cost_center"],
                models=tuple(item["models"]),
                max_budget_usd=float(item["max_budget_usd"]),
                budget_duration=item.get("budget_duration", defaults.get("budget_duration", "30d")),
                rpm=int(item["rpm"]),
                tpm=int(item["tpm"]),
            )
        )
    return teams


def validate_catalog(catalog: dict[str, CatalogModel]) -> list[str]:
    errors: list[str] = []
    for model in catalog.values():
        bad = model.tiers - set(TIERS)
        if bad:
            errors.append(f"{model.alias}: unknown tiers {sorted(bad)}")
        if model.fallback:
            target = catalog.get(model.fallback)
            if target is None:
                errors.append(f"{model.alias}: fallback {model.fallback!r} is not in the catalog")
            elif not model.tiers <= target.tiers:
                missing = sorted(model.tiers - target.tiers)
                errors.append(f"{model.alias}: fallback {target.alias} does not permit tiers {missing}")
    return errors


def validate_teams(teams: list[Team], catalog: dict[str, CatalogModel]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for team in teams:
        where = f"team {team.team_id}"
        if not TEAM_ID.match(team.team_id):
            errors.append(f"{where}: team_id must be lowercase letters, digits and hyphens")
        if team.team_id in seen:
            errors.append(f"{where}: duplicate team_id")
        seen.add(team.team_id)
        if team.risk_tier not in TIERS:
            errors.append(f"{where}: risk_tier must be one of {TIERS}")
        if not DURATION.match(team.budget_duration):
            errors.append(f"{where}: budget_duration {team.budget_duration!r} is not like 30d")
        if team.max_budget_usd <= 0 or team.rpm <= 0 or team.tpm <= 0:
            errors.append(f"{where}: budget and limits must be positive")
        if not team.models:
            errors.append(f"{where}: at least one model is required")
        for alias in team.models:
            model = catalog.get(alias)
            if model is None:
                errors.append(f"{where}: model {alias!r} is not in the catalog")
            elif team.risk_tier in TIERS and team.risk_tier not in model.tiers:
                errors.append(f"{where}: model {alias} is not approved for {team.risk_tier}")
    return errors
