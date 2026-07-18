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
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
```

Open [http://localhost:5173](http://localhost:5173) (or `http://127.0.0.1:5173`
if another local Node process is using `localhost`). The map is clearly marked
`REPLAY DATA`; aircraft positions, altitude, and callsigns are simulated and must
not be interpreted as live traffic.

Stop the demo with:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

### Live RF mode

### Prerequisites

- RTL-SDR USB dongle
- Python 3.11+
- Node.js 18+
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
ANTHROPIC_API_KEY=your_key_here
```

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

## License

MIT
