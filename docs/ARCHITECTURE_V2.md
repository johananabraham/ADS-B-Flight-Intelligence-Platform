# Feeder integrity v2 architecture

## Runtime path

```text
dump1090/readsb :30003
        |
        v
strict SBS parser -> bounded queue -> normalized observation
                                      |
                                      v
                           shared integrity_core
                                      |
                       +--------------+-------------+
                       v                            v
              bounded JSONL store          in-memory snapshot
                       |                            |
                       +---------- REST / WebSocket+
                                      |
                              read-only local UI
```

The read-only pilot-summary route derives aggregate operational counters from the
runtime and bounded event store. It is a one-way privacy boundary: it counts track
states and evidence kinds but never serializes the underlying track, receiver,
position, callsign, or wall-clock observation fields.

The sidecar has no database, Redis, vector store, cloud, or LLM dependency. The
full platform adapts its observations into the same shared core. A policy document
defines units, windows, thresholds, expiry, and compatible schema version.
Deterministic input plus policy yields deterministic evidence, episode, snapshot,
and identifier values.

## Failure and trust boundaries

- Network input is untrusted; malformed/partial frames are rejected without
  unbounded buffering.
- Queues, track caches, deduplication state, query limits, labels, and event storage
  are bounded. Drops and degraded/reconnecting state remain observable.
- Persistence uses rotation, retention, truncated-tail recovery, quarantine, and
  duplicate suppression. Failure does not upgrade evidence confidence.
- APIs are read-only. Host exposure defaults to loopback. Container privileges and
  writable paths are minimized.
- `INSUFFICIENT_DATA` is distinct from `NOMINAL`; source health is distinct from
  aircraft evidence; evidence never proves spoofing or intent.

## Other modes

The full platform adds PostgreSQL/PostGIS, authenticated operator workflows,
corroboration, and grounded safety research. The static evidence build compiles a
separate browser-only entry point; verification rejects fetch, WebSocket, API, live
tile, or external asset capabilities from its bundle.
