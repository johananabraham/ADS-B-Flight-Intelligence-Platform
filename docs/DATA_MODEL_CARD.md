# Data and model card

## Intended task

The live integrity path applies deterministic, versioned rules to normalized ADS-B
observations and reports explainable evidence. It is an integrity monitor for local
feeder operators and a research platform—not an aircraft-authentication or spoofing
classifier.

## Data

| Dataset | Role | Publication state |
|---|---|---|
| Fictional SBS recordings and generated trajectories | Regression/demo | Checked in with provenance |
| Private seven-day RF capture | Benign calibration | Not collected; publication blocked |
| Zenodo 2023 GPS anomalies and NOTAM indexes | Candidate selection | CC BY 4.0 processing approved; not redistributed |
| ADSB.lol historical traces | Candidate replay option | ODbL obligations recorded; no trace committed |

Train/evaluation sessions are split before variants are generated. Frozen-policy
evaluation verifies the policy checksum before scoring. Public candidate selection
uses deterministic identifiers and time windows before integrity scoring.

## Models and rules

Production/sidecar output comes from the shared deterministic integrity engine.
Evidence includes measured values, thresholds, policy version, source observation
IDs, and stable output IDs. Offline logistic-regression, decision-tree, and random-
forest baselines are comparisons only and are not loaded by the live path.

## Measured results

The frozen feeder-v1 synthetic suite detects 20/20 abrupt and 20/20 gradual cases.
These are generated regression cases, not a field false-positive rate. The private
seven-day benchmark is `BLOCKED_CAPTURE_PENDING`; the public anomaly case is
`BLOCKED_REPLICATION`. Nulls and blocked outcomes must remain visible in UI and
reports.

## Limitations and risks

ADS-B is untrusted, observations can be incomplete or delayed, and one receiver
cannot independently establish ground truth. Geometry, multipath, decoder behavior,
clock quality, receiver outages, and ordinary operations can all create unusual
evidence. Performance may shift by region, antenna, hardware, traffic density, and
software version. Never infer malicious intent or make safety decisions from this
output alone.
