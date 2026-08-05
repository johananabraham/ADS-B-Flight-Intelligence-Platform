# Kinematic Evaluation Laboratory 1.0

This laboratory measures the deterministic pairwise kinematic policy against
generated, fully reproducible track sessions. It is a development and regression
tool. It is not evidence that the system detects real-world spoofing, and its clean
scenario alert rate is not a field false-positive rate.

## Leakage boundary

The generator creates an original clean source session, assigns that entire session
to `train`, `validation`, or `test` with a stable SHA-256 partition, and only then
creates variants. Every clean and attacked variant from one source session remains
in the same split. This prevents near-identical observations from one flight from
appearing on both sides of a future model evaluation.

The default deterministic dataset contains 90 source sessions:

| Split | Source sessions | Scenario variants |
|---|---:|---:|
| Train | 46 | 322 |
| Validation | 22 | 154 |
| Test | 22 | 154 |

Each scenario manifest records the generator version, session seed, source-session
hash, split, attack parameters, detection window, and observation count. Observation
IDs are deterministic UUIDv5 values, so repeated generation with the same inputs
produces the same dataset.

## Scenario families

Each source session produces one clean control and six manipulated variants:

- abrupt position jump;
- abrupt altitude jump;
- abrupt reported-velocity jump;
- abrupt heading jump;
- subtle cumulative position drift; and
- a replayed timestamp with missing speed evidence.

The evaluator reports flags and `INSUFFICIENT_DATA` separately. A duplicate or
replayed timestamp is therefore never credited as a successful detection merely
because the pair could not be scored.

## Held-out rules-only baseline

Run:

```bash
PYTHONPATH=backend:. python scripts/run_kinematic_evaluation.py --check \
  --baseline evaluation/results/kinematic_rules_baseline_v1.json
```

The checked-in Policy 1.0 baseline evaluates only the held-out test split:

| Scenario | Sessions | Detection rate | Median delay |
|---|---:|---:|---:|
| Clean control | 22 | 0% synthetic sequence alert rate | n/a |
| Abrupt position | 22 | 100% | 0 s |
| Abrupt altitude | 22 | 100% | 0 s |
| Abrupt velocity | 22 | 100% | 0 s |
| Abrupt heading | 22 | 100% | 0 s |
| Gradual position drift | 22 | 0% | n/a |
| Replayed timestamp | 22 | 0% | n/a |

The 66.67% aggregate attack detection rate is less informative than the per-family
results. The pairwise rules catch obvious one-message discontinuities and miss the
subtle gradual drift by design. The replayed timestamp yields 22 insufficient pairs,
which establishes a separate need for sequence/timing integrity rules.

## Regression gate

CI requires all four abrupt families to remain at 100% on the deterministic held-out
suite and requires zero alerts on the generated clean controls. The gate deliberately
does not require gradual-drift or replay detection from a detector that does not yet
implement those capabilities.

The complete command output includes the per-scenario results and reproduction
manifest. A compact reviewed baseline is stored at
`evaluation/results/kinematic_rules_baseline_v1.json`.

## Next evidence required

1. The additive short-window trajectory result is now measured against this
   unchanged manifest in `docs/windowed-trajectory-evaluation-v1.md`.
2. Import a legally usable benign RF capture and report reviewed alerts per flight
   hour. Keep that number separate from synthetic clean performance.
3. Add missing-message, latency-jitter, date-line, polar, and legitimate high-rate
   edge-case sessions before changing policy thresholds.
4. Start ML only after the rules-only baseline and data lineage remain reproducible.
