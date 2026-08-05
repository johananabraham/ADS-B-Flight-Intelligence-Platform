"""HTTP control surface for recorded replay."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.replay.controller import ReplayController


class ControlCommand(BaseModel):
    action: Literal["pause", "resume", "restart", "seek", "speed"]
    value: float | None = None


def create_control_app(controller: ReplayController) -> FastAPI:
    app = FastAPI(title="Recorded Replay Control", version="1.0.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/status")
    async def status() -> dict[str, object]:
        return (await controller.status()).to_dict()

    @app.post("/commands")
    async def command(request: ControlCommand) -> dict[str, object]:
        try:
            if request.action == "pause":
                snapshot = await controller.pause()
            elif request.action == "resume":
                snapshot = await controller.resume()
            elif request.action == "restart":
                snapshot = await controller.restart()
            elif request.action == "seek":
                if request.value is None:
                    raise ValueError("seek requires a value in seconds")
                snapshot = await controller.seek(request.value)
            else:
                if request.value is None:
                    raise ValueError("speed requires a value")
                snapshot = await controller.set_speed(request.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return snapshot.to_dict()

    return app
