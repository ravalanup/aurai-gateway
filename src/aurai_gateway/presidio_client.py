"""Small async client for the Presidio analyzer REST service."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class AnalyzerUnavailable(RuntimeError):
    """The analyzer could not be reached or returned an error."""


@dataclass(frozen=True)
class Finding:
    entity_type: str
    start: int
    end: int
    score: float


class PresidioAnalyzerClient:
    """Calls POST {base_url}/analyze on the Presidio analyzer service."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    async def analyze(
        self,
        text: str,
        entities: list[str],
        language: str = "en",
        score_threshold: float = 0.5,
    ) -> list[Finding]:
        if not text or not entities:
            return []
        try:
            response = await self._client.post(
                "/analyze",
                json={
                    "text": text,
                    "language": language,
                    "entities": entities,
                    "score_threshold": score_threshold,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AnalyzerUnavailable(str(exc)) from exc

        return [
            Finding(
                entity_type=item["entity_type"],
                start=int(item["start"]),
                end=int(item["end"]),
                score=float(item["score"]),
            )
            for item in payload
        ]

    async def aclose(self) -> None:
        await self._client.aclose()
