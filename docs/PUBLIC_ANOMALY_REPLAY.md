# Public GPS-anomaly candidate replay

Current outcome: **BLOCKED_REPLICATION**. No synthetic event is presented as a real incident.

The deterministic workflow targets Zenodo record `11420433` (dataset concept DOI `10.5281/zenodo.11411991`, v2). The reviewed record identifies `GPS_Jumps_from_Routes-2023.csv.zip` with MD5 `5a8df29f8b289ba9c17b3ec8a5569ab9` and `NOTAM_ICAO_GPS-2023.csv.zip` with MD5 `dddee46a925f6f55788377dcd0d6f157`. It describes possible anomalies; this project uses the narrower phrase “public research GPS-anomaly candidate correlated with contemporaneous NOTAM data.”

As checked on 2026-08-21, the official Zenodo API identifies the pinned record's license as CC BY 4.0 and reports the same filenames and checksums recorded in the source manifest. The candidate and NOTAM indexes are therefore `APPROVED_FOR_PROCESSING`; any redistribution requires attribution. ADSB.lol's historical-data page identifies its data as ODbL 1.0 and says daily per-aircraft JSON gzip files are distributed through GitHub releases. No surrounding trace has been acquired, so the checked result remains `BLOCKED_REPLICATION`. Publication must still meet attribution/share-alike obligations. Sources: [Zenodo record API](https://zenodo.org/api/records/11420433), [Zenodo record](https://zenodo.org/records/11420433), and [ADSB.lol historical data](https://www.adsb.lol/docs/open-data/historical/).

## Reproducible workflow

Never commit the downloaded archives, normalized traces, or the private selection manifest. Copy `evaluation/manifests/public-anomaly-sources-v1.json` into `.private/` and retain the reviewed license evidence with the private acquisition notes. If upstream metadata changes or cannot be verified, change `license_status` back to `REVIEW_REQUIRED` so processing fails closed.

Normalize legally acquired surrounding traces into one `.private/traces/<icao24>.jsonl` file per aircraft. Each row must contain `observed_at`, `latitude`, `longitude`, and optional altitude/speed/track/vertical-rate/source-message fields. Then run:

```bash
PYTHONPATH=backend:. python scripts/select_public_candidate.py \
  --manifest .private/public-anomaly-sources-reviewed.json \
  --candidate-archive .private/GPS_Jumps_from_Routes-2023.csv.zip \
  --notam-archive .private/NOTAM_ICAO_GPS-2023.csv.zip \
  --trace-directory .private/traces \
  --output .private/public-candidate-selection.json
```

Selection occurs before detector scoring. It requires a valid aircraft identifier and timestamp, spatial and temporal overlap with an active GPS NOTAM, at least ten minutes of trace coverage, at least six usable positions on each side, and deterministic ordering by UTC timestamp then source ID. Archive filenames, checksums, and license states are verified first.

Replay only the frozen selection and trace:

```bash
PYTHONPATH=backend:. python scripts/replay_public_candidate.py \
  --selection .private/public-candidate-selection.json \
  --trace .private/traces/<selected-aircraft>.jsonl \
  --policy backend/integrity_core/policies/feeder-v1.json \
  --license-approved \
  --output evaluation/results/public-anomaly-candidate-v1.json
```

The only outcomes are `DETECTED`, `MISSED`, `INSUFFICIENT_DATA`, and `BLOCKED_REPLICATION`. `DETECTED` means the frozen policy opened relevant integrity evidence near the indexed point; it does not prove spoofing, malicious intent, or true aircraft position.
