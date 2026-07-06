#!/usr/bin/env python3
"""
ADS-B Data Ingestion Service

Pulls aircraft data from dump1090 JSON endpoint and stores in PostgreSQL.
Run this continuously to maintain live tracking data.
"""

import asyncio
import httpx
import logging
from datetime import datetime
from typing import Optional
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from app.models import Aircraft, AircraftPosition
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AircraftData:
    """Parsed aircraft data from dump1090."""

    def __init__(self, data: dict):
        self.icao_hex = data.get("hex", "").upper()
        self.callsign = self._clean_callsign(data.get("flight"))
        self.latitude = data.get("lat")
        self.longitude = data.get("lon")
        self.altitude = data.get("alt_baro") or data.get("altitude")
        self.ground_speed = data.get("gs")
        self.track = data.get("track")
        self.vertical_rate = data.get("baro_rate") or data.get("vert_rate")
        self.squawk = data.get("squawk")
        self.seen = data.get("seen", 0)  # seconds since last message
        self.messages = data.get("messages", 0)

    def _clean_callsign(self, callsign: Optional[str]) -> Optional[str]:
        if callsign:
            return callsign.strip()
        return None

    def is_valid(self) -> bool:
        """Check if we have minimum required data."""
        return bool(self.icao_hex) and len(self.icao_hex) == 6

    def has_position(self) -> bool:
        """Check if we have valid position data."""
        return self.latitude is not None and self.longitude is not None

    def __repr__(self):
        return f"<Aircraft {self.icao_hex} {self.callsign or 'N/A'}>"


async def fetch_aircraft_data(client: httpx.AsyncClient) -> list[dict]:
    """Fetch aircraft data from dump1090 JSON endpoint."""
    try:
        response = await client.get(settings.dump1090_url, timeout=5.0)
        response.raise_for_status()
        data = response.json()

        # dump1090 returns {"aircraft": [...], "now": timestamp}
        return data.get("aircraft", [])

    except httpx.RequestError as e:
        logger.error(f"Failed to fetch from dump1090: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing dump1090 data: {e}")
        return []


def upsert_aircraft(db, aircraft_data: AircraftData):
    """Insert or update aircraft record."""
    now = datetime.utcnow()

    stmt = insert(Aircraft).values(
        icao_hex=aircraft_data.icao_hex,
        callsign=aircraft_data.callsign,
        latitude=aircraft_data.latitude,
        longitude=aircraft_data.longitude,
        altitude=aircraft_data.altitude,
        ground_speed=aircraft_data.ground_speed,
        track=aircraft_data.track,
        vertical_rate=aircraft_data.vertical_rate,
        squawk=aircraft_data.squawk,
        last_seen=now,
        first_seen=now,
        messages_received=aircraft_data.messages,
    )

    # On conflict, update the existing record
    stmt = stmt.on_conflict_do_update(
        index_elements=["icao_hex"],
        set_={
            "callsign": stmt.excluded.callsign,
            "latitude": stmt.excluded.latitude,
            "longitude": stmt.excluded.longitude,
            "altitude": stmt.excluded.altitude,
            "ground_speed": stmt.excluded.ground_speed,
            "track": stmt.excluded.track,
            "vertical_rate": stmt.excluded.vertical_rate,
            "squawk": stmt.excluded.squawk,
            "last_seen": stmt.excluded.last_seen,
            "messages_received": stmt.excluded.messages_received,
        },
    )

    db.execute(stmt)


def insert_position(db, aircraft_data: AircraftData):
    """Insert position record for flight trail."""
    if not aircraft_data.has_position():
        return

    position = AircraftPosition(
        icao_hex=aircraft_data.icao_hex,
        latitude=aircraft_data.latitude,
        longitude=aircraft_data.longitude,
        altitude=aircraft_data.altitude,
        ground_speed=aircraft_data.ground_speed,
        track=aircraft_data.track,
        vertical_rate=aircraft_data.vertical_rate,
        timestamp=datetime.utcnow(),
    )
    db.add(position)


async def ingest_loop():
    """Main ingestion loop."""
    logger.info(f"Starting ingestion from {settings.dump1090_url}")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                raw_data = await fetch_aircraft_data(client)

                if not raw_data:
                    logger.debug("No aircraft data received")
                    await asyncio.sleep(1)
                    continue

                db = SessionLocal()
                try:
                    aircraft_count = 0
                    position_count = 0

                    for raw in raw_data:
                        aircraft = AircraftData(raw)

                        if not aircraft.is_valid():
                            continue

                        # Skip if we haven't seen this aircraft recently
                        if aircraft.seen > 60:
                            continue

                        upsert_aircraft(db, aircraft)
                        aircraft_count += 1

                        if aircraft.has_position():
                            insert_position(db, aircraft)
                            position_count += 1

                    db.commit()
                    logger.info(
                        f"Processed {aircraft_count} aircraft, "
                        f"{position_count} positions"
                    )

                except Exception as e:
                    logger.error(f"Database error: {e}")
                    db.rollback()
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Ingestion error: {e}")

            # Poll every second
            await asyncio.sleep(1)


def main():
    """Entry point."""
    try:
        asyncio.run(ingest_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down ingestion service")


if __name__ == "__main__":
    main()
