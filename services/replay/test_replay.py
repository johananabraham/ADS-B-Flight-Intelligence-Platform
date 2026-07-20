import asyncio
from datetime import datetime, timezone
from pathlib import Path
import unittest

import httpx

from services.replay.control_api import create_control_app
from services.replay.controller import PlaybackState, ReplayController
from services.replay.recording import PlaybackCursor, Recording, RecordingValidationError
from services.replay.replay import AircraftState, demo_scenario


FIXTURE = Path(__file__).parent / "recordings" / "columbus_generated_v1.json"


class AircraftStateTests(unittest.TestCase):
    def test_sbs_message_matches_ingestion_field_positions(self) -> None:
        aircraft = demo_scenario()[0]
        fields = aircraft.to_sbs(datetime(2026, 7, 18, tzinfo=timezone.utc), 7).split(",")

        self.assertEqual(len(fields), 22)
        self.assertEqual(fields[0], "MSG")
        self.assertEqual(fields[4], aircraft.icao_hex)
        self.assertEqual(fields[10], aircraft.callsign)
        self.assertEqual(fields[17], aircraft.squawk)

    def test_advance_moves_aircraft_and_updates_altitude(self) -> None:
        aircraft = AircraftState("ABC123", "TEST1", 6_000, 120, 90, 40, -83, 600)

        advanced = aircraft.advance(60)

        self.assertAlmostEqual(advanced.latitude, 40, places=5)
        self.assertGreater(advanced.longitude, aircraft.longitude)
        self.assertEqual(advanced.altitude, 6_600)

    def test_demo_scenario_has_unique_aircraft(self) -> None:
        scenario = demo_scenario()

        self.assertEqual(len({aircraft.icao_hex for aircraft in scenario}), len(scenario))


class RecordedPlaybackTests(unittest.TestCase):
    def test_fixture_has_explicit_generated_provenance_and_valid_hash(self) -> None:
        recording = Recording.load(FIXTURE)

        self.assertEqual(recording.recording_id, "columbus-generated-v1")
        self.assertEqual(recording.source.kind, "GENERATED")
        self.assertEqual(recording.source.license_id, "CC0-1.0")
        self.assertEqual(len(recording.events), 6)

    def test_two_cursors_produce_the_same_order_and_timing(self) -> None:
        recording = Recording.load(FIXTURE)

        def consume(cursor: PlaybackCursor) -> list[tuple[float, str]]:
            result = []
            while scheduled := cursor.next_event():
                result.append((scheduled.delay_seconds, scheduled.event.sbs_message))
            return result

        self.assertEqual(consume(PlaybackCursor(recording)), consume(PlaybackCursor(recording)))

    def test_speed_changes_delay_without_changing_event_order(self) -> None:
        recording = Recording.load(FIXTURE)
        normal = PlaybackCursor(recording, speed=1.0)
        fast = PlaybackCursor(recording, speed=2.0)

        normal_events = [normal.next_event() for _ in range(3)]
        fast_events = [fast.next_event() for _ in range(3)]

        self.assertEqual(normal_events[2].delay_seconds, 1.0)
        self.assertEqual(fast_events[2].delay_seconds, 0.5)
        self.assertEqual(
            [item.event.sbs_message for item in normal_events],
            [item.event.sbs_message for item in fast_events],
        )

    def test_seek_starts_at_first_event_on_or_after_offset(self) -> None:
        recording = Recording.load(FIXTURE)
        cursor = PlaybackCursor(recording)

        cursor.seek(1.5)
        scheduled = cursor.next_event()

        self.assertEqual(scheduled.event.offset_ms, 2_000)
        self.assertEqual(scheduled.delay_seconds, 0.5)

    def test_modified_event_fails_integrity_check(self) -> None:
        import json

        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        document["events"][0]["sbs_message"] = document["events"][0]["sbs_message"].replace(
            "12500", "99999"
        )

        with self.assertRaisesRegex(RecordingValidationError, "events_sha256"):
            Recording.from_dict(document)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ReplayControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.controller = ReplayController(Recording.load(FIXTURE), clock=self.clock)

    async def test_pause_resume_speed_seek_and_restart_update_clock(self) -> None:
        self.clock.advance(0.5)
        paused = await self.controller.pause()
        self.clock.advance(1)

        self.assertEqual(paused.position_ms, 500)
        self.assertEqual((await self.controller.status()).position_ms, 500)

        await self.controller.set_speed(2.0)
        resumed = await self.controller.resume()
        self.clock.advance(0.25)

        self.assertEqual(resumed.state, PlaybackState.PLAYING)
        self.assertEqual((await self.controller.status()).position_ms, 1_000)

        sought = await self.controller.seek(1.5)
        self.assertEqual(sought.position_ms, 1_500)
        self.assertEqual(sought.event_index, 4)

        restarted = await self.controller.restart()
        self.assertEqual(restarted.position_ms, 0)
        self.assertEqual(restarted.event_index, 0)

    async def test_seek_interrupts_waiting_event(self) -> None:
        await self.controller.next_event()
        await self.controller.next_event()
        waiting = asyncio.create_task(self.controller.next_event())
        await asyncio.sleep(0)

        await self.controller.seek(2)
        event = await asyncio.wait_for(waiting, timeout=0.1)

        self.assertEqual(event.offset_ms, 2_000)


class ReplayControlApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_and_command_validation(self) -> None:
        controller = ReplayController(Recording.load(FIXTURE))
        transport = httpx.ASGITransport(app=create_control_app(controller))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            status = await client.get("/status")
            invalid = await client.post("/commands", json={"action": "speed", "value": 3})

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["recording_id"], "columbus-generated-v1")
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
