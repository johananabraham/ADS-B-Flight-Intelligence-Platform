# Independent feeder pilot program

The pilot answers a narrower question than “does this detect spoofing?”:

> Can an independent dump1090/readsb operator install the sidecar, keep it running,
> understand its evidence, and use it to investigate a receiver or telemetry issue?

## Recruitment and eligibility

Recruit three to five operators who are not contributors to this repository. A
participant needs an authorized ADS-B feeder, SBS/BaseStation TCP output, Docker
Compose, and permission to run local monitoring. Do not request their exact
location, raw messages, aircraft identifiers, screenshots of live tracks, feeder
account credentials, or remote shell access.

Record only a random participant label such as `pilot-01`. Participation is
voluntary; operators may stop at any time and should review every artifact before
sharing it. Pilot data is for product evaluation, not aircraft tracking or safety
decisions.

## Protocol

1. Ask the operator to start from the public README without live assistance. Record
   whether installation succeeds and elapsed minutes rounded to a whole minute.
2. Run the readiness check:

   ```bash
   python scripts/check_pilot_readiness.py --sample-seconds 10
   ```

   It must report `READY`. A failed check is a product finding, not an operator
   failure.
3. Run the sidecar for at least seven consecutive days. Once per day, save the
   aggregate endpoint locally:

   ```bash
   curl --fail --silent http://127.0.0.1:8090/api/v1/pilot/summary \
     -o pilot-summary-day-N.json
   ```

   The JSON contains randomized process-session identity, relative uptime,
   connection ratio, message/drop/reconnect counts, memory, and aggregate
   state/evidence counts. It contains no aircraft or receiver identifiers,
   coordinates, callsigns, or wall-clock timestamps. Operators must still inspect
   it before sharing.
4. When `QUESTIONABLE` evidence appears, ask whether its explanation was
   understandable and whether it led to a useful check of the antenna, decoder,
   clock, network, or feed. Do not ask the operator to identify the aircraft.
5. At the end, collect the sanitized summaries and conduct the interview in
   `PILOT_INTERVIEW.md`. Keep raw operational data local.
6. Ask the participant to build a validated, enumeration-only evidence bundle.
   The command refuses unknown summary fields and requires explicit consent and
   privacy-review confirmations:

   ```bash
   python scripts/build_pilot_evidence_bundle.py \
     --participant-id pilot-01 \
     --summary pilot-summary-day-1.json \
     --summary pilot-summary-day-2.json \
     --summary pilot-summary-day-3.json \
     --summary pilot-summary-day-4.json \
     --summary pilot-summary-day-5.json \
     --summary pilot-summary-day-6.json \
     --summary pilot-summary-day-7.json \
     --installation-minutes 12 \
     --readiness-status READY \
     --state-meanings-explained-correctly \
     --useful-outcome OPERATIONAL_FINDING \
     --keep-installed YES \
     --outcome-code OPERATIONAL_FINDING \
     --confirm-consent \
     --confirm-privacy-review \
     --output pilot-01-evidence.json
   ```

   Add `--assisted-installation`, `--drops-investigated`, or `--withdrawn` only
   when applicable. Do not encode interview prose in the bundle.
7. After receiving reviewed bundles, generate the deterministic aggregate report:

   ```bash
   python scripts/build_pilot_report.py \
     --input pilot-01-evidence.json \
     --input pilot-02-evidence.json \
     --input pilot-03-evidence.json \
     --json-output pilot-report.json \
     --markdown-output pilot-report.md
   ```

   The command exits nonzero and reports `PILOT_INCOMPLETE` until every success
   criterion passes. See `PILOT_EVIDENCE.md` for the schema and claim boundary.

## Success criteria

The first pilot is successful only when:

- At least three independent operators attempt installation.
- At least two complete seven days.
- Median unaided installation time is at most 15 minutes.
- Every completed participant can correctly explain that `QUESTIONABLE` is not
  proof of spoofing and `INSUFFICIENT_DATA` is not nominal.
- No completed run has hidden message drops; visible drops are investigated.
- At least one participant reports either a useful operational finding or a
  concrete usability change backed by their run evidence.
- No shared artifact fails privacy review.
- Every completed run used one frozen policy version and passed the readiness
  check before its field period.

A pilot with no detected evidence can still be useful, but it cannot support a
claim that the detector caught a real anomaly. Publish participant counts,
completion rate, rounded installation time, aggregate operational measurements,
themes, changes made, limitations, and withdrawals. Never publish a participant’s
location or aircraft history.

## Claim unlocked by success

After the criteria pass, the defensible claim is:

> Independent ADS-B feeder operators installed and evaluated the local integrity
> sidecar; the pilot measured deployability, reliability, comprehension, and
> operational usefulness.

It still does not justify “detects spoofing,” “verified aircraft trust,” or a
field false-positive-rate claim.
