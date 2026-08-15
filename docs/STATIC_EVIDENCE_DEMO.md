# Static recorded-evidence demo

Build status: implemented and locally verifiable. Public Vercel deployment is intentionally pending the physical benchmark/privacy gate and explicit release authorization.

```bash
cd frontend
npm ci
npm run build:static
cd ..
python scripts/verify_static_demo.py
```

`VITE_RUNTIME_MODE=STATIC_EVIDENCE` makes Vite resolve a dedicated application entry. The resulting browser application contains only checked-in fixtures and local play/pause/speed/reset/scenario controls. It excludes the live application module, auth/session code, API clients, WebSocket clients, map tiles, remote fonts, and remote stylesheets. It needs no secrets and performs no automatic external request.

Every rendered view permanently states `RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC`. The fixture includes a routine synthetic control, synthetic abrupt evidence, synthetic gradual evidence, the measured frozen-policy synthetic results, the honestly blocked physical benchmark, and the honestly blocked public-candidate replication. A blocked result is not shown as zero, nominal, or successful.

The root `vercel.json` runs the static build and serves `frontend/dist`. Vercel hosts only these immutable files; it does not host FastAPI, PostgreSQL, the SBS sidecar, or persistent WebSockets. The authoritative operational demo remains the local feeder Compose deployment.
