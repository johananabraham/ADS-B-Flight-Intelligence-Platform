from datetime import datetime, timezone
import unittest

from services.replay.replay import AircraftState, demo_scenario


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


if __name__ == "__main__":
    unittest.main()
