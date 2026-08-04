"""Resilient adapters for permitted external aircraft-observation sources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import httpx

from ..schemas.observation import (
    ObservationProvenance,
    ObservationQualityFlag,
    ObservationSourceType,
    TrackObservation,
)


class ExternalFetchStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class GeographicBounds:
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.min_latitude <= self.max_latitude <= 90:
            raise ValueError("invalid latitude bounds")
        if not -180 <= self.min_longitude <= self.max_longitude <= 180:
            raise ValueError("invalid longitude bounds")


@dataclass(frozen=True)
class ExternalFetchResult:
    status: ExternalFetchStatus
    observations: tuple[TrackObservation, ...]
    fetched_at: datetime
    from_cache: bool
    reason: str | None = None


@dataclass(frozen=True)
class SourceHealth:
    provider: str
    circuit_state: str
    requests: int
    successes: int
    failures: int
    cache_hits: int
    rate_limit_events: int
    consecutive_failures: int
    last_success_at: datetime | None
    last_error: str | None
    retry_after: datetime | None
    credits_remaining: int | None


@dataclass(frozen=True)
class OpenSkyConfig:
    api_base_url: str = "https://opensky-network.org/api"
    auth_url: str = (
        "https://auth.opensky-network.org/auth/realms/opensky-network/"
        "protocol/openid-connect/token"
    )
    client_id: str = ""
    client_secret: str = ""
    request_timeout_seconds: float = 5.0
    cache_ttl_seconds: float = 10.0
    minimum_poll_interval_seconds: float = 10.0
    failure_backoff_seconds: float = 2.0
    circuit_failure_threshold: int = 3
    circuit_open_seconds: float = 60.0


@dataclass(frozen=True)
class _CacheEntry:
    result: ExternalFetchResult
    expires_at: datetime


class OpenSkyObservationSource:
    """Bounded OpenSky state-vector client with explicit resilience state."""

    provider = "OpenSky Network"
    license_id = "OpenSky terms (research/non-commercial use)"

    def __init__(
        self,
        config: OpenSkyConfig = OpenSkyConfig(),
        *,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._cache: dict[str, _CacheEntry] = {}
        self._next_request_at: datetime | None = None
        self._circuit_open_until: datetime | None = None
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._health = SourceHealth(
            provider=self.provider,
            circuit_state="CLOSED",
            requests=0,
            successes=0,
            failures=0,
            cache_hits=0,
            rate_limit_events=0,
            consecutive_failures=0,
            last_success_at=None,
            last_error=None,
            retry_after=None,
            credits_remaining=None,
        )

    @property
    def health(self) -> SourceHealth:
        now = self._now()
        circuit_state = (
            "OPEN"
            if self._circuit_open_until and now < self._circuit_open_until
            else "CLOSED"
        )
        return replace(self._health, circuit_state=circuit_state)

    async def fetch_states(
        self,
        *,
        bounds: GeographicBounds,
        icao_hex: str | None = None,
    ) -> ExternalFetchResult:
        """Fetch a bounded live snapshot or return explicit unavailability."""
        now = self._now()
        cache_key = self._cache_key(bounds, icao_hex)
        cached = self._cache.get(cache_key)
        if cached and now < cached.expires_at:
            self._health = replace(
                self._health, cache_hits=self._health.cache_hits + 1
            )
            return replace(cached.result, from_cache=True)

        blocked_reason = self._blocked_reason(now)
        if blocked_reason:
            if cached:
                self._health = replace(
                    self._health, cache_hits=self._health.cache_hits + 1
                )
                return replace(cached.result, from_cache=True, reason=blocked_reason)
            return ExternalFetchResult(
                status=ExternalFetchStatus.UNAVAILABLE,
                observations=(),
                fetched_at=now,
                from_cache=False,
                reason=blocked_reason,
            )

        self._health = replace(self._health, requests=self._health.requests + 1)
        self._next_request_at = now + timedelta(
            seconds=self._config.minimum_poll_interval_seconds
        )
        try:
            headers = await self._authorization_header()
            response = await self._request(
                "GET",
                f"{self._config.api_base_url.rstrip('/')}/states/all",
                params=self._params(bounds, icao_hex),
                headers=headers,
            )
        except (httpx.HTTPError, ValueError) as exc:
            return self._record_failure(now, f"request failed: {type(exc).__name__}")

        if response.status_code == 429:
            retry_seconds = _non_negative_int(
                response.headers.get("X-Rate-Limit-Retry-After-Seconds")
            ) or 60
            retry_at = now + timedelta(seconds=retry_seconds)
            self._next_request_at = retry_at
            self._health = replace(
                self._health,
                rate_limit_events=self._health.rate_limit_events + 1,
                last_error="rate limited by provider",
                retry_after=retry_at,
                credits_remaining=0,
            )
            return ExternalFetchResult(
                status=ExternalFetchStatus.UNAVAILABLE,
                observations=(),
                fetched_at=now,
                from_cache=False,
                reason="provider rate limit active",
            )
        if response.status_code != 200:
            return self._record_failure(now, f"provider returned HTTP {response.status_code}")

        try:
            payload = response.json()
            observations = tuple(self._parse_states(payload, received_at=now))
        except (TypeError, ValueError, IndexError) as exc:
            return self._record_failure(now, f"invalid provider payload: {type(exc).__name__}")

        credits = _non_negative_int(response.headers.get("X-Rate-Limit-Remaining"))
        self._health = replace(
            self._health,
            successes=self._health.successes + 1,
            consecutive_failures=0,
            last_success_at=now,
            last_error=None,
            retry_after=self._next_request_at,
            credits_remaining=credits,
        )
        result = ExternalFetchResult(
            status=ExternalFetchStatus.AVAILABLE,
            observations=observations,
            fetched_at=now,
            from_cache=False,
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + timedelta(seconds=self._config.cache_ttl_seconds),
        )
        return result

    async def _authorization_header(self) -> dict[str, str]:
        if not self._config.client_id or not self._config.client_secret:
            return {}
        now = self._now()
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return {"Authorization": f"Bearer {self._access_token}"}
        response = await self._request(
            "POST",
            self._config.auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("authentication response did not contain an access token")
        expires_in = _non_negative_int(str(payload.get("expires_in", 1800))) or 1800
        self._access_token = token
        self._token_expires_at = now + timedelta(seconds=max(1, expires_in - 30))
        return {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client:
            return await self._client.request(method, url, **kwargs)
        async with httpx.AsyncClient(
            timeout=self._config.request_timeout_seconds
        ) as client:
            return await client.request(method, url, **kwargs)

    def _record_failure(self, now: datetime, reason: str) -> ExternalFetchResult:
        consecutive = self._health.consecutive_failures + 1
        backoff = self._config.failure_backoff_seconds * (2 ** (consecutive - 1))
        retry_at = now + timedelta(seconds=backoff)
        self._next_request_at = retry_at
        if consecutive >= self._config.circuit_failure_threshold:
            self._circuit_open_until = now + timedelta(
                seconds=self._config.circuit_open_seconds
            )
            retry_at = self._circuit_open_until
        self._health = replace(
            self._health,
            failures=self._health.failures + 1,
            consecutive_failures=consecutive,
            last_error=reason,
            retry_after=retry_at,
        )
        return ExternalFetchResult(
            status=ExternalFetchStatus.UNAVAILABLE,
            observations=(),
            fetched_at=now,
            from_cache=False,
            reason=reason,
        )

    def _blocked_reason(self, now: datetime) -> str | None:
        if self._circuit_open_until and now < self._circuit_open_until:
            return "source circuit breaker is open"
        if self._next_request_at and now < self._next_request_at:
            return "source poll interval or backoff is active"
        return None

    def _parse_states(
        self, payload: dict[str, Any], *, received_at: datetime
    ) -> list[TrackObservation]:
        rows = payload.get("states") or []
        if not isinstance(rows, list):
            raise TypeError("states must be a list")
        observations = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 17:
                continue
            icao_hex = str(row[0]).strip().upper()
            observed_timestamp = row[3] if row[3] is not None else row[4]
            if observed_timestamp is None:
                continue
            observed_at = datetime.fromtimestamp(float(observed_timestamp), tz=timezone.utc)
            latitude = _optional_float(row[6])
            longitude = _optional_float(row[5])
            if (latitude is None) != (longitude is None):
                latitude = longitude = None
            flags = (
                frozenset()
                if latitude is not None
                else frozenset({ObservationQualityFlag.PARTIAL})
            )
            observations.append(
                TrackObservation(
                    provenance=ObservationProvenance(
                        source_type=ObservationSourceType.EXTERNAL_FEED,
                        source_id="opensky-live-states",
                        provider=self.provider,
                        license_id=self.license_id,
                    ),
                    icao_hex=icao_hex,
                    observed_at=observed_at,
                    received_at=received_at,
                    callsign=row[1],
                    latitude=latitude,
                    longitude=longitude,
                    altitude_ft=_meters_to_feet(row[7]),
                    ground_speed_knots=_meters_per_second_to_knots(row[9]),
                    track_degrees=_optional_float(row[10]),
                    vertical_rate_fpm=_meters_per_second_to_fpm(row[11]),
                    squawk=row[14],
                    quality_flags=flags,
                    raw_message_id=f"opensky:{icao_hex}:{observed_timestamp}",
                )
            )
        return observations

    @staticmethod
    def _params(bounds: GeographicBounds, icao_hex: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "lamin": bounds.min_latitude,
            "lamax": bounds.max_latitude,
            "lomin": bounds.min_longitude,
            "lomax": bounds.max_longitude,
        }
        if icao_hex:
            params["icao24"] = icao_hex.lower()
        return params

    @staticmethod
    def _cache_key(bounds: GeographicBounds, icao_hex: str | None) -> str:
        return ":".join(
            [
                icao_hex.upper() if icao_hex else "*",
                f"{bounds.min_latitude:.3f}",
                f"{bounds.max_latitude:.3f}",
                f"{bounds.min_longitude:.3f}",
                f"{bounds.max_longitude:.3f}",
            ]
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("external source clock must include a timezone")
        return value


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _meters_to_feet(value: Any) -> int | None:
    number = _optional_float(value)
    return None if number is None else round(number * 3.28084)


def _meters_per_second_to_knots(value: Any) -> float | None:
    number = _optional_float(value)
    return None if number is None else number * 1.94384


def _meters_per_second_to_fpm(value: Any) -> int | None:
    number = _optional_float(value)
    return None if number is None else round(number * 196.8504)


def _non_negative_int(value: str | None) -> int | None:
    try:
        parsed = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return parsed if parsed is not None and parsed >= 0 else None
