# Short-Window Trajectory Evaluation v1

## Purpose

Pairwise checks catch abrupt impossible movement but can miss small position changes
that accumulate over several reports. This checkpoint adds a second, additive
evidence path: dead-reckon an aircraft's endpoint from its reported speed and track
over a short window, then compare that prediction with the reported endpoint.

It does not replace the five pairwise rules and does not authenticate an ADS-B
transmitter. A flag means that the reports are internally inconsistent under the
versioned policy; it is not proof of spoofing or intent.

## Policy 1.0-development

- Requires 6–31 strictly time-ordered observations from exactly one aircraft and
  one complete provenance identity.
- Accepts windows from 5 through 30 seconds.
- Requires position, ground speed, and track on every observation.
- Flags a cumulative endpoint residual greater than 0.002 nautical miles.
- Persists the policy version, source identity, all observation IDs, measurements,
  and rule output with a deterministic evaluation ID.

The 0.002-nautical-mile limit is a development threshold selected to test whether
the method closes the known synthetic drift gap. It has not been calibrated against
benign captured RF and must not be presented as a field-ready threshold.

## Held-out method

The comparison uses the unchanged Generator 1.0 dataset and split assignment:
90 source sessions are partitioned before variants are generated, producing 46
training, 22 validation, and 22 held-out test sessions. Only the 154 test scenarios
are reported. Pair policy 1.0 and window policy 1.0-development run together; the
combined detector flags a scenario when either evidence path flags within its
labeled detection window.

Run the reviewed result:

```bash
PYTHONPATH=backend:. python scripts/run_windowed_kinematic_evaluation.py --check \
  --baseline evaluation/results/windowed_trajectory_baseline_v1.json
```

## Results

| Held-out scenario | Pairwise | Window | Combined | Median combined delay |
|---|---:|---:|---:|---:|
| Clean generated control | 0/22 | 0/22 | 0/22 | — |
| Abrupt position | 22/22 | 22/22 | 22/22 | 0 s |
| Abrupt altitude | 22/22 | 0/22 | 22/22 | 0 s |
| Abrupt velocity | 22/22 | 22/22 | 22/22 | 0 s |
| Abrupt heading | 22/22 | 22/22 | 22/22 | 0 s |
| Gradual position drift | 0/22 | 22/22 | 22/22 | 2 s |
| Replayed timestamp | 0/22 | 0/22 | 0/22 | — |

The important measured change is gradual drift: 0/22 with pairwise evidence becomes
22/22 with combined evidence, while the generated clean controls remain 0/22.
Replayed timestamps remain an explicit gap and produce insufficient window evidence.

## Product integration

The ingestion service evaluates each newly stored observation. Window results are
stored idempotently in `window_kinematic_evaluations`, exposed through
`GET /api/v1/kinematics/window-evaluations`, and displayed under the aircraft's
Integrity Evidence panel. Window flags are currently evidence, not standalone
operator alerts, until alert deduplication and suppression policy are designed.

## Limits and next evidence

- Generated clean results are not a real-world false-positive rate.
- Calibrate on legally usable benign RF captures across aircraft classes, message
  loss, receiver geometry, and GPS/track noise.
- Add timestamp-specific evidence rather than treating insufficient timing as an
  attack detection.
- Measure alerts per flight hour and detection delay before promoting the policy
  from `development` or creating operator alerts from window results.
