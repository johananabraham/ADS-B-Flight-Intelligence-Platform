# Benchmark methodology

Three evidence tiers are reported separately.

1. **Synthetic regression.** Source sessions are split before variants are made.
   The policy is frozen and checksum-verified, then abrupt and gradual families are
   evaluated with deterministic seeds. Results guard behavior; they do not estimate
   field prevalence or false-positive rates.
2. **Private benign field benchmark.** Capture seven chronological days from one
   authorized receiver. Freeze on days 1–6 before viewing day 7. Exclude documented
   outages, review episodes, and publish only sanitized aggregates. This benchmark
   is currently `BLOCKED_CAPTURE_PENDING`.
3. **Licensed public anomaly replay.** Validate archive hash and redistribution
   decision, choose the candidate deterministically before scoring, require a
   surrounding trace and adequate reports, then replay through the same shared
   core. Outcomes are `DETECTED`, `NOT_DETECTED`, `INSUFFICIENT_DATA`, or
   `BLOCKED_REPLICATION`; the current result is the latter.

Every result records code/policy versions, source manifest, parameters, counts,
exclusions, and limitations. Never merge tiers into a single accuracy claim. See
`BENIGN_FIELD_EVALUATION.md`, `PUBLIC_ANOMALY_REPLAY.md`, and the evaluation JSON
artifacts for exact commands and schemas.
