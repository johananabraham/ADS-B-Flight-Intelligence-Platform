# ADS-B Recording Format 1.0

This format stores an ordered, immutable set of SBS/BaseStation messages for
repeatable development and evaluation. A recording is not the same thing as the
generated live simulation: it preserves original timestamps and replays the same
messages in the same order on every run.

## Required fields

- `schema_version`: currently `1.0`.
- `recording_id`: stable identity used in observation provenance.
- `title` and `description`: human-readable context.
- `created_at`: timezone-aware creation timestamp.
- `start_time`: timestamp represented by offset zero.
- `source`: source kind/name plus license and attribution.
- `receiver_id`: receiver identity when relevant, otherwise `null`.
- `events_sha256`: SHA-256 of canonical JSON for the `events` array.
- `events`: non-empty list ordered by `offset_ms`.

Each event contains a non-negative `offset_ms`, timezone-aware `observed_at`, and
one ASCII `sbs_message`. The event offset, explicit timestamp, and timestamp inside
the SBS message must agree. The loader rejects unordered, altered, malformed, or
timezone-naive data before opening the replay server.

The checked-in `columbus_generated_v1.json` fixture is fictional, released as
CC0-1.0, and safe to redistribute. It must never be described as captured RF or
real aircraft traffic.
