# Edge-station health evidence v1

## Scope

Station health answers whether an edge node is reporting fresh operational
telemetry. When the loopback host bridge is present, it also correlates aggregate
dump1090/sidecar connection, message freshness, queue, drop, and reconnect evidence.
It deliberately does not claim ADS-B authenticity, aircraft-message correctness,
RF sensitivity, antenna coverage, or true aircraft position.

Policy 1.1 produces five explainable states:

| State | Meaning |
|---|---|
| `HEALTHY` | The heartbeat is at most 45 seconds old and reported limits pass. |
| `DEGRADED` | The heartbeat is fresh, but device or known receiver-pipeline evidence is outside policy. |
| `STALE` | The heartbeat is late or has an invalid future timestamp. |
| `OFFLINE` | A broker Last Will or graceful presence event is newer than telemetry. |
| `NO_DATA` | The backend lacks enough station telemetry to evaluate health. |

Every API result includes the policy version, exact reasons, evaluation time,
telemetry age, optional pipeline age, and source message IDs. This keeps
operator-visible state tied to immutable evidence. Missing pipeline telemetry does
not retroactively degrade ESP32-only nodes; the API/UI show that evidence as absent.

## Reproducible offline result

`evaluation/results/station_health_offline_v1.json` covers eleven deterministic
scenarios: the original device/presence cases plus receiver disconnect, stale bridge,
full receiver queue, and receiver-source silence. All eleven match their controlled
expectations, for synthetic exact-match accuracy of 1.0.

Reproduce the checked-in artifact:

```bash
PYTHONPATH=backend:. python scripts/run_station_health_evaluation.py --check \
  --baseline evaluation/results/station_health_offline_v1.json
```

This is synthetic state-machine evidence, not field reliability evidence. The
artifact explicitly records zero physical ESP32 sessions and zero live MQTT
messages.

## Hardware-free transport demo

After provisioning and starting the edge Compose stack, publish schema-valid
telemetry through the same TLS and ACL path used by firmware:

```bash
export MQTT_HOST=localhost
export MQTT_CA_CERT=edge/mosquitto/secrets/ca.crt
export STATION_MQTT_PASSWORD_FILE=edge/mosquitto/secrets/roof-node-1.password
PYTHONPATH=backend:. python -m services.edge_telemetry.simulator --count 5 --interval 2
curl http://localhost:8000/api/v1/stations/
```

The simulator is clearly identified by firmware version `0.1.0+simulator`; it is
not evidence that physical firmware or RF hardware was exercised.

With the local feeder sidecar running, publish aggregate pipeline health through its
separate pipeline-only MQTT account:

```bash
export PIPELINE_MQTT_PASSWORD_FILE=edge/mosquitto/secrets/roof-node-1-bridge.password
PYTHONPATH=backend:. python -m services.edge_telemetry.receiver_bridge --count 5
```

The bridge accepts only an HTTP loopback sidecar URL, rejects redirects, validates a
strict aggregate schema, and never forwards raw messages or aircraft/receiver
identifiers.

## Field promotion gate

Before claiming demonstrated ESP32 reliability, run the target board through
Wi-Fi loss, broker restart, power cycle, queue saturation, watchdog recovery,
and a multi-hour soak. Record reconnect duration, message loss/duplication,
memory floor, reset reason, and broker/backend evidence for each test.
