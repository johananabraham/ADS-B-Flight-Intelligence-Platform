# ADS-B Flight Intelligence Platform

Real-time aircraft tracking and anomaly detection system using Software Defined Radio (SDR).

[![CI](https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/actions/workflows/ci.yml)

## Metrics Summary

| Metric | Value | Evidence |
|--------|-------|----------|
| Backend test coverage | 170 tests passing | CI `backend` job |
| Kinematic detection (abrupt) | 100% | Held-out 22 sessions |
| Kinematic detection (gradual) | 100% with window | Held-out 22 sessions |
| Generated clean FP rate | 0% | 88 control scenarios |
| ML baseline F1 | 0.9333 | Held-out evaluation |
| Dependency vulnerabilities | 0 | pip-audit + npm audit |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  RTL-SDR    │────▶│   dump1090   │────▶│  Ingestion  │────▶│  PostgreSQL  │
│  Antenna    │     │   Decoder    │     │   Service   │     │   + PostGIS  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                                                                     │
                    ┌──────────────┐     ┌─────────────┐            │
                    │   React UI   │◀────│  FastAPI    │◀───────────┘
                    │   + Leaflet  │     │   Backend   │
                    └──────────────┘     └─────────────┘
                                                │
                    ┌──────────────┐     ┌──────┴──────┐
                    │  AI Summary  │◀────│  Anomaly    │
                    │   (Claude)   │     │  Detection  │
                    └──────────────┘     └─────────────┘
```

## Features

- **Real-time ADS-B ingestion** via RTL-SDR + dump1090
- **Live flight tracking** on interactive map
- **Anomaly detection** for altitude, speed, squawk codes, restricted airspace
- **Explainable kinematic integrity checks** tied to immutable source observations
- **Short-window trajectory residuals** for subtle cumulative drift evidence
- **AI-generated intelligence summaries** via Claude API
- **Historical data analysis** with time-series queries

## Tech Stack

| Component | Technology |
|-----------|------------|
| Signal Receiver | RTL-SDR dongle + dump1090/readsb |
| Ingestion Pipeline | Python |
| Database | PostgreSQL + PostGIS |
| Backend API | FastAPI |
| Frontend | React + TypeScript + Leaflet.js |
| Anomaly Detection | Python (statistical + ML) |
| AI Summary | Anthropic Claude API |
| Deployment | Docker + AWS EC2 / Raspberry Pi |

## Quick Start

### Demo mode (no SDR hardware required)

Run the complete platform with a deterministic six-aircraft replay feed:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build --renew-anon-volumes -d
```

Open [http://localhost:5173](http://localhost:5173) (or `http://127.0.0.1:5173`
if another local Node process is using `localhost`). The map is clearly marked
`REPLAY DATA`; aircraft positions, altitude, and callsigns are simulated and must
not be interpreted as live traffic.

Verify the complete demo path after it starts:

```bash
python3 scripts/verify_demo.py
```

The verifier checks the API, rendered frontend shell, active aircraft, recent
simulation observations in PostgreSQL, unique observation IDs, and all six demo
aircraft. It exits nonzero when any part of that path is unavailable.

### Recorded replay mode

The repository also contains a versioned, fictional six-event SBS recording with
CC0 licensing and explicit provenance. Unlike demo simulation, this mode emits the
same saved messages with their original relative timing and timestamps:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml \
  -f docker-compose.recorded.yml up --build --renew-anon-volumes -d
docker compose exec -T backend alembic -c alembic.ini upgrade head
python3 scripts/verify_recorded_replay.py
```

The website is labeled `RECORDED REPLAY` and adds an operator timeline with
pause/resume, restart, seek, and 0.5x/1x/2x/10x playback controls. Commands travel
through the public FastAPI backend to an internal replay-control service, so the
browser never receives direct access to the replay container.

The verifier requires exactly six immutable observations, six unique IDs, two
aircraft, the expected original timestamp range, working replay controls, four
passing kinematic evaluations, and zero kinematic flags. See
`docs/recording-format-v1.md` for the format and integrity rules.

### Deterministic integrity scenario

Switch replay and ingestion to the explicitly generated impossible-motion fixture:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml \
  -f docker-compose.recorded.yml -f docker-compose.kinematic-attack.yml \
  up --build --force-recreate -d replay ingestion
python3 scripts/verify_kinematic_replay.py
```

Select `TEST001` and expand **Integrity Evidence**. The system shows each measured
value, policy threshold, source, and policy version. The verifier requires exactly
two immutable observations, one evaluation, one idempotent alert, and all five
expected failed rules. This demonstrates inconsistent motion; it does not prove
that a transmitter was spoofed.

### Reproducible kinematic evaluation

Run the leakage-safe generated scenario suite without Docker or radio hardware:

```bash
PYTHONPATH=backend:. python3 scripts/run_kinematic_evaluation.py --check \
  --baseline evaluation/results/kinematic_rules_baseline_v1.json
```

The generator splits 90 original source sessions before creating any variants, then
scores only the 22-session held-out test split. Policy 1.0 detects 100% of the
generated abrupt position, altitude, velocity, and heading scenarios with zero
delay. It detects 0% of the subtle gradual-drift and replayed-timestamp scenarios;
those measured gaps define the next engineering work. Generated clean sessions
produce zero alerts, but that is **not** a real-world false-positive-rate claim.
See `docs/kinematic-evaluation-v1.md` for methodology and the checked-in result.

The additive short-window policy closes the measured gradual-drift gap on the same
held-out scenarios: pairwise detection is 0/22 and combined detection is 22/22,
with a 2-second median delay and 0/22 generated clean controls flagged. Reproduce
the reviewed comparison with:

```bash
PYTHONPATH=backend:. python3 scripts/run_windowed_kinematic_evaluation.py --check \
  --baseline evaluation/results/windowed_trajectory_baseline_v1.json
```

These are synthetic regression results, not a real-world false-positive rate. The
window threshold remains `1.0-development` until benign captured RF calibration.
See `docs/windowed-trajectory-evaluation-v1.md` for method, integration, and limits.

Generator 1.1 adds missing-message and latency-jitter impairments, plausible ghost
identities, cross-source ICAO conflicts, high-rate reports, Date Line crossings, and
polar controls. It reports controls, impairments, and attacks separately while
leaving the reviewed Generator 1.0 suite unchanged:

```bash
PYTHONPATH=backend:. python3 scripts/run_extended_kinematic_evaluation.py --check \
  --baseline evaluation/results/kinematic_extended_baseline_v1_1.json
```

On the 22-session held-out split, the pairwise policy flags 0/88 generated controls,
0/44 impairment scenarios, and 88/176 attack scenarios. The missed families are
documented detector boundaries—not hidden failures: gradual drift needs window
evidence, while replay, ghost identity, and cross-source conflict need timing or
corroboration evidence. See `docs/kinematic-evaluation-v1.1.md` for the taxonomy and
complete itemized result.

### Offline interpretable ML comparison

The repository trains logistic regression, decision tree, and random forest
baselines on session-isolated Generator 1.1 prefixes and compares them with
always-normal and pair-plus-window rules:

```bash
PYTHONPATH=backend:. python3 scripts/run_ml_baselines.py --check \
  --baseline evaluation/results/ml_baselines_v1.json
```

On generated held-out sessions, rules-only F1 is 0.7692 and each learned baseline
reaches 0.9333, with no alerts across 88 controls or 44 impairments. All models miss
the plausible ghost family, demonstrating the need for independent corroboration.
These models are offline-only because generated performance is not field evidence.
See `docs/ml-evaluation-v1.md` for leakage controls, feature warnings, itemized
results, and promotion requirements.

### Cross-source corroboration

The selected-aircraft UI can compare a provenance-bearing local observation with a
bounded OpenSky state-vector query. The adapter normalizes external observations,
caches snapshots, honors provider retry headers, and exposes backoff, circuit-breaker,
credit, and source-health state. OpenSky access is disabled by default:

```bash
OPENSKY_ENABLED=true
# Optional OAuth2 credentials; anonymous access has lower limits.
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=
```

The result is one of `CORROBORATED`, `LOCAL_ONLY`, `EXTERNAL_ONLY`, `CONFLICTING`,
`STALE`, or `UNAVAILABLE`. `UNAVAILABLE` is source health, not an aircraft anomaly.
The UI fetches only when an operator expands the cross-source panel and refreshes no
faster than every 15 seconds.

The checked-in four-hour fixture verifies all six states without contacting a live
provider:

```bash
PYTHONPATH=backend:. python3 scripts/run_corroboration_evaluation.py --check \
  --baseline evaluation/results/corroboration_offline_v1.json
```

This is an offline synthetic regression—not measured OpenSky coverage or latency.
A permitted multi-hour live run and human review of real conflicts remain required.
See `docs/corroboration-evaluation-v1.md` for the exact evidence boundary and current
OpenSky operational constraints.

### Secure edge-station telemetry

An ESP32 can report receiver-station compute and connectivity health without an SDR
attached to the ESP32 itself. The TLS-only Mosquitto path, QoS 1 consumer, immutable
PostgreSQL events, fleet API, and station dashboard are available with:

```bash
scripts/provision_edge_mqtt.sh mqtt
docker compose -f docker-compose.yml -f docker-compose.edge.yml up --build -d
```

For a hardware-free transport demo, publish correctly labeled simulator heartbeats:

```bash
STATION_NODE_ID=roof-node-1 \
STATION_MQTT_PASSWORD_FILE=edge/mosquitto/secrets/roof-node-1.password \
MQTT_CA_CERT=edge/mosquitto/secrets/ca.crt \
python3 -m services.edge_telemetry.simulator
```

Open **STATIONS** in the top status bar. The panel distinguishes healthy, degraded,
stale, offline, and missing data, but it does not claim to measure ADS-B RF quality.
The ESP-IDF firmware and flashing instructions are in
`firmware/esp32-station/README.md`. Run the broker authorization proof with
`scripts/test_edge_mqtt_security.sh`; it requires Docker.

The checked-in station-health artifact is an offline 7/7 classification regression,
not physical outage evidence. ESP32 power/Wi-Fi loss and queue recovery still need
to be measured on hardware before making a resilience claim.

### Explainable trust assessment

Expand **EXPLAINABLE TRUST STATE** for a selected aircraft to inspect pairwise and
windowed motion checks, cross-source corroboration, station health, and the status of
the offline-only ML candidate. The API is:

```bash
curl http://localhost:8000/api/v1/trust/ABC123
```

It returns `TRUSTED`, `QUESTIONABLE`, `LOW_CONFIDENCE`, or `INSUFFICIENT_DATA` with
component policy versions, ages, reasons, and evidence identifiers. It intentionally
returns `numeric_score: null`: a combined score will not be published until it is
calibrated against reviewed field evidence.

Expanding the panel persists the evidence snapshot as an immutable trust assessment.
Operators can then acknowledge or annotate it, filter the event history, inspect the
record, and export a JSON evidence bundle. Assessment and action retries are
idempotent, so a retried request does not create duplicate evidence. Run the complete
Docker-backed proof with:

```bash
python3 scripts/verify_trust_workflow.py
```

Operator identity is derived from the authenticated session. This
workflow is suitable for local engineering validation, but public deployment remains
blocked on a hardened reverse proxy, distributed rate limiting, and a documented
audit-retention policy. See
`docs/trust-operator-workflow-v1.md` for the API and evidence boundaries.

### Real receiver calibration

The repository now includes an offline workflow for exporting a bounded `LIVE_RF`
observation set and measuring pair/window residuals, insufficient-data rates,
flagged evaluations, and grouped alert episodes per observed track hour:

```bash
PYTHONPATH=backend:. python3 scripts/export_live_rf_calibration.py --help
PYTHONPATH=backend:. python3 scripts/run_observation_calibration.py --help
```

Raw local captures are git-ignored because they may expose receiver and aircraft
locations. Reports remain `engineering_validation_only` until the manifest identifies
captured RF and records a completed routine-traffic review. Even then, the measured
value is an alert rate—not a false-positive rate without authoritative ground truth.
Follow `docs/rf-calibration-workflow-v1.md` for the complete collection, integrity,
review, and interpretation procedure.

Stop the demo with:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

### Live RF mode

### Prerequisites

- RTL-SDR USB dongle
- Python 3.11+
- Node.js 20.19+ (or use the frontend container)
- PostgreSQL 15+ with PostGIS
- Docker (optional)

### 1. Install dump1090

```bash
# macOS
brew install dump1090-mutability

# Ubuntu/Debian
sudo apt-get install dump1090-mutability

# Or build from source
git clone https://github.com/flightaware/dump1090.git
cd dump1090 && make
```

### 2. Start dump1090

```bash
dump1090 --net --interactive
# JSON available at http://localhost:8080/data/aircraft.json
```

### 3. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up database
createdb adsb_intel
psql adsb_intel -c "CREATE EXTENSION postgis;"

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload
```

### 4. Start the ingestion service

```bash
cd services/ingestion
python ingest.py
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 6. (Optional) Start anomaly detection

```bash
cd services/anomaly_detection
python detector.py
```

## Environment Variables

Create `.env` in root:

```env
DATABASE_URL=postgresql://localhost/adsb_intel
DUMP1090_URL=http://localhost:8080/data/aircraft.json
OBSERVATION_SOURCE_TYPE=LIVE_RF
OBSERVATION_SOURCE_ID=dump1090-sbs
OBSERVATION_RECEIVER_ID=local-receiver
ANTHROPIC_API_KEY=your_key_here
```

The demo Compose override labels its generated traffic as `SIMULATION`. For a
recorded file, use `RECORDED_REPLAY` and set `OBSERVATION_RECORDING_ID`; do not
label replayed traffic as live RF.

## Continuous Integration

GitHub Actions runs Python lint/tests, pairwise and short-window held-out synthetic
kinematic regression gates, migration SQL validation, frontend
lint/build, C++ decoder build/tests, dependency audits, and the complete Docker
demo, clean replay, and kinematic attack verifiers. Security audits are retained as
a non-blocking job so code-quality failures remain distinguishable from newly
published dependency advisories.

## Claims and Evidence

| Claim | Evidence | Verification |
|-------|----------|--------------|
| 170+ backend tests pass | `pytest backend/tests/` | CI `backend` job |
| C++ decoder matches dump1090 | `decoder/docs/validation-results.md` | CI `decoder` job |
| Zero dependency vulnerabilities | pip-audit + npm audit | CI `security` job |
| Kinematic rules detect 100% abrupt attacks | `evaluation/results/kinematic_rules_baseline_v1.json` | CI baseline gate |
| Window rule closes gradual-drift gap | `evaluation/results/windowed_trajectory_baseline_v1.json` | CI baseline gate |
| Cross-source corroboration 6 states verified | `evaluation/results/corroboration_offline_v1.json` | CI baseline gate |
| Station health 7/7 classifications | `evaluation/results/station_health_offline_v1.json` | CI baseline gate |
| ML baselines improve F1 to 0.9333 | `evaluation/results/ml_baselines_v1.json` | CI baseline gate |
| MQTT TLS + ACLs enforced | `scripts/test_edge_mqtt_security.sh` | CI `edge-transport-security` job |
| ESP32 firmware compiles | ESP-IDF 6.0.2 docker build | CI `esp32-firmware` job |
| Demo verifier passes | `scripts/verify_demo.py` | CI `demo` job |
| Trust workflow persists correctly | `scripts/verify_trust_workflow.py` | CI `demo` job |

**Not yet verified:**
- Real RF capture alert rate (pending private captures)
- Live OpenSky corroboration (pending multi-hour comparison)
- Physical ESP32 outage/recovery (pending hardware test)

## Project Structure

```
.
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Config, database
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   └── tests/
├── frontend/               # React frontend
│   └── src/
│       ├── components/     # React components
│       ├── hooks/          # Custom hooks
│       └── types/          # TypeScript types
├── services/
│   ├── ingestion/          # dump1090 data ingestion
│   ├── anomaly_detection/  # Anomaly detection engine
│   └── ai_summary/         # Claude AI summaries
├── scripts/                # Utility scripts
├── docker/                 # Docker configs
└── data/
    └── airports/           # Airport/airspace data
```

## Anomaly Detection

The system flags these anomaly types:

| Type | Description | Severity |
|------|-------------|----------|
| RAPID_DESCENT | Descent > 4000 ft/min outside approach | HIGH |
| SPEED_ANOMALY | Speed outside expected range for altitude | MEDIUM |
| SQUAWK_7500 | Hijack code | CRITICAL |
| SQUAWK_7600 | Radio failure | HIGH |
| SQUAWK_7700 | General emergency | CRITICAL |
| TRACK_LOSS | Track continuity was lost; no cause or intent is inferred | MEDIUM |
| RESTRICTED_AIRSPACE | Entered no-fly zone | HIGH |
| KINEMATIC_PLAUSIBILITY | Two observations exceed one or more versioned motion limits | MEDIUM/HIGH |

Operational events (emergency squawks, rapid motion, restricted-airspace entry,
and track loss) are presented separately from integrity evidence. Integrity
evidence reports inconsistent or inadequate telemetry; it does not prove
spoofing, malicious intent, or aircraft danger. `GHOST_FLIGHT` remains readable
only as a legacy stored value and is not emitted by live detection.

Kinematic evidence currently checks implied ground speed, reported acceleration,
turn rate, derived vertical rate, and disagreement between reported and implied
speed. Thresholds are conservative general limits, not aircraft-type performance
models, and the UI states that inconsistency is not proof of spoofing.

## License

MIT
