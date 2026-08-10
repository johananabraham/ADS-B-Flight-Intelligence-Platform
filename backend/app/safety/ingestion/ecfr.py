"""Parser for dated XML from the official eCFR Versioner API."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ElementTree
from datetime import date, datetime, timezone

import httpx
from pydantic import ValidationError

from .contracts import (
    EcfrSectionRecord,
    ParsedSource,
    SourceArtifact,
    SourceKind,
    ValidationIssue,
    ValidationReport,
)


ECFR_API_BASE_URL = "https://www.ecfr.gov/api/versioner/v1"


def _normalized_text(element: ElementTree.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _section_identifier(element: ElementTree.Element) -> str | None:
    identifier = element.attrib.get("N", "").strip()
    if re.fullmatch(r"\d+\.\d+[A-Za-z0-9-]*", identifier):
        return identifier
    head = element.find("HEAD")
    if head is None:
        return None
    match = re.search(r"§\s*(\d+\.\d+[A-Za-z0-9-]*)", _normalized_text(head))
    return match.group(1) if match else None


def parse_ecfr_part_xml(
    artifact: SourceArtifact,
) -> ParsedSource[EcfrSectionRecord]:
    """Parse each section from one dated Title 14 part XML response."""
    if artifact.kind is not SourceKind.ECFR_PART_XML:
        raise ValueError("artifact kind must be ECFR_PART_XML")
    if artifact.effective_date is None:
        raise ValueError("eCFR artifacts require effective_date")
    try:
        part = int(artifact.parameters["part"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("eCFR artifacts require an integer part parameter") from error
    try:
        root = ElementTree.fromstring(artifact.content)
    except ElementTree.ParseError as error:
        raise ValueError(f"invalid eCFR XML: {error}") from error

    section_elements = [
        element
        for element in root.iter()
        if element.attrib.get("TYPE") == "SECTION"
    ]
    parsed_by_id: dict[str, EcfrSectionRecord] = {}
    issues: list[ValidationIssue] = []
    duplicate_count = 0
    for index, element in enumerate(section_elements):
        identifier = _section_identifier(element)
        try:
            if identifier is None:
                raise ValueError("section identifier is missing or unsupported")
            head = element.find("HEAD")
            title = _normalized_text(head) if head is not None else f"§ {identifier}"
            record = EcfrSectionRecord(
                cfr_part=part,
                cfr_section=identifier,
                section_title=title,
                section_text=_normalized_text(element),
                effective_date=artifact.effective_date,
                source_url=(
                    f"https://www.ecfr.gov/on/{artifact.effective_date.isoformat()}"
                    f"/title-14/section-{identifier}"
                ),
            )
        except (TypeError, ValueError, ValidationError) as error:
            issues.append(
                ValidationIssue(
                    source_index=index,
                    source_identifier=identifier,
                    code="INVALID_SECTION",
                    message=str(error),
                )
            )
            continue
        if identifier in parsed_by_id:
            duplicate_count += 1
            issues.append(
                ValidationIssue(
                    source_index=index,
                    source_identifier=identifier,
                    code="DUPLICATE_IDENTIFIER",
                    message="duplicate CFR section; first valid section retained",
                )
            )
            continue
        parsed_by_id[identifier] = record

    records = list(parsed_by_id.values())
    report = ValidationReport(
        source_kind=artifact.kind,
        source_uri=artifact.source_uri,
        source_sha256=artifact.content_sha256,
        source_bytes=len(artifact.content),
        retrieved_at=artifact.retrieved_at,
        effective_date=artifact.effective_date,
        parameters=artifact.parameters,
        source_record_count=len(section_elements),
        parsed_record_count=len(records),
        rejected_record_count=len(section_elements) - len(records) - duplicate_count,
        duplicate_identifier_count=duplicate_count,
        null_rates={},
        issues=tuple(issues),
    )
    return ParsedSource[EcfrSectionRecord](records=tuple(records), report=report)


def fetch_ecfr_part(
    part: int,
    effective_date: date,
    *,
    client: httpx.Client | None = None,
    max_attempts: int = 3,
) -> SourceArtifact:
    """Fetch one reproducible, dated Title 14 part from the official API."""
    if part <= 0:
        raise ValueError("part must be positive")
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("max_attempts must be between 1 and 5")
    url = (
        f"{ECFR_API_BASE_URL}/full/{effective_date.isoformat()}"
        f"/title-14.xml?part={part}"
    )
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(30.0),
        follow_redirects=False,
        headers={"User-Agent": "ADS-B-Flight-Intelligence-Platform/1.0"},
    )
    try:
        for attempt in range(max_attempts):
            try:
                response = http_client.get(url)
            except httpx.RequestError:
                if attempt + 1 == max_attempts:
                    raise
                time.sleep(0.25 * (2**attempt))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 == max_attempts:
                    response.raise_for_status()
                time.sleep(0.25 * (2**attempt))
                continue
            response.raise_for_status()
            return SourceArtifact(
                kind=SourceKind.ECFR_PART_XML,
                source_uri=url,
                retrieved_at=datetime.now(timezone.utc),
                effective_date=effective_date,
                parameters={"part": part},
                content=response.content,
            )
    finally:
        if owns_client:
            http_client.close()
    raise RuntimeError("unreachable eCFR fetch state")
