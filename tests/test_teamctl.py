from pathlib import Path

import httpx

from aurai_gateway import teamctl
from aurai_gateway.catalog import load_teams

ROOT = Path(__file__).resolve().parents[1]


def test_validate_command_succeeds(capsys):
    code = teamctl.main(
        ["validate", str(ROOT / "teams/teams.yaml"), "--catalog", str(ROOT / "config/model-catalog.yaml")]
    )
    assert code == 0
    assert "valid" in capsys.readouterr().out


def test_team_payload_carries_risk_tier_in_metadata():
    team = next(t for t in load_teams(ROOT / "teams/teams.yaml") if t.team_id == "guest-assistant")
    payload = teamctl.team_payload(team)
    assert payload["metadata"]["risk_tier"] == "T3"
    assert payload["max_budget"] == 5000
    assert payload["team_alias"] == "Guest Assistant"


def test_apply_creates_missing_and_updates_existing(monkeypatch, capsys):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/team/info":
            exists = request.url.params["team_id"] == "sandbox"
            return httpx.Response(200 if exists else 400, json={})
        return httpx.Response(200, json={})

    real_client = httpx.Client
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    monkeypatch.setattr(teamctl.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    code = teamctl.main(["apply", str(ROOT / "teams/teams.yaml"), "--catalog", str(ROOT / "config/model-catalog.yaml")])
    assert code == 0
    assert ("POST", "/team/update") in calls
    assert ("POST", "/team/new") in calls
    out = capsys.readouterr().out
    assert "updated sandbox" in out and "created guest-assistant" in out


def test_apply_requires_admin_key(monkeypatch):
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    try:
        teamctl.main(["apply", str(ROOT / "teams/teams.yaml"), "--catalog", str(ROOT / "config/model-catalog.yaml")])
    except SystemExit as exc:
        assert "LITELLM_MASTER_KEY" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
