# ADS-B Flight Intelligence Platform

Real-time aircraft tracking and anomaly detection system using Software Defined Radio (SDR).

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

GitHub Actions runs Python lint/tests, migration SQL validation, frontend
lint/build, C++ decoder build/tests, dependency audits, and the complete Docker
demo, clean replay, and kinematic attack verifiers. Security audits are retained as
a non-blocking job so code-quality failures remain distinguishable from newly
published dependency advisories.

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
| GHOST_FLIGHT | Aircraft disappeared mid-flight | MEDIUM |
| RESTRICTED_AIRSPACE | Entered no-fly zone | HIGH |
| KINEMATIC_PLAUSIBILITY | Two observations exceed one or more versioned motion limits | MEDIUM/HIGH |

Kinematic evidence currently checks implied ground speed, reported acceleration,
turn rate, derived vertical rate, and disagreement between reported and implied
speed. Thresholds are conservative general limits, not aircraft-type performance
models, and the UI states that inconsistency is not proof of spoofing.

## License

MIT
