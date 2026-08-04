# LIVE_RF Calibration Workflow v1

## Purpose

This workflow measures how often the deterministic pair and short-window policies
flag observations captured by one real receiver. It preserves the source identity,
time bounds, observation count, and SHA-256 of the exported JSONL file so a report
can be reproduced later.

The result is an **alert rate on a reviewed routine-traffic capture**. It is not a
false-positive rate because ADS-B alone does not provide authoritative ground truth
that every received position was correct or that no transmitter was manipulated.

## 1. Collect LIVE_RF observations

Run the normal platform with the SDR ingestion source explicitly labeled:

```env
OBSERVATION_SOURCE_TYPE=LIVE_RF
OBSERVATION_SOURCE_ID=home-sdr
OBSERVATION_RECEIVER_ID=receiver-1
```

Record the receiver configuration, antenna, approximate environment, software
versions, start/end times, outages, and any known interference in private notes.
Begin with 1–2 hours, then collect captures at different times and traffic levels.

Captured positions can reveal aircraft and receiver-location information. Keep raw
exports under `calibration/local/`, which is git-ignored, and do not publish them
without checking applicable law, licensing, privacy, and redistribution terms.

## 2. Export an immutable bounded dataset

Use `DATABASE_URL` rather than placing credentials in shell history:

```bash
export DATABASE_URL='postgresql://adsb:password@localhost:5432/adsb_intel'
PYTHONPATH=backend:. python scripts/export_live_rf_calibration.py \
  --dataset-id receiver-1-2026-08-04-morning \
  --source-id home-sdr \
  --receiver-id receiver-1 \
  --from 2026-08-04T08:00:00-04:00 \
  --to 2026-08-04T10:00:00-04:00 \
  --license-id PRIVATE-LOCAL \
  --attribution 'Local receiver owner' \
  --output-directory calibration/local/receiver-1-2026-08-04-morning
```

The exporter reads only matching `LIVE_RF` observations and refuses mixed source
or receiver provenance. It writes:

- `manifest.json`: dataset identity, provenance, license/attribution, actual time
  bounds, observation count, review status, and observations SHA-256.
- `observations.jsonl`: one validated `TrackObservation` 1.0 object per line.

It refuses to overwrite an existing dataset directory. A new export starts as
`UNREVIEWED`, so its metrics are automatically limited to engineering validation.

## 3. Run the first report

```bash
PYTHONPATH=backend:. python scripts/run_observation_calibration.py \
  --manifest calibration/local/receiver-1-2026-08-04-morning/manifest.json \
  --observations calibration/local/receiver-1-2026-08-04-morning/observations.jsonl \
  --output calibration/local/receiver-1-2026-08-04-morning/report-unreviewed.json
```

The loader rejects changed hashes, duplicate observation IDs, count mismatches,
wrong source/receiver identity, and timestamps outside the manifest range.

## 4. Review the capture and episodes

Before changing the manifest review status:

1. Confirm the source was the named physical receiver—not replay or simulation.
2. Record receiver outages, clock problems, configuration changes, and obvious data
   gaps that could explain insufficient or inconsistent evidence.
3. Review every grouped alert episode against the track timeline and, where legally
   permitted, an independent source. Record likely receiver/data-quality causes and
   unresolved cases separately.
4. Do not mark unexplained alerts as false simply because the aircraft looked normal.

Store the review notes privately, compute their hash, and then change these manifest
fields (using the actual reviewer and timestamp):

```json
"review_status": "ROUTINE_TRAFFIC_REVIEWED",
"reviewed_at": "2026-08-04T12:30:00-04:00",
"reviewed_by": "reviewer@example.test",
"review_notes_sha256": "<64-character lowercase SHA-256>"
```

The observations hash remains unchanged, and the manifest will reject a reviewed
status without all three review-evidence fields. Rerun the report and retain the
notes beside it locally. The report's claim scope becomes
`reviewed_routine_rf_alert_rate`; it still explicitly rejects a false-positive claim.

## 5. Interpret the report

- `observed_track_hours` sums only positive same-track intervals of at most 30
  seconds. Long periods with no observations do not inflate the denominator.
- Pair and window sections show PASS, FLAGGED, and INSUFFICIENT_DATA counts plus
  flagged evaluations per observed track hour.
- Residual percentiles show what the captured distribution looks like before any
  threshold changes.
- Alert episodes collapse consecutive pair/window flags for the same aircraft and
  receiver when they are no more than 30 seconds apart. This approximates an
  operator-review unit and prevents sliding windows from being counted as dozens
  of independent incidents.

## Promotion criteria

Do not promote window policy `1.0-development` or enable production window alerts
from one convenient capture. Collect multiple reviewed sessions spanning traffic
levels, aircraft classes, weather/receiver conditions, and message loss. Publish
the dataset manifests and aggregate report only when redistribution is permitted;
otherwise publish sanitized metrics and the exact procedure while retaining raw
evidence privately.

Threshold changes require a new policy version and must rerun both the unchanged
synthetic attack baseline and every retained routine-RF calibration dataset.
