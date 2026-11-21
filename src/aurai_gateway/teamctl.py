"""aurai-teamctl: validate and apply team policy through the LiteLLM admin API.

  aurai-teamctl validate teams/teams.yaml
  aurai-teamctl apply    teams/teams.yaml --base-url http://localhost:4000
  aurai-teamctl issue-key sandbox --base-url http://localhost:4000 --alias demo --days 7

The admin key is read from the environment variable named by --admin-key-env (default
LITELLM_MASTER_KEY). It is never accepted on the command line, so it does not land in shell history.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

from .catalog import Team, load_catalog, load_teams, validate_catalog, validate_teams

DEFAULT_CATALOG = "config/model-catalog.yaml"


def team_payload(team: Team) -> dict:
    return {
        "team_id": team.team_id,
        "team_alias": team.alias,
        "models": list(team.models),
        "max_budget": team.max_budget_usd,
        "budget_duration": team.budget_duration,
        "rpm_limit": team.rpm,
        "tpm_limit": team.tpm,
        "metadata": {
            "risk_tier": team.risk_tier,
            "owner": team.owner,
            "cost_center": team.cost_center,
            "managed_by": "aurai-gateway/teams",
        },
    }


def _check(teams_path: str, catalog_path: str) -> tuple[list[Team], list[str]]:
    catalog = load_catalog(catalog_path)
    teams = load_teams(teams_path)
    errors = validate_catalog(catalog) + validate_teams(teams, catalog)
    return teams, errors


def cmd_validate(args: argparse.Namespace) -> int:
    teams, errors = _check(args.teams, args.catalog)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"ok: {len(teams)} teams valid")
    return 0


def _client(args: argparse.Namespace) -> httpx.Client:
    key = os.environ.get(args.admin_key_env)
    if not key:
        raise SystemExit(f"error: set {args.admin_key_env} to the gateway admin key")
    return httpx.Client(
        base_url=args.base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {key}"},
        timeout=30.0,
    )


def cmd_apply(args: argparse.Namespace) -> int:
    teams, errors = _check(args.teams, args.catalog)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    with _client(args) as client:
        for team in teams:
            payload = team_payload(team)
            info = client.get("/team/info", params={"team_id": team.team_id})
            exists = info.status_code == 200
            action = "update" if exists else "new"
            if args.dry_run:
                print(f"would {'update' if exists else 'create'} {team.team_id} ({team.risk_tier})")
                continue
            response = client.post(f"/team/{action}", json=payload)
            if response.status_code >= 300:
                print(f"error: {team.team_id}: {response.status_code} {response.text}", file=sys.stderr)
                return 1
            print(f"{'updated' if exists else 'created'} {team.team_id} ({team.risk_tier})")
    return 0


def cmd_issue_key(args: argparse.Namespace) -> int:
    teams, errors = _check(args.teams, args.catalog)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    team = next((t for t in teams if t.team_id == args.team_id), None)
    if team is None:
        print(f"error: unknown team {args.team_id}", file=sys.stderr)
        return 1

    body = {
        "team_id": team.team_id,
        "key_alias": args.alias,
        "duration": f"{args.days}d",
        "metadata": {"risk_tier": team.risk_tier, "issued_by": "aurai-teamctl"},
    }
    with _client(args) as client:
        response = client.post("/key/generate", json=body)
    if response.status_code >= 300:
        print(f"error: {response.status_code} {response.text}", file=sys.stderr)
        return 1
    print(response.json().get("key", ""))
    print("Store this key now; it is shown only once.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aurai-teamctl", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, needs_server: bool) -> None:
        p.add_argument("--catalog", default=DEFAULT_CATALOG)
        if needs_server:
            p.add_argument("--base-url", default="http://localhost:4000")
            p.add_argument("--admin-key-env", default="LITELLM_MASTER_KEY")

    p = sub.add_parser("validate", help="check teams against the model catalog")
    p.add_argument("teams", type=Path)
    common(p, False)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("apply", help="create or update teams on the gateway")
    p.add_argument("teams", type=Path)
    common(p, True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("issue-key", help="generate a virtual key for a team")
    p.add_argument("team_id")
    p.add_argument("--teams", type=Path, default=Path("teams/teams.yaml"))
    common(p, True)
    p.add_argument("--alias", required=True, help="a label for the key, e.g. the app name")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_issue_key)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
