# Cross-source Corroboration v1

## Purpose

This phase asks whether an independent external observation agrees with a local
aircraft observation. It does not authenticate an aircraft, prove spoofing, infer
intent, or perform full sensor fusion.

## Architecture

1. The API loads the latest non-external, provenance-bearing observation for the
   selected ICAO address.
2. The OpenSky adapter requests a 0.5° × 0.5° bounding box and the selected ICAO.
3. OpenSky state vectors are normalized into the version 1.0 observation contract,
   including provider and licensing provenance.
4. The pure comparison engine applies policy 1.0 freshness, time, position, and
   altitude tolerances.
5. The API and UI return evidence and source health without creating an anomaly.

Policy 1.0 uses these conservative development tolerances:

| Measurement | Tolerance |
|---|---:|
| Observation age | 30 seconds |
| Future clock skew | 2 seconds |
| Cross-source time delta | 15 seconds |
| Position distance | 3 nautical miles |
| Altitude difference | 1,500 feet |

These are development policy values, not empirically calibrated uncertainty bounds.

## Evidence states

| State | Meaning |
|---|---|
| `CORROBORATED` | Fresh same-ICAO observations have comparable evidence within policy tolerances. |
| `LOCAL_ONLY` | The local observation has no fresh external match while the provider is available. |
| `EXTERNAL_ONLY` | The external source has no local counterpart in the comparison set. |
| `CONFLICTING` | Associated observations disagree beyond position or altitude tolerance. |
| `STALE` | Evidence is too old, too far apart in time, or lacks comparable measurements. |
| `UNAVAILABLE` | The external source is disabled, failed, rate limited, or circuit-open. |

None of these states alone proves malicious activity. In particular, provider
failure must remain `UNAVAILABLE`, never `LOCAL_ONLY` or “suspicious.”

## Provider resilience

The adapter implements:

- bounded queries and a 10-second cache;
- a 10-second minimum poll interval for anonymous freshness resolution;
- OAuth2 client-credentials token acquisition and token caching when configured;
- `X-Rate-Limit-Remaining` and retry-after tracking;
- exponential failure backoff and a circuit breaker after three failures;
- request, success, failure, cache-hit, rate-limit, and health counters.

The current [official OpenSky REST documentation](https://openskynetwork.github.io/opensky-api/rest.html)
states that anonymous state vectors have 10-second resolution and a daily credit
allowance, while authenticated access uses OAuth2 and higher limits. The
[official overview](https://openskynetwork.github.io/opensky-api/) describes the live
API as research/non-commercial data and directs commercial users to OpenSky. Review
the current terms before any public or commercial deployment.

## Offline evidence

Artifact: `evaluation/results/corroboration_offline_v1.json`

The deterministic fixture represents four hours at 20-second intervals: 720
comparisons, with 120 examples of each state. It measures:

- zero classification mismatches across the six controlled scenario families;
- 5/6 synthetic provider availability;
- 1/2 synthetic both-source coverage;
- 1.5-second simulated median external receive latency and 2.5-second p95;
- ten recorded synthetic conflict samples, all marked as not human reviewed.

The rates above describe a deliberately balanced fixture. They do not estimate real
OpenSky coverage, latency, availability, or false-alert rates.

Reproduce the reviewed artifact:

```bash
PYTHONPATH=backend:. python3 scripts/run_corroboration_evaluation.py --check \
  --baseline evaluation/results/corroboration_offline_v1.json
```

## Promotion requirements

Before describing this feature as demonstrated live corroboration:

1. Confirm the intended deployment complies with current provider terms.
2. Run a permitted multi-hour local/external comparison over several traffic and
   receiver conditions.
3. Record provider coverage, receive latency, cache behavior, rate limits, outages,
   and all six state rates from that run.
4. Manually review a sample of real `CONFLICTING`, `LOCAL_ONLY`, and `EXTERNAL_ONLY`
   results and record reviewer identity and notes.
5. Revisit tolerances using measured source timing and position uncertainty.

Until then, the defensible claim is: **implemented and deterministically verified
offline cross-source corroboration, with live field validation pending**.
