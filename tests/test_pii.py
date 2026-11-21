import pytest

from aurai_gateway.pii import PiiBlocked, PiiUnavailable, apply_policy, mask_text
from aurai_gateway.policy import load_policy
from aurai_gateway.presidio_client import Finding

POLICY = load_policy()


def chat(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


def test_mask_text_replaces_spans_and_keeps_surrounding_text():
    text = "Mail alex@example.com now"
    out = mask_text(text, [Finding("EMAIL_ADDRESS", 5, 21, 0.9)])
    assert out == "Mail <EMAIL_ADDRESS> now"


def test_mask_text_overlap_keeps_best_span():
    text = "call 555-123-4567"
    out = mask_text(text, [Finding("PHONE_NUMBER", 5, 17, 0.9), Finding("US_SSN", 5, 10, 0.4)])
    assert out == "call <PHONE_NUMBER>"


async def test_t0_masks_identifiers_but_not_email(client):
    data = chat("SSN 123-45-6789 and alex@example.com")
    result = await apply_policy(data, POLICY.for_tier("T0"), client)
    content = data["messages"][0]["content"]
    assert "<US_SSN>" in content
    assert "alex@example.com" in content
    assert result.masked["US_SSN"] == 1


async def test_t1_masks_contact_details(client):
    data = chat("Reach me at alex@example.com or 555-123-4567")
    await apply_policy(data, POLICY.for_tier("T1"), client)
    content = data["messages"][0]["content"]
    assert "<EMAIL_ADDRESS>" in content and "<PHONE_NUMBER>" in content


async def test_t2_masks_names_and_flags(client):
    data = chat("Alex Rivera asked about the schedule")
    result = await apply_policy(data, POLICY.for_tier("T2"), client)
    assert data["messages"][0]["content"].startswith("<PERSON>")
    assert POLICY.for_tier("T2").flag is True
    assert result.trace_metadata()["masked_total"] == 1


async def test_t3_blocks_identifiers(client):
    data = chat("My card is 4111 1111 1111 1111")
    with pytest.raises(PiiBlocked) as excinfo:
        await apply_policy(data, POLICY.for_tier("T3"), client)
    assert excinfo.value.entity_types == ["CREDIT_CARD"]


async def test_t3_masks_non_blocking_entities(client):
    data = chat("Sam Chen can be reached at sam@example.com")
    await apply_policy(data, POLICY.for_tier("T3"), client)
    content = data["messages"][0]["content"]
    assert "<PERSON>" in content and "<EMAIL_ADDRESS>" in content


async def test_content_parts_and_embedding_input_are_processed(client):
    data = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": "mail sam@example.com"}]}],
        "input": ["call 555-123-4567"],
    }
    await apply_policy(data, POLICY.for_tier("T1"), client)
    assert "<EMAIL_ADDRESS>" in data["messages"][0]["content"][0]["text"]
    assert data["input"] == ["call <PHONE_NUMBER>"]


async def test_clean_request_is_unchanged(client):
    data = chat("What are the opening hours?")
    result = await apply_policy(data, POLICY.for_tier("T3"), client)
    assert data["messages"][0]["content"] == "What are the opening hours?"
    assert not result.masked


async def test_trace_metadata_never_contains_values(client):
    data = chat("SSN 123-45-6789")
    result = await apply_policy(data, POLICY.for_tier("T0"), client)
    assert "123-45-6789" not in str(result.trace_metadata())


async def test_low_tier_fails_open_when_analyzer_down(down_client):
    data = chat("SSN 123-45-6789")
    result = await apply_policy(data, POLICY.for_tier("T1"), down_client)
    assert result.analyzer_error is True
    assert data["messages"][0]["content"] == "SSN 123-45-6789"


async def test_high_tier_fails_closed_when_analyzer_down(down_client):
    with pytest.raises(PiiUnavailable):
        await apply_policy(chat("hello"), POLICY.for_tier("T2"), down_client)
    with pytest.raises(PiiUnavailable):
        await apply_policy(chat("hello"), POLICY.for_tier("T3"), down_client)
