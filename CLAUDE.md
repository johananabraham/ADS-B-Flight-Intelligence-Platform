# Aviation Intelligence Platform - Project Memory

## Project Overview
Unified aviation intelligence platform combining real-time ADS-B flight tracking (via SDR hardware) with AI-powered safety research (RAG over NTSB/FAA data).

**Goal:** Resume differentiator showcasing hardware (SDR/RF) + AI (RAG/LLM) integration.

## Architecture

### Real-Time Flight Tracking (ADS-B)
- **SDR Hardware:** RTL-SDR dongle (Nooelec NESDR SMArt v5)
- **Signal Decoder:** dump1090 on port 30003 (SBS format)
- **Backend:** FastAPI + PostgreSQL + PostGIS
- **Frontend:** React + TypeScript + Leaflet.js + Tailwind
- **Features:** Real-time map, filters, geofencing, anomaly detection, statistics

### Safety Research Agent (RAG)
- **Data Sources:** NTSB incidents (~40k+), FAA regulations (14 CFR Parts 61, 91, 121, 135)
- **Vector DB:** ChromaDB with all-MiniLM-L6-v2 embeddings
- **LLM:** Groq Llama 3.3 70B (or OpenAI fallback)
- **Agent:** ReAct-style with 4 tools (search narratives, query DB, search regulations, get details)

## Current Integration Status

### Branch: `feature/safety-research-integration`

### Tasks
1. [DONE] Add Safety Agent database models and ChromaDB setup
2. [DONE] Port Safety Agent tools and RAG logic
3. [DONE] Create integrated API endpoints
4. [PENDING] Add frontend Safety Research panel
5. [PENDING] Integrate safety context into aircraft details
6. [PENDING] Add anomaly-triggered safety research

## Key Files

### ADS-B Platform
- `backend/app/main.py` - FastAPI entry point
- `backend/app/api/aircraft.py` - Aircraft REST endpoints
- `backend/app/api/websocket.py` - Real-time WebSocket
- `backend/app/models/aircraft.py` - Aircraft, AircraftPosition, Anomaly models
- `services/ingestion/ingest.py` - dump1090 to PostgreSQL ingestion
- `services/anomaly_detection/detector.py` - Anomaly detection service
- `frontend/src/App.tsx` - Main React app
- `frontend/src/components/FlightMap.tsx` - Leaflet map

### Safety Agent (to be integrated)
- `app/db/models.py` - Incident, Regulation models
- `app/db/vectorstore.py` - ChromaDB client
- `app/agent/agent.py` - ReAct agent loop
- `app/agent/tools.py` - 4 RAG tools
- `app/agent/prompts.py` - System prompts
- `app/agent/schemas.py` - OpenAI function schemas

## Running the Platform

```bash
# Start dump1090 (requires RTL-SDR dongle)
dump1090 --net --net-bind-address 0.0.0.0 --quiet &

# Start Docker services
docker compose up -d

# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
```

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `DUMP1090_HOST` - dump1090 host (host.docker.internal for Docker)
- `DUMP1090_PORT` - dump1090 SBS port (30003)
- `LLM_API_KEY` / `GROQ_API_KEY` - LLM API key
- `LLM_BASE_URL` - LLM API base URL
- `ANTHROPIC_API_KEY` - For AI summaries (optional)

## Integration Plan

### Phase 1: Shared Infrastructure
- Add Incident/Regulation models to existing DB
- Add ChromaDB dependency and vectorstore module
- Merge config settings

### Phase 2: Backend Integration
- Port Safety Agent tools into ADS-B backend
- New endpoints: `/api/v1/safety/query`, `/api/v1/aircraft/{icao}/safety-context`

### Phase 3: Frontend Integration
- SafetyPanel component (press `R`)
- Aircraft detail → safety context tab
- Natural language query interface

### Phase 4: Smart Features
- Anomaly → auto-search historical incidents
- Real-time risk scoring based on NTSB statistics
- Compliance warnings

## Recent Changes
- 2026-07-11: Fixed Docker networking for dump1090 ingestion
- 2026-07-11: Added REST polling fallback for WebSocket
- 2026-07-11: Added libgeos-dev to Dockerfiles for PostGIS support
- 2026-07-11: Started safety research integration (branch created)
- 2026-07-11: Added Incident/Regulation models, ChromaDB vectorstore
- 2026-07-11: Ported Safety Agent tools (5 tools) and ReAct agent
- 2026-07-11: Added /api/v1/safety/* endpoints (query, context, stats)

## Notes
- dump1090 must bind to 0.0.0.0 for Docker containers to connect
- ChromaDB uses local embeddings (no API dependency)
- Safety Agent already has evaluation suite with 30 test cases
