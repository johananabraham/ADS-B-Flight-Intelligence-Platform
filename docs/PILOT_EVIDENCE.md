# Pilot evidence bundle and field report

This workflow turns locally reviewed sidecar summaries into reproducible evidence
without collecting aircraft or receiver-operational data. It evaluates whether
the independent feeder pilot met its published criteria; it does not evaluate
whether an aircraft position was true.

## Privacy boundary

Keep daily summaries and participant bundles under `pilot/local/` while the pilot
is running. That directory is ignored by Git. A participant must inspect every
summary and explicitly confirm consent and privacy review before creating a
bundle.

The bundle accepts only:

- a random label matching `pilot-NN` or `pilot-NNN`;
- rounded installation minutes and enumerated installation/readiness outcomes;
- ordered day indexes and the exact allow-listed `/api/v1/pilot/summary` fields;
- boolean comprehension/drop-review answers;
- enumerated interview codes, useful-outcome category, and retention intent.

Free text, wall-clock timestamps, receiver labels, locations, coordinates,
callsigns, aircraft identifiers, screenshots, raw messages, and unknown JSON
fields are rejected. Counters cannot decrease within one process session, and a
session label cannot disappear and later reappear. Restarts remain visible as a
new random session label and are handled without double-counting counters.

## Deterministic decision

`scripts/build_pilot_report.py` validates every bundle before writing either
output. Its `PILOT_SUCCESS` result requires:

- at least three installation attempts;
- at least two non-withdrawn seven-day completions;
- median unaided installation time of no more than 15 rounded minutes;
- correct state-meaning comprehension and a `READY` result for every completion;
- investigation of every visible nonzero drop counter;
- at least one operational finding or concrete usability change;
- one frozen policy version across completed runs;
- privacy review of every shared bundle.

Negative results and withdrawals remain in participant and completion counts. A
failed criterion produces `PILOT_INCOMPLETE` and a nonzero command exit. The
generated JSON contains machine-readable criteria; the Markdown contains the same
decision, aggregate operational counters, and limitations.

## Allowed claim

Only `PILOT_SUCCESS` unlocks this statement:

> Independent ADS-B feeder operators installed and evaluated the local integrity
> sidecar; the pilot measured deployability, reliability, comprehension, and
> operational usefulness.

It never unlocks “detects spoofing,” “verified aircraft trust,” or a field
false-positive-rate claim. Daily indexes and interview answers remain
participant-reported rather than independently attested.
