# ADS-B Flight Intelligence Platform - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │  RTL-SDR     │   │   OpenSky    │   │   Recorded   │   │  Simulator   │ │
│  │  + dump1090  │   │   Network    │   │   Replay     │   │  (Demo)      │ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
│         │                  │                  │                  │         │
│         └────────────┬─────┴──────────┬───────┴──────────────────┘         │
│                      │                │                                     │
│                      ▼                ▼                                     │
│              ┌───────────────────────────────────┐                         │
│              │     TrackObservation v1.0        │                         │
│              │  (Normalized Observation Contract)│                         │
│              └───────────────────────────────────┘                         │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼              INGESTION                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Python Ingestion Service                        │   │
│  │  • SBS/BaseStation parsing                                           │   │
│  │  • Source provenance tracking                                        │   │
│  │  • Immutable observation persistence                                 │   │
│  │  • Kinematic evidence evaluation                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼              PERSISTENCE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────┐   ┌──────────────────────────────┐   │
│  │         PostgreSQL + PostGIS      │   │          ChromaDB            │   │
│  │                                   │   │                              │   │
│  │  • track_observations (immutable) │   │  • incident_narratives       │   │
│  │  • aircraft (mutable state)       │   │  • faa_regulations           │   │
│  │  • aircraft_positions (history)   │   │                              │   │
│  │  • anomalies                      │   │  (Semantic search vectors)   │   │
│  │  • kinematic_evaluations          │   │                              │   │
│  │  • trust_assessments              │   │                              │   │
│  │  • incidents, regulations         │   │                              │   │
│  │  • edge_stations, edge_events     │   │                              │   │
│  └──────────────────────────────────┘   └──────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼              BACKEND API                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          FastAPI Backend                             │   │
│  │                                                                      │   │
│  │  /api/v1/aircraft/*         REST + WebSocket aircraft tracking       │   │
│  │  /api/v1/kinematics/*       Kinematic evidence and evaluations       │   │
│  │  /api/v1/trust/*            Explainable trust assessment             │   │
│  │  /api/v1/corroboration/*    Cross-source comparison                  │   │
│  │  /api/v1/stations/*         Edge station fleet health                │   │
│  │  /api/v1/safety/*           NTSB/FAA research agent                  │   │
│  │  /api/v1/replay/*           Recorded replay controls                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                               ▼              FRONTEND                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    React + TypeScript + Leaflet                      │   │
│  │                                                                      │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │   │
│  │  │  FlightMap     │  │  Aircraft      │  │  Operator Panels       │ │   │
│  │  │  (Canvas)      │  │  Detail View   │  │  • Trust Evidence      │ │   │
│  │  │                │  │                │  │  • Station Fleet       │ │   │
│  │  │  Real-time     │  │  • Position    │  │  • Safety Research     │ │   │
│  │  │  aircraft      │  │  • Kinematic   │  │  • Replay Controls     │ │   │
│  │  │  positions     │  │    Evidence    │  │  • Alerts Panel        │ │   │
│  │  │                │  │  • Trust State │  │                        │ │   │
│  │  └────────────────┘  │  • Route       │  └────────────────────────┘ │   │
│  │                      └────────────────┘                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           EDGE STATIONS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      MQTT/TLS      ┌──────────────┐                      │
│  │   ESP32      │ ─────────────────▶ │  Mosquitto   │                      │
│  │   Station    │     QoS 1          │   Broker     │                      │
│  │              │                    │              │                      │
│  │  • Heartbeat │                    │  • TLS 1.2+  │                      │
│  │  • Wi-Fi     │                    │  • Per-node  │                      │
│  │    metrics   │                    │    auth      │                      │
│  │  • Watchdog  │                    │  • ACLs      │                      │
│  └──────────────┘                    └──────┬───────┘                      │
│                                             │                               │
│                                             ▼                               │
│                               ┌──────────────────────┐                     │
│                               │   MQTT Consumer      │                     │
│                               │   → PostgreSQL       │                     │
│                               └──────────────────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Observation → Track → Evidence

```
Raw ADS-B Message
       │
       ▼
┌──────────────────┐
│ Parse SBS/Mode S │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ TrackObservation │  ◄── Immutable, source-attributed
│     v1.0         │      UUID5(source_id + raw_hash)
└────────┬─────────┘
         │
         ├─────────────────────────────────────────┐
         │                                         │
         ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│ Persist to       │                    │ Update Mutable   │
│ track_observations│                   │ Aircraft State   │
└────────┬─────────┘                    └──────────────────┘
         │
         ▼
┌──────────────────┐
│ Kinematic        │  ◄── Compare consecutive observations
│ Evaluation       │      from same aircraft/source
└────────┬─────────┘
         │
         ├── PASS ──────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌──────────────────┐                    ┌──────────────────┐
│ FLAGGED:         │                    │ No action        │
│ Create anomaly   │                    │                  │
│ with evidence    │                    │                  │
└──────────────────┘                    └──────────────────┘
```

### 2. Trust Assessment Flow

```
Operator selects aircraft
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│                   Trust Assessment                        │
│                                                          │
│  ┌─────────────────┐   ┌─────────────────┐              │
│  │ Pairwise        │   │ Windowed        │              │
│  │ Kinematic       │   │ Trajectory      │              │
│  │ Evidence        │   │ Evidence        │              │
│  └────────┬────────┘   └────────┬────────┘              │
│           │                     │                        │
│           ▼                     ▼                        │
│  ┌─────────────────┐   ┌─────────────────┐              │
│  │ Corroboration   │   │ Station Health  │              │
│  │ State           │   │ State           │              │
│  └────────┬────────┘   └────────┬────────┘              │
│           │                     │                        │
│           └─────────┬───────────┘                        │
│                     │                                    │
│                     ▼                                    │
│          ┌──────────────────┐                            │
│          │ Combined Trust   │                            │
│          │ State            │                            │
│          │                  │                            │
│          │ TRUSTED          │                            │
│          │ QUESTIONABLE     │                            │
│          │ LOW_CONFIDENCE   │                            │
│          │ INSUFFICIENT_DATA│                            │
│          └──────────────────┘                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ Persist snapshot │  ◄── Immutable assessment
│ + operator can   │      with evidence references
│ acknowledge/     │
│ annotate         │
└──────────────────┘
```

## Component Details

### Kinematic Evidence Rules (Policy v1.0)

| Rule | Threshold | Unit |
|------|-----------|------|
| Implied Ground Speed | > 800 | knots |
| Reported Acceleration | > 3.0 | g |
| Turn Rate | > 6.0 | °/sec |
| Derived Vertical Rate | > 6000 | ft/min |
| Speed Disagreement | > 50 | knots |

### Cross-Source Corroboration States

| State | Meaning |
|-------|---------|
| `CORROBORATED` | Local and external sources agree |
| `LOCAL_ONLY` | No external observation available |
| `EXTERNAL_ONLY` | External data but no local observation |
| `CONFLICTING` | Position/altitude disagree beyond tolerance |
| `STALE` | External data too old |
| `UNAVAILABLE` | Provider error or disabled |

### Station Health States

| State | Meaning |
|-------|---------|
| `HEALTHY` | Recent heartbeat, metrics normal |
| `DEGRADED` | Recent but metrics concerning |
| `STALE` | Heartbeat > 2 minutes old |
| `OFFLINE` | No contact or explicit disconnect |
| `NO_DATA` | Station registered but never reported |

## Evaluation Results

| Evaluation | Result | Evidence |
|------------|--------|----------|
| Kinematic Rules v1.0 | 100% abrupt attack detection | `evaluation/results/kinematic_rules_baseline_v1.json` |
| Window Policy v1.0-dev | 22/22 gradual drift detected | `evaluation/results/windowed_trajectory_baseline_v1.json` |
| ML Baselines | F1 0.9333 (held-out) | `evaluation/results/ml_baselines_v1.json` |
| Corroboration | 6/6 states verified | `evaluation/results/corroboration_offline_v1.json` |
| Station Health | 7/7 classifications | `evaluation/results/station_health_offline_v1.json` |

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript 5.9, Leaflet.js, Tailwind CSS |
| Backend | FastAPI, Python 3.11, Pydantic 2.x |
| Database | PostgreSQL 15 + PostGIS |
| Vector Store | ChromaDB with MiniLM embeddings |
| Message Broker | Mosquitto 2.0 (TLS + ACLs) |
| Firmware | ESP-IDF 6.0.2 |
| CI/CD | GitHub Actions |
| Container | Docker Compose |
