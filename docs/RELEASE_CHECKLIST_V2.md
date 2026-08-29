# Feeder integrity v2 release checklist

Status is evidence, not aspiration. `PASS` has a reproducible artifact or test;
`BLOCKED` needs an external input or owner decision; `UNVERIFIED` needs an
environment that was unavailable locally. A v2 tag is forbidden while any blocking
gate remains.

## Acceptance matrix

| Gate | Status | Evidence / next action |
|---|---|---|
| Baseline preserved | PASS | `v1.0-pre-feeder` points to reconciled pre-v2 main |
| Auth/session/RBAC/Origin hardening | PASS | Backend regression and migration suites |
| Shared deterministic core and policy validation | PASS | Core golden, compatibility, expiry, unit, ordering, duplicate tests |
| Database-free sidecar | PASS | Strict SBS parser, bounded runtime/store, REST/WS/metrics/UI tests |
| 100 msg/s for 30 minutes, p95 <250 ms, no unbounded growth | PASS | 180,000 messages, 0 drops, p95 1.699 ms, 95.781 MB; `evaluation/results/feeder-soak-v1.json` |
| Non-root/read-only container and Compose contract | PASS | Compose contract, container build, hardened startup, and read-only health check passed in [CI run 31948219688](https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/actions/runs/31948219688) |
| AMD64/ARM64 image workflow with SBOM/provenance | PASS (workflow) | `.github/workflows/feeder-image.yml`; publication intentionally tag-gated |
| Python lint/type/tests and migrations | PASS | Ruff clean; mypy clean across 22 v2 sources; 326 backend tests pass and 1 is skipped; one Alembic head and offline upgrade pass |
| TypeScript lint/type/live/static builds | PASS | ESLint, `tsc`, Vite live build, Vite static build, and static verifier pass |
| C++ decoder build/tests | PASS | CMake build and CTest passed in [CI run 31948219688](https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/actions/runs/31948219688) |
| Seven-day chronological benign benchmark | BLOCKED | Physical authorized capture not collected; fail-closed preflight, private atomic progress, non-overwriting retries, and interrupted-attempt preservation are implemented; see `acceptance/phase2-benign-field-status.md` |
| Privacy sanitizer and allow-list tests | PASS | Field privacy tests and private-data ignore/history rules |
| Frozen synthetic abrupt/gradual recall | PASS | 20/20 and 20/20 in `frozen_policy_synthetic_v1.json` |
| Public candidate selection/replay workflow | PASS | Deterministic tests cover detected/missed/insufficient/blocked outcomes |
| Real public anomaly replay | BLOCKED | Zenodo indexes are CC BY 4.0 and approved for processing; compliant surrounding trace not yet acquired; checked result is `BLOCKED_REPLICATION` |
| Browser-only static evidence build | PASS | Static build verifier and desktop/mobile interaction review; no live network capabilities |
| Static public deployment | PASS | [Production Vercel demo](https://adsb-feeder-integrity-evidence.vercel.app/) verified at desktop and 390px mobile widths after static-bundle, privacy-history, and credential scans |
| Hardware demo video | BLOCKED | Requires physical dongle/capture and manual privacy review |
| ESP32 private-LAN deployment preflight | PASS (software) | Exact private bind, certificate SAN/expiry, secret permissions, and ACL checks; physical outage/recovery remains blocked |
| Receiver pipeline / ESP32 health correlation | PASS (software) | Loopback-only bridge, separate pipeline-only MQTT principal, strict aggregate schema, immutable persistence, and dashboard evidence; physical validation remains blocked |
| Independent feeder pilot | READY TO RECRUIT | Summary, readiness, strict evidence bundles, deterministic success report, and protocol complete; requires 3–5 external operators |
| Reachable-history restricted-artifact scan | PASS | `scripts/audit_release_history.py`; dedicated Gitleaks CI scans secrets |
| Python and npm dependency scans | PASS WITH EXPIRING EXCEPTION | Chroma CVE-2026-45830/45833 affect server endpoints that are not deployed; exact 0.4.22 exception expires 2026-09-30 and reset is disabled. Sidecar and npm have no known findings |
| Static/configuration and container scans | PASS | Trivy source/configuration scan and sidecar critical-vulnerability image scan passed in [CI run 31948219688](https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/actions/runs/31948219688) |
| Sample environment placeholders | PASS | `.env.example` reviewed; no tracked `.env`/keys/database/raw captures |
| Asset/data redistribution inventory | PASS with blockers | `THIRD_PARTY_NOTICES.md`; licensed Zenodo indexes remain excluded and the unacquired ODbL trace remains blocked |
| Repository software license | PASS | Root `LICENSE`, README scope statement, and frontend package metadata consistently declare Apache-2.0 |
| Tagged v2 release/checksums/images | BLOCKED | Intentionally not created until every blocking gate passes |

## Required documentation

- [Responsible use](RESPONSIBLE_USE.md)
- [Security reporting](../SECURITY.md)
- [Privacy](PRIVACY.md)
- [Data/model card](DATA_MODEL_CARD.md)
- [Architecture](ARCHITECTURE_V2.md)
- [Benchmark methodology](BENCHMARK_METHODOLOGY.md)
- [Reproducibility](REPRODUCIBILITY.md)
- [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Promotion procedure

1. Keep repository license metadata consistent and resolve every third-party
   `BLOCKED` item.
2. Complete the untouched day-7 benchmark and publish only sanitized reviewed
   aggregates.
3. Complete the real candidate replay or retain a fully documented, licensed
   `BLOCKED_REPLICATION` result acceptable for release scope.
4. Run the full CI commit with all blocking jobs green, including image scanning and
   the 30-minute sidecar soak. Review Gitleaks and Trivy output, not only job status.
5. Privacy-review the hardware video/static deployment; verify all links from a
   clean browser session.
6. Tag `v2.x.y`. The tag triggers multi-architecture GHCR publication with SBOM and
   provenance. Record immutable image digests and release checksums in the GitHub
   release notes.
