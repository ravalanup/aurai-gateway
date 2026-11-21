"""Shared test helpers: a fake Presidio analyzer built on httpx.MockTransport."""

from __future__ import annotations

import re

import httpx
import pytest

from aurai_gateway.presidio_client import PresidioAnalyzerClient

# Synthetic patterns standing in for the real analyzer. Tests exercise our policy code, not Presidio.
PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "US_SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
    "PHONE_NUMBER": re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),
    "PERSON": re.compile(r"\b(?:Alex Rivera|Sam Chen)\b"),
}


def fake_analyzer_handler(request: httpx.Request) -> httpx.Response:
    import json

    body = json.loads(request.content)
    results = []
    for entity in body["entities"]:
        pattern = PATTERNS.get(entity)
        if not pattern:
            continue
        for match in pattern.finditer(body["text"]):
            results.append({"entity_type": entity, "start": match.start(), "end": match.end(), "score": 0.9})
    return httpx.Response(200, json=results)


@pytest.fixture
def client() -> PresidioAnalyzerClient:
    return PresidioAnalyzerClient("http://analyzer.test", transport=httpx.MockTransport(fake_analyzer_handler))


@pytest.fixture
def down_client() -> PresidioAnalyzerClient:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("analyzer down", request=request)

    return PresidioAnalyzerClient("http://analyzer.test", transport=httpx.MockTransport(refuse))
