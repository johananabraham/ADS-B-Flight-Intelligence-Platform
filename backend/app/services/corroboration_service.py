"""Application service that compares local observations with an external source."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from ..schemas.observation import TrackObservation
from .corroboration import CorroborationPolicy, CorroborationResult, compare_observations
from .external_observations import (
    ExternalFetchResult,
    ExternalFetchStatus,
    GeographicBounds,
    SourceHealth,
)


class ExternalObservationSource(Protocol):
    @property
    def health(self) -> SourceHealth: ...

    async def fetch_states(
        self, *, bounds: GeographicBounds, icao_hex: str | None = None
    ) -> ExternalFetchResult: ...


class CorroborationService:
    """Coordinate bounded acquisition and deterministic observation association."""

    def __init__(
        self,
        source: ExternalObservationSource,
        *,
        policy: CorroborationPolicy = CorroborationPolicy(),
        search_radius_degrees: float = 0.25,
    ) -> None:
        if search_radius_degrees <= 0 or search_radius_degrees > 2.5:
            raise ValueError("search radius must be greater than zero and at most 2.5 degrees")
        self._source = source
        self._policy = policy
        self._search_radius_degrees = search_radius_degrees

    @property
    def source_health(self) -> SourceHealth:
        return self._source.health

    async def corroborate(
        self,
        local: TrackObservation,
        *,
        evaluated_at: datetime | None = None,
    ) -> CorroborationResult:
        now = evaluated_at or datetime.now(timezone.utc)
        if local.latitude is None or local.longitude is None:
            return compare_observations(
                local=local,
                external=None,
                evaluated_at=now,
                source_available=True,
                policy=self._policy,
            )
        fetched = await self._source.fetch_states(
            bounds=self._bounds_around(local.latitude, local.longitude),
            icao_hex=local.icao_hex,
        )
        match = next(
            (
                candidate
                for candidate in fetched.observations
                if candidate.icao_hex == local.icao_hex
            ),
            None,
        )
        return compare_observations(
            local=local,
            external=match,
            evaluated_at=now,
            source_available=fetched.status is ExternalFetchStatus.AVAILABLE,
            policy=self._policy,
        )

    def _bounds_around(self, latitude: float, longitude: float) -> GeographicBounds:
        radius = self._search_radius_degrees
        return GeographicBounds(
            min_latitude=max(-90, latitude - radius),
            max_latitude=min(90, latitude + radius),
            min_longitude=max(-180, longitude - radius),
            max_longitude=min(180, longitude + radius),
        )
