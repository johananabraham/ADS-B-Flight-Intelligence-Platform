# Interpretable ML Baselines 1.0-development

## Decision

Logistic regression, a bounded decision tree, and a bounded random forest improve
held-out generated-scenario F1 over the deterministic rules-only baseline. They
remain **offline evaluation tools**: ingestion does not load them, operator evidence
does not persist their output, and they cannot create alerts.

Generated attacks and controls do not establish performance on malicious RF or a
field false-alert rate.

## Leakage and evaluation contract

Generator 1.1 assigns every variant from one source session to exactly one split
before feature extraction. Models train on prefixes from 46 training sessions, are
reported against 22 validation sessions, and are evaluated on 22 held-out test
sessions. Attack prefixes become positive only after their declared start, enabling
first-detection delay and pre-attack alert measurement.

Feature schema 1.0 contains 18 timing, latency, identity/provenance, pairwise-rule,
and short-window features. When no pair is scorable, extraction returns `ABSTAIN`
with a reason. The 22 high-rate test controls therefore remain explicit abstentions
because their 0.2-second spacing is below Policy 1.0's 0.5-second minimum.

Kinematic outputs overlap the generated attack mechanisms. The report identifies
those potentially circular features; this experiment tests a simple evidence
combiner, not a general learned representation of flight.

## Reproduce

```bash
PYTHONPATH=backend:. python scripts/run_ml_baselines.py --check \
  --baseline evaluation/results/ml_baselines_v1.json
```

The baseline binds implementation revision `a33442a`, the evaluation-module
SHA-256, Generator 1.1, feature schema 1.0, scikit-learn 1.9.0, model parameters,
and root seed `20260720`.

## Held-out results

| Detector | Precision | Recall | F1 | Control alerts | Impairment alerts |
|---|---:|---:|---:|---:|---:|
| Always normal | 0.0000 | 0.0000 | 0.0000 | 0/88 | 0/44 |
| Pair + window rules | 1.0000 | 0.6250 | 0.7692 | 0/88 | 0/44 |
| Logistic regression | 1.0000 | 0.8750 | 0.9333 | 0/88 | 0/44 |
| Decision tree | 1.0000 | 0.8750 | 0.9333 | 0/88 | 0/44 |
| Random forest | 1.0000 | 0.8750 | 0.9333 | 0/88 | 0/44 |

The generated validation split has the same aggregate metrics. All learned models
detect abrupt changes, gradual drift, replayed timestamps, and cross-source identity
conflict. Logistic-regression gradual-drift delay is 2 seconds; its other detected
families are immediate in this generated suite.

All models miss 22/22 plausible ghost scenarios. That is the expected boundary: a
physically plausible single-source track contains no proof that the aircraft exists.
Independent corroboration is the next evidence path.

## Promotion gate

CI rejects learned models below rules-only F1 on validation or test, generated
control/impairment alerts, invented field metrics, baseline drift, or any promotion
state other than `OFFLINE_EVALUATION_ONLY`.

Promotion requires isolated reviewed routine-RF sessions, measured alert burden,
itemized detection and delay, stable explanations, a versioned model artifact with
rollback, and evidence that ML adds value over rules on captured data. Until then,
the production UI makes no ML-based trust claim.
