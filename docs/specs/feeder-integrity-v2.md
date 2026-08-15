# ADS-B Feeder Integrity Platform v2

Status: approved implementation specification

Target duration: 6–8 weeks

Primary audience: hobbyist and small-network ADS-B feeder operators
Career signal: applied AI/ML engineering plus backend/platform engineering

## 1. Product statement

Turn the existing ADS-B Flight Intelligence Platform into an open, self-hosted integrity monitor for untrusted real-time aviation telemetry. The product must help a feeder operator answer:

1. Is my receiver and data pipeline healthy?
2. Which tracks contain unusual or internally inconsistent telemetry?
3. What evidence caused the system to question a track?
4. Can I reproduce the result from a recorded stream?

The product is not a certified aviation safety system and must never claim that it has proven spoofing, jamming, malicious intent, or aircraft danger. It reports integrity evidence, operational events, receiver health, and data limitations.

The flagship repository is this repository. The older `Aviation-Safety-Research-Agent` repository is a deprecated precursor; do not merge it into this codebase again. The already-integrated NTSB/FAA research feature remains a secondary capability, not the product headline.

## 2. Success criteria

The release is complete only when all of the following are true:

- A feeder operator can connect an SBS/BaseStation stream on port 30003 and launch the sidecar with one Docker Compose command.
- The sidecar runs without PostgreSQL, ChromaDB, an LLM key, or a cloud account.
- A compact local UI and versioned API show receiver health, recent tracks, integrity state, and human-readable evidence.
- The same integrity core is used by the lightweight sidecar and the existing full platform; detection logic is not duplicated.
- A seven-day benign RTL-SDR capture is evaluated with a frozen policy and a chronological holdout.
- Synthetic abrupt and gradual attack cases achieve at least 95% targeted-family detection on the frozen policy.
- The benign holdout produces no more than 0.1 reviewed integrity-alert episodes per track-hour.
- One public, documented GPS-anomaly candidate is replayed without tuning the policy to that event. A miss or an insufficient-data result is acceptable if reported honestly.
- A static, anonymous portfolio demo is deployed to Vercel and clearly labeled as recorded research evidence, not live traffic.
- Authentication protects mutations in the full platform, while intended read-only views remain anonymous.
- Documentation, privacy checks, license checks, tests, and security scans pass before the repository is promoted publicly.

## 3. Scope and non-goals

### In scope

- SBS/BaseStation TCP input from dump1090-compatible feeders.
- Receiver/pipeline health, timing consistency, pairwise kinematics, windowed kinematics, and evidence-based track state.
- Deterministic recording and replay.
- A database-free sidecar with a bounded local event store.
- Sanitized benchmark artifacts derived from a private seven-day capture.
- Offline public anomaly-candidate replay.
- Static Vercel evidence demo and local full-stack demo.
- Hardening the existing authentication, observability, evaluation, and documentation needed to support the release.

### Out of scope for v2

- ML inference in the live decision path.
- UAT, FLARM, raw Mode-S demodulation, Beast binary, or direct RTL-SDR access in the sidecar.
- Multilateration or claims of verified aircraft position.
- Automatic reporting to airports, regulators, or law enforcement.
- Native mobile applications, paid hosting, Kubernetes, or a managed SaaS control plane.
- Safety-of-life, air-traffic-control, or certified operational use.
- Publishing raw RF captures, exact receiver location, aircraft identifiers, callsigns, squawks, or reversible pseudonyms.

## 4. Repository and branch sequence

Preserve the existing untracked `AGENTS.md`, `DECODER_PLAN.md`, and `graphify-out/` content. Do not stage, delete, rewrite, or include those items unless explicitly requested later.

Perform work in this order:

1. Finish and harden `codex/authentication-rbac`.
2. Merge authentication into `main` after its blocking tests pass.
3. Rebase the current `codex/safety-observability` branch onto the updated `main`, resolve conflicts conservatively, test, and merge it. This branch supersedes the older safety hardening/data-ingestion branches.
4. Do not merge historical kinematics, window, ML, corroboration, station-health, trust-workflow, or old safety branches again; their completed work is already represented on `main`.
5. Tag the consolidated baseline `v1.0-pre-feeder`.
6. Implement the remaining phases as small PRs using these branch names in order:
   - `codex/feeder-sidecar-v1`
   - `codex/live-rf-calibration-v1`
   - `codex/public-anomaly-replay-v1`
   - `codex/static-evidence-demo-v1`
   - `codex/portfolio-launch-v1`

Each PR must update the relevant tests and documentation. Never bundle raw capture data or downloaded public datasets in a source PR.

## 5. Phase 0 — consolidate and harden the full platform

### 5.1 Authentication and authorization

Keep anonymous access for explicitly read-only product surfaces. Require an authenticated operator or admin for annotations, configuration, acknowledgements, ingest controls, user management, or any other mutation.

Replace browser `localStorage` bearer-token storage with a server-set session cookie:

- Cookie name: `adsb_session`.
- Attributes: `HttpOnly`, `SameSite=Strict`, `Path=/`, and `Secure` outside local development.
- Session duration: eight hours with no silent multi-day extension.
- Login sets the cookie; logout invalidates it and clears the cookie.
- The frontend determines session state through a read-only `/api/v1/auth/me` request, not by decoding browser-stored credentials.
- State-changing requests must reject missing or unapproved `Origin` headers. The allowed-origin list comes from configuration and has no wildcard in production.
- Maintain role checks server-side. Hiding a button is not authorization.

Use one unambiguous environment variable for the signing key throughout settings, Docker Compose, tests, and deployment docs: `JWT_SECRET_KEY`. Production startup must fail when it is missing, is a known development value, or is shorter than 32 bytes. A generated development-only default may be used only when the environment explicitly identifies itself as local development.

Create an Alembic migration for users, roles, session/token invalidation data if used, and audit records. Do not rely on `Base.metadata.create_all` as the production migration strategy. Initial admin creation must be an explicit interactive or one-shot CLI command; do not publish default credentials.

Record audit events for login success/failure, logout, user/role changes, configuration mutations, and operator acknowledgements. Do not record passwords, raw tokens, cookie values, or full request bodies.

The current in-memory IP limiter may remain as a local abuse guard but must be documented as process-local and not presented as distributed or production-grade rate limiting.

### 5.2 Taxonomy correction

Separate two concepts throughout models, APIs, UI, filters, and documentation:

- `OPERATIONAL_EVENT`: emergency squawk, rapid descent, restricted-airspace entry, track loss, and similar events that may be operationally important but do not establish corrupt telemetry.
- `INTEGRITY_EVIDENCE`: timing inconsistency, impossible or implausible kinematics, cross-source conflict, duplicate/replay-like behavior, and receiver/data-quality evidence.

Rename the existing “ghost flight” disappearance behavior to `TRACK_LOSS`. Reserve “ghost” only for labeled offline synthetic scenarios. Existing stored event values must be migrated or compatibility-mapped so old data remains readable.

### 5.3 Observability consolidation

Merge the safety-observability work after authentication. Retain structured logs, health endpoints, ingest counters, error counters, and request/processing latency metrics. Tracing must be opt-in and disabled by default. Raw SBS lines, aircraft identifiers, prompts, document passages, session cookies, and authorization headers must never be included in traces or structured logs.

Phase 0 acceptance:

- Anonymous reads and protected mutations have endpoint-level tests.
- The full frontend has working login, logout, expired-session, forbidden-action, and role-aware states.
- Production refuses an insecure secret.
- A clean database upgrades through Alembic; an existing development database remains readable.
- The operational/integrity taxonomy appears consistently in persisted data and the UI.

## 6. Phase 1 — lightweight feeder sidecar

### 6.1 Deployment contract

Provide `docker-compose.feeder.yml` and publish multi-architecture images for `linux/amd64` and `linux/arm64` to GHCR. The documented launch command is:

```bash
docker compose -f docker-compose.feeder.yml up -d
```

Configuration:

| Variable | Default | Behavior |
| --- | --- | --- |
| `ADSB_INPUT_HOST` | `host.docker.internal` | Host exposing an SBS TCP stream |
| `ADSB_INPUT_PORT` | `30003` | SBS/BaseStation TCP port |
| `RECEIVER_ID` | required | Local stable receiver label; not uploaded anywhere |
| `SIDECAR_BIND_HOST` | `127.0.0.1` | API/UI bind address |
| `SIDECAR_PORT` | `8090` | API/UI port |
| `INTEGRITY_POLICY_PATH` | bundled policy | Optional mounted frozen policy file |
| `EVENT_RETENTION_HOURS` | `168` | Maximum event age in the local store |
| `EVENT_STORE_MAX_MB` | `128` | Hard upper bound for rotating JSONL data |

Do not add PostgreSQL, Redis, ChromaDB, an LLM, or external telemetry as sidecar dependencies. Network egress is unnecessary for normal operation.

### 6.2 Shared integrity core

Extract parser-independent and database-independent integrity logic into a shared Python package consumed by both the sidecar and full platform. It owns:

- Normalized observation types.
- Deterministic evidence and episode identifiers.
- Pairwise and windowed feature calculation.
- Timing rules and kinematic rules.
- Policy loading and validation.
- Evidence aggregation into track state.

Adapters own SBS parsing, database persistence, JSONL persistence, HTTP transport, and UI formatting. The shared core must not import FastAPI, SQLAlchemy, Postgres-specific types, or sidecar storage code.

Use the existing deterministic policy behavior as the starting point. Existing offline ML baselines remain evaluation artifacts and must not vote on the live state in this release.

### 6.3 State semantics

Sidecar track state is one of:

- `NOMINAL`: enough recent data exists and no active evidence crosses the frozen policy threshold.
- `QUESTIONABLE`: one or more active integrity evidence items cross the policy threshold.
- `INSUFFICIENT_DATA`: the system cannot evaluate reliably because observations, required fields, time span, or receiver health are inadequate.

Do not use `TRUSTED`; lack of an alert does not verify authenticity. Do not expose a numeric trust score until field calibration justifies one.

Integrity evidence kinds for v1:

- `PAIR_KINEMATIC`: abrupt speed, acceleration, vertical-rate, turn, or position inconsistency across adjacent observations.
- `WINDOW_KINEMATIC`: gradual drift or sustained inconsistency detectable only across a time window.
- `TIMING_DUPLICATE`: duplicate message or deterministic duplicate observation.
- `TIMING_NON_INCREASING`: source event time fails to advance.
- `TIMING_OUT_OF_ORDER`: observation arrives outside the permitted reordering window.
- `TIMING_EXCESSIVE_LATENCY`: source time and receive time differ beyond policy when both clocks are meaningful.
- `TIMING_GAP`: track observation gap exceeds policy; this is evidence of continuity loss, not spoofing.

Timing rules must be source-aware. Replay input uses replay-clock metadata and must not be judged against wall-clock latency.

Evidence expires according to the policy. A track returns from `QUESTIONABLE` to `NOMINAL` only after all active evidence has expired and the minimum-data requirement is still met. If data becomes inadequate, use `INSUFFICIENT_DATA`.

### 6.4 Versioned public interfaces

Expose these anonymous, read-only local interfaces:

- `GET /api/v1/integrity/health`
- `GET /api/v1/integrity/tracks`
- `GET /api/v1/integrity/tracks/{track_id}`
- `GET /api/v1/integrity/events?since=&state=&kind=&limit=`
- `GET /api/v1/integrity/stream` as a WebSocket
- `GET /metrics` in Prometheus text format

`track_id`, evidence IDs, and episode IDs must be deterministic for identical normalized replay input and policy version. Never expose raw receiver identifiers, callsigns, or coordinates through metrics labels.

Minimum `IntegritySnapshotV1` response shape:

```json
{
  "schema_version": "1.0",
  "track_id": "string",
  "observed_at": "RFC3339 UTC",
  "state": "NOMINAL|QUESTIONABLE|INSUFFICIENT_DATA",
  "observation_count": 0,
  "window_seconds": 0.0,
  "policy_version": "string",
  "active_evidence": [
    {
      "evidence_id": "string",
      "kind": "PAIR_KINEMATIC",
      "severity": "INFO|WARNING|CRITICAL",
      "first_observed_at": "RFC3339 UTC",
      "last_observed_at": "RFC3339 UTC",
      "summary": "human-readable sentence",
      "measured": {"metric_name": 0.0},
      "thresholds": {"metric_name": 0.0}
    }
  ],
  "limitations": ["string"]
}
```

Unknown JSON fields must be ignored by clients. Breaking changes require a new URL or schema major version. Additive fields may be introduced within v1.

The WebSocket sends a `hello` message containing schema and policy versions, followed by `snapshot`, `evidence_opened`, `evidence_updated`, `evidence_closed`, and `receiver_health` messages. A reconnecting client first fetches current REST state; the WebSocket is not an authoritative event-history transport.

Prometheus metrics must include connection state, reconnect count, parsed messages, parse failures by bounded reason, observations evaluated, open evidence count by kind, tracks by state, processing latency, queue depth, dropped-message count, and process memory. Labels must be bounded.

### 6.5 Local storage and resilience

Store only normalized integrity events and minimal track summaries in rotating JSONL segments. Write via append plus flush, validate records on startup, tolerate a truncated final line, and quarantine an invalid segment without preventing the live service from starting. Enforce both age and total-size bounds.

The SBS client must reconnect with capped exponential backoff and jitter. It must expose disconnected/degraded status without fabricating track state. Bound all queues and track caches. Evict inactive tracks deterministically. On overload, increment a dropped-message counter and surface degraded receiver health; never silently discard.

### 6.6 Compact sidecar UI

Serve a responsive read-only UI from the sidecar container. It contains:

- Receiver connection and processing-health banner.
- Counts for nominal, questionable, and insufficient-data tracks.
- Sortable recent-tracks table.
- Track drawer with active/closed evidence, measured values, thresholds, and limitations.
- Recent integrity-event timeline with kind/state filters.
- Policy version and recorded/live source indicator.

A geographic map is optional in the full platform and intentionally absent from the compact sidecar v1. The sidecar’s value is evidence and receiver health, not visual spectacle.

Phase 1 performance acceptance on a development laptop and an ARM64 Raspberry-Pi-class target when available:

- Documented setup completes in less than 15 minutes for a user who already has dump1090 producing SBS.
- Sustains 100 SBS messages/second for 30 minutes.
- p95 time from parsed observation to updated snapshot is under 100 ms.
- No unreported drops; the test fails if `dropped_messages_total` increases.
- Steady-state memory target is at most 256 MB with configured bounds.
- Killing and restarting the SBS source produces a visible degraded state and automatic recovery.
- Replaying identical input with the same policy produces identical IDs and evidence results.

## 7. Phase 2 — seven-day benign RF evaluation

### 7.1 Capture protocol

Use the existing RTL-SDR and dump1090 setup. Do not buy additional hardware. Capture seven consecutive or clearly documented calendar days from one receiver configuration. Record software versions, policy version, receiver configuration, antenna/configuration changes, outages, restarts, and checksums in a private manifest.

Raw SBS recordings and exact capture metadata remain outside Git in a gitignored directory. They must never be uploaded as CI artifacts. Keep enough private data to reproduce the report locally, but do not implement automatic destructive cleanup.

Freeze the policy before evaluating day 7:

- Days 1–4: development and calibration.
- Days 5–6: validation and one permitted policy freeze.
- Day 7: untouched holdout; no threshold or rule changes after results are viewed.

If a capture outage makes a day unusable, document it and extend capture until seven usable days exist. Never silently remove difficult periods.

### 7.2 Sanitized public feature export

Publish only derived features needed to reproduce aggregate evaluation:

- Random, nonreversible session and track labels created for the export.
- Seconds relative to session start, never wall-clock timestamps or dates.
- Position deltas in a local relative coordinate system, never latitude/longitude or receiver position.
- Relative altitude and derived pair/window metrics needed by the policy.
- Missingness indicators, receiver-health class, policy outcome, and reviewer disposition.
- Split name and export-schema version.

Remove ICAO addresses, callsigns, registrations, squawks, route/origin/destination, absolute coordinates, exact altitude when unnecessary, wall-clock time, receiver ID/location, network addresses, filenames containing dates, and private salts/mappings.

Add an automated privacy test that searches field names and serialized values for forbidden identifiers, coordinate ranges, timestamps/dates, private paths, and known capture identifiers. Manually inspect a sample before publication.

### 7.3 Evaluation protocol

Define an alert episode as contiguous `QUESTIONABLE` evidence for one public track label, merging evidence separated by less than the policy cooldown. Report:

- Usable duration and track-hours per split.
- Missing-data and receiver-degraded duration.
- Integrity episodes per track-hour by kind and severity.
- Percentage and absolute count of tracks with an episode.
- Reviewer dispositions: expected maneuver/data artifact, receiver/pipeline issue, unexplained, or insufficient context.
- Synthetic targeted-family recall for abrupt and gradual cases using the identical frozen policy.
- Known limitations and every excluded interval with reason.

Call the benign metric “reviewed routine-traffic integrity-alert rate,” not a false-positive rate, because the data lacks verified ground truth.

Promotion gate:

- At most 0.1 reviewed integrity-alert episodes per track-hour on day 7.
- At least 95% targeted-family detection on both abrupt and gradual synthetic suites.
- Every holdout episode manually reviewed.
- No result attributable to a known parser, timestamp, unit-conversion, or replay-clock defect.
- Report and fixture generation are reproducible from a manifest and command.

If the gate is missed, publish the measured result and remediation plan. Do not tune on day 7 or hide the gap.

## 8. Phase 3 — public GPS-anomaly candidate replay

Use the Zenodo dataset “2023 GPS Anomalies, NOTAMs, and Aircraft Traffic” as the primary candidate index. Pin the exact record/DOI version, filenames, cryptographic checksums, access date, and license/redistribution decision in a manifest. The expected candidate index archive is `GPS_Jumps_from_Routes-2023.csv.zip`; stream/process only required files and never commit the multi-gigabyte source dataset.

Prefer a surrounding trace from a source whose license permits the intended processing and publication, with ADSB.lol historical data as the first option. Record attribution and ODbL obligations where applicable. If a compliant surrounding trace cannot be obtained, publish the candidate-selection and blocked-replication result rather than substituting a synthetic event and calling it real.

Select the event before scoring it. A qualifying candidate must have:

- A valid aircraft identifier and timestamp in the public index.
- Temporal overlap with an active GPS-interference NOTAM in the dataset.
- At least ten minutes of observations around the indexed jump.
- At least six usable position reports on each side of the candidate point.
- Sufficient fields to run the frozen integrity core without manual reconstruction.

When multiple candidates qualify, choose the first after deterministic sorting by UTC timestamp and stable identifier. Save the candidate-selection query and a frozen manifest. Do not inspect detector scores to choose among candidates.

Replay the trace through the same normalized observation path and frozen policy used for synthetic and benign evaluation. Produce a machine-readable result and a short case study containing the timeline, evidence, thresholds, receiver/source limitations, and outcome. Permitted outcomes are:

- `DETECTED`: frozen policy opened relevant integrity evidence near the indexed anomaly.
- `MISSED`: data was sufficient, but the frozen policy did not open relevant evidence.
- `INSUFFICIENT_DATA`: source coverage or fields were inadequate for a valid evaluation.
- `BLOCKED_REPLICATION`: licensing or trace acquisition prevented the evaluation.

Describe it as a “public research GPS-anomaly candidate correlated with contemporaneous NOTAM data.” Do not call it confirmed spoofing or malicious activity.

## 9. Phase 4 — static Vercel evidence demo

Use Vercel Hobby only for a personal, noncommercial static portfolio demo. Do not attempt to host PostgreSQL, persistent WebSockets, the SBS sidecar, or the full FastAPI platform on Vercel.

Add frontend build mode `VITE_RUNTIME_MODE=STATIC_EVIDENCE`. In that mode the app loads a compact checked-in fixture containing:

- A short routine/nominal replay.
- One synthetic abrupt case.
- One synthetic gradual case.
- Aggregate seven-day benchmark results.
- The public anomaly-candidate result, including miss/insufficient/blocked outcomes.

Playback runs entirely in the browser with play, pause, speed, reset, and scenario selection. Every page displays `RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC`. The demo links to methodology, dataset manifests, model/data cards, source code, and local Docker instructions.

Static mode has no authentication UI, mutations, annotations, external API calls, receiver setup, or claims of live processing. It must build without secrets and work from a clean browser session. The authoritative operational demo remains the local Docker sidecar/full platform; record a short video showing the physical dongle, dump1090, sidecar health, and evidence flow.

## 10. Phase 5 — public portfolio launch

Before making the flagship public or promoting the release:

- Scan the complete reachable Git history for secrets, raw captures, receiver location, aircraft identifiers, private salts, database dumps, and restricted datasets.
- Run dependency, container, and static security scans with no unresolved critical findings.
- Verify every included dataset, fixture, screenshot, map tile, icon, and third-party asset has documented redistribution rights and attribution.
- Add responsible-use, security-reporting, privacy, data/model card, architecture, benchmark-methodology, and reproducibility documentation.
- Ensure sample environment files contain placeholders only.
- Ensure logs, fixtures, screenshots, and demo videos do not reveal exact receiver location or credentials.
- Create a tagged release with multi-architecture sidecar images and checksum/provenance information.

The portfolio narrative is:

> Built a sensor-to-decision integrity platform for unauthenticated, safety-critical telemetry: real RF ingestion, deterministic evidence, leakage-safe evaluation, privacy-preserving field calibration, reproducible incident replay, and deployable operator tooling.

Supported claims must state exact measured results and limitations. Avoid “detects spoofing,” “prevents attacks,” “production-ready airspace security,” or “verified aircraft trust.”

## 11. Required tests

### Shared core

- Unit and property tests for units, time ordering, wraparound headings, missing fields, stationary tracks, impossible jumps, gradual drift, duplicates, replay timestamps, and policy expiry.
- Golden replay tests proving identical input/policy produces identical snapshots, evidence, episodes, and IDs.
- Compatibility tests proving full-platform and sidecar adapters produce identical normalized observations and core outcomes.
- Policy schema/version validation and rejection of unknown breaking versions.

### SBS ingestion and resilience

- Valid and malformed SBS lines, partial TCP frames, multiple lines per frame, reconnects, source restarts, long gaps, out-of-order messages, and backpressure.
- Bounded cache/queue tests, deterministic eviction, dropped-message visibility, and 100-message/second soak test.
- JSONL rotation, retention, crash/truncated-line recovery, invalid-segment quarantine, and duplicate suppression.

### API, WebSocket, UI, and metrics

- Contract tests for all v1 REST schemas and query limits.
- WebSocket hello/event ordering, disconnect/reconnect, and REST resynchronization.
- Metrics existence, bounded labels, and absence of aircraft/receiver identifiers.
- Sidecar empty/loading/degraded/live/replay/error states, keyboard navigation, narrow-screen layout, and evidence explanations.

### Authentication and migration

- Cookie attributes, login/logout/expiry, invalidation, role matrix, forbidden mutations, anonymous reads, Origin rejection, production secret validation, and sanitized audit events.
- Alembic upgrade from an empty database and the last supported schema; downgrade only where the project policy requires it.
- Frontend tests proving expired or forbidden sessions fail closed.

### Evaluation and privacy

- Session/chronological split invariants and proof that no public track/session crosses splits.
- Frozen-policy checksum verification before holdout and public-candidate scoring.
- Synthetic family coverage, benign episode calculation, excluded-interval accounting, and deterministic report generation.
- Sanitizer tests for identifiers, coordinates, dates/timestamps, paths, salts, receiver metadata, and schema allow-list enforcement.
- Public-candidate deterministic selection, manifest checksum, license gate, and all four outcome states.

### Static demo and release

- Vercel/static build with no secrets or network calls.
- Fixture schema validation, browser replay determinism, permanent recorded-demo labeling, and broken-link checks.
- Existing backend, frontend, decoder, safety-agent, kinematic, ML-baseline, corroboration, station-health, and trust-workflow suites remain passing.
- CI runs Python lint/type/tests, TypeScript lint/type/tests/build, C++ decoder tests, migration tests, Docker smoke tests, sidecar load test, multi-architecture image build, static demo build, dependency scan, secret scan, and container scan.

## 12. Delivery schedule

Use this as sequencing guidance, not permission to skip gates:

- Week 1: finish authentication, taxonomy, migration, and observability consolidation; tag baseline.
- Weeks 2–3: extract shared core; implement sidecar ingest, local store, APIs, metrics, compact UI, multi-architecture images, and load/resilience tests.
- Week 4: begin seven-day capture while completing sanitizer, evaluation tooling, and documentation.
- Week 5: freeze policy after days 1–6, run untouched day-7 holdout, review episodes, and publish the benchmark report/fixture.
- Week 6: select and replay the public anomaly candidate; publish the case study regardless of outcome.
- Week 7: implement/deploy the static Vercel demo, record the hardware demo, and complete public documentation.
- Week 8 contingency: close performance, privacy, licensing, security, or reproducibility gaps; release only after all blocking gates pass.

## 13. Instructions for an implementation model

When handing this document to a smaller implementation model:

1. Give it one phase or one narrowly scoped PR at a time; do not ask it to implement the whole specification in one pass.
2. Require it to read repository `AGENTS.md`, this specification, current branch status, and the relevant existing tests before editing.
3. Require a short implementation plan and list of files it expects to touch before code changes.
4. Tell it to preserve unrelated dirty-worktree changes and never stage all files indiscriminately.
5. Require tests proportional to each change and the exact commands/results in its handoff.
6. Do not allow it to weaken thresholds, remove failing tests, invent benchmark results, fabricate a real incident outcome, or publish data merely to make a gate pass.
7. Stop and escalate when a license is ambiguous, a schema migration risks data loss, capture data may reveal location/identity, or observed repository structure conflicts with this specification.
8. Merge only after the phase-specific acceptance criteria pass. A documented negative research result is preferable to an unsupported success claim.

## 14. Fixed assumptions and references

Fixed decisions:

- Flagship: ADS-B Flight Intelligence Platform.
- Primary user: ADS-B feeder operator.
- Distribution: database-free Docker sidecar with compact UI and API.
- Live input v1: SBS/BaseStation TCP on port 30003.
- Supported image architectures: Linux AMD64 and ARM64.
- Field evidence: seven-day benign capture plus one public anomaly candidate.
- Public capture artifacts: sanitized derived features only.
- Hosted demo: static Vercel Hobby deployment; full stack remains local/self-hosted.
- Demo access: static demo anonymous; full-platform reads anonymous and mutations authenticated.
- Budget: free tier and existing RTL-SDR/optional ESP32 hardware only.
- Claim boundary: research/feeder integrity tooling, never certified or safety-of-life use.

Starting research references:

- EASA GNSS interference safety information: https://www.easa.europa.eu/en/domains/air-operations/global-navigation-satellite-system-outages-and-alterations
- OpenSky Network data and research: https://opensky-network.org/
- Public 2023 GPS anomalies/NOTAM/traffic dataset: https://zenodo.org/records/11420433
- ADSB.lol historical data and licensing: https://www.adsb.lol/docs/open-data/historical/
- Vercel Hobby plan: https://vercel.com/docs/plans/hobby

Re-verify licenses, service limits, and external-source availability at implementation time because those facts may change.
