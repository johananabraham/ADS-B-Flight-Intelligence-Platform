# Static recorded-evidence demo

Deployment status: live at
[adsb-feeder-integrity-evidence.vercel.app](https://adsb-feeder-integrity-evidence.vercel.app/).
The production build, privacy/history scans, desktop interaction check, and 390px
mobile layout check passed on 2026-08-20. The demo continues to show physical
benchmark and public-replay blockers honestly while those gates are incomplete.

```bash
cd frontend
npm ci
npm run build:static
cd ..
python scripts/verify_static_demo.py
```

`VITE_RUNTIME_MODE=STATIC_EVIDENCE` makes Vite resolve a dedicated application entry. The resulting browser application contains only checked-in fixtures and local play/pause/speed/reset/scenario controls. It excludes the live application module, auth/session code, API clients, WebSocket clients, map tiles, remote fonts, and remote stylesheets. It needs no secrets and performs no automatic external request.

Every rendered view permanently states `RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC`. The fixture includes a routine synthetic control, synthetic abrupt evidence, synthetic gradual evidence, the measured frozen-policy synthetic results, the honestly blocked physical benchmark, and the honestly blocked public-candidate replication. A blocked result is not shown as zero, nominal, or successful.

Configure `frontend/` as the Vercel project root. Its `vercel.json` runs the
static-evidence build and serves only `dist`. Keeping the deployment boundary at
`frontend/` prevents Vercel's monorepo service detection from selecting the
FastAPI or replay services. Vercel hosts only the generated immutable files; it
does not host FastAPI, PostgreSQL, the SBS sidecar, or persistent WebSockets. The
authoritative operational demo remains the local feeder Compose deployment.
