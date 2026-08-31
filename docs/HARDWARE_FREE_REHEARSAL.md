# Hardware-free evidence rehearsal

## Purpose

This rehearsal keeps integrity and receiver-health development moving when the
RTL-SDR or target ESP32 is unavailable. One deterministic command runs three
software evidence paths and returns a machine-readable pass/fail result:

1. Frozen-policy abrupt and gradual synthetic detection.
2. Eleven controlled station-health classifications.
3. A receiver lifecycle policy transition from `HEALTHY` to `DEGRADED`, then
   `STALE`, and finally back to `HEALTHY` after fresh simulated telemetry.

The command exercises the same integrity engine and station-health evaluator used
by the application. It does not bypass a failing check or convert unavailable
hardware evidence into a passing field result.

## Run the frozen rehearsal

From the repository root with backend dependencies installed:

```bash
PYTHONPATH=backend:. python scripts/run_hardware_free_rehearsal.py --check \
  --baseline evaluation/results/hardware_free_rehearsal_v1.json
```

The command exits nonzero if any required synthetic recall falls below `0.95`, a
station-health classification changes, the receiver lifecycle no longer matches
the expected sequence, or the aggregate output drifts from the checked-in
baseline.

To inspect a fresh report without changing the baseline:

```bash
PYTHONPATH=backend:. python scripts/run_hardware_free_rehearsal.py --check \
  --output /tmp/hardware-free-rehearsal.json
```

The output contains aggregates and deterministic synthetic reasons only. It does
not contain SBS lines, aircraft identifiers, coordinates, receiver location, or
credentials.

## Acceptance contract

The rehearsal passes only when all four checks are true:

| Check | Required result |
|---|---|
| Abrupt targeted-family recall | At least `0.95` |
| Gradual targeted-family recall | At least `0.95` |
| Controlled station-health classifications | Exact match |
| Receiver recovery policy sequence | Exact match |

The checked-in v1 artifact uses 20 deterministic cases per synthetic family. Its
station-health component is tied to an implementation revision and source hash;
its integrity component is tied to the frozen policy SHA-256.

## Claim boundary

`HARDWARE_FREE_REHEARSAL_ONLY` means the software behaved as expected for
controlled inputs. It does **not** demonstrate:

- reception of physical ADS-B traffic;
- a field-calibrated routine-traffic alert rate;
- physical ESP32, Wi-Fi, MQTT, or watchdog reliability;
- measured receiver outage or recovery time; or
- detection of a real spoofing or interference event.

Those claims still require an authorized live receiver or consenting independent
feeder plus physical ESP32 testing. The report encodes these boundaries as false
claim-permission fields so downstream documentation cannot silently reinterpret a
software rehearsal as field validation.
