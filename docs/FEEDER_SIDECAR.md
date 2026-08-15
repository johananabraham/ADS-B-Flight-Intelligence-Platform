# Feeder integrity sidecar

The feeder sidecar is a local, read-only integrity monitor for an existing dump1090-compatible SBS/BaseStation stream. It reports unusual or internally inconsistent telemetry and receiver limitations. It does not verify aircraft position, diagnose intent, or provide safety-of-life guidance.

## Start in under 15 minutes

Prerequisites: Docker with Compose and dump1090 exposing SBS TCP port 30003.

```bash
export RECEIVER_ID=my-local-feeder
docker compose -f docker-compose.feeder.yml up -d
```

Open <http://127.0.0.1:8090>. The stable `RECEIVER_ID` stays local and is not included in API responses or metric labels. If dump1090 runs on another machine, set `ADSB_INPUT_HOST` to its address. The default `host.docker.internal` works with Docker Desktop and is mapped to the host gateway by the Compose file on supported Linux engines.

The container needs no PostgreSQL, Redis, ChromaDB, LLM key, cloud account, or normal internet egress. It connects only to the configured SBS source and binds the host-facing UI/API to loopback. To intentionally serve another machine on your trusted LAN, edit the port host binding only after applying appropriate firewall and network access controls.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ADSB_INPUT_HOST` | `host.docker.internal` | SBS TCP host |
| `ADSB_INPUT_PORT` | `30003` | SBS TCP port |
| `RECEIVER_ID` | required | Stable local receiver label |
| `SIDECAR_PORT` | `8090` | Loopback host port |
| `INTEGRITY_POLICY_PATH` | bundled v1 policy | Mounted strict JSON policy |
| `EVENT_RETENTION_HOURS` | `168` | Event-segment age bound |
| `EVENT_STORE_MAX_MB` | `128` | Event-segment size bound |

The policy file uses JSON (which is also valid YAML 1.2), rejects unknown fields and unsupported schema versions, and is shown in every snapshot. The bundled `1.0-development` policy is not field-calibrated and must not be described as production or certified.

## Interfaces

- `GET /api/v1/integrity/health`
- `GET /api/v1/integrity/tracks`
- `GET /api/v1/integrity/tracks/{track_id}`
- `GET /api/v1/integrity/events`
- `WS /api/v1/integrity/stream`
- `GET /metrics`
- `GET /api/v1/pilot/summary`

WebSocket clients should fetch REST state after reconnecting. Event JSONL is bounded evidence history, not an authoritative raw-aircraft archive. Raw SBS lines, callsigns, coordinates, squawks, and receiver labels are not written to the event store or metric labels.

## Operational behavior

The SBS client uses capped exponential reconnect backoff with jitter. `DISCONNECTED` and overload-induced `DEGRADED` states remain visible. Processing and subscriber queues are bounded, and any input drop increments `adsb_sidecar_dropped_messages_total`; the sidecar never treats a silent drop as success.

Stop without deleting the retained event volume:

```bash
docker compose -f docker-compose.feeder.yml down
```

## Performance evidence

The checked-in paced soak result in
`evaluation/results/feeder-soak-v1.json` processed 180,000 messages over 1,800
seconds at 100 messages/second with zero drops, 1.699 ms p95 processing latency,
and 95.781 MB process memory. This is a local synthetic transport benchmark, not a
field traffic or detection-quality measurement.

## Independent pilot readiness

With live SBS traffic flowing, verify installation and generate a privacy-safe
aggregate:

```bash
python scripts/check_pilot_readiness.py --sample-seconds 10
curl --fail --silent http://127.0.0.1:8090/api/v1/pilot/summary
```

The readiness command fails unless the source is connected, messages and
evaluations advance, the queue remains within capacity, and drops remain zero. See
`docs/PILOT_PROGRAM.md` before inviting another operator or sharing an aggregate.
