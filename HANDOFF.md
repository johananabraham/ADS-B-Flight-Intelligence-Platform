# Project Handoff and Expansion Roadmap

Last updated: 2026-07-18

Repository: `johananabraham/ADS-B-Flight-Intelligence-Platform`

Current branch: `codex/replay-demo-mode`

Current commit: `ce86718` (`feat: add hardware-free ADS-B replay demo`)

## 1. Product Direction

Build a multi-source aviation intelligence platform that accepts live RF, remote
sensor, recorded, simulated, and internet data; normalizes those sources into one
track model; detects operational anomalies; and connects live tracks to grounded
NTSB and FAA safety research.

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
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
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

## 3. Known Risks and Technical Debt

- `npm audit` currently reports seven high-severity `minimatch` findings in the
  lint dependency chain and one moderate Vite/esbuild development-server finding.
  Available automatic fixes require breaking upgrades; handle them in a dedicated
  dependency-upgrade branch.
- Docker Scout could not run because Docker Desktop is not authenticated.
- Root Compose contains development credentials and exposes PostgreSQL publicly on
  the host. Move secrets to environment/secret storage and bind development ports
  to loopback before any public deployment.
- Root Compose uses development bind mounts and Vite rather than production static
  hosting.
- There is no root CI workflow, comprehensive backend test suite, migration gate,
  authentication, authorization, or rate limiting.
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

## 5. Twelve-Week Expansion Plan

Each phase ends with evidence. A feature is not complete because code exists; it is
complete when a test, metric, trace, or recorded failure demonstration proves the
claim.

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

## 6. RAG Decision Framework

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

## 7. Product UX Backlog

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

## 8. Recruiter and Interview Positioning

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

## 9. Immediate Next Actions

1. Merge or open a PR for `codex/replay-demo-mode` after review.
2. Add the automated end-to-end demo verifier and root CI workflow.
3. Create the dedicated dependency-upgrade/security branch.
4. Build actual recorded SBS replay and timeline controls.
5. Begin ESP32 heartbeat firmware in a separate `firmware/esp32-sensor-node/`
   subtree after confirming the board model and available sensors.
6. Do not expand advanced RAG until NTSB/eCFR ingestion and the baseline evaluation
   harness exist.

## 10. Handoff Rules for the Next Engineer or Agent

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
