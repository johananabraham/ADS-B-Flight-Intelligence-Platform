"""Select the first qualifying candidate without inspecting detector scores."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from shapely import wkt
from shapely.strtree import STRtree


class CandidateSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class CandidateSelection:
    candidate_id: str
    source_identifier: str
    aircraft_identifier: str
    candidate_time: datetime
    notam_identifier: str
    trace: tuple[dict[str, Any], ...]

    def private_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "candidate_id": self.candidate_id,
            "source_identifier": self.source_identifier,
            "aircraft_identifier": self.aircraft_identifier,
            "candidate_time": self.candidate_time.isoformat().replace("+00:00", "Z"),
            "notam_identifier": self.notam_identifier,
        }


def _time(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _valid_aircraft(value: str) -> bool:
    return len(value) == 6 and all(char in "0123456789abcdefABCDEF" for char in value)


class _NotamIndex:
    def __init__(self, notams: Iterable[dict[str, Any]]) -> None:
        self.notices = []
        self.geometries = []
        for notice in notams:
            try:
                geometry = wkt.loads(notice["WKT"])
                _time(notice["time_start"])
                _time(notice["time_end"])
            except Exception:
                continue
            self.notices.append(notice)
            self.geometries.append(geometry)
        self.tree = STRtree(self.geometries)

    def overlap(self, candidate: dict[str, Any]):
        candidate_time = _time(candidate["time_of_spoofing"])
        try:
            candidate_geometry = wkt.loads(candidate["WKT"])
        except Exception as exc:
            raise CandidateSelectionError("candidate WKT is invalid") from exc
        matches = []
        for index in self.tree.query(candidate_geometry, predicate="intersects"):
            notice = self.notices[int(index)]
            if _time(notice["time_start"]) <= candidate_time <= _time(notice["time_end"]):
                matches.append(notice)
        return min(matches, key=lambda value: str(value["notam_id"])) if matches else None


def _active_overlapping_notam(candidate: dict[str, Any], notams: Iterable[dict[str, Any]]):
    candidate_time = _time(candidate["time_of_spoofing"])
    try:
        candidate_geometry = wkt.loads(candidate["WKT"])
    except Exception as exc:
        raise CandidateSelectionError("candidate WKT is invalid") from exc
    matches = []
    for notice in notams:
        if not (_time(notice["time_start"]) <= candidate_time <= _time(notice["time_end"])):
            continue
        try:
            geometry = wkt.loads(notice["WKT"])
        except Exception:
            continue
        if geometry.intersects(candidate_geometry):
            matches.append(notice)
    return min(matches, key=lambda value: str(value["notam_id"])) if matches else None


def _qualified_trace(trace: Iterable[dict[str, Any]], candidate_time: datetime):
    normalized = sorted(trace, key=lambda item: _time(item["observed_at"]))
    before = [item for item in normalized if _time(item["observed_at"]) < candidate_time]
    after = [item for item in normalized if _time(item["observed_at"]) > candidate_time]
    if len(before) < 6 or len(after) < 6:
        return None
    if _time(normalized[0]["observed_at"]) > candidate_time - timedelta(minutes=5):
        return None
    if _time(normalized[-1]["observed_at"]) < candidate_time + timedelta(minutes=5):
        return None
    required = ("latitude", "longitude")
    if any(any(item.get(field) is None for field in required) for item in normalized):
        return None
    return tuple(normalized)


def select_candidate(
    candidates: Iterable[dict[str, Any]],
    notams: Iterable[dict[str, Any]],
    traces: dict[str, Iterable[dict[str, Any]]],
) -> CandidateSelection:
    """Select first by UTC timestamp then stable source id, before detector scoring."""
    best = None
    notice_index = _NotamIndex(notams)
    for candidate in candidates:
        aircraft = str(candidate.get("icao24", "")).lower()
        source_id = str(candidate.get("id", ""))
        if not source_id or not _valid_aircraft(aircraft):
            continue
        candidate_time = _time(candidate["time_of_spoofing"])
        notice = notice_index.overlap(candidate)
        if notice is None:
            continue
        trace = _qualified_trace(traces.get(aircraft, ()), candidate_time)
        if trace is None:
            continue
        eligible = (candidate_time, source_id, candidate, notice, trace)
        if best is None or (candidate_time, source_id) < (best[0], best[1]):
            best = eligible
    if best is None:
        raise CandidateSelectionError("no candidate satisfies NOTAM overlap and trace coverage")
    candidate_time, source_id, candidate, notice, trace = best
    identity = f"{candidate_time.isoformat()}:{source_id}:{candidate['icao24']}"
    return CandidateSelection(
        candidate_id="candidate_" + hashlib.sha256(identity.encode()).hexdigest()[:20],
        source_identifier=source_id,
        aircraft_identifier=str(candidate["icao24"]).upper(),
        candidate_time=candidate_time,
        notam_identifier=str(notice["notam_id"]),
        trace=trace,
    )
