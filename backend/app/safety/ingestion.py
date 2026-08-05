"""Idempotent NTSB and eCFR data ingestion with source manifests.

This module provides bulk ingestion pipelines for:
- NTSB aviation incident data from data.ntsb.gov
- eCFR regulations from ecfr.gov API (14 CFR Parts 61, 91, 121, 135)

All ingestion is idempotent - running the same data produces no duplicates.
Source manifests track exactly which version of source data produced the corpus.
"""

import csv
import hashlib
import json
import logging
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import httpx

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.vectorstore import (
    add_faa_regulations,
    add_incident_narratives,
    get_collection_stats,
)
from app.models.safety import Incident, Regulation

logger = logging.getLogger(__name__)

MANIFEST_DIR = Path("data/manifests")
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


class IngestionManifest:
    """Track source data version and ingestion metadata."""

    def __init__(
        self,
        source_type: str,
        source_url: str,
        source_hash: str,
        ingested_at: datetime,
        record_count: int,
        vector_count: int,
        errors: list[str] | None = None,
    ):
        self.source_type = source_type
        self.source_url = source_url
        self.source_hash = source_hash
        self.ingested_at = ingested_at
        self.record_count = record_count
        self.vector_count = vector_count
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_hash": self.source_hash,
            "ingested_at": self.ingested_at.isoformat(),
            "record_count": self.record_count,
            "vector_count": self.vector_count,
            "errors": self.errors,
            "manifest_version": "1.0",
        }

    def save(self, filename: str | None = None) -> Path:
        if filename is None:
            timestamp = self.ingested_at.strftime("%Y%m%d_%H%M%S")
            filename = f"{self.source_type}_{timestamp}.json"
        path = MANIFEST_DIR / filename
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


def compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 hash of content for idempotency tracking."""
    return hashlib.sha256(content).hexdigest()


def chunk_text(text: str, max_chars: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks for vectorization."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at sentence boundary
        if end < len(text):
            for sep in [". ", ".\n", "\n\n", "\n", " "]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + max_chars // 2:
                    end = last_sep + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else end

    return [c for c in chunks if c]


# ============================================================================
# NTSB Incident Ingestion
# ============================================================================


def download_ntsb_data(url: str | None = None) -> tuple[bytes, str]:
    """Download NTSB aviation data ZIP file.

    Returns (content_bytes, sha256_hash).
    """
    settings = get_settings()
    url = url or settings.ntsb_data_url

    logger.info(f"Downloading NTSB data from {url}")
    with urlopen(url, timeout=300) as response:
        content = response.read()

    content_hash = compute_content_hash(content)
    logger.info(f"Downloaded {len(content)} bytes, hash: {content_hash[:16]}...")
    return content, content_hash


def parse_ntsb_csv(zip_content: bytes) -> list[dict[str, Any]]:
    """Parse NTSB aviation incident CSV from ZIP archive."""
    incidents = []

    with zipfile.ZipFile(StringIO(zip_content.decode("latin-1"))) as zf:
        # Find the main data file (usually avall.txt or similar)
        csv_files = [n for n in zf.namelist() if n.endswith((".txt", ".csv"))]
        if not csv_files:
            raise ValueError("No CSV/TXT files found in NTSB archive")

        for csv_file in csv_files:
            logger.info(f"Processing {csv_file}")
            with zf.open(csv_file) as f:
                content = f.read().decode("latin-1")
                reader = csv.DictReader(StringIO(content), delimiter="|")

                for row in reader:
                    try:
                        incident = parse_ntsb_row(row)
                        if incident:
                            incidents.append(incident)
                    except Exception as e:
                        logger.warning(f"Failed to parse row: {e}")

    return incidents


def parse_ntsb_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Parse a single NTSB CSV row into incident dict."""
    ntsb_id = row.get("ev_id") or row.get("EventId") or row.get("ntsb_no")
    if not ntsb_id:
        return None

    def safe_int(val: str | None) -> int | None:
        if not val or val.strip() == "":
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def safe_date(val: str | None) -> datetime | None:
        if not val or val.strip() == "":
            return None
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"]:
            try:
                return datetime.strptime(val.strip(), fmt)
            except ValueError:
                continue
        return None

    return {
        "ntsb_id": ntsb_id.strip()[:20],
        "event_date": safe_date(
            row.get("ev_date") or row.get("EventDate") or row.get("ntsb_date")
        ),
        "event_city": (row.get("ev_city") or row.get("City") or "")[:100],
        "event_state": (row.get("ev_state") or row.get("State") or "")[:50],
        "event_country": (row.get("ev_country") or row.get("Country") or "USA")[:50],
        "aircraft_make": (row.get("acft_make") or row.get("Make") or "")[:100],
        "aircraft_model": (row.get("acft_model") or row.get("Model") or "")[:100],
        "aircraft_category": (row.get("acft_category") or row.get("AircraftCategory") or "")[:50],
        "aircraft_damage": (row.get("damage") or row.get("AircraftDamage") or "")[:50],
        "registration_number": (row.get("regis_no") or row.get("RegistrationNumber") or "")[:20],
        "fatal_injuries": safe_int(row.get("inj_tot_f") or row.get("TotalFatalInjuries")),
        "serious_injuries": safe_int(row.get("inj_tot_s") or row.get("TotalSeriousInjuries")),
        "minor_injuries": safe_int(row.get("inj_tot_m") or row.get("TotalMinorInjuries")),
        "uninjured": safe_int(row.get("inj_tot_n") or row.get("TotalUninjured")),
        "weather_condition": (row.get("wx_cond_basic") or row.get("WeatherCondition") or "")[:50],
        "phase_of_flight": (row.get("phase_flt_spec") or row.get("BroadPhaseOfFlight") or "")[:100],
        "flight_purpose": (row.get("flt_purp") or row.get("PurposeOfFlight") or "")[:100],
        "investigation_type": (row.get("ntsb_docket") or row.get("InvestigationType") or "")[:50],
        "probable_cause": row.get("pc_sect_s") or row.get("ProbableCause") or "",
        "narrative": row.get("narr_cause") or row.get("ReportNarrative") or "",
        "pilot_certificate": (row.get("cert_type") or row.get("PilotCertification") or "")[:50],
        "pilot_total_hours": safe_int(
            row.get("total_time_hrs") or row.get("PilotTotalHours")
        ),
    }


def ingest_ntsb_data(
    url: str | None = None,
    skip_existing: bool = True,
    batch_size: int = 1000,
) -> IngestionManifest:
    """Ingest NTSB incident data into PostgreSQL and ChromaDB.

    Args:
        url: Override URL for NTSB data
        skip_existing: If True, skip incidents already in database
        batch_size: Number of records to commit per batch

    Returns:
        IngestionManifest with ingestion metadata
    """
    ingested_at = datetime.now(timezone.utc)
    errors: list[str] = []
    record_count = 0
    vector_count = 0

    # Download and hash
    try:
        content, content_hash = download_ntsb_data(url)
    except Exception as e:
        return IngestionManifest(
            source_type="ntsb",
            source_url=url or get_settings().ntsb_data_url,
            source_hash="",
            ingested_at=ingested_at,
            record_count=0,
            vector_count=0,
            errors=[f"Download failed: {e}"],
        )

    # Parse
    try:
        incidents = parse_ntsb_csv(content)
    except Exception as e:
        return IngestionManifest(
            source_type="ntsb",
            source_url=url or get_settings().ntsb_data_url,
            source_hash=content_hash,
            ingested_at=ingested_at,
            record_count=0,
            vector_count=0,
            errors=[f"Parse failed: {e}"],
        )

    logger.info(f"Parsed {len(incidents)} incidents")

    # Insert into PostgreSQL
    session = SessionLocal()
    try:
        for i in range(0, len(incidents), batch_size):
            batch = incidents[i : i + batch_size]
            for incident_data in batch:
                ntsb_id = incident_data["ntsb_id"]

                if skip_existing:
                    existing = session.query(Incident).filter_by(ntsb_id=ntsb_id).first()
                    if existing:
                        continue

                try:
                    incident = Incident(**incident_data)
                    session.merge(incident)  # Upsert
                    record_count += 1
                except Exception as e:
                    errors.append(f"Failed to insert {ntsb_id}: {e}")

            session.commit()
            logger.info(f"Committed batch {i // batch_size + 1}")

    finally:
        session.close()

    # Index narratives in ChromaDB
    narrative_ids = []
    narrative_docs = []
    narrative_metas = []

    for incident_data in incidents:
        narrative = incident_data.get("narrative", "")
        if not narrative or len(narrative) < 50:
            continue

        ntsb_id = incident_data["ntsb_id"]
        chunks = chunk_text(narrative)

        for j, chunk in enumerate(chunks):
            chunk_id = f"{ntsb_id}_{j}"
            narrative_ids.append(chunk_id)
            narrative_docs.append(chunk)
            narrative_metas.append({
                "ntsb_id": ntsb_id,
                "chunk_index": j,
                "aircraft_make": incident_data.get("aircraft_make", ""),
                "aircraft_model": incident_data.get("aircraft_model", ""),
                "event_state": incident_data.get("event_state", ""),
                "weather_condition": incident_data.get("weather_condition", ""),
                "phase_of_flight": incident_data.get("phase_of_flight", ""),
            })

    if narrative_ids:
        try:
            add_incident_narratives(narrative_ids, narrative_docs, narrative_metas)
            vector_count = len(narrative_ids)
            logger.info(f"Indexed {vector_count} narrative chunks")
        except Exception as e:
            errors.append(f"ChromaDB indexing failed: {e}")

    manifest = IngestionManifest(
        source_type="ntsb",
        source_url=url or get_settings().ntsb_data_url,
        source_hash=content_hash,
        ingested_at=ingested_at,
        record_count=record_count,
        vector_count=vector_count,
        errors=errors,
    )

    manifest.save()
    return manifest


# ============================================================================
# eCFR Regulations Ingestion
# ============================================================================


def fetch_ecfr_part(title: int, part: int) -> list[dict[str, Any]]:
    """Fetch a specific CFR part from eCFR API."""
    settings = get_settings()
    base_url = settings.ecfr_api_base_url

    # Get current structure
    url = f"{base_url}/structure/{datetime.now().strftime('%Y-%m-%d')}/title-{title}.json"

    with httpx.Client(timeout=60) as client:
        response = client.get(url)
        response.raise_for_status()
        structure = response.json()

    # Find the part
    sections = []
    for child in structure.get("children", []):
        if child.get("type") == "part" and child.get("identifier") == str(part):
            sections = extract_ecfr_sections(child, title, part)
            break

    return sections


def extract_ecfr_sections(
    node: dict[str, Any], title: int, part: int, path: str = ""
) -> list[dict[str, Any]]:
    """Recursively extract sections from eCFR structure."""
    sections = []

    if node.get("type") == "section":
        section_num = node.get("identifier", "")
        section_title = node.get("label", "")
        sections.append({
            "cfr_title": title,
            "cfr_part": part,
            "cfr_section": section_num,
            "cfr_subpart": path,
            "section_title": section_title,
            # Text will be fetched separately
        })

    for child in node.get("children", []):
        child_path = path
        if node.get("type") == "subpart":
            child_path = node.get("identifier", path)
        sections.extend(extract_ecfr_sections(child, title, part, child_path))

    return sections


def fetch_ecfr_section_text(title: int, section: str) -> str:
    """Fetch full text for a specific section."""
    settings = get_settings()
    date = datetime.now().strftime("%Y-%m-%d")
    url = f"{settings.ecfr_api_base_url}/full/{date}/title-{title}/section-{section}.json"

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("text", "")
    except Exception as e:
        logger.warning(f"Failed to fetch section {section}: {e}")
        return ""


def ingest_ecfr_data(
    parts: list[int] | None = None,
    batch_size: int = 50,
) -> IngestionManifest:
    """Ingest eCFR regulations into PostgreSQL and ChromaDB.

    Args:
        parts: CFR parts to ingest (default: [61, 91, 121, 135])
        batch_size: Number of sections to commit per batch

    Returns:
        IngestionManifest with ingestion metadata
    """
    if parts is None:
        parts = [61, 91, 121, 135]

    ingested_at = datetime.now(timezone.utc)
    errors: list[str] = []
    record_count = 0
    vector_count = 0
    title = 14  # 14 CFR

    settings = get_settings()
    source_url = f"{settings.ecfr_api_base_url} (Parts: {parts})"
    all_content = []

    # Fetch all sections
    all_sections = []
    for part in parts:
        try:
            logger.info(f"Fetching 14 CFR Part {part}")
            sections = fetch_ecfr_part(title, part)
            all_sections.extend(sections)
            logger.info(f"Found {len(sections)} sections in Part {part}")
        except Exception as e:
            errors.append(f"Failed to fetch Part {part}: {e}")

    # Fetch section text and insert
    session = get_session()
    try:
        for i, section_data in enumerate(all_sections):
            section_num = section_data["cfr_section"]

            # Fetch text
            text = fetch_ecfr_section_text(title, section_num)
            if not text:
                continue

            all_content.append(text)
            section_data["section_text"] = text
            section_data["effective_date"] = datetime.now(timezone.utc)
            section_data["source_url"] = (
                f"https://www.ecfr.gov/current/title-{title}/section-{section_num}"
            )

            try:
                reg = Regulation(**section_data)
                session.merge(reg)  # Upsert
                record_count += 1
            except Exception as e:
                errors.append(f"Failed to insert {section_num}: {e}")

            if (i + 1) % batch_size == 0:
                session.commit()
                logger.info(f"Committed {i + 1} sections")

        session.commit()
    finally:
        session.close()

    # Compute content hash
    content_hash = compute_content_hash("".join(all_content).encode())

    # Index in ChromaDB
    reg_ids = []
    reg_docs = []
    reg_metas = []

    for section_data in all_sections:
        text = section_data.get("section_text", "")
        if not text or len(text) < 20:
            continue

        section_id = f"{section_data['cfr_part']}.{section_data['cfr_section']}"
        chunks = chunk_text(text, max_chars=800)

        for j, chunk in enumerate(chunks):
            chunk_id = f"14cfr_{section_id}_{j}"
            reg_ids.append(chunk_id)
            reg_docs.append(chunk)
            reg_metas.append({
                "cfr_title": section_data["cfr_title"],
                "cfr_part": section_data["cfr_part"],
                "cfr_section": section_data["cfr_section"],
                "section_title": section_data.get("section_title", ""),
                "chunk_index": j,
            })

    if reg_ids:
        try:
            add_faa_regulations(reg_ids, reg_docs, reg_metas)
            vector_count = len(reg_ids)
            logger.info(f"Indexed {vector_count} regulation chunks")
        except Exception as e:
            errors.append(f"ChromaDB indexing failed: {e}")

    manifest = IngestionManifest(
        source_type="ecfr",
        source_url=source_url,
        source_hash=content_hash,
        ingested_at=ingested_at,
        record_count=record_count,
        vector_count=vector_count,
        errors=errors,
    )

    manifest.save()
    return manifest


# ============================================================================
# Combined Ingestion
# ============================================================================


def ingest_all(
    ntsb_url: str | None = None,
    ecfr_parts: list[int] | None = None,
) -> dict[str, IngestionManifest]:
    """Run all ingestion pipelines.

    Returns dict of manifests keyed by source type.
    """
    manifests = {}

    logger.info("Starting NTSB ingestion...")
    manifests["ntsb"] = ingest_ntsb_data(url=ntsb_url)

    logger.info("Starting eCFR ingestion...")
    manifests["ecfr"] = ingest_ecfr_data(parts=ecfr_parts)

    # Log summary
    for source_type, manifest in manifests.items():
        logger.info(
            f"{source_type}: {manifest.record_count} records, "
            f"{manifest.vector_count} vectors, {len(manifest.errors)} errors"
        )

    return manifests


def get_ingestion_status() -> dict[str, Any]:
    """Get current ingestion status from manifests and collections."""
    manifests = list(MANIFEST_DIR.glob("*.json"))
    latest = {}

    for manifest_path in sorted(manifests, reverse=True):
        data = json.loads(manifest_path.read_text())
        source_type = data.get("source_type")
        if source_type and source_type not in latest:
            latest[source_type] = data

    # Add current collection stats
    try:
        stats = get_collection_stats()
    except Exception:
        stats = {}

    return {
        "manifests": latest,
        "collections": stats,
    }
