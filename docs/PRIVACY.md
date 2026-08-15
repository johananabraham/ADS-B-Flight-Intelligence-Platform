# Privacy and data handling

## Data boundary

Live SBS messages may contain aircraft identifiers, callsigns, precise positions,
timestamps, and a receiver-dependent observation footprint. Raw captures and exact
receiver metadata are private even though ADS-B is broadcast over radio.

Raw calibration data belongs only under `.private/`, `private-captures/`, or
`calibration/local/`; these paths are ignored and forbidden by the release-history
audit. Do not upload them as CI artifacts. The sidecar stores bounded local JSONL
events; operators choose retention and remain responsible for filesystem access and
deletion. The tooling never automatically destroys private captures.

## Publication boundary

Only allow-listed aggregate fields produced by `sanitize_benign_capture.py` may be
published. The sanitizer replaces source identities with non-reversible,
run-specific labels and removes coordinates, wall-clock dates/timestamps, paths,
salts, and receiver metadata. `evaluation/field_privacy.py` rejects unknown fields
and forbidden serialized values. A human must inspect a sample before publication.

Synthetic fixtures use fictional identifiers. Public-source material is admitted
only through a versioned manifest, checksum, and explicit license decision. An
ambiguous license produces `BLOCKED_REPLICATION`; it is never silently substituted
with synthetic data.

## Logs and metrics

Metrics use bounded operational labels and exclude aircraft and receiver
identifiers. Authentication audit events are sanitized. Before sharing logs,
screenshots, or video, inspect them for coordinates, aircraft identities, local
paths, usernames, hostnames, and credentials.

## Independent pilot summaries

`GET /api/v1/pilot/summary` is the only sidecar output designed for voluntary
sharing during the feeder pilot. It contains a random process-session label,
relative uptime and source-connectivity ratio, aggregate counters, current state
counts, evidence-kind counts, and memory use. It excludes receiver labels,
aircraft/track identifiers, callsigns, coordinates, raw messages, network
addresses, filesystem paths, and wall-clock timestamps. Counters reset when the
sidecar process restarts; the random session label makes that boundary visible.
Operators must inspect the JSON before sharing it and must not supplement it with
live screenshots or raw event output.
