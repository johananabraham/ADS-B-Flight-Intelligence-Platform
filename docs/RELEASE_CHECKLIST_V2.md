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
| Non-root/read-only container and Compose contract | UNVERIFIED | Compose config passes; local Docker daemon unavailable, so build/smoke/image scan require CI or Docker Desktop |
| AMD64/ARM64 image workflow with SBOM/provenance | PASS (workflow) | `.github/workflows/feeder-image.yml`; publication intentionally tag-gated |
| Python lint/type/tests and migrations | PASS | Ruff clean; mypy clean across 21 v2 sources; 266 backend tests; one Alembic head and offline upgrade pass |
| TypeScript lint/type/live/static builds | PASS | ESLint, `tsc`, Vite live build, Vite static build, and static verifier pass |
| C++ decoder build/tests | UNVERIFIED | CMake/CTest are unavailable locally; blocking CI job is configured |
| Seven-day chronological benign benchmark | BLOCKED | Physical authorized capture not collected; see `acceptance/phase2-benign-field-status.md` |
| Privacy sanitizer and allow-list tests | PASS | Field privacy tests and private-data ignore/history rules |
| Frozen synthetic abrupt/gradual recall | PASS | 20/20 and 20/20 in `frozen_policy_synthetic_v1.json` |
| Public candidate selection/replay workflow | PASS | Deterministic tests cover detected/missed/insufficient/blocked outcomes |
| Real public anomaly replay | BLOCKED | Source license identifier/trace publication requirements unresolved; checked result is `BLOCKED_REPLICATION` |
| Browser-only static evidence build | PASS | Static build verifier and desktop/mobile interaction review; no live network capabilities |
| Static public deployment | BLOCKED | Publication awaits privacy, license, security, and repository-license decisions |
| Hardware demo video | BLOCKED | Requires physical dongle/capture and manual privacy review |
| Reachable-history restricted-artifact scan | PASS | `scripts/audit_release_history.py`; dedicated Gitleaks CI scans secrets |
| Python and npm dependency scans | PASS | pip-audit 2.10.1 reports no known backend/sidecar findings; npm reports zero vulnerabilities after the nanoid fix |
| Static/configuration and container scans | UNVERIFIED | Blocking Trivy CI is configured; local Trivy/Docker unavailable and remote CI has not run on this commit |
| Sample environment placeholders | PASS | `.env.example` reviewed; no tracked `.env`/keys/database/raw captures |
| Asset/data redistribution inventory | PASS with blockers | `THIRD_PARTY_NOTICES.md`; unresolved data sources remain excluded |
| Repository software license | BLOCKED | No `LICENSE` exists; owner must choose terms before public distribution |
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

1. Resolve the repository software license and every third-party `BLOCKED` item.
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
