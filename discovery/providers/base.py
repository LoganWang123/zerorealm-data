"""Search provider abstraction."""

from __future__ import annotations

from typing import Protocol

from discovery.models import SearchCandidate


class SearchProvider(Protocol):
    """Discovery-only search interface. Implementations must not invent Evidence."""

    name: str

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        language: str | None = None,
        region: str | None = None,
        domains: list[str] | None = None,
    ) -> list[SearchCandidate]:
        ...
