#!/usr/bin/env python3
"""
AI Summary Service

Generates daily intelligence summaries using Claude API.
Analyzes anomalies, traffic patterns, and notable events.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
import anthropic

from app.models import (
    AircraftPosition,
    Anomaly,
    AnomalySeverity,
    DailySummary,
)
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_daily_stats(db, date: datetime) -> dict:
    """Gather statistics for the day."""
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    # Unique aircraft tracked
    unique_aircraft = (
        db.query(func.count(func.distinct(AircraftPosition.icao_hex)))
        .filter(
            and_(
                AircraftPosition.timestamp >= start,
                AircraftPosition.timestamp < end,
            )
        )
        .scalar()
    )

    # Total positions recorded
    total_positions = (
        db.query(func.count(AircraftPosition.id))
        .filter(
            and_(
                AircraftPosition.timestamp >= start,
                AircraftPosition.timestamp < end,
            )
        )
        .scalar()
    )

    # Anomalies by type
    anomaly_counts = (
        db.query(Anomaly.anomaly_type, func.count(Anomaly.id))
        .filter(
            and_(
                Anomaly.detected_at >= start,
                Anomaly.detected_at < end,
            )
        )
        .group_by(Anomaly.anomaly_type)
        .all()
    )

    # Anomalies by severity
    severity_counts = (
        db.query(Anomaly.severity, func.count(Anomaly.id))
        .filter(
            and_(
                Anomaly.detected_at >= start,
                Anomaly.detected_at < end,
            )
        )
        .group_by(Anomaly.severity)
        .all()
    )

    # Get notable anomalies (critical and high severity)
    notable_anomalies = (
        db.query(Anomaly)
        .filter(
            and_(
                Anomaly.detected_at >= start,
                Anomaly.detected_at < end,
                Anomaly.severity.in_([AnomalySeverity.CRITICAL, AnomalySeverity.HIGH]),
            )
        )
        .order_by(Anomaly.detected_at)
        .all()
    )

    return {
        "date": start.strftime("%Y-%m-%d"),
        "unique_aircraft": unique_aircraft or 0,
        "total_positions": total_positions or 0,
        "anomaly_counts": {t.value: c for t, c in anomaly_counts},
        "severity_counts": {s.value: c for s, c in severity_counts},
        "notable_anomalies": [
            {
                "type": a.anomaly_type.value,
                "severity": a.severity.value,
                "icao": a.icao_hex,
                "callsign": a.callsign,
                "description": a.description,
                "time": a.detected_at.strftime("%H:%M:%S"),
                "position": (
                    f"{a.latitude:.4f}, {a.longitude:.4f}"
                    if a.latitude and a.longitude
                    else "Unknown"
                ),
            }
            for a in notable_anomalies
        ],
    }


def generate_prompt(stats: dict) -> str:
    """Generate the prompt for Claude."""
    return f"""You are an aviation intelligence analyst. Generate a concise daily summary report based on the following ADS-B flight tracking data.

Date: {stats['date']}
Aircraft Tracked: {stats['unique_aircraft']}
Position Records: {stats['total_positions']}

Anomalies Detected by Type:
{_format_dict(stats['anomaly_counts'])}

Anomalies by Severity:
{_format_dict(stats['severity_counts'])}

Notable Events (Critical/High Severity):
{_format_anomalies(stats['notable_anomalies'])}

Write a professional intelligence summary that:
1. Provides a brief overview of the day's air traffic activity
2. Highlights any significant anomalies or events
3. Notes any patterns or trends observed
4. Keeps a factual, objective tone appropriate for an intelligence briefing

Keep the summary to 3-4 paragraphs. Be specific about times and details when available."""


def _format_dict(d: dict) -> str:
    if not d:
        return "None"
    return "\n".join(f"  - {k}: {v}" for k, v in d.items())


def _format_anomalies(anomalies: list) -> str:
    if not anomalies:
        return "None"
    lines = []
    for a in anomalies:
        lines.append(
            f"  - [{a['time']}] {a['type']} ({a['severity']}): "
            f"{a['icao']} ({a['callsign'] or 'N/A'}) - {a['description']} "
            f"at {a['position']}"
        )
    return "\n".join(lines)


async def generate_summary(date: Optional[datetime] = None) -> str:
    """Generate AI summary for a given date."""
    if date is None:
        date = datetime.utcnow() - timedelta(days=1)  # Yesterday by default

    db = SessionLocal()
    try:
        stats = get_daily_stats(db, date)

        if stats["unique_aircraft"] == 0:
            return f"No flight data recorded for {stats['date']}."

        prompt = generate_prompt(stats)

        # Call Claude API
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        summary_text = message.content[0].text

        # Save to database
        summary = DailySummary(
            date=date.replace(hour=0, minute=0, second=0, microsecond=0),
            total_aircraft=stats["unique_aircraft"],
            total_positions=stats["total_positions"],
            total_anomalies=sum(stats["anomaly_counts"].values()),
            summary_text=summary_text,
            key_events=stats["notable_anomalies"],
        )

        # Check if summary already exists for this date
        existing = (
            db.query(DailySummary)
            .filter(DailySummary.date == summary.date)
            .first()
        )

        if existing:
            existing.summary_text = summary_text
            existing.total_aircraft = stats["unique_aircraft"]
            existing.total_positions = stats["total_positions"]
            existing.total_anomalies = sum(stats["anomaly_counts"].values())
            existing.key_events = stats["notable_anomalies"]
            existing.generated_at = datetime.utcnow()
        else:
            db.add(summary)

        db.commit()
        logger.info(f"Generated summary for {stats['date']}")

        return summary_text

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def scheduled_summary_loop():
    """Run summary generation on a schedule (e.g., daily at midnight)."""
    logger.info("Starting AI summary service")

    while True:
        now = datetime.utcnow()

        # Generate summary at 00:05 UTC for the previous day
        if now.hour == 0 and now.minute >= 5 and now.minute < 10:
            try:
                yesterday = now - timedelta(days=1)
                summary = await generate_summary(yesterday)
                logger.info(f"Daily summary generated:\n{summary[:200]}...")
            except Exception as e:
                logger.error(f"Failed to generate daily summary: {e}")

        # Sleep for 5 minutes between checks
        await asyncio.sleep(300)


def main():
    """Entry point. Can run scheduled or generate for specific date."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Summary Service")
    parser.add_argument(
        "--date",
        type=str,
        help="Generate summary for specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Run as scheduled service",
    )

    args = parser.parse_args()

    if args.date:
        # Generate for specific date
        date = datetime.strptime(args.date, "%Y-%m-%d")
        summary = asyncio.run(generate_summary(date))
        print("\n" + "=" * 60)
        print(f"DAILY INTELLIGENCE SUMMARY - {args.date}")
        print("=" * 60)
        print(summary)
        print("=" * 60)
    elif args.scheduled:
        # Run as scheduled service
        asyncio.run(scheduled_summary_loop())
    else:
        # Generate for yesterday
        summary = asyncio.run(generate_summary())
        print("\n" + "=" * 60)
        print("DAILY INTELLIGENCE SUMMARY")
        print("=" * 60)
        print(summary)
        print("=" * 60)


if __name__ == "__main__":
    main()
