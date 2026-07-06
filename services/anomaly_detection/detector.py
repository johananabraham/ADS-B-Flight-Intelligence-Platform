#!/usr/bin/env python3
"""
ADS-B Anomaly Detection Service

Continuously monitors aircraft data and flags anomalies:
- Rapid descent/climb outside normal parameters
- Speed anomalies for altitude
- Emergency squawk codes (7500, 7600, 7700)
- Ghost flights (aircraft disappearing mid-flight)
- Restricted airspace violations
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from app.models import Aircraft, AircraftPosition, Anomaly, AnomalyType, AnomalySeverity
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Expected speed ranges by altitude (knots)
EXPECTED_SPEED_BY_ALTITUDE = {
    # (min_alt, max_alt): (min_speed, max_speed)
    (0, 10000): (60, 300),
    (10000, 25000): (150, 400),
    (25000, 35000): (250, 500),
    (35000, 45000): (300, 550),
    (45000, 60000): (350, 600),
}

# Restricted airspace zones (example - would load from config/database)
RESTRICTED_ZONES = [
    # (name, min_lat, max_lat, min_lon, max_lon)
    ("DC_SFRA", 38.7, 39.1, -77.2, -76.8),  # Washington DC Special Flight Rules Area
]

# Emergency squawk codes
EMERGENCY_SQUAWKS = {
    "7500": (AnomalyType.SQUAWK_7500, AnomalySeverity.CRITICAL, "Hijack code"),
    "7600": (AnomalyType.SQUAWK_7600, AnomalySeverity.HIGH, "Radio failure"),
    "7700": (AnomalyType.SQUAWK_7700, AnomalySeverity.CRITICAL, "General emergency"),
}


class AnomalyDetector:
    """Detects anomalies in flight behavior."""

    def __init__(self, db_session):
        self.db = db_session
        self.recent_anomalies = {}  # Track recent anomalies to avoid duplicates

    def check_squawk_codes(self, aircraft: Aircraft) -> Optional[Anomaly]:
        """Check for emergency squawk codes."""
        if not aircraft.squawk:
            return None

        squawk = aircraft.squawk.strip()
        if squawk in EMERGENCY_SQUAWKS:
            anomaly_type, severity, description = EMERGENCY_SQUAWKS[squawk]

            # Check if we already flagged this recently
            key = f"{aircraft.icao_hex}_{anomaly_type.value}"
            if key in self.recent_anomalies:
                last_flagged = self.recent_anomalies[key]
                if datetime.utcnow() - last_flagged < timedelta(minutes=5):
                    return None

            self.recent_anomalies[key] = datetime.utcnow()

            return Anomaly(
                icao_hex=aircraft.icao_hex,
                callsign=aircraft.callsign,
                anomaly_type=anomaly_type,
                severity=severity,
                latitude=aircraft.latitude,
                longitude=aircraft.longitude,
                altitude=aircraft.altitude,
                description=f"{description} - Squawk {squawk}",
                details={
                    "squawk": squawk,
                    "ground_speed": aircraft.ground_speed,
                    "track": aircraft.track,
                },
            )

        return None

    def check_vertical_rate(self, aircraft: Aircraft) -> Optional[Anomaly]:
        """Check for abnormal climb/descent rates."""
        if aircraft.vertical_rate is None:
            return None

        # Skip if near ground (could be landing/takeoff)
        if aircraft.altitude and aircraft.altitude < 3000:
            return None

        rate = aircraft.vertical_rate

        # Rapid descent (> 4000 ft/min)
        if rate < -settings.rapid_descent_threshold:
            key = f"{aircraft.icao_hex}_RAPID_DESCENT"
            if key in self.recent_anomalies:
                if datetime.utcnow() - self.recent_anomalies[key] < timedelta(minutes=2):
                    return None

            self.recent_anomalies[key] = datetime.utcnow()

            return Anomaly(
                icao_hex=aircraft.icao_hex,
                callsign=aircraft.callsign,
                anomaly_type=AnomalyType.RAPID_DESCENT,
                severity=AnomalySeverity.HIGH,
                latitude=aircraft.latitude,
                longitude=aircraft.longitude,
                altitude=aircraft.altitude,
                description=f"Rapid descent at {abs(rate)} ft/min",
                details={
                    "vertical_rate": rate,
                    "ground_speed": aircraft.ground_speed,
                    "altitude": aircraft.altitude,
                },
            )

        # Rapid climb (> 5000 ft/min - less common, could indicate issues)
        if rate > 5000:
            key = f"{aircraft.icao_hex}_RAPID_CLIMB"
            if key in self.recent_anomalies:
                if datetime.utcnow() - self.recent_anomalies[key] < timedelta(minutes=2):
                    return None

            self.recent_anomalies[key] = datetime.utcnow()

            return Anomaly(
                icao_hex=aircraft.icao_hex,
                callsign=aircraft.callsign,
                anomaly_type=AnomalyType.RAPID_CLIMB,
                severity=AnomalySeverity.MEDIUM,
                latitude=aircraft.latitude,
                longitude=aircraft.longitude,
                altitude=aircraft.altitude,
                description=f"Unusually rapid climb at {rate} ft/min",
                details={
                    "vertical_rate": rate,
                    "ground_speed": aircraft.ground_speed,
                    "altitude": aircraft.altitude,
                },
            )

        return None

    def check_speed_anomaly(self, aircraft: Aircraft) -> Optional[Anomaly]:
        """Check for speed anomalies based on altitude."""
        if aircraft.ground_speed is None or aircraft.altitude is None:
            return None

        speed = aircraft.ground_speed
        altitude = aircraft.altitude

        # Find expected speed range for altitude
        expected_range = None
        for (min_alt, max_alt), speed_range in EXPECTED_SPEED_BY_ALTITUDE.items():
            if min_alt <= altitude < max_alt:
                expected_range = speed_range
                break

        if not expected_range:
            return None

        min_speed, max_speed = expected_range

        # Allow some tolerance
        tolerance = settings.speed_anomaly_threshold
        if speed < min_speed * (1 - tolerance) or speed > max_speed * (1 + tolerance):
            key = f"{aircraft.icao_hex}_SPEED"
            if key in self.recent_anomalies:
                if datetime.utcnow() - self.recent_anomalies[key] < timedelta(minutes=3):
                    return None

            self.recent_anomalies[key] = datetime.utcnow()

            return Anomaly(
                icao_hex=aircraft.icao_hex,
                callsign=aircraft.callsign,
                anomaly_type=AnomalyType.SPEED_ANOMALY,
                severity=AnomalySeverity.MEDIUM,
                latitude=aircraft.latitude,
                longitude=aircraft.longitude,
                altitude=aircraft.altitude,
                description=f"Speed {speed} kts unusual for altitude {altitude} ft",
                details={
                    "ground_speed": speed,
                    "altitude": altitude,
                    "expected_range": expected_range,
                },
            )

        return None

    def check_restricted_airspace(self, aircraft: Aircraft) -> Optional[Anomaly]:
        """Check if aircraft entered restricted airspace."""
        if aircraft.latitude is None or aircraft.longitude is None:
            return None

        lat, lon = aircraft.latitude, aircraft.longitude

        for zone_name, min_lat, max_lat, min_lon, max_lon in RESTRICTED_ZONES:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                key = f"{aircraft.icao_hex}_RESTRICTED_{zone_name}"
                if key in self.recent_anomalies:
                    if datetime.utcnow() - self.recent_anomalies[key] < timedelta(minutes=5):
                        return None

                self.recent_anomalies[key] = datetime.utcnow()

                return Anomaly(
                    icao_hex=aircraft.icao_hex,
                    callsign=aircraft.callsign,
                    anomaly_type=AnomalyType.RESTRICTED_AIRSPACE,
                    severity=AnomalySeverity.HIGH,
                    latitude=lat,
                    longitude=lon,
                    altitude=aircraft.altitude,
                    description=f"Entered restricted airspace: {zone_name}",
                    details={
                        "zone": zone_name,
                        "position": {"lat": lat, "lon": lon},
                    },
                )

        return None

    def detect_ghost_flights(self) -> list[Anomaly]:
        """Find aircraft that disappeared mid-flight."""
        anomalies = []
        cutoff = datetime.utcnow() - timedelta(seconds=settings.ghost_flight_timeout)

        # Find aircraft last seen between 5-15 minutes ago
        # (too recent = might come back, too old = already stale)
        min_cutoff = datetime.utcnow() - timedelta(minutes=15)

        stale_aircraft = (
            self.db.query(Aircraft)
            .filter(
                and_(
                    Aircraft.last_seen < cutoff,
                    Aircraft.last_seen > min_cutoff,
                    Aircraft.altitude > 5000,  # Was in flight, not on ground
                )
            )
            .all()
        )

        for aircraft in stale_aircraft:
            key = f"{aircraft.icao_hex}_GHOST"
            if key in self.recent_anomalies:
                continue

            self.recent_anomalies[key] = datetime.utcnow()

            anomalies.append(
                Anomaly(
                    icao_hex=aircraft.icao_hex,
                    callsign=aircraft.callsign,
                    anomaly_type=AnomalyType.GHOST_FLIGHT,
                    severity=AnomalySeverity.MEDIUM,
                    latitude=aircraft.latitude,
                    longitude=aircraft.longitude,
                    altitude=aircraft.altitude,
                    description=f"Aircraft signal lost at {aircraft.altitude} ft",
                    details={
                        "last_seen": aircraft.last_seen.isoformat(),
                        "last_position": {
                            "lat": aircraft.latitude,
                            "lon": aircraft.longitude,
                        },
                    },
                )
            )

        return anomalies

    def analyze_aircraft(self, aircraft: Aircraft) -> list[Anomaly]:
        """Run all anomaly checks on an aircraft."""
        anomalies = []

        checks = [
            self.check_squawk_codes,
            self.check_vertical_rate,
            self.check_speed_anomaly,
            self.check_restricted_airspace,
        ]

        for check in checks:
            anomaly = check(aircraft)
            if anomaly:
                anomalies.append(anomaly)

        return anomalies


async def detection_loop():
    """Main detection loop."""
    logger.info("Starting anomaly detection service")

    while True:
        db = SessionLocal()
        try:
            detector = AnomalyDetector(db)

            # Get recently active aircraft
            cutoff = datetime.utcnow() - timedelta(minutes=5)
            active_aircraft = (
                db.query(Aircraft).filter(Aircraft.last_seen >= cutoff).all()
            )

            anomalies_found = []

            # Check each active aircraft
            for aircraft in active_aircraft:
                anomalies = detector.analyze_aircraft(aircraft)
                anomalies_found.extend(anomalies)

            # Check for ghost flights
            ghost_anomalies = detector.detect_ghost_flights()
            anomalies_found.extend(ghost_anomalies)

            # Save anomalies
            for anomaly in anomalies_found:
                db.add(anomaly)

            if anomalies_found:
                db.commit()
                logger.info(f"Detected {len(anomalies_found)} anomalies")

                for anomaly in anomalies_found:
                    logger.warning(
                        f"ANOMALY: {anomaly.anomaly_type.value} - "
                        f"{anomaly.icao_hex} - {anomaly.description}"
                    )

        except Exception as e:
            logger.error(f"Detection error: {e}")
            db.rollback()
        finally:
            db.close()

        # Run detection every 5 seconds
        await asyncio.sleep(5)


def main():
    """Entry point."""
    try:
        asyncio.run(detection_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down anomaly detection service")


if __name__ == "__main__":
    main()
