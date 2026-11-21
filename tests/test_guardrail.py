"""Tests for the LiteLLM wrapper. Skipped when litellm is not installed."""

import httpx
import pytest

pytest.importorskip("litellm")
pytest.importorskip("fastapi")

from fastapi import HTTPException  # noqa: E402

from aurai_gateway.guardrail import AuraiPIIGuardrail  # noqa: E402
from aurai_gateway.presidio_client import PresidioAnalyzerClient  # noqa: E402

from .conftest import fake_analyzer_handler  # noqa: E402


class FakeKey:
    def __init__(self, metadata=None, team_metadata=None):
        self.metadata = metadata or {}
        self.team_metadata = team_metadata or {}


@pytest.fixture
def guardrail():
    g = AuraiPIIGuardrail(guardrail_name="aurai-pii", event_hook="pre_call", default_on=True)
    g.client = PresidioAnalyzerClient("http://analyzer.test", transport=httpx.MockTransport(fake_analyzer_handler))
    return g


def request(text):
    return {"messages": [{"role": "user", "content": text}], "model": "aurai-fast"}


async def test_masks_and_tags_trace_for_t2_team(guardrail):
    data = await guardrail.async_pre_call_hook(
        FakeKey(team_metadata={"risk_tier": "T2"}), None, request("mail sam@example.com"), "completion"
    )
    assert "<EMAIL_ADDRESS>" in data["messages"][0]["content"]
    assert data["metadata"]["aurai_pii"]["masked_total"] == 1
    assert data["metadata"]["aurai_risk_tier"] == "T2"
    assert "aurai:pii-masked" in data["metadata"]["tags"]


async def test_t3_rejects_identifiers_with_400(guardrail):
    with pytest.raises(HTTPException) as excinfo:
        await guardrail.async_pre_call_hook(
            FakeKey(team_metadata={"risk_tier": "T3"}), None, request("SSN 123-45-6789"), "completion"
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["entity_types"] == ["US_SSN"]


async def test_untagged_key_uses_default_tier(guardrail):
    data = await guardrail.async_pre_call_hook(FakeKey(), None, request("hello"), "completion")
    assert data["metadata"]["aurai_risk_tier"] == "T2"


async def test_other_call_types_pass_through(guardrail):
    data = request("SSN 123-45-6789")
    out = await guardrail.async_pre_call_hook(FakeKey(), None, data, "image_generation")
    assert out["messages"][0]["content"] == "SSN 123-45-6789"
