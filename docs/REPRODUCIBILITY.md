# Reproducibility

Use Python 3.11+, Node 20, CMake, and Docker with Compose. From a clean checkout:

```bash
PYTHONPATH=backend:. pytest -q backend/tests
ruff check backend services scripts sidecar evaluation
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run build:static
python scripts/verify_static_demo.py
cmake -S decoder -B decoder/build -DBUILD_TESTS=ON
cmake --build decoder/build --parallel 2
ctest --test-dir decoder/build --output-on-failure
RECEIVER_ID=repro docker compose -f docker-compose.feeder.yml config --quiet
python scripts/audit_release_history.py
```

Recreate frozen synthetic evidence with:

```bash
PYTHONPATH=backend:. python scripts/evaluate_frozen_synthetic.py \
  --policy backend/integrity_core/policies/feeder-v1.json --cases 20 \
  --output /tmp/frozen-policy-synthetic-v1.json
```

Compare the output with `evaluation/results/frozen_policy_synthetic_v1.json`,
including policy SHA-256. Public source archives are never assumed: follow
`PUBLIC_ANOMALY_REPLAY.md`, verify the pinned checksum/license gate, and accept a
blocked result when inputs cannot be lawfully reproduced. Private RF reproduction
requires an authorized local capture and the workflow in
`BENIGN_FIELD_EVALUATION.md`; raw data must stay outside Git.
