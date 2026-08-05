from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from app.services.corroboration import (
    CorroborationPolicy,
    CorroborationState,
    compare_observations,
)
from app.services.corroboration_service import CorroborationService
from app.services.external_observations import (
    ExternalFetchStatus,
    GeographicBounds,
    OpenSkyConfig,
    OpenSkyObservationSource,
)


NOW = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
BOUNDS = GeographicBounds(40.0, 41.0, -75.0, -74.0)


def observation(
    source_type: ObservationSourceType,
    *,
    icao_hex: str = "ABC123",
    observed_at: datetime = NOW,
    latitude: float | None = 40.5,
    longitude: float | None = -74.5,
    altitude_ft: int | None = 10_000,
) -> TrackObservation:
    return TrackObservation(
        provenance=ObservationProvenance(
            source_type=source_type,
            source_id="local"
            if source_type is not ObservationSourceType.EXTERNAL_FEED
            else "external",
            receiver_id="receiver-1"
            if source_type is ObservationSourceType.LIVE_RF
            else None,
            provider="test-provider"
            if source_type is ObservationSourceType.EXTERNAL_FEED
            else None,
        ),
        icao_hex=icao_hex,
        observed_at=observed_at,
        received_at=observed_at,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=altitude_ft,
    )


@pytest.mark.parametrize(
    ("local", "external", "available", "expected"),
    [
        (
            observation(ObservationSourceType.LIVE_RF),
            None,
            True,
            CorroborationState.LOCAL_ONLY,
        ),
        (
            None,
            observation(ObservationSourceType.EXTERNAL_FEED),
            True,
            CorroborationState.EXTERNAL_ONLY,
        ),
        (
            observation(ObservationSourceType.LIVE_RF),
            None,
            False,
            CorroborationState.UNAVAILABLE,
        ),
    ],
)
def test_presence_and_source_health_states(local, external, available, expected):
    result = compare_observations(
        local=local,
        external=external,
        evaluated_at=NOW,
        source_available=available,
    )

    assert result.state is expected


def test_fresh_matching_observations_are_corroborated():
    result = compare_observations(
        local=observation(ObservationSourceType.LIVE_RF),
        external=observation(
            ObservationSourceType.EXTERNAL_FEED,
            latitude=40.51,
            longitude=-74.51,
            altitude_ft=10_400,
        ),
        evaluated_at=NOW,
        source_available=True,
    )

    assert result.state is CorroborationState.CORROBORATED
    assert result.position_distance_nm is not None
    assert result.position_distance_nm < 3
    assert result.altitude_difference_ft == 400


def test_position_or_altitude_disagreement_is_conflicting():
    result = compare_observations(
        local=observation(ObservationSourceType.LIVE_RF),
        external=observation(
            ObservationSourceType.EXTERNAL_FEED,
            latitude=41.5,
            longitude=-74.5,
            altitude_ft=13_000,
        ),
        evaluated_at=NOW,
        source_available=True,
    )

    assert result.state is CorroborationState.CONFLICTING
    assert result.position_distance_nm > 3
    assert result.altitude_difference_ft == 3_000


def test_old_or_temporally_misaligned_evidence_is_stale():
    result = compare_observations(
        local=observation(
            ObservationSourceType.LIVE_RF,
            observed_at=NOW - timedelta(seconds=31),
        ),
        external=observation(ObservationSourceType.EXTERNAL_FEED),
        evaluated_at=NOW,
        source_available=True,
    )

    assert result.state is CorroborationState.STALE


def test_future_dated_evidence_beyond_clock_skew_is_stale():
    result = compare_observations(
        local=observation(
            ObservationSourceType.LIVE_RF,
            observed_at=NOW + timedelta(seconds=3),
        ),
        external=observation(ObservationSourceType.EXTERNAL_FEED),
        evaluated_at=NOW,
        source_available=True,
    )

    assert result.state is CorroborationState.STALE


def test_missing_comparable_measurements_does_not_claim_corroboration():
    result = compare_observations(
        local=observation(
            ObservationSourceType.LIVE_RF,
            latitude=None,
            longitude=None,
            altitude_ft=None,
        ),
        external=observation(
            ObservationSourceType.EXTERNAL_FEED,
            latitude=None,
            longitude=None,
            altitude_ft=None,
        ),
        evaluated_at=NOW,
        source_available=True,
    )

    assert result.state is CorroborationState.STALE


@pytest.mark.asyncio
async def test_service_does_not_query_global_feed_without_local_position():
    class SourceThatMustNotBeCalled:
        async def fetch_states(self, **_kwargs):
            raise AssertionError("external source should not be queried")

    local = observation(
        ObservationSourceType.LIVE_RF,
        latitude=None,
        longitude=None,
        altitude_ft=10_000,
    )
    service = CorroborationService(SourceThatMustNotBeCalled())

    result = await service.corroborate(local, evaluated_at=NOW)

    assert result.state is CorroborationState.STALE
    assert "no complete position" in result.explanation


def opensky_row(*, observed_at: datetime = NOW) -> list[object]:
    return [
        "abc123",
        "TEST123 ",
        "United States",
        int(observed_at.timestamp()),
        int(observed_at.timestamp()),
        -74.5,
        40.5,
        3_048.0,
        False,
        128.6,
        90.0,
        2.54,
        None,
        3_100.0,
        "1200",
        False,
        0,
    ]


@pytest.mark.asyncio
async def test_opensky_adapter_normalizes_units_provenance_and_query_bounds():
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={"time": int(NOW.timestamp()), "states": [opensky_row()]},
            headers={"X-Rate-Limit-Remaining": "399"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = OpenSkyObservationSource(client=client, clock=lambda: NOW)
        result = await source.fetch_states(bounds=BOUNDS, icao_hex="ABC123")

    assert result.status is ExternalFetchStatus.AVAILABLE
    assert len(result.observations) == 1
    external = result.observations[0]
    assert external.icao_hex == "ABC123"
    assert external.altitude_ft == 10_000
    assert external.ground_speed_knots == pytest.approx(250.0, abs=0.1)
    assert external.vertical_rate_fpm == 500
    assert external.provenance.provider == "OpenSky Network"
    assert captured_request is not None
    assert captured_request.url.params["icao24"] == "abc123"
    assert captured_request.url.params["lamin"] == "40.0"
    assert source.health.credits_remaining == 399


@pytest.mark.asyncio
async def test_opensky_cache_prevents_duplicate_provider_request():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"states": [opensky_row()]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = OpenSkyObservationSource(client=client, clock=lambda: NOW)
        first = await source.fetch_states(bounds=BOUNDS, icao_hex="ABC123")
        second = await source.fetch_states(bounds=BOUNDS, icao_hex="ABC123")

    assert first.from_cache is False
    assert second.from_cache is True
    assert requests == 1
    assert source.health.cache_hits == 1


@pytest.mark.asyncio
async def test_rate_limit_is_unavailable_and_honors_retry_header():
    response = httpx.Response(429, headers={"X-Rate-Limit-Retry-After-Seconds": "120"})
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as client:
        source = OpenSkyObservationSource(client=client, clock=lambda: NOW)
        result = await source.fetch_states(bounds=BOUNDS)

    assert result.status is ExternalFetchStatus.UNAVAILABLE
    assert source.health.rate_limit_events == 1
    assert source.health.retry_after == NOW + timedelta(seconds=120)


@pytest.mark.asyncio
async def test_repeated_failures_open_circuit_without_extra_request():
    now = NOW
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(503)

    config = OpenSkyConfig(
        minimum_poll_interval_seconds=0,
        failure_backoff_seconds=0,
        circuit_failure_threshold=2,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = OpenSkyObservationSource(config, client=client, clock=lambda: now)
        await source.fetch_states(bounds=BOUNDS)
        await source.fetch_states(bounds=BOUNDS)
        blocked = await source.fetch_states(bounds=BOUNDS)

    assert requests == 2
    assert source.health.circuit_state == "OPEN"
    assert blocked.status is ExternalFetchStatus.UNAVAILABLE
    assert blocked.reason == "source circuit breaker is open"


@pytest.mark.asyncio
async def test_oauth_client_credentials_token_is_cached_and_sent_as_bearer():
    auth_requests = 0
    api_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal auth_requests, api_authorization
        if request.url.path.endswith("/token"):
            auth_requests += 1
            return httpx.Response(
                200, json={"access_token": "test-token", "expires_in": 1800}
            )
        api_authorization = request.headers.get("Authorization")
        return httpx.Response(200, json={"states": [opensky_row()]})

    config = OpenSkyConfig(
        client_id="client-id",
        client_secret="client-secret",
        minimum_poll_interval_seconds=0,
        cache_ttl_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = OpenSkyObservationSource(config, client=client, clock=lambda: NOW)
        await source.fetch_states(bounds=BOUNDS, icao_hex="ABC123")
        await source.fetch_states(bounds=BOUNDS, icao_hex="ABC123")

    assert auth_requests == 1
    assert api_authorization == "Bearer test-token"


def test_policy_rejects_negative_tolerances():
    with pytest.raises(ValueError, match="cannot be negative"):
        CorroborationPolicy(max_position_distance_nm=-1)
