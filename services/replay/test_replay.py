from datetime import datetime, timezone
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
