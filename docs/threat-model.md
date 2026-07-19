# ADS-B Integrity Threat Model

Status: Phase 0 baseline

Scope: civilian aviation-data integrity research and controlled testing

## Goal

Identify evidence that an aircraft observation or track is inconsistent,
unreliable, stale, or insufficiently corroborated. The system does not prove intent,
identify an attacker, or certify an aircraft's true physical location.

## Protected Decisions

The operator should be able to decide:

- whether a track is fresh enough to display;
- whether movement is physically plausible;
- whether independent sources agree within documented tolerances;
- whether a warning may be explained by receiver/network degradation; and
- which evidence caused an integrity state.

## Trust Boundaries

```text
RF/external/replay/simulation source (untrusted observations)
                         |
                  source adapter
                         |
        validated TrackObservation boundary
                         |
       tracking and integrity services (trusted code)
                         |
             database, API, operator UI
```

Every source is treated as fallible. External aviation feeds are corroborating
sources, not guaranteed ground truth. Simulation and recorded replay must be
visibly labeled and must never be presented as live RF.

## Threat and Failure Cases

| Case | Observable evidence | Initial response | Not proven |
|---|---|---|---|
| Abrupt position manipulation | Impossible implied speed or position jump | Kinematic anomaly | Malicious intent |
| Gradual position drift | Persistent residuals or source disagreement | Accumulate evidence over a window | True location |
| Altitude/velocity manipulation | Reported and implied motion disagree | Structured rule evidence | Transmitter identity |
| Ghost track | New identity with weak history/corroboration | Mark unverified; monitor | Fabrication |
| Stale replay | Old or repeated timing/message pattern | Stale/duplicate evidence | Deliberate replay |
| ICAO identity conflict | Same identity in incompatible states | Conflict evidence | Which source is correct |
| Delayed/out-of-order delivery | Observation time precedes track history | Preserve and flag timing quality | Source compromise |
| Receiver outage/degradation | Falling message rate, CRC/health changes | Degrade station/source health | Quiet airspace alone |
| External feed outage | Provider stale, unavailable, or rate limited | Mark corroboration unavailable | Local track suspicious |
| Application defect | Parsing, timing, units, or state bug | Tests, observability, manual review | External attack |

## Non-Goals

- Cryptographic authentication of ADS-B broadcasts.
- Operational air-traffic-control separation or safety-of-life decisions.
- Attribution of malicious intent.
- Weapon targeting or threat engagement.
- Claiming real-world spoofing from controlled synthetic tests.
- Direct 1090 MHz reception with an ESP32.

## Evidence and Labels

Prefer evidence labels such as `STALE`, `OUT_OF_ORDER`, `KINEMATICALLY_IMPLAUSIBLE`,
`CONFLICTING`, `UNVERIFIED`, and `SOURCE_UNAVAILABLE`. Do not automatically translate
an anomaly into “attack” or missing corroboration into “false aircraft.”

## Evaluation Requirements

- Split future ML data by original flight/capture session before generating attacks.
- Report attack-type metrics, detection delay, and false alerts per flight hour.
- Separate synthetic detection claims from observations on ordinary live traffic.
- Record source versions, capture hashes, generator seeds, thresholds, model version,
  and code commit for every published result.
- Preserve an `INSUFFICIENT_DATA` outcome when evidence cannot support a conclusion.

## Privacy, Licensing, and Deployment

- Store only data needed for the documented research purpose.
- Record source license/provenance and obey redistribution restrictions.
- Do not expose a home receiver, MQTT broker, ESP32, or database directly to the
  public internet.
- Public demos default to simulation, shareable recorded fixtures, or permitted
  external data and visibly identify the active source.
