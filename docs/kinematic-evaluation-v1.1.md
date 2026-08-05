# Extended Kinematic Evaluation Laboratory 1.1

## Purpose

Generator 1.1 broadens the deterministic test laboratory beyond obvious motion
jumps. It adds receiver-like impairments, threats that cannot be solved by
single-source motion checks, and legitimate timing/geographic edge cases. The goal
is to measure both what Policy 1.0 catches and where a different evidence source is
required before any machine-learning model is introduced.

This is generated engineering data. It is not captured RF, proof of spoofing, or a
real-world false-positive-rate measurement.

## Reproduction contract

The reviewed run uses root seed `20260720` and 90 source sessions. SHA-256 assigns
each complete source session to a split before any variants are generated:

| Split | Source sessions | Scenario variants |
|---|---:|---:|
| Train | 46 | 644 |
| Validation | 22 | 308 |
| Test | 22 | 308 |

Every manifest entry records Generator `1.1`, the source-session hash, seed, split,
scenario class and type, generation parameters, expected detection window, and
deterministic observation identities. Generator 1.0 remains available unchanged so
its previously reviewed baseline can still be reproduced.

Run both the regression gates and reviewed comparison:

```bash
PYTHONPATH=backend:. python scripts/run_extended_kinematic_evaluation.py --check \
  --baseline evaluation/results/kinematic_extended_baseline_v1_1.json
```

## Scenario taxonomy

Generator 1.1 labels scenarios before scoring them:

- `CONTROL`: ordinary clean motion, high-rate reports, International Date Line
  crossing, and polar motion;
- `IMPAIRMENT`: two missing observations and deterministic receive-latency jitter;
- `ATTACK`: the six Generator 1.0 manipulations plus a plausible ghost identity and
  one conflicting same-ICAO report from a second simulated source.

Loss and jitter are not labeled attacks because packet loss and network delay are
normal failure modes. A ghost track follows plausible motion, so motion consistency
alone cannot prove whether that aircraft exists. The identity-conflict case changes
source provenance, so the pairwise engine correctly refuses to compare it rather
than hiding the mismatch inside a motion score.

## Held-out pairwise results

Policy 1.0 scores only the 22-session held-out test split:

| Scenario | Class | Flagged sequences | Insufficient pairs |
|---|---|---:|---:|
| Clean motion | Control | 0/22 | 0 |
| Clean high-rate reports | Control | 0/22 | 242 |
| Clean Date Line crossing | Control | 0/22 | 0 |
| Clean polar motion | Control | 0/22 | 0 |
| Missing messages | Impairment | 0/22 | 0 |
| Receive-latency jitter | Impairment | 0/22 | 0 |
| Abrupt position | Attack | 22/22 | 0 |
| Abrupt altitude | Attack | 22/22 | 0 |
| Abrupt velocity | Attack | 22/22 | 0 |
| Abrupt heading | Attack | 22/22 | 0 |
| Gradual position drift | Attack | 0/22 | 0 |
| Replayed timestamp | Attack | 0/22 | 22 |
| Plausible ghost identity | Attack | 0/22 | 0 |
| Cross-source identity conflict | Attack | 0/22 | 44 |

Across the generated controls and impairments, no sequence is flagged. The pairwise
rules detect 88 of 176 attack scenarios, or 50%. That aggregate is intentionally
not presented as overall product accuracy: the additive window detector already
closes this exact gradual-drift gap, while replay, ghost, and identity conflict need
timing-integrity or cross-source evidence that Policy 1.0 does not implement.

High-rate controls produce `INSUFFICIENT_DATA` because their 0.2-second spacing is
below Policy 1.0's conservative 0.5-second minimum. They are not silently treated as
passing and they do not generate alerts. Missing observations preserve correct
elapsed motion, so a kinematic-only check does not infer malicious loss.

## Why this is useful before ML

The result prevents a classifier from receiving an artificially easy benchmark.
It establishes legitimate abstentions, normal impairments, and attacks that require
independent existence or identity evidence. A future model must be compared against:

1. an always-normal baseline;
2. pairwise Policy 1.0;
3. pairwise plus Window Policy 1.0-development; and
4. explicit unavailable/insufficient behavior.

Features that directly encode the generator's injected offsets must be identified
as circular. Train, validation, and test remain separated by source session—not by
individual message or generated variant.

## Remaining evidence gates

- Collect and manually review routine `LIVE_RF` captures before publishing any
  field alert rate.
- Add explicit sequence/timing-integrity evidence for replay and unexpected loss.
- Add cross-source corroboration before claiming ghost or identity-conflict
  detection.
- Keep an ML model only if it improves held-out, session-level results without
  increasing reviewed routine-RF alert burden.
