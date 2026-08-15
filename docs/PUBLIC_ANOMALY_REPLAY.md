# Public GPS-anomaly candidate replay

Current outcome: **BLOCKED_REPLICATION**. No synthetic event is presented as a real incident.

The deterministic workflow targets Zenodo record `11420433` (dataset concept DOI `10.5281/zenodo.11411991`, v2). The reviewed record identifies `GPS_Jumps_from_Routes-2023.csv.zip` with MD5 `5a8df29f8b289ba9c17b3ec8a5569ab9` and `NOTAM_ICAO_GPS-2023.csv.zip` with MD5 `dddee46a925f6f55788377dcd0d6f157`. It describes possible anomalies; this project uses the narrower phrase “public research GPS-anomaly candidate correlated with contemporaneous NOTAM data.”

As checked on 2026-08-15, the Zenodo primary record was open but the reviewed metadata did not expose a precise license identifier. Its manifest therefore remains `REVIEW_REQUIRED` and processing fails closed. ADSB.lol’s historical-data page identifies its data as ODbL 1.0 and says daily per-aircraft JSON gzip files are distributed through GitHub releases. Publication must still meet attribution/share-alike obligations. Sources: [Zenodo record](https://zenodo.org/records/11420433), [ADSB.lol historical data](https://www.adsb.lol/docs/open-data/historical/), and [ADSB.lol privacy/license](https://www.adsb.lol/privacy-license/).

## Reproducible workflow after license approval

Never commit the downloaded archives, normalized traces, or the private selection manifest. Copy `evaluation/manifests/public-anomaly-sources-v1.json` into `.private/`, record the reviewed license decision and change `license_status` to `APPROVED_FOR_PROCESSING` only with evidence.

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
