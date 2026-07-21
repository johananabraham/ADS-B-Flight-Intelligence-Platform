# ADR 0001: Separate Source Observations from System Tracks

- Status: accepted
- Date: 2026-07-18

## Context

The current ingestion service merges partial SBS messages into one mutable aircraft
row. That is sufficient for a live map, but integrity analysis needs to know which
source reported each value, when it was observed, when it arrived, and what quality
issues were present. A merged row loses that evidence.

## Decision

Introduce a versioned `TrackObservation` contract as the boundary between source
adapters and future tracking/integrity services.

- An observation is one immutable report from one source and time.
- A track is system-maintained state derived from multiple observations.
- An anomaly is structured evidence about observations or a track.
- Provenance is required and source-specific context is validated.
- Stale/out-of-order data is preserved and flagged rather than discarded at schema
  validation.

Phase 0 adds the contract and tests without replacing the current ingestion path.
Later migrations will persist observations and derive tracks while preserving the
working demo during the transition.

## Consequences

Benefits:

- Enables source comparison, replay, auditability, and reproducible evaluation.
- Prevents simulated, external, and live RF data from becoming indistinguishable.
- Makes timing and quality evidence available to integrity rules.

Costs:

- More storage and a future database migration.
- Source adapters must populate provenance consistently.
- Track-building logic can no longer assume the newest merged row is ground truth.

## Rejected Alternatives

- Add source fields only to `Aircraft`: rejected because one mutable row cannot
  preserve multiple conflicting observations.
- Store only raw messages: rejected because every consumer would repeat parsing and
  validation, while source metadata still needs a common contract.
- Replace the current ingestion pipeline immediately: rejected to keep this phase
  small, testable, and non-disruptive.
