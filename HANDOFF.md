# Project Handoff and Expansion Roadmap

Last updated: 2026-07-20

Repository: `johananabraham/ADS-B-Flight-Intelligence-Platform`

Current branch: `codex/replay-control-ui`

Branch point before Phase 0 implementation: `fc21cf1`

## 0. Start Here — Explanation for a Junior Developer

### What is this project?

Airplanes broadcast short radio messages called **ADS-B messages**. Those messages
usually include information such as the airplane's identity, position, altitude,
speed, and direction.

This project receives or generates those messages, turns them into aircraft tracks,
stores them, displays them on a map, and looks for evidence that a track may be
incorrect or untrustworthy.

In very simple terms, the finished product should answer four questions:

1. **What aircraft can the system see?**
2. **Where are they going?**
3. **Does the reported movement make sense, and do other sources agree?**
4. **Why did the system trust or distrust a track?**

It also includes a safety research assistant that can search NTSB accident reports
and FAA regulations. That assistant is useful after an operator sees an event and
wants historical or regulatory context. It is not the source of the live aircraft
data and it is not the main detection system.

### How does it work today?

```text
Real mode                         Hardware-free demo mode

Aircraft radio signal             Python aircraft simulator
        |                                   |
RTL-SDR + dump1090                fake-but-valid SBS messages
        |                                   |
        +---------------+-------------------+
                        |
                ingestion service
                        |
                 PostgreSQL database
                        |
                  FastAPI backend
                        |
            REST API + live WebSocket
                        |
             React aircraft map and UI
```

The demo does not secretly insert aircraft directly into the frontend. It generates
the same kind of text messages the real receiver would provide, then sends them
through the normal ingestion, database, API, and WebSocket path. This makes it useful
for development and demonstrations when the RTL-SDR dongle is not connected.

### What does “integrity” mean here?

Integrity means deciding whether the aircraft data appears consistent and
trustworthy. ADS-B messages are not authenticated. Receiving a valid-looking
message does not prove that every field is true.

The planned integrity engine will check several kinds of evidence:

```text
Does the movement obey reasonable physics?       kinematic rules
Does the pattern resemble injected test attacks? ML classifier
Does another licensed data source agree?         cross-source corroboration
Is the local receiver station healthy?           ESP32/receiver telemetry
Is the information fresh and complete?           source quality checks
```

The output should never be a mysterious red or green number. The UI should explain
which checks passed, failed, or lacked enough information.

### Important beginner vocabulary

- **Decoder:** converts raw Mode S/ADS-B messages into useful fields.
- **Observation:** one report from one source at one time.
- **Track:** the system's changing history/estimate for one aircraft.
- **Anomaly:** something unusual; it is not automatically an attack.
- **Corroboration:** checking whether an independent source agrees.
- **False positive:** normal behavior incorrectly flagged as suspicious.
- **Replay:** saved messages played again using their timestamps.
- **Simulation:** newly generated fictional aircraft data.
- **RAG:** retrieves relevant documents before an LLM writes an answer.
- **Grounded answer:** an answer supported by cited source documents.
- **Deployment:** running the product on a server so other people can use it.

### User's goal and constraints

- Learn by building a real system over several weeks, not by generating shallow
  features in a few prompts.
- Produce a polished, deployable portfolio project especially relevant to Anduril
  and similar aerospace/defense companies.
- Use the hardware already owned: one RTL-SDR and one ESP32; avoid unnecessary
  purchases.
- Prefer direct, understandable implementations and be able to explain every major
  architecture decision in an interview.
- Commit and push frequently on `codex/*` branches.
- Run tests, builds, Clean Code review, and available security scans at checkpoints.
- Never claim a metric or capability that was not actually tested and recorded.
- Eventually deploy a safe public demonstration while keeping development, demo,
  and real-receiver modes clearly separated.

## 1. Product Direction

Build a deployable ADS-B integrity and aviation intelligence platform that accepts
live RF, remote sensor, recorded, simulated, and licensed internet data; normalizes
those sources into one observation model; detects and explains questionable tracks;
and connects events to grounded NTSB and FAA safety research.

The strongest version of this project is not simply a flight map or a RAG chatbot.
It is an end-to-end sensor-to-decision system with measurable correctness,
degraded-mode behavior, source provenance, operator UX, and repeatable deployment.

### Anduril-focused north star

Position the product as a small, aviation-specific command-and-control platform:

```text
Distributed sensors and external feeds
                |
      secure edge data transport
                |
   normalized observations + provenance
                |
 track fusion, confidence, and anomalies
                |
      operator common operating picture
                |
 grounded safety/regulatory investigation
```

This direction matches the public engineering themes Anduril repeatedly describes:
integrating disparate distributed sensors into a common data layer, processing at
the edge, maintaining an operator interface, and turning sensor data into faster
decisions. The project must remain civilian aviation/safety software; do not add
weapon-targeting language or pretend that ADS-B alone is a complete surveillance
system.

The three headline demonstrations should eventually be:

1. **Edge loss:** disconnect a remote sensor and show bounded data loss, immediate
   health degradation, store-and-forward recovery, and measured recovery time.
2. **Conflicting sensors:** inject delayed/duplicate/conflicting observations and
   show source provenance, fusion confidence, and quantitative tracking results.
3. **Investigation:** select a track or recorded event and produce a cited NTSB/FAA
   investigation whose retrieval and citation quality is measured by the eval set.

If those three demonstrations are polished and reproducible, they are more valuable
than ten shallow AI features.

## 2. Current Verified State

### Live tracking platform

- FastAPI backend with aircraft, anomaly, safety, health, and WebSocket routes.
- PostgreSQL/PostGIS persistence for aircraft, positions, anomalies, incidents,
  and regulations.
- Python SBS/BaseStation ingestion service.
- React/TypeScript/Leaflet operator map with aircraft list, detail view, filters,
  overlays, statistics, alerts, geofences, export, and safety research panel.
- Python anomaly service for rapid descent, speed, emergency squawks, ghost
  flights, and restricted-airspace-related events.
- Docker Compose topology for database, backend, ingestion, anomaly detection,
  and frontend.

### Hardware-free demonstration

- Deterministic Python source generates six fictional aircraft near Columbus,
  Ohio in SBS/BaseStation format.
- The simulator uses the real ingestion, database, API, WebSocket, and frontend
  path; there is no demo-only database shortcut.
- Positions, altitude, speed, heading, vertical rate, callsign, and squawk update
  each second.
- Scenario resets every five minutes to keep traffic in the demonstration area.
- UI displays an explicit `REPLAY DATA` provenance badge.
- Replay container runs as a non-root user and has a TCP health check.
- Replay movement and SBS field placement have three passing unit tests.
- Browser verification confirmed six aircraft and a live WebSocket connection.

Start it with:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build --renew-anon-volumes -d
```

Open `http://localhost:5173`. On the current development machine, use
`http://127.0.0.1:5173` because a separate host Node process also listens on the
IPv6 localhost address.

### C++ Mode S decoder subsystem

- Core Mode S decoding library and HTTP service.
- Three service instances behind nginx.
- Prometheus metrics and a provisioned Grafana dashboard.
- Load generator and automated fault-tolerance test script.
- dump1090 parity validation evidence and decoder validation documentation.
- Previous checkpoint reported 51 passing decoder tests; rerun before publishing
  that number in a README or résumé.

### Safety research / RAG scaffold

Implemented:

- SQLAlchemy `Incident` and `Regulation` models.
- Persistent ChromaDB collections for incident narratives and FAA regulations.
- Four agent tools: narrative search, structured incident query, regulation
  search, and incident detail/context retrieval.
- Direct OpenAI-compatible function-calling loop.
- Safety query API and React research panel.
- Structured and semantic retrieval paths.

Not yet production-ready:

- No complete NTSB CAROL/bulk ingestion pipeline is present in this branch.
- No complete eCFR ingestion pipeline is present.
- Vector store currently uses ChromaDB's local MiniLM default, not the originally
  proposed OpenAI embedding model.
- No checked-in 30-case evaluation dataset or evaluation runner.
- No Langfuse tracing integration.
- No source-version manifest proving which NTSB/eCFR snapshot produced an answer.
- No automated citation-grounding or answer-faithfulness checks.
- The synchronous OpenAI client and synchronous SQL session are called from async
  endpoints and should be isolated or converted before load testing.
- The UI does not expose citations as first-class clickable source objects.

### Integrity roadmap Phase 0 checkpoint

Implemented on `codex/track-observation-contract`:

- Baseline ADS-B integrity threat model and explicit non-goals.
- ADR separating immutable source observations from derived system tracks.
- Versioned Pydantic `TrackObservation` 1.0 contract.
- Source-specific provenance for live RF, simulation, recorded replay, and external
  feeds.
- Timing-quality classification for stale, clock-skewed, and out-of-order reports.
- SBS-state adapter from the current ingestion field names to the shared contract.
- Unit tests for identity normalization, partial reports, invalid positions,
  timezone requirements, provenance requirements, timing evidence, and SBS mapping.

Implemented on `codex/observation-persistence`:

- Append-only `track_observations` PostgreSQL model with source/time indexes.
- Alembic migration `20260719_01` and application-metadata integration.
- Stable UUIDv5 identity derived from source ID and the SHA-256 raw-message ID.
- Idempotent PostgreSQL `ON CONFLICT DO NOTHING` persistence.
- SBS generated-time parsing as timezone-aware UTC evidence.
- Ingestion writes each raw observation before updating the existing mutable track.
- Compose provenance defaults distinguish live RF from the hardware-free demo.
- 19 unit tests pass, including timestamp extraction and duplicate handling.
- Real Postgres duplicate check: first insert accepted, retry ignored, one row stored.
- Isolated replay smoke test persisted 500 unique observations across six aircraft;
  the labeled smoke-test rows were deleted afterward.

Implemented on `codex/ci-demo-verifier`:

- Root GitHub Actions workflow for Python, frontend, C++ decoder, security audits,
  migration SQL, and a complete Docker demo job.
- Dependency-free `scripts/verify_demo.py` for local and CI evidence collection.
- ESLint configuration so the existing frontend lint command actually executes.
- Removed ten pre-existing unused Python imports required to turn on repository lint.
- Idempotent observation migration supports the current development `create_all`
  startup order while CI validates the Alembic revision.
- 21 Python tests pass, Python lint passes, frontend lint passes, and the production
  frontend build passes.
- The C++ decoder builds with warnings-as-errors and all 51 CTest cases pass.
- Fresh Compose verification passed with six API aircraft, 169 recent observations,
  169 unique IDs, and all six simulated aircraft represented.
- In-app browser verification rendered `REPLAY DATA`, six aircraft, live position
  updates, and no browser console errors.
- Draft PR #1 contains both Phase 0 commits; `actionlint` 1.7.7 validates the
  workflow, and manual workflow dispatch is available after registration on main.

Implemented on `codex/dependency-security-upgrades`:

- Upgraded vulnerable backend packages including FastAPI, Pydantic,
  python-dotenv, scikit-learn, pytest, and their compatible dependency graph.
- Migrated Pydantic settings/ORM schemas and SQLAlchemy declarative imports away
  from APIs deprecated by the upgraded versions.
- Upgraded the frontend toolchain to Node 20.19, Vite 7.3.6, ESLint 9.39.5,
  TypeScript 5.9.3, and TypeScript ESLint 8.64.0.
- Migrated ESLint to flat configuration and made Vite's path aliases valid in an
  ES module environment.
- Frontend container now uses reproducible `npm ci`; `.dockerignore` prevents host
  `node_modules` from replacing Linux container binaries.
- Documented and CI demo startup renew anonymous dependency volumes so a rebuilt
  image cannot silently run packages retained from an older container.
- Security result: Python changed from 11 known dependency vulnerabilities to zero;
  npm changed from eight findings (seven high, one moderate) to zero.
- Regression evidence: 21 backend tests and Python lint pass; frontend lint and
  production build pass under Node 20.19.
- Full rebuilt Compose demo passed with the running Node 20.19.6/Vite 7.3.6
  frontend, six API aircraft, and 1,545 recent uniquely identified observations
  across all six simulated aircraft.

Implemented on `codex/recorded-replay-format`:

- Versioned recording format 1.0 with stable recording identity, explicit source,
  license/attribution, original timestamps, receiver context, and ordered SBS events.
- SHA-256 integrity validation rejects modified event arrays before playback.
- Timestamp validation requires the event offset, ISO timestamp, and timestamp
  inside each SBS message to agree.
- Deterministic per-client cursor supports restart, seek, and 0.5x/1x/2x/10x speed
  scheduling without changing event order.
- Checked-in fictional CC0 fixture contains six events for two aircraft and is
  explicitly labeled as generated rather than captured RF.
- Dedicated `docker-compose.recorded.yml` switches ingestion provenance to
  `RECORDED_REPLAY` and supplies the stable recording ID.
- Automated recorded-mode verifier checks the API/frontend path and requires six
  persisted events, six unique observation IDs, two aircraft, and the exact
  original timestamp range.
- Live smoke test passed those checks and confirmed repeated loops remain
  idempotent. TCP health-check disconnects are handled without unhandled errors.
- CI now runs recorded replay verification after the six-aircraft simulation test.
- Checkpoint gate: 29 Python tests pass, Ruff and actionlint pass, Python/npm audits
  report zero known vulnerabilities, and the secret-pattern scan is clean.
- Normal simulation mode was restored after testing and its verifier passed with
  six aircraft and 25/25 unique recent observations.

Implemented on `codex/replay-control-ui`:

- One authoritative, monotonic replay controller now owns playback position,
  event index, pause/resume state, restart, seek, loop behavior, and
  0.5x/1x/2x/10x speed changes.
- The replay container exposes an internal FastAPI control service on port 8081;
  its HTTP health check does not consume replay messages.
- The public backend proxies validated status and command requests at
  `/api/v1/replay/status` and `/api/v1/replay/commands`. The replay service is not
  published directly to the host or browser.
- Recorded mode adds an accessible operator timeline with explicit playing,
  paused, and completed states; pause/resume, restart, seek, and speed controls;
  progress and event counts; busy/error feedback; and 44-pixel control targets.
- The timeline appears only under the explicit `RECORDED REPLAY` build mode.
- Browser verification confirmed clean rendering, pause/resume, restart, speed
  selection, accessible names/state, and no console warnings or errors.
- The automated verifier proved restart, 2x speed, a frozen paused clock, seek to
  one second while paused, and resume. It also preserved exactly six unique
  observations for two aircraft and the original `2026-07-19 12:00:00` through
  `12:00:02` timestamp range.
- Checkpoint gate: 35 Python tests, Ruff, frontend ESLint, TypeScript/Vite build,
  actionlint, `git diff --check`, and the secret-pattern scan pass. Python and npm
  dependency audits report zero known vulnerabilities.

Not implemented in these checkpoints:

- Replacement of the existing mutable aircraft-state ingestion path.
- Kinematic anomaly rules, ML, external corroboration, or trust scoring.

## 3. Known Risks and Technical Debt

- The dependency upgrades are verified locally but still require a GitHub-hosted
  CI run after their branch is pushed and connected to a pull request.
- Docker Scout could not run because Docker Desktop is not authenticated.
- Root Compose contains development credentials and exposes PostgreSQL publicly on
  the host. Move secrets to environment/secret storage and bind development ports
  to loopback before any public deployment.
- Root Compose uses development bind mounts and Vite rather than production static
  hosting.
- Two concurrent ingestion writers updating the same aircraft can deadlock because
  each holds a multi-aircraft transaction until the batch commit. The supported
  topology currently has one ingestion writer; add deterministic lock ordering or
  smaller transactions before active/active ingestion.
- The new root CI workflow still needs its first successful GitHub-hosted run after
  this branch is pushed. Authentication, authorization, and rate limiting remain
  unimplemented.
- The local host still has Node 18.12.1, which is too old for the upgraded frontend;
  use the Node 20.19 container or install Node 20.19+ for host-side frontend work.
- Recorded replay startup settings still come from environment variables. The
  control API is intentionally internal and unauthenticated; add authorization and
  audit logging before exposing operator controls in a public deployment.
- Data-source identity is a frontend build-time label. It should eventually come
  from a signed backend source-status API.
- Simulator aircraft are fictional. Do not describe demo traffic as captured or
  live traffic.
- The existing `graphify-out/` directory contains cache fragments but no usable
  `graph.json`; architecture analysis currently falls back to source inspection.
- Untracked `AGENTS.md`, `DECODER_PLAN.md`, and `graphify-out/` predate this
  checkpoint and have intentionally not been committed.

## 4. ESP32: Useful and Honest Scope

An ordinary ESP32 cannot directly replace an RTL-SDR for 1090 MHz ADS-B. It lacks
the required 1090 MHz RF front end and is not a practical drop-in high-rate Mode S
receiver. Do not claim otherwise.

### Recommended architecture

```text
1090 MHz antenna + SDR/dedicated receiver
                  |
          Raspberry Pi/readsb
                  |
          normalized track feed
                  |
        Wi-Fi/Ethernet/VPN/MQTT
                  |
          central platform

ESP32 at sensor site
  -> node heartbeat
  -> GPS/site identity
  -> temperature, voltage, enclosure status
  -> Wi-Fi quality and uptime
  -> MQTT over TLS health events
  -> local status LEDs/display and reset control
```

This makes the ESP32 a real edge-node controller. The RF decoder remains on a Pi,
mini PC, or dedicated ADS-B module. If a dedicated receiver exposes decoded data
over UART, an ESP32 could forward those decoded messages, but the receiver module—not
the ESP32—does the RF work.

### ESP32 milestone (two weeks)

Week A:

- Create an ESP-IDF firmware project.
- Define a versioned `SensorHeartbeat` schema: node ID, firmware version, uptime,
  RSSI, temperature, supply voltage, GPS position, message rate, queue depth, and
  last receiver timestamp.
- Publish heartbeat and health data over MQTT with TLS certificate validation.
- Add reconnect backoff, watchdog, offline queue limits, and last-will message.
- Add a local LED state machine: booting, connected, degraded, offline.

Week B:

- Add Mosquitto to Compose and a backend MQTT consumer.
- Add `sensor_nodes` and `sensor_health_events` tables.
- Add node enrollment credentials and per-node topic authorization.
- Add a map layer and operator panel showing node location, health, age, message
  rate, and online/degraded/offline state.
- Demonstrate failure by disconnecting ESP32 Wi-Fi or power and measure detection
  and recovery time.
- Record evidence: dashboard screenshot, logs, test procedure, and recovery metric.

Do not start by buying unusual RF modules. First prove the edge telemetry path with
the ESP32 already owned.

## 5. Primary Detailed Pathway — ADS-B Integrity Product (14–16 Weeks)

This is the main build order. Do not work on every subsystem at once. Finish each
phase with evidence, update this handoff, commit it, and only then move forward.

### Phase 0 — Threat model and shared data contract (Week 1)

Purpose: define what the system is trying to detect before writing detection code.

Build:

- A threat model covering abrupt and gradual position manipulation, altitude and
  velocity manipulation, ghost tracks, stale-message replay, ICAO identity conflict,
  delayed/missing messages, receiver outage, and external-source disagreement.
- A versioned `TrackObservation` schema containing source ID, receiver ID, ICAO,
  observation time, receive time, position, altitude, velocity, heading, vertical
  rate, optional signal data, quality flags, and provenance.
- Separate database concepts for raw observations, system tracks, anomaly evidence,
  and operator decisions.
- Architecture decision records for simulation versus replay and corroboration
  versus formal sensor fusion.

Verify:

- Schema validation tests cover missing, stale, malformed, and out-of-order data.
- Every existing source can be mapped to the contract without losing provenance.

Junior-dev lesson: this prevents each later feature from inventing a different
meaning for “aircraft data.”

### Phase 1 — Reproducible foundation and CI (Week 2)

Purpose: make the current product trustworthy to change.

Build:

- End-to-end demo verification proving replay TCP, ingestion, PostgreSQL, REST,
  WebSocket, and changing positions.
- Root GitHub Actions workflow for decoder tests, replay tests, backend/API tests,
  TypeScript build, linting, Compose validation, Docker builds, dependency scanning,
  and secret scanning.
- Alembic migrations and a migration smoke test.
- A claims/evidence table linking each README statement to its test artifact.
- Dedicated dependency-upgrade branch for the known npm audit findings.

Verify:

- A clean clone can start and verify the demo with documented commands.
- CI is green without relying on local untracked files or a pre-populated database.

### Phase 2 — Actual recorded replay and operator controls (Week 3)

Purpose: create repeatable scenarios for detection development.

Status: implemented through the replay format, generated fixture, internal control
service, backend proxy, operator timeline, and deterministic integration verifier.
Authentication and audit logging remain deployment hardening work.

Build:

- A versioned recording format containing messages, original timestamps, source,
  receiver, capture metadata, and license/provenance.
- A legally shareable sample recording. If no real recording can be redistributed,
  check in a clearly labeled generated fixture and document how users create their
  own local recording.
- Replay controls: pause, resume, restart, seek, and 0.5x/1x/2x/10x speed.
- Explicit UI states for `LIVE RF`, `SIMULATION`, `RECORDED REPLAY`, and external
  live data.

Verify:

- The same recording produces the same ordered observations on repeated runs.
- Timing and seek integration tests pass within documented tolerance.

### Phase 3 — Deterministic kinematic plausibility engine (Weeks 4–5)

Purpose: detect physically inconsistent movement without machine learning.

Build:

- Compute time delta, great-circle distance, implied ground speed, acceleration,
  turn rate, climb/descent rate, and disagreement with reported velocity.
- Start with conservative, documented thresholds; do not imply that one threshold
  represents every aircraft type.
- Return structured evidence: rule, measured value, threshold, source observations,
  confidence/quality, and explanation.
- Handle clock skew, duplicate messages, missing positions, stale data, and tiny time
  deltas without generating divide-by-zero or alert storms.

Verify:

- Unit/property tests for normal tracks, teleportation, abrupt altitude changes,
  impossible speed, delayed messages, duplicates, and gradual drift.
- Run against a real benign capture and report alerts per flight hour plus manually
  reviewed examples. This is a benign-data baseline, not proof that the capture had
  no malicious traffic.

### Phase 4 — Synthetic attack dataset and evaluation harness (Weeks 6–7)

Purpose: create a reproducible test laboratory without claiming real spoofing data.

Build:

- Transform complete track/capture sessions into labeled test cases for abrupt and
  gradual position, altitude, and velocity manipulation; ghost tracks; replay; and
  identity conflict.
- Split train/validation/test by original flight or capture session before generating
  variants. Never randomly split individual messages from the same flight.
- Record generator version, random seed, source recording hash, attack parameters,
  and expected detection window.
- Include realistic noise, missing messages, latency, and legitimate edge cases.

Verify:

- Dataset generation is deterministic from seed and manifest.
- No source flight/capture crosses evaluation splits.
- Metrics are itemized by attack type and obvious versus subtle variants.

### Phase 5 — Interpretable ML anomaly model (Weeks 8–9)

Purpose: test whether learned patterns improve over deterministic rules.

Build:

- Start with logistic regression, decision tree, and random forest baselines.
- Features may include motion residuals, message timing, consistency, source quality,
  and kinematic outputs, but document circular features that directly mirror the
  synthetic generator.
- Version model, feature schema, dataset manifest, code commit, and evaluation result.
- Add an abstain/unknown path when required features are missing.

Verify:

- Compare every model against “always normal” and Phase 3 rules-only baselines.
- Report precision, recall, F1, false alerts per flight hour, detection delay, and
  results per attack type—not only aggregate accuracy.
- Keep ML only if it adds measurable value on held-out capture sessions.

### Phase 6 — External cross-source corroboration (Week 10)

Purpose: determine whether a licensed external source agrees with the local feed.

Build:

- An adapter for one permitted external aviation data source, initially OpenSky if
  its current limits and terms fit the use case.
- Match observations using ICAO, time, position, altitude, and freshness tolerances.
- Produce `CORROBORATED`, `LOCAL_ONLY`, `EXTERNAL_ONLY`, `CONFLICTING`, `STALE`, and
  `UNAVAILABLE` states.
- Rate-limit handling, caching, backoff, circuit breaker, and source-health metrics.

Verify:

- Multi-hour comparison artifact records coverage, latency, and each state rate.
- Manually review a sample of conflicts.
- Demonstrate that external API failure produces `UNAVAILABLE`, not “suspicious.”

Use the phrase **cross-source corroboration** until the system actually performs
state estimation with observation association and uncertainty. Do not market a
simple API comparison as full sensor fusion.

### Phase 7 — ESP32 edge-station telemetry (Weeks 11–12)

Purpose: add honest embedded and distributed-system work using existing hardware.

Build:

- ESP-IDF firmware publishing node ID, firmware version, uptime, reconnect count,
  RSSI, and any measurements the actual board/sensors can provide.
- MQTT over TLS with certificate validation, per-node credentials, last-will event,
  bounded offline queue, exponential backoff, watchdog, and status LED states.
- Mosquitto, backend MQTT consumer, sensor node tables, and fleet-health UI.
- Correlate node health with decoder message rate/CRC metrics to distinguish quiet
  airspace, RF/receiver degradation, and network/node failure where evidence allows.

Verify:

- Physically disconnect Wi-Fi or ESP32 power and record detection time, data loss,
  reconnect time, and queued-message behavior.
- Attempt unauthorized topic access and verify denial.

The ESP32 does not receive 1090 MHz ADS-B. It monitors and communicates station
health. A Raspberry Pi/mini PC plus SDR or a dedicated receiver still performs RF
reception and decoding.

### Phase 8 — Explainable trust assessment and operator UX (Week 13)

Purpose: combine evidence without hiding it behind a magic score.

Build:

- Store component outputs separately: kinematic evidence, ML probability,
  corroboration state, source freshness, and station health.
- Add an overall state such as `TRUSTED`, `QUESTIONABLE`, `LOW_CONFIDENCE`, or
  `INSUFFICIENT_DATA`; calibrate any numeric score against evaluation data.
- UI shows color/state plus exact reasons, measured values, source age, and evidence
  timeline.
- Operator can acknowledge, annotate, filter, inspect, and export an event.

Verify:

- UI tests prove component evidence is visible.
- Scenario tests cover low trust, source unavailable, receiver degraded, and
  insufficient data without conflating them.
- Conduct a small usability review: can another developer explain why a track was
  flagged without reading backend logs?

### Phase 9 — Complete grounded safety research (Week 14, then ongoing)

Purpose: allow operators to investigate historical and regulatory context.

Build in this order:

1. Idempotent NTSB and eCFR ingestion with source manifests and validation reports.
2. A reviewed 30-case baseline evaluation set.
3. SQL exact-match, dense retrieval Recall@3/5, citation precision/recall,
   faithfulness, latency, and cost metrics.
4. Clickable citations and exact source spans/effective dates in the UI.
5. Only then test BM25+dense fusion, reranking, parent/child retrieval, temporal CFR
   lookup, citation verification, or a causal knowledge graph.

Verify:

- Re-ingestion is idempotent and all answer sources are versioned.
- Advanced retrieval is retained only if it beats the checked-in baseline.

The RAG agent explains and researches; it does not decide whether live ADS-B is
authentic and it does not replace deterministic safety-critical logic.

### Phase 10 — Deployment, security, and portfolio release (Weeks 15–16)

Purpose: make the project usable by someone other than its developer.

Build:

- Production images: frontend built to static files and served by nginx/Caddy;
  backend without reload or source bind mounts; non-root containers.
- Managed PostgreSQL or a backed-up persistent database; persistent vector data.
- HTTPS, restricted CORS, authentication/RBAC, rate limits, request limits, audit
  logs, secure headers, and secret storage.
- Public deployment defaults to simulation or a legally permitted delayed/external
  feed. Do not expose a home SDR, database, MQTT broker, or ESP32 directly to the
  public internet.
- CI builds versioned images, deploys a staging environment, runs migrations and
  smoke tests, promotes the release, then polls `/health` with rollback on failure.
- Prometheus/OpenTelemetry/Langfuse where applicable, Grafana dashboards, structured
  logs, correlation IDs, backups, restore rehearsal, and cost budget/alerts.

Suggested deployment shape:

```text
Public browser
      |
 HTTPS reverse proxy / static frontend
      |
  authenticated FastAPI service
      |
 managed PostgreSQL + persistent vector data

Home/remote receiver and ESP32
      |
 outbound-only TLS/VPN connection
      |
 private ingestion/MQTT endpoint
```

Verify:

- Deploy from a clean release tag.
- Run API/UI smoke tests against staging and production.
- Execute backup restore, service restart, bad-deploy rollback, rate-limit, and
  dependency/security scans.
- Document monthly cost, data licensing, privacy, and known limitations.

Portfolio release:

- 60–90 second demo covering injected test anomaly, source disagreement, and edge
  outage/recovery.
- Architecture diagram, threat model, evaluation report, failure-test report,
  architecture decision records, and résumé claims/evidence table.

This is the deployment target, not a claim that public production deployment exists
today.

## 6. Appendix — Earlier Broad Backlog (Superseded as a Schedule)

This section preserves useful ideas from the earlier roadmap, but it is not a second
schedule. Follow Section 5 as the authoritative order. Pull items from this appendix
only when they support the active Section 5 phase. A feature is complete only when a
test, metric, trace, or recorded failure demonstration proves the claim.

### Phase 1 — Reproducible demo and CI foundation (Week 1)

Deliverables:

- Add an end-to-end verification script that starts demo mode and proves database,
  REST, WebSocket, and changing-position behavior.
- Add backend/API tests and run existing decoder/replay tests in CI.
- Add Ruff, ESLint/TypeScript, dependency scanning, secret scanning, and Docker
  build checks.
- Add database migrations and a migration smoke test.
- Create a production Compose profile with health checks and no source bind mounts.

Proof:

- Green GitHub Actions run from a clean clone.
- One command starts the demo and one command verifies it.
- Publish test counts and exact scope, not a vague “100% success rate.”

Résumé signal: reliable delivery, test automation, honest engineering claims.

### Phase 2 — Real recording and replay control (Week 2)

Deliverables:

- Define a versioned recording format with source, timestamp, receiver, and license
  metadata.
- Record or import a legally redistributable SBS sample.
- Build timestamp-aware replay with pause, resume, 0.5x/1x/2x/10x speed, seek, and
  deterministic reset.
- Add scenario metadata and controls to the operator UI.
- Keep simulated and recorded sources visibly distinct.

Proof:

- The same recording produces the same ordered output across repeated runs.
- Integration test verifies timing tolerance and seek behavior.

Résumé signal: deterministic simulation, time-series systems, reproducibility.

### Phase 3 — Source adapter framework and internet live feed (Week 3)

Deliverables:

- Define one normalized `TrackObservation` contract.
- Implement adapters for SBS TCP, simulation, recorded file, and one licensed
  internet provider.
- Add source status, latency, licensing, stale-data, and provenance fields.
- Add backoff, rate-limit handling, circuit breaker, and cached degraded mode.
- Add source selector/status UI without allowing simulated data to appear live.

Proof:

- Contract tests run the same observation cases against every adapter.
- Kill or rate-limit the provider and demonstrate graceful degradation.

Résumé signal: external API integration, resilient adapters, data provenance.

### Phase 4 — ESP32 and distributed sensor-node control plane (Weeks 4–5)

Implement the ESP32 milestone in Section 4, then connect a real remote ADS-B decoder
running on a Pi/mini PC when hardware becomes available.

Additional deliverables:

- Mutual TLS or per-node certificates.
- Store-and-forward behavior with bounded queues.
- Clock-skew reporting and server-side timestamp policy.
- Remote configuration with signed version and rollback—not arbitrary remote shell.
- Fleet dashboard and node health alerts.

Proof:

- Power/network interruption test with measured detection, data loss, backlog, and
  recovery.
- Two logical sensor nodes can report concurrently without cross-tenant access.

Résumé signal: embedded firmware, edge computing, secure distributed systems,
hardware/software integration.

### Phase 5 — Multi-sensor tracking and fusion (Week 6)

Deliverables:

- Separate observations from fused tracks in the data model.
- Deduplicate the same ICAO observation from multiple sensors.
- Add source priority, freshness, confidence, and conflict handling.
- Implement a documented baseline tracker, then an alpha-beta or Kalman filter only
  if evaluation shows improvement.
- Visualize raw observations versus fused tracks and uncertainty.

Proof:

- Synthetic tests cover delayed, duplicated, missing, and contradictory sensors.
- Report position error, track continuity, false merges, and processing latency.

Résumé signal: sensor fusion, estimation/tracking, quantitative algorithm work.

### Phase 6 — Complete the aviation safety data pipeline (Weeks 7–8)

Deliverables:

- Idempotent NTSB bulk ingestion with checkpointing, retries, dead-letter records,
  source hashes, and ingestion manifests.
- eCFR ingestion for Parts 61, 91, 121, and 135 with effective dates and snapshots.
- Section-aware narrative chunking: factual information, analysis, probable cause,
  and findings.
- Preserve canonical URLs, NTSB IDs, CFR sections, effective dates, and exact source
  spans for citations.
- Add ingestion validation reports: counts, null rates, duplicate rates, encoding
  failures, date coverage, and vector/SQL consistency.

Proof:

- Re-running ingestion produces no duplicates.
- A manifest identifies every source file/API version and resulting row/chunk count.
- Manual golden-query review is recorded before agent tuning.

Résumé signal: real-world ETL, data quality, lineage, idempotency.

### Phase 7 — Retrieval evaluation before advanced RAG (Week 9)

Deliverables:

- Build at least 30 reviewed cases: 15 retrieval, 10 structured, 5 synthesis.
- Measure Recall@3/5, structured exact match, citation precision/recall, answer
  faithfulness, latency, and cost.
- Establish baselines for vector-only, lexical-only, and current hybrid retrieval.
- Add metadata normalization and query filters before adding complexity.
- Store every run as versioned JSON with corpus, embedding, prompt, and model IDs.

Proof:

- README table contains reproducible before/after metrics.
- CI runs cheap deterministic retrieval/SQL cases; full LLM judge runs manually or
  nightly.

Résumé signal: evaluation-driven AI engineering rather than prompt experimentation.

### Phase 8 — Advanced grounded retrieval (Week 10)

Only adopt features that beat the Week 9 baseline.

Candidates:

- Hybrid BM25 + dense retrieval with reciprocal-rank fusion.
- Cross-encoder reranking of the top candidates.
- Parent/child retrieval so a relevant section returns enough report context.
- Query decomposition for questions combining statistics, narratives, and CFR text.
- Citation verifier that rejects unsupported claims or asks the agent to revise.
- Temporal regulation retrieval using the rule version effective on the incident
  date.
- Aircraft make/model canonicalization and aviation synonym expansion.

Do not replace PostgreSQL with a vector store. Counts and aggregations remain SQL.
Do not replace the four focused tools with dozens of overlapping tools.

Proof:

- Statistical comparison against Phase 7 baselines.
- Failure-case catalog explains regressions as well as wins.

Résumé signal: grounded RAG, reranking, temporal retrieval, measurable trade-offs.

### Phase 9 — Causal knowledge graph / GraphRAG experiment (Week 11)

This should complement—not replace—hybrid RAG.

Model entities such as:

- Incident, aircraft type, flight phase, weather condition, causal factor, finding,
  pilot qualification, airport, and CFR section.
- Typed relationships with provenance: `OCCURRED_DURING`, `INVOLVED_CONDITION`,
  `FOUND_CAUSAL_FACTOR`, `POTENTIALLY_RELEVANT_RULE`.

Use deterministic extraction from structured NTSB fields first. LLM-extracted
relationships must retain source spans and confidence and must never be treated as
official NTSB findings without verification.

Evaluate graph traversal on genuinely relational questions such as overlapping
causal factors across accident classes. Keep it only if it improves accuracy or
explainability enough to justify operational cost.

Proof:

- Separate graph test set and comparison with SQL+dense retrieval.
- Every graph edge used in an answer traces to an NTSB/CFR source location.

Résumé signal: knowledge modeling and GraphRAG with evidence, not buzzwords.

### Phase 10 — Production hardening and portfolio release (Week 12)

Deliverables:

- Authentication, RBAC, rate limits, request size limits, and audit logs.
- Secret manager/environment separation and least-privilege database users.
- OpenTelemetry/Langfuse traces, Prometheus service metrics, Grafana dashboards,
  structured logs, and correlation IDs.
- SLOs for API availability, track freshness, ingestion lag, and query latency.
- Backup/restore rehearsal and dependency/failure runbooks.
- Load, soak, fault-injection, and security tests with recorded results.
- Cloud deployment using infrastructure as code and a documented cost ceiling.
- Architecture decision records, threat model, data/license attribution, polished
  README, screenshots, short demo video, and recruiter-oriented case study.

Proof:

- Public demo health check and release tag.
- Restore from backup and failure tests are actually executed and documented.
- Final claims table maps every résumé statement to test evidence.

Résumé signal: ownership of a complete, operated product.

## 7. RAG Decision Framework

The RAG system is worth extending because aviation safety questions combine exact
structured filters, long narratives, and time-sensitive regulations. However, RAG
must not become the entire product.

Use this rule:

- SQL for counts, filters, trends, and exact metadata.
- Dense/lexical retrieval for narrative themes and regulation text.
- A knowledge graph for multi-hop, typed relationships only after evaluation.
- The LLM for planning and synthesis, never as the source of record.
- Source documents and versioned data remain authoritative.

Potential non-RAG additions with greater recruiter value than another prompt tweak:

- Multi-sensor fusion and uncertainty.
- ESP32/Pi edge-node fleet management.
- Offline/degraded operation and store-and-forward.
- Geospatial alerting and replayable incident timelines.
- Data provenance, licensing, and auditability.
- Fault injection with measured recovery.
- Operator workflows: acknowledge, investigate, annotate, export, and share a case.

## 8. Product UX Backlog

Prioritize operator clarity:

1. Unified source status panel: source type, age, latency, region, license, health.
2. Replay timeline with pause, seek, speed, and scenario description.
3. Sensor-node layer with online/degraded/offline state.
4. Investigation workspace that pins tracks, alerts, NTSB cases, and CFR sections.
5. Clickable citations with source excerpts and effective dates.
6. Saved searches and shareable investigation links.
7. Empty/error states that say whether the problem is no traffic, stale source,
   backend failure, or missing credentials.
8. Accessibility and responsive review, including keyboard and screen-reader flows.

Avoid adding decorative dashboards with no operational decision behind them.

## 9. Recruiter and Interview Positioning

The most compelling story is:

> Built and operated a multi-source aviation intelligence platform spanning a C++
> Mode S decoder, distributed edge telemetry, real-time track ingestion and fusion,
> geospatial anomaly detection, and an evaluated safety-research agent grounded in
> NTSB and FAA data.

Do not use that sentence until every listed component is implemented and proven.

Strong eventual bullet patterns:

- “Designed a source-agnostic tracking pipeline ingesting RF, replay, simulation,
  and remote sensor feeds through a versioned observation contract.”
- “Implemented and evaluated multi-sensor track fusion under delayed, duplicated,
  and conflicting observations, reporting continuity, error, and latency metrics.”
- “Built an idempotent NTSB/eCFR pipeline and hybrid SQL+dense retrieval agent with
  versioned Recall@K, exact-match, citation, latency, and cost evaluations.”
- “Demonstrated service and edge-node recovery through executed fault-injection,
  network-loss, and power-loss tests with documented recovery measurements.”

Numbers should come from checked-in evaluation artifacts, not estimates.

### What an Anduril recruiter should understand in 30 seconds

- This candidate can connect hardware, networks, backend services, algorithms, and
  an operator UI into one functioning system.
- They test failure modes instead of only testing happy paths.
- They understand the difference between observations and fused tracks, simulation
  and live data, and model output and authoritative evidence.
- They can quantify correctness, freshness, latency, recovery, and cost.
- They can explain engineering trade-offs without hiding limitations.

### What to deprioritize

- Additional LLM providers or a generic chatbot interface.
- More dashboards without an operator decision or SLO behind them.
- Kubernetes before one-node deployment, CI, backup/restore, and load testing work.
- Complex ML anomaly models before labeled data and a deterministic baseline.
- A custom PCB or direct ESP32 ADS-B receiver before the distributed-node transport
  and health-control plane are proven.
- GraphRAG before hybrid retrieval has a measurable baseline.

### Portfolio assets required for maximum impact

- A 90-second demo video showing the three headline scenarios.
- One architecture diagram that distinguishes observation, track, alert, and
  investigation data paths.
- A metrics table with decoder parity, retrieval Recall@K, fusion error/continuity,
  throughput, latency, and recovery time.
- A failure-test report with commands and timestamps.
- Two or three concise architecture decision records explaining major trade-offs.
- A public demo or deterministic local demo that works from a clean clone.
- A short case study: problem, constraints, design, what broke, measured results,
  and what would change at 100 sensors or 10,000 tracks.

## 10. Immediate Next Actions

1. Review the stacked Phase 0, CI, dependency-security, recorded-replay, and
   replay-control PRs.
2. Confirm the first GitHub-hosted CI run after the workflow reaches `main`.
3. Add deterministic kinematic checks over immutable observations, beginning with
   time delta, implied speed, acceleration, turn rate, and vertical-rate evidence.
4. Add replay scenarios that deterministically trigger and do not trigger each
   kinematic rule, then measure false positives against the clean fixture.
5. Begin ESP32 heartbeat firmware in a separate `firmware/esp32-sensor-node/`
   subtree after confirming the board model and available sensors.
6. Do not expand advanced RAG until NTSB/eCFR ingestion and the baseline evaluation
   harness exist.

## 11. Handoff Rules for the Next Engineer or Agent

- Preserve unrelated untracked files unless explicitly authorized.
- Work on `codex/*` feature branches and commit each verified checkpoint.
- Run tests, build, dependency/security scans, secret scan, and `git diff --check`
  before every feature commit.
- Never claim live data while simulation or replay is active.
- Never claim fault tolerance, decoder parity, dashboarding, or evaluation metrics
  unless the corresponding test was run and the result was recorded.
- Keep changes surgical; do not mix dependency upgrades with product features.
- Update this file after every milestone with commit, commands, evidence, known
  failures, and the next safe action.

## 12. Copy/Paste Context for a New Chat

Use this when starting a new Codex chat:

> Work in the ADS-B Flight Intelligence Platform repository. Read `CLAUDE.md` and
> `HANDOFF.md` completely before changing files. The product goal is a deployable,
> Anduril-relevant civilian ADS-B integrity platform: multi-source observations,
> deterministic kinematic checks, leakage-safe synthetic/ML evaluation,
> cross-source corroboration, ESP32 station-health telemetry, explainable operator
> trust states, and a grounded NTSB/eCFR research assistant. Section 5 of
> `HANDOFF.md` is the authoritative 14–16 week order. First inspect git status and
> preserve unrelated untracked `AGENTS.md`, `DECODER_PLAN.md`, and `graphify-out/`.
> Use `codex/*` branches, make frequent checkpoint commits, run proportional tests,
> builds, Clean Code review, and available security scans, and never claim unmeasured
> results. Current hardware-free demo uses
> `docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build --renew-anon-volumes -d`
> and is simulation, not live traffic. Phase 0 now includes the threat model,
> versioned `TrackObservation` contract, append-only persistence, migration, and an
> isolated 500-message replay smoke test. Root CI and the automated end-to-end
> verifier are implemented on `codex/ci-demo-verifier`. Dependency audits are at
> zero known findings on `codex/dependency-security-upgrades`. Recording format
> 1.0, deterministic playback, a CC0 generated fixture, and recorded-mode verifier
> are on `codex/recorded-replay-format`. The internal replay-control API, backend
> proxy, accessible operator timeline, and deterministic control verification are
> on `codex/replay-control-ui`; deterministic kinematic plausibility checks are
> next. Confirm the
> first hosted Actions run before claiming CI is green. Deployment is planned
> for Section 5 Phase 10; public production deployment is not complete today.
