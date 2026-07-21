#!/usr/bin/env python3
"""
ADS-B Data Ingestion Service

Connects to dump1090 SBS output (port 30003) and stores in PostgreSQL.
Run this continuously to maintain live tracking data.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from app.models import Aircraft, AircraftPosition
from app.core.config import get_settings
from app.schemas.observation import ObservationSourceType
from app.services.observation_adapters import sbs_state_to_observation
from app.services.observation_persistence import insert_observation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# In-memory aircraft state
aircraft_state: Dict[str, dict] = {}


def parse_sbs_timestamp(date_value: str, time_value: str) -> Optional[datetime]:
    """Parse a BaseStation UTC timestamp, including optional milliseconds."""
    timestamp = f"{date_value.strip()} {time_value.strip()}"
    for pattern in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(timestamp, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_sbs_message(line: str) -> Optional[dict]:
    """Parse SBS BaseStation format message."""
    try:
        parts = line.strip().split(',')
        if len(parts) < 11:
            return None

        msg_type = parts[0]
        if msg_type != 'MSG':
            return None

        icao_hex = parts[4].upper()
        if not icao_hex or len(icao_hex) != 6:
            return None

        data = {
            'hex': icao_hex,
            '_observed_at': parse_sbs_timestamp(parts[6], parts[7]),
            '_raw_message_id': hashlib.sha256(line.strip().encode('utf-8')).hexdigest(),
        }

        # Callsign (field 10)
        if len(parts) > 10 and parts[10].strip():
            data['flight'] = parts[10].strip()

        # Altitude (field 11)
        if len(parts) > 11 and parts[11].strip():
            try:
                data['altitude'] = int(parts[11])
            except ValueError:
                pass

        # Ground speed (field 12)
        if len(parts) > 12 and parts[12].strip():
            try:
                data['gs'] = float(parts[12])
            except ValueError:
                pass

        # Track/heading (field 13)
        if len(parts) > 13 and parts[13].strip():
            try:
                data['track'] = float(parts[13])
            except ValueError:
                pass

        # Latitude (field 14)
        if len(parts) > 14 and parts[14].strip():
            try:
                data['lat'] = float(parts[14])
            except ValueError:
                pass

        # Longitude (field 15)
        if len(parts) > 15 and parts[15].strip():
            try:
                data['lon'] = float(parts[15])
            except ValueError:
                pass

        # Vertical rate (field 16)
        if len(parts) > 16 and parts[16].strip():
            try:
                data['vert_rate'] = int(parts[16])
            except ValueError:
                pass

        # Squawk (field 17)
        if len(parts) > 17 and parts[17].strip():
            data['squawk'] = parts[17].strip()

        return data

    except Exception as e:
        logger.debug(f"Failed to parse SBS message: {e}")
        return None


def merge_aircraft_state(icao: str, new_data: dict) -> dict:
    """Merge new data into existing aircraft state."""
    if icao not in aircraft_state:
        aircraft_state[icao] = {'hex': icao, 'last_update': datetime.utcnow()}

    state = aircraft_state[icao]
    for key, value in new_data.items():
        if value is not None and not key.startswith('_'):
            state[key] = value
    state['last_update'] = datetime.utcnow()

    return state


def upsert_aircraft(db, data: dict):
    """Insert or update aircraft record."""
    now = datetime.utcnow()

    stmt = insert(Aircraft).values(
        icao_hex=data.get('hex'),
        callsign=data.get('flight'),
        latitude=data.get('lat'),
        longitude=data.get('lon'),
        altitude=data.get('altitude'),
        ground_speed=data.get('gs'),
        track=data.get('track'),
        vertical_rate=data.get('vert_rate'),
        squawk=data.get('squawk'),
        last_seen=now,
        first_seen=now,
        messages_received=1,
    )

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
            "messages_received": Aircraft.messages_received + 1,
        },
    )

    db.execute(stmt)


def insert_position(db, data: dict):
    """Insert position record for flight trail."""
    if data.get('lat') is None or data.get('lon') is None:
        return

    position = AircraftPosition(
        icao_hex=data.get('hex'),
        latitude=data.get('lat'),
        longitude=data.get('lon'),
        altitude=data.get('altitude'),
        ground_speed=data.get('gs'),
        track=data.get('track'),
        vertical_rate=data.get('vert_rate'),
        timestamp=datetime.utcnow(),
    )
    db.add(position)


async def connect_and_ingest():
    """Connect to dump1090 SBS port and ingest data."""
    host = os.environ.get('DUMP1090_HOST', 'localhost')
    port = int(os.environ.get('DUMP1090_PORT', 30003))
    source_type = ObservationSourceType(
        os.environ.get('OBSERVATION_SOURCE_TYPE', ObservationSourceType.LIVE_RF.value)
    )
    source_id = os.environ.get('OBSERVATION_SOURCE_ID', 'dump1090-sbs')
    receiver_id = os.environ.get('OBSERVATION_RECEIVER_ID', 'local-receiver')
    recording_id = os.environ.get('OBSERVATION_RECORDING_ID')

    logger.info(f"Connecting to dump1090 SBS output at {host}:{port}")

    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            logger.info("Connected to dump1090")

            db = SessionLocal()
            batch_count = 0
            position_count = 0
            last_commit = datetime.utcnow()

            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        logger.warning("Connection closed by dump1090")
                        break

                    line = line.decode('utf-8', errors='ignore')
                    data = parse_sbs_message(line)

                    if data:
                        received_at = datetime.now(timezone.utc)
                        observation = sbs_state_to_observation(
                            data,
                            source_type=source_type,
                            source_id=source_id,
                            receiver_id=(
                                receiver_id
                                if source_type is ObservationSourceType.LIVE_RF
                                else None
                            ),
                            recording_id=(
                                recording_id
                                if source_type is ObservationSourceType.RECORDED_REPLAY
                                else None
                            ),
                            observed_at=data.get('_observed_at') or received_at,
                            received_at=received_at,
                            raw_message_id=data.get('_raw_message_id'),
                        )
                        insert_observation(db, observation)

                        icao = data['hex']
                        merged = merge_aircraft_state(icao, data)

                        upsert_aircraft(db, merged)
                        batch_count += 1

                        if merged.get('lat') and merged.get('lon'):
                            insert_position(db, merged)
                            position_count += 1

                        # Commit every 2 seconds or every 100 messages
                        now = datetime.utcnow()
                        if batch_count >= 100 or (now - last_commit).seconds >= 2:
                            db.commit()
                            if batch_count > 0:
                                logger.info(f"Committed {batch_count} updates, {position_count} positions, {len(aircraft_state)} aircraft tracked")
                            batch_count = 0
                            position_count = 0
                            last_commit = now

            except Exception as e:
                logger.error(f"Error during ingestion: {e}")
                db.rollback()
            finally:
                db.close()
                writer.close()
                await writer.wait_closed()

        except ConnectionRefusedError:
            logger.error(f"Cannot connect to dump1090 at {host}:{port}. Is it running with --net?")
        except Exception as e:
            logger.error(f"Connection error: {e}")

        logger.info("Reconnecting in 5 seconds...")
        await asyncio.sleep(5)


def main():
    """Entry point."""
    try:
        asyncio.run(connect_and_ingest())
    except KeyboardInterrupt:
        logger.info("Shutting down ingestion service")


if __name__ == "__main__":
    main()
