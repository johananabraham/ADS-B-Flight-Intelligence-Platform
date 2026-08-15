"""Opt-in Langfuse tracing for the direct safety-agent loop."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from uuid import uuid4

from ..core.config import Settings, get_settings


logger = logging.getLogger(__name__)


class TraceObservation:
    """Uniform update interface for active and disabled observations."""

    def __init__(self, observation: Any | None = None) -> None:
        self._observation = observation

    def update(self, **attributes: Any) -> None:
        if self._observation is not None:
            self._observation.update(**attributes)


class SafetyTrace:
    """One request trace with nested generation and tool observations."""

    def __init__(
        self,
        *,
        trace_id: str,
        client: Any | None,
        capture_content: bool,
    ) -> None:
        self.trace_id = trace_id
        self.trace_url = client.get_trace_url(trace_id=trace_id) if client else None
        self._client = client
        self._capture_content = capture_content
        self._root = TraceObservation()

    def content(self, value: Any, summary: Any) -> Any:
        """Return full content only when explicitly enabled."""
        return value if self._capture_content else summary

    @contextmanager
    def agent(self, *, query: str, session_id: str | None):
        """Create the root agent observation and propagate request attributes."""
        if self._client is None:
            yield self
            return

        input_payload = self.content(
            {"query": query},
            {"query_characters": len(query), "content_capture": False},
        )
        with self._client.start_as_current_observation(
            trace_context={"trace_id": self.trace_id},
            name="aviation-safety-query",
            as_type="agent",
            input=input_payload,
            metadata={"content_capture": self._capture_content},
        ) as root:
            self._root = TraceObservation(root)
            propagated = {
                "trace_name": "aviation-safety-query",
                "tags": ["safety-agent", "direct-function-calling"],
                "version": "1.0",
            }
            if session_id:
                propagated["session_id"] = session_id
            try:
                from langfuse import propagate_attributes
            except ImportError:
                yield self
            else:
                with propagate_attributes(**propagated):
                    yield self

    @contextmanager
    def generation(
        self,
        *,
        iteration: int,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
    ):
        """Create one model-generation observation."""
        if self._client is None:
            yield TraceObservation()
            return
        input_payload = self.content(
            {"messages": messages},
            {"message_count": len(messages), "content_capture": False},
        )
        with self._client.start_as_current_observation(
            name=f"agent-generation-{iteration}",
            as_type="generation",
            model=model,
            model_parameters={"temperature": temperature},
            input=input_payload,
            metadata={"iteration": iteration},
        ) as observation:
            yield TraceObservation(observation)

    @contextmanager
    def tool(self, *, name: str, arguments: dict[str, Any]):
        """Create one nested tool observation."""
        if self._client is None:
            yield TraceObservation()
            return
        input_payload = self.content(
            arguments,
            {"argument_names": sorted(arguments), "content_capture": False},
        )
        with self._client.start_as_current_observation(
            name=name,
            as_type="tool",
            input=input_payload,
        ) as observation:
            yield TraceObservation(observation)

    def complete(self, response: Any) -> None:
        """Record the final request outcome without forcing content capture."""
        self._root.update(
            output=self.content(
                {"answer": response.answer},
                {
                    "answer_characters": len(response.answer),
                    "citation_count": len(response.citations),
                    "tool_call_count": len(response.tool_calls),
                    "error": bool(response.error),
                },
            ),
            level="ERROR" if response.error else "DEFAULT",
            status_message=response.error,
        )


@lru_cache(maxsize=4)
def _langfuse_client(
    public_key: str,
    secret_key: str,
    base_url: str,
    environment: str,
) -> Any | None:
    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning(
            "Langfuse tracing requested but the optional package is unavailable; "
            "using local trace IDs only"
        )
        return None
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        environment=environment,
        tracing_enabled=True,
    )


def _configured_client(settings: Settings) -> Any | None:
    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "Langfuse tracing enabled without both credentials; "
            "using local trace IDs only"
        )
        return None
    return _langfuse_client(
        settings.langfuse_public_key,
        settings.langfuse_secret_key,
        settings.langfuse_base_url,
        settings.langfuse_environment,
    )


def create_safety_trace(*, settings: Settings | None = None) -> SafetyTrace:
    """Create a valid correlation ID whether or not export is configured."""
    resolved_settings = settings or get_settings()
    return SafetyTrace(
        trace_id=uuid4().hex,
        client=_configured_client(resolved_settings),
        capture_content=resolved_settings.langfuse_capture_content,
    )
