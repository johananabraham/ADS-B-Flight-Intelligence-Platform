"""Serve deterministic SBS/BaseStation messages over TCP."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone

HOST = os.getenv("REPLAY_HOST", "0.0.0.0")
PORT = int(os.getenv("REPLAY_PORT", "30003"))
INTERVAL_SECONDS = float(os.getenv("REPLAY_INTERVAL_SECONDS", "1"))
RESET_SECONDS = float(os.getenv("REPLAY_RESET_SECONDS", "300"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AircraftState:
    icao_hex: str
    callsign: str
    altitude: float
    ground_speed: float
    track: float
    latitude: float
    longitude: float
    vertical_rate: int
    squawk: str = "1200"

    def advance(self, seconds: float) -> "AircraftState":
        """Move the aircraft using a simple constant-speed great-circle approximation."""
        distance_nm = self.ground_speed * seconds / 3600
        track_radians = math.radians(self.track)
        latitude_delta = distance_nm * math.cos(track_radians) / 60
        longitude_scale = max(math.cos(math.radians(self.latitude)), 0.01)
        longitude_delta = distance_nm * math.sin(track_radians) / (60 * longitude_scale)
        altitude = max(0, self.altitude + self.vertical_rate * seconds / 60)
        return replace(
            self,
            altitude=altitude,
            latitude=self.latitude + latitude_delta,
            longitude=self.longitude + longitude_delta,
        )

    def to_sbs(self, timestamp: datetime, sequence: int) -> str:
        """Serialize state to the SBS fields consumed by the ingestion service."""
        date = timestamp.astimezone(timezone.utc).strftime("%Y/%m/%d")
        time = timestamp.astimezone(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        fields = [
            "MSG", "3", "1", str(sequence), self.icao_hex, str(sequence),
            date, time, date, time, self.callsign, str(round(self.altitude)),
            str(round(self.ground_speed)), str(round(self.track, 1)),
            f"{self.latitude:.5f}", f"{self.longitude:.5f}",
            str(self.vertical_rate), self.squawk, "0", "0", "0", "0",
        ]
        return ",".join(fields)


def demo_scenario() -> list[AircraftState]:
    """Return a repeatable set of aircraft around Columbus, Ohio."""
    return [
        AircraftState("A1B2C3", "DAL1842", 12_500, 310, 72, 39.86, -83.25, 800, "2431"),
        AircraftState("A4D5E6", "UAL228", 31_000, 455, 248, 40.18, -82.65, 0, "4272"),
        AircraftState("A7F8B9", "RCH401", 22_000, 390, 135, 40.31, -83.14, -500, "5214"),
        AircraftState("C1D2E3", "N172SP", 4_500, 112, 18, 39.70, -82.91, 200),
        AircraftState("C4F5A6", "JBU615", 8_200, 245, 310, 39.95, -82.62, -1_200, "3610"),
        AircraftState("C7B8D9", "FDX903", 27_000, 430, 190, 40.42, -82.92, 0, "6345"),
    ]


async def stream_aircraft(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("Replay client connected: %s", peer)
    aircraft = demo_scenario()
    sequence = 1
    elapsed_seconds = 0.0
    try:
        while not reader.at_eof():
            timestamp = datetime.now(timezone.utc)
            payload = "\n".join(item.to_sbs(timestamp, sequence) for item in aircraft) + "\n"
            writer.write(payload.encode("ascii"))
            await writer.drain()
            aircraft = [item.advance(INTERVAL_SECONDS) for item in aircraft]
            sequence += 1
            elapsed_seconds += INTERVAL_SECONDS
            if elapsed_seconds >= RESET_SECONDS:
                aircraft = demo_scenario()
                elapsed_seconds = 0.0
                logger.info("Replay scenario reset for client: %s", peer)
            await asyncio.sleep(INTERVAL_SECONDS)
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info("Replay client disconnected: %s", peer)


async def main() -> None:
    server = await asyncio.start_server(stream_aircraft, HOST, PORT)
    logger.info("ADS-B replay listening on %s:%s with %s aircraft", HOST, PORT, len(demo_scenario()))
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Replay stopped")
