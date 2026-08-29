# Demo Verification Checklist

**Date:** 2026-08-05
**Branch:** `codex/authentication-rbac`
**Verifier:** Automated Testing + Manual Verification

## Executive Summary

This document provides a verification checklist for the three headline demos outlined in the Phase 2 implementation plan. Some demos require additional infrastructure setup (MQTT, edge nodes) or data (NTSB/FAA) that is currently unavailable.

---

## Demo 1: Edge Loss (Station Outage)

**Scenario:** Disconnect sensor, show bounded data loss, recovery

**Status:** ⏸️ **REQUIRES SETUP**

### Prerequisites

- [ ] MQTT broker (eclipse-mosquitto) running
- [ ] Edge consumer service running
- [ ] At least one edge station simulator running
- [ ] Station health monitoring enabled

### Setup Commands

```bash
# Provision MQTT credentials
./scripts/provision_edge_mqtt.sh mqtt

# Start edge stack
docker compose -f docker-compose.yml -f docker-compose.edge.yml up -d

# Start simulator
STATION_NODE_ID=roof-node-1 \
STATION_MQTT_PASSWORD_FILE=edge/mosquitto/secrets/roof-node-1.password \
MQTT_CA_CERT=edge/mosquitto/secrets/ca.crt \
python3 -m services.edge_telemetry.simulator &
```

### Verification Steps

1. **Baseline State** (Healthy)
   - [ ] Open UI at http://localhost:5173
   - [ ] Press `N` to open Station Fleet Panel
   - [ ] Verify station "roof-node-1" shows status: ONLINE
   - [ ] Note timestamp and heartbeat interval
   - [ ] Screenshot: `baseline-healthy.png`

2. **Simulate Failure**
   - [ ] Kill simulator process: `pkill -f edge_telemetry.simulator`
   - [ ] Wait 60 seconds (2x heartbeat interval)
   - [ ] Verify station status changes: ONLINE → STALE → OFFLINE
   - [ ] Note transition timestamps
   - [ ] Screenshot: `station-offline.png`

3. **Verify Bounded Data Loss**
   - [ ] Check PostgreSQL for last heartbeat timestamp
   - [ ] Calculate data loss window (time since last heartbeat)
   - [ ] Verify no ghost data generated during offline period
   - [ ] Document: "Lost X seconds of telemetry"

4. **Recovery**
   - [ ] Restart simulator with same NODE_ID
   - [ ] Verify station status: OFFLINE → STALE → ONLINE
   - [ ] Measure recovery time (from restart to ONLINE)
   - [ ] Verify resumed heartbeat sequence number
   - [ ] Screenshot: `station-recovered.png`

### Success Criteria

- ✅ Station transitions through expected states (ONLINE → STALE → OFFLINE)
- ✅ Data loss is bounded to outage window (no phantom data)
- ✅ Recovery is automatic and complete
- ✅ Sequence numbers resume correctly (no duplicates)
- ✅ UI accurately reflects station health in real-time

### Metrics to Document

- Time to STALE detection: `<X> seconds`
- Time to OFFLINE detection: `<X> seconds`
- Data loss window: `<X> seconds`
- Recovery time: `<X> seconds`
- Total outage duration: `<X> seconds`

---

## Demo 2: Conflicting Sensors (Kinematic Plausibility)

**Scenario:** Inject conflicting observations, show source provenance

**Status:** ✅ **READY TO TEST**

### Prerequisites

- [x] Platform running with recorded replay mode
- [x] Kinematic attack scenario recording available
- [x] Trust assessment engine enabled

### Setup Commands

```bash
# Start with kinematic attack scenario
docker compose \
  -f docker-compose.yml \
  -f docker-compose.demo.yml \
  -f docker-compose.recorded.yml \
  -f docker-compose.kinematic-attack.yml \
  up --build -d

# Verify replay is loaded
curl http://localhost:8000/api/v1/replay/status
```

### Verification Steps

1. **Locate Flagged Track**
   - [ ] Open UI at http://localhost:5173
   - [ ] Login with admin credentials
   - [ ] Press `A` to open Alerts Panel
   - [ ] Look for KINEMATIC_PLAUSIBILITY anomaly
   - [ ] Note ICAO hex of flagged aircraft
   - [ ] Screenshot: `kinematic-alert.png`

2. **Examine Trust Assessment**
   - [ ] Click on flagged aircraft
   - [ ] Expand Trust Assessment section
   - [ ] Verify state shows: QUESTIONABLE or LOW_CONFIDENCE
   - [ ] Note reasons listed (should mention kinematic implausibility)
   - [ ] Screenshot: `trust-questionable.png`

3. **Component Breakdown**
   - [ ] Expand trust component details
   - [ ] Verify PAIR_KINEMATICS component shows FLAGGED
   - [ ] Check evidence IDs are present
   - [ ] Read reasons for each component
   - [ ] Verify timestamp and policy version
   - [ ] Screenshot: `trust-components.png`

4. **Source Provenance**
   - [ ] Check observation sources listed
   - [ ] Verify conflicting positions are shown
   - [ ] Confirm implausibility metrics (acceleration, velocity)
   - [ ] Verify operator can see WHICH sensors disagreed
   - [ ] Screenshot: `source-provenance.png`

5. **Operator Action**
   - [ ] Click "Acknowledge" or "Annotate" button
   - [ ] Add operator note: "Reviewed - likely position spoofing"
   - [ ] Verify action is recorded
   - [ ] Check action appears in trust events list
   - [ ] Screenshot: `operator-action.png`

### Success Criteria

- ✅ Kinematic implausibility detected and flagged
- ✅ Trust state reflects uncertainty (QUESTIONABLE/LOW_CONFIDENCE)
- ✅ Component breakdown shows which evidence caused flag
- ✅ Operator can see conflicting observations and sources
- ✅ Operator actions are recorded with identity and timestamp
- ✅ UI explains WHY the track is flagged (not just "bad")

### Metrics to Document

- Detection latency: `<X> seconds after implausible observation`
- Number of flagged observations: `<X>`
- Acceleration threshold violated: `<X> m/s²`
- Velocity jump: `<X> m/s`
- Operator action recorded: `<timestamp>`

---

## Demo 3: Investigation (Safety Research)

**Scenario:** Query NTSB/FAA data, get cited response

**Status:** ⚠️ **LIMITED** (No data ingested)

### Prerequisites

- [x] Safety Research panel implemented
- [ ] NTSB incident data ingested (BLOCKED - API 403)
- [ ] FAA regulations ingested (BLOCKED - API 404)
- [x] Safety query endpoints available

### Setup Commands

```bash
# Platform should already be running
# No additional setup required
```

### Verification Steps (Without Data)

1. **Open Safety Panel**
   - [ ] Open UI at http://localhost:5173
   - [ ] Login with admin credentials
   - [ ] Press `R` to open Safety Research panel
   - [ ] Verify panel appears
   - [ ] Screenshot: `safety-panel-empty.png`

2. **Test Query Interface**
   - [ ] Enter query: "What are common causes of Cessna 172 accidents?"
   - [ ] Click Submit
   - [ ] Verify response format (should explain no data available)
   - [ ] Screenshot: `safety-query-no-data.png`

3. **API Endpoint Test**
   - [ ] Test via curl:
     ```bash
     curl -X POST http://localhost:8000/api/v1/safety/query \
       -H "Origin: http://localhost:5173" \
       -H "Content-Type: application/json" \
       -d '{"query": "test query"}'
     ```
   - [ ] Verify JSON response structure
   - [ ] Check for error messages about missing data

### Verification Steps (With Data - Future)

When NTSB/eCFR data is available:

1. **Submit Research Query**
   - [ ] Query: "What are common causes of Cessna 172 accidents?"
   - [ ] Wait for agent response
   - [ ] Verify response includes:
     - [ ] NTSB incident citations (event ID, date, aircraft)
     - [ ] Relevant CFR references (14 CFR Part X Section Y)
     - [ ] Statistics from database (e.g., "Found 47 incidents")
   - [ ] Screenshot: `safety-research-response.png`

2. **Verify Citations**
   - [ ] Click on an NTSB citation link
   - [ ] Verify link goes to actual NTSB record
   - [ ] Confirm citation is relevant to query
   - [ ] Check CFR references are accurate

3. **Test Multiple Queries**
   - [ ] "What regulations govern night VFR minimums?"
   - [ ] "Show me recent accidents involving stall/spin"
   - [ ] "What are preflight requirements for VFR flight?"
   - [ ] Verify each returns relevant, cited responses

### Current Status

**Without Data:**
- ✅ Safety panel UI implemented
- ✅ Query interface functional
- ✅ API endpoints available
- ❌ No NTSB data (API blocked)
- ❌ No eCFR data (API blocked)
- ⚠️ Agent will respond "No data available"

**Workaround for Demo:**
- Use mock/sample data
- Pre-record agent responses
- Demonstrate with cached regulation text
- Focus on UI/UX rather than actual RAG

### Success Criteria (When Data Available)

- ✅ Query submitted successfully
- ✅ Agent searches NTSB database
- ✅ Agent searches FAA regulations
- ✅ Response includes citations (event IDs, CFR sections)
- ✅ Response includes statistics from database
- ✅ Citations are clickable and valid
- ✅ Response is relevant to query

---

## Authentication Demo (Bonus)

**Scenario:** Show authentication protecting sensitive operations

**Status:** ✅ **COMPLETE AND TESTABLE**

### Verification Steps

1. **Unauthenticated Access**
   - [ ] Open UI in incognito window
   - [ ] Verify login form appears
   - [ ] Cannot access platform without login
   - [ ] Screenshot: `login-required.png`

2. **Login Flow**
   - [ ] Enter username: `admin`
   - [ ] Enter the password created through the interactive bootstrap script
   - [ ] Click Login
   - [ ] Verify redirect to platform
   - [ ] Verify user info shown (top-right)
   - [ ] Screenshot: `logged-in.png`

3. **Protected Operations**
   - [ ] Try replay control (should work for admin/operator)
   - [ ] Try operator action on trust event
   - [ ] Verify actions require authentication
   - [ ] Screenshot: `protected-action.png`

4. **Role-Based Access**
   - [ ] Create viewer user (if admin)
   - [ ] Login as viewer
   - [ ] Try replay control (should fail - 403 Forbidden)
   - [ ] Try operator action (should fail - 403 Forbidden)
   - [ ] Screenshot: `rbac-denied.png`

5. **Logout**
   - [ ] Click logout button or press `L`
   - [ ] Verify redirect to login
   - [ ] Verify token cleared
   - [ ] Try to access platform (should show login)
   - [ ] Screenshot: `logged-out.png`

### Success Criteria

- ✅ Platform requires authentication
- ✅ Login flow works correctly
- ✅ User info displayed after login
- ✅ Protected endpoints check authentication
- ✅ RBAC prevents unauthorized actions
- ✅ Logout clears session
- ✅ All 21 auth tests passing

---

## Summary of Demo Readiness

| Demo | Status | Can Demo? | Blockers |
|------|--------|-----------|----------|
| **1. Edge Loss** | ⏸️ Setup Required | Partial | Need MQTT + simulator setup |
| **2. Kinematic Conflict** | ✅ Ready | **YES** | None - replay scenario exists |
| **3. Safety Research** | ⚠️ Limited | UI Only | No NTSB/eCFR data |
| **Bonus: Authentication** | ✅ Complete | **YES** | None - fully working |

### Recommended Demo Flow

For a 90-second demo video:

**0:00-0:15** - Title + Authentication
- Show login screen
- Login as admin
- Show role badge and user info

**0:15-0:45** - Kinematic Conflict Detection (Demo 2)
- Show live map with aircraft
- Point out flagged aircraft (QUESTIONABLE)
- Expand trust assessment
- Show component breakdown
- Highlight source provenance
- Record operator action

**0:45-1:15** - Safety Research (Demo 3)
- Press `R` to open safety panel
- Show query interface
- Explain data ingestion blocker
- Mention future capability with real NTSB/FAA data

**1:15-1:30** - Closing
- Show metrics: 296 backend tests passing, 1 skipped, authentication complete
- Show role-based access control
- GitHub link

### Alternative: Focus on What Works

**0:00-0:20** - Authentication & RBAC
- Login flow
- Role-based permissions
- Protected operations

**0:20-0:50** - Trust Assessment Engine
- Kinematic plausibility detection
- Source provenance
- Operator workflow

**0:50-1:20** - Architecture Overview
- Show components: ADS-B → Trust Engine → Safety Research
- Explain integration points
- Highlight portfolio differentiators

**1:20-1:30** - Metrics & GitHub

---

## Next Steps

1. **Choose demos to record** based on readiness
2. **Set up kinematic attack scenario** (most ready)
3. **Practice demo flow** with timing
4. **Record 90-second video** focusing on working features
5. **Update README** with verified metrics
6. **Document known limitations** honestly

---

## Notes

- All authentication tests (21/21) passing ✅
- Platform runs successfully in Docker ✅
- Edge demo requires additional setup time
- Data ingestion blocked by external APIs
- Focus demo on **what works** rather than what's blocked
- Honesty about limitations builds credibility
