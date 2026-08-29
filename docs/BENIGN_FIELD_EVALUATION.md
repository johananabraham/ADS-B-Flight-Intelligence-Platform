# Seven-day benign field evaluation protocol

Status: tooling complete; physical seven-day capture pending. No benign holdout result is claimed yet.

This protocol measures a **reviewed routine-traffic integrity-alert rate**, not a false-positive rate. Routine traffic has no verified ground-truth position or authenticity labels.

## Private capture

Keep raw SBS and receiver metadata under the gitignored `.private/` directory. Use one unchanged receiver/antenna configuration unless a change is explicitly recorded.

```bash
PYTHONPATH=backend:. python scripts/capture_benign_sbs.py \
  --day 1 --host 127.0.0.1 --port 30003 \
  --receiver-configuration "documented-private-config-v1"
```

The command fails before creating a capture unless the source both accepts a
connection and emits a bounded SBS `MSG` record. During capture it atomically updates
`.private/benign-capture-v1/capture-status.private.json` with aggregate-only health
(bytes, lines, connection state, and outage count). Existing captures are never
overwritten: a retry receives an `attempt-NN` filename and a distinct manifest entry.
The capture and all metadata files are owner-only. An interrupted attempt is preserved,
checksummed, recorded as `INTERRUPTED`, and remains unusable pending review.
The source address must be numeric loopback (`127.0.0.0/8` or `::1`) so raw receiver
traffic is not collected from or exposed through a remote network endpoint.

Repeat until seven usable calendar days exist. Inspect each capture and set its private manifest entry to `"usable": true`; document outages, restarts, software versions, antenna/configuration changes, and reasons for any unusable interval. Never delete a difficult interval merely to improve a metric.

Before marking an attempt usable, verify its recorded checksum, byte/line counts,
elapsed and connected durations, outage intervals, `capture_state`, and unchanged
receiver configuration. Keep failed attempts in the manifest with `usable: false`.

- Days 1–4: development/calibration.
- Days 5–6: validation and one permitted freeze.
- Day 7: untouched chronological holdout.

Freeze only after days 1–6 are usable and before viewing day-7 outcomes:

```bash
PYTHONPATH=backend:. python scripts/freeze_integrity_policy.py \
  --capture-manifest .private/benign-capture-v1/capture-manifest.private.json \
  --policy backend/integrity_core/policies/feeder-v1.json \
  --output .private/benign-capture-v1/policy-freeze.private.json
```

The command fails closed if days 1–6 are incomplete or the private manifest says day-7 results were viewed.

## Synthetic frozen-policy gate

```bash
PYTHONPATH=backend:. python scripts/evaluate_frozen_synthetic.py \
  --policy backend/integrity_core/policies/feeder-v1.json \
  --output .private/benign-capture-v1/synthetic-results.json
```

This uses the same `IntegrityEngine` and policy as live evaluation. It exits nonzero if either abrupt or gradual targeted-family recall is below 95%.

## Sanitized export and review

```bash
PYTHONPATH=backend:. python scripts/sanitize_benign_capture.py \
  --manifest .private/benign-capture-v1/capture-manifest.private.json \
  --policy backend/integrity_core/policies/feeder-v1.json \
  --output evaluation/public/benign-features-v1.jsonl
```

The exporter emits random nonreversible public session/track labels, relative seconds, local position deltas, relative altitude, derived evidence features, missingness, receiver-health class, policy state, and split. It fails closed on non-allow-listed fields, identifiers, absolute coordinates/times, network addresses, or private paths. Manually inspect a sample before publication.

Create a private review JSON with `reviews: [{"episode_id": "…", "disposition": "…"}]`. Allowed dispositions are `EXPECTED_MANEUVER_OR_DATA_ARTIFACT`, `RECEIVER_OR_PIPELINE_ISSUE`, `UNEXPLAINED`, and `INSUFFICIENT_CONTEXT`. Generate the report:

```bash
PYTHONPATH=backend:. python scripts/report_benign_evaluation.py \
  --export evaluation/public/benign-features-v1.jsonl \
  --policy backend/integrity_core/policies/feeder-v1.json \
  --freeze-manifest .private/benign-capture-v1/policy-freeze.private.json \
  --reviews .private/benign-capture-v1/reviews.private.json \
  --synthetic-results .private/benign-capture-v1/synthetic-results.json \
  --output evaluation/results/benign-field-v1.json
```

Promotion requires no more than 0.1 reviewed episodes per holdout track-hour, at least 95% recall for both synthetic families, every holdout episode reviewed, and no known parser/time/unit/replay-clock defect. A missing day-7 holdout is reported as `BLOCKED_CAPTURE_PENDING`; a measured miss is `GATE_NOT_MET`. Neither may be relabeled as success.
