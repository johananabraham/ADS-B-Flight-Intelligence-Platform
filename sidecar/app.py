"""Read-only local REST, WebSocket, metrics, and UI transport."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse

from integrity_core import EvidenceKind, TrackState, load_policy

from .config import SidecarConfig
from .service import SidecarRuntime
from .store import RotatingEventStore
from integrity_core import IntegrityEngine


def create_app(config: SidecarConfig | None = None, *, start_ingestion: bool = True) -> FastAPI:
    selected = config or SidecarConfig.from_env()
    policy = load_policy(selected.policy_path)
    store = RotatingEventStore(
        selected.event_directory,
        retention_hours=selected.retention_hours,
        max_bytes=selected.store_max_mb * 1024 * 1024,
    )
    runtime = SidecarRuntime(selected, IntegrityEngine(policy), store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_ingestion:
            await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(
        title="ADS-B Feeder Integrity Sidecar",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.runtime = runtime

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self' ws: wss:; img-src 'self' data:"
        )
        return response

    @app.get("/api/v1/integrity/health")
    async def health():
        return runtime.health_dict()

    @app.get("/api/v1/integrity/tracks")
    async def tracks(limit: int = Query(100, ge=1, le=1000)):
        return {
            "schema_version": "1.0",
            "tracks": [item.public_dict() for item in runtime.engine.snapshots()[:limit]],
        }

    @app.get("/api/v1/integrity/tracks/{track_id}")
    async def track(track_id: str):
        snapshot = runtime.engine.snapshot(track_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="track not found")
        result = snapshot.public_dict()
        result["recent_events"] = runtime.store.query(track_id=track_id, limit=50)
        return result

    @app.get("/api/v1/integrity/events")
    async def events(
        since: datetime | None = None,
        state: TrackState | None = None,
        kind: EvidenceKind | None = None,
        limit: int = Query(100, ge=1, le=1000),
    ):
        return {
            "schema_version": "1.0",
            "events": runtime.store.query(
                since=since,
                state=state.value if state else None,
                kind=kind.value if kind else None,
                limit=limit,
            ),
        }

    @app.websocket("/api/v1/integrity/stream")
    async def stream(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "hello",
                "schema_version": "1.0",
                "policy_version": policy.policy_version,
            }
        )
        queue = runtime.subscribe()
        try:
            while True:
                await websocket.send_json(await queue.get())
        except WebSocketDisconnect:
            pass
        finally:
            runtime.unsubscribe(queue)

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        return PlainTextResponse(
            runtime.metrics.render(runtime.engine.snapshots()),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    static = Path(__file__).parent / "static"

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    @app.get("/assets/{name}")
    async def asset(name: str):
        if name not in {"app.css", "app.js"}:
            raise HTTPException(status_code=404, detail="asset not found")
        return FileResponse(static / name)

    return app
