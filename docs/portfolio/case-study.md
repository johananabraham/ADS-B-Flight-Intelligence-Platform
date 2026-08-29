# ADS-B Flight Intelligence Platform: Case Study

## Problem Statement

Modern aviation tracking relies heavily on ADS-B (Automatic Dependent Surveillance-Broadcast), a cooperative surveillance technology where aircraft self-report their position, altitude, and identity. However, ADS-B messages are:

1. **Unencrypted** - Anyone can receive them with a $20 SDR dongle
2. **Unauthenticated** - No cryptographic verification of sender identity
3. **Self-reported** - Aircraft broadcast their own position data

This creates potential for spoofing, jamming, and false injection attacks. Air traffic control systems need mechanisms to detect when reported data is inconsistent or suspicious.

## Constraints

- **Hardware**: Single RTL-SDR dongle + ESP32 development board
- **Budget**: Zero cloud compute cost during development
- **Timeline**: Multi-week incremental development
- **Data**: NTSB/FAA public datasets for safety research integration
- **Complexity**: Must be explainable to non-ML audiences (interviewers)

## Design Decisions

### 1. Observation vs Track Separation

**Decision**: Separate immutable source observations from mutable track state.

**Rationale**: Every detection claim needs evidence provenance. If we only store the latest position, we lose the raw data that triggered an alert.

**Implementation**:
- `TrackObservation` schema with source attribution
- Append-only `track_observations` table
- UUIDv5 identity from source + message hash (idempotent)

### 2. Deterministic Rules Before ML

**Decision**: Build versioned kinematic rules before any machine learning.

**Rationale**:
- Rules are explainable ("implied speed was 1200 knots, threshold is 800")
- Rules establish a measurable baseline
- ML improvement must beat the rules baseline

**Implementation**:
- Five kinematic rules with documented thresholds
- Policy version tracking (v1.0)
- Every evaluation stores measured value + threshold + both observation IDs

### 3. Leakage-Safe Evaluation

**Decision**: Split train/validation/test by source session, not by individual message.

**Rationale**: Random message-level splits leak attack signatures across splits, inflating metrics.

**Implementation**:
- Generator assigns sessions to splits before creating attack variants
- 22 held-out sessions for final evaluation
- Itemized per-attack-family results

### 4. Explainable Trust, Not Magic Scores

**Decision**: Show component evidence instead of a single trust number.

**Rationale**: Operators need to understand *why* a track is flagged, not just that it is.

**Implementation**:
- Component states: kinematic, window, corroboration, station
- Overall state: TRUSTED / QUESTIONABLE / LOW_CONFIDENCE / INSUFFICIENT_DATA
- No numeric score until calibrated against reviewed field data

### 5. Hardware-Free Demo Mode

**Decision**: Create deterministic simulation that uses the real data path.

**Rationale**: Reviewers and interviewers don't have SDR hardware.

**Implementation**:
- Python simulator generates valid SBS messages
- Same ingestion → database → API → WebSocket → frontend path
- Clear `REPLAY DATA` badge in UI

## What Worked

### Deterministic Kinematic Detection

The pairwise kinematic rules detect 100% of generated abrupt attacks (position jump, altitude jump, velocity jump, heading jump) with zero delay. The windowed trajectory rule closes the gradual-drift gap.

```
Held-out Results (22 sessions):
- Abrupt attacks: 88/88 detected (100%)
- Gradual drift: 22/22 detected with window rule
- Generated clean: 0/22 flagged
```

### Idempotent Everything

The system can replay the same recording indefinitely without data duplication:
- Observation UUIDs from content hash
- PostgreSQL `ON CONFLICT DO NOTHING`
- Assessment retries don't create duplicates

### CI as Source of Truth

Every claim has a corresponding CI job:
- 292 backend tests passing, 1 skipped
- 6 evaluation baselines with `--check` gates
- Complete Docker demo verification
- MQTT TLS/ACL proof script

## What Didn't Work (Or Isn't Done Yet)

### 1. Real RF Calibration

The kinematic thresholds are conservative estimates. We have:
- ✓ Generated scenario validation
- ✗ Multi-hour routine traffic capture
- ✗ Measured false-positive rate

**Next step**: Capture several hours of actual receiver traffic, run the calibration harness, manually review every grouped alert episode.

### 2. Live External Corroboration

The OpenSky adapter works offline:
- ✓ 720 synthetic comparisons pass
- ✗ Zero live API calls verified
- ✗ No real conflict examples reviewed

**Next step**: Enable OpenSky with proper credentials, run a 4-hour comparison, document any conflicts.

### 3. ESP32 Physical Test

The firmware compiles and the MQTT path is proven:
- ✓ CI proves TLS + ACLs + authentication
- ✗ No physical power/Wi-Fi outage test
- ✗ No measured recovery time

**Next step**: Flash the ESP32, intentionally disconnect it, measure detection and recovery latency.

### 4. Safety Agent Data

The versioned ingestion and retrieval baseline now provide:
- ✓ Dated eCFR Part 91 artifact lineage (286 parsed sections)
- ✓ 15 engineering-reviewed official-source retrieval cases
- ✓ Recall@3 0.9333, Recall@5 0.9333, MRR 0.8111
- ✗ No complete authorized NTSB dataset ingestion
- ✗ No structured-query exact-match or synthesis-quality baseline
- ✗ No independent aviation-domain review or citation verification

**Next step**: ingest an authorized NTSB export, add exact expected incident IDs and
SQL counts, then conduct independent review before making broader quality claims.

## Metrics

| Metric | Value | Evidence |
|--------|-------|----------|
| Backend tests | 170 passing | CI `backend` job |
| Kinematic abrupt detection | 100% | `kinematic_rules_baseline_v1.json` |
| Kinematic gradual detection | 100% (with window) | `windowed_trajectory_baseline_v1.json` |
| Generated clean FP rate | 0% | baseline files |
| ML F1 improvement | 0.7692 → 0.9333 | `ml_baselines_v1.json` |
| Corroboration states | 6/6 correct | `corroboration_offline_v1.json` |
| Station health states | 7/7 correct | `station_health_offline_v1.json` |
| Dependency vulnerabilities | 0 | CI `security` job |

## Scale Considerations

**Current topology**: Single receiver, single backend, single database.

**At 100 sensors**:
- MQTT broker would handle connection load
- Consumer would batch database writes
- Need per-track sharding or time-series partitioning
- Trust assessment becomes O(sensors × tracks)

**At 10,000 tracks**:
- Canvas rendering already optimized (not DOM markers)
- PostgreSQL needs indexing review
- WebSocket fan-out needs connection pooling
- Consider track age pruning policy

## Interview Talking Points

1. **Observation/Track separation**: Why mutable state hides evidence
2. **Leakage-safe evaluation**: Why session-level splits matter
3. **Explainable trust**: Why operators need reasons, not scores
4. **Idempotency**: How to replay without duplication
5. **CI as evidence**: Why every claim needs a test artifact
6. **Honest limitations**: What isn't proven yet and why

## Files to Review

| File | Purpose |
|------|---------|
| `backend/app/schemas/observation.py` | TrackObservation contract |
| `backend/app/services/kinematics.py` | Kinematic evidence rules |
| `backend/app/evaluation/kinematic_harness.py` | Scenario generator |
| `backend/app/services/trust_assessment.py` | Component trust logic |
| `firmware/esp32-station/main/main.c` | Edge station firmware |
| `scripts/verify_demo.py` | End-to-end verification |
