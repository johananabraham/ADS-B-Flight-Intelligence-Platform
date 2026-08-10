"""Safety-agent trace lifecycle and privacy-default tests."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.observability.safety_tracing import SafetyTrace, create_safety_trace
from app.safety import agent


def test_disabled_export_still_returns_valid_local_trace_id():
    trace = create_safety_trace(settings=Settings(langfuse_enabled=False))

    assert len(trace.trace_id) == 32
    assert int(trace.trace_id, 16) >= 0
    assert trace.content("sensitive", {"redacted": True}) == {"redacted": True}

    with trace.agent(query="sensitive query", session_id="session-1"):
        with trace.tool(name="search", arguments={"query": "sensitive"}) as span:
            span.update(output={"result_count": 1})


def test_explicit_content_capture_preserves_observation_payloads():
    trace = SafetyTrace(trace_id="a" * 32, client=None, capture_content=True)

    assert trace.content("full content", {"redacted": True}) == "full content"


class RecordingObservation:
    def __init__(self, record: dict):
        self.record = record

    def update(self, **attributes):
        self.record.setdefault("updates", []).append(attributes)


class FakeLangfuseClient:
    def __init__(self):
        self.records = []

    def get_trace_url(self, *, trace_id):
        return f"https://langfuse.example/trace/{trace_id}"

    @contextmanager
    def start_as_current_observation(self, **attributes):
        record = {"attributes": attributes}
        self.records.append(record)
        yield RecordingObservation(record)


def test_langfuse_adapter_builds_agent_generation_and_tool_tree():
    client = FakeLangfuseClient()
    trace = SafetyTrace(trace_id="c" * 32, client=client, capture_content=False)

    with trace.agent(query="sensitive query", session_id="session-1"):
        with trace.generation(
            iteration=1,
            model="test-model",
            messages=[{"role": "user", "content": "sensitive query"}],
            temperature=0.1,
        ) as generation:
            generation.update(usage_details={"total_tokens": 3})
        with trace.tool(name="search", arguments={"query": "sensitive"}) as tool:
            tool.update(output={"result_count": 1})
        trace.complete(
            SimpleNamespace(answer="answer", citations=(), tool_calls=(), error=None)
        )

    assert trace.trace_url == f"https://langfuse.example/trace/{'c' * 32}"
    assert [record["attributes"]["as_type"] for record in client.records] == [
        "agent",
        "generation",
        "tool",
    ]
    assert client.records[0]["attributes"]["input"] == {
        "query_characters": len("sensitive query"),
        "content_capture": False,
    }
    assert client.records[1]["attributes"]["input"]["message_count"] == 1
    assert client.records[2]["attributes"]["input"]["argument_names"] == ["query"]


class RecordingTrace:
    def __init__(self):
        self.trace_id = "b" * 32
        self.trace_url = None
        self.records = []
        self.completed = None

    @contextmanager
    def agent(self, **attributes):
        self.records.append(("agent", attributes))
        yield self

    @contextmanager
    def generation(self, **attributes):
        record = {"type": "generation", "attributes": attributes}
        self.records.append(record)
        yield RecordingObservation(record)

    @contextmanager
    def tool(self, **attributes):
        record = {"type": "tool", "attributes": attributes}
        self.records.append(record)
        yield RecordingObservation(record)

    def content(self, _value, summary):
        return summary

    def complete(self, response):
        self.completed = response


class FakeMessage:
    def __init__(self, *, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **_kwargs):
        return {"content": self.content, "tool_calls": bool(self.tool_calls)}


class FakeUsage:
    total_tokens = 7

    def model_dump(self, **_kwargs):
        return {"total_tokens": self.total_tokens}


def _response(message, finish_reason):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=FakeUsage(),
    )


@pytest.mark.asyncio
async def test_agent_records_each_generation_and_tool_call(monkeypatch):
    function = SimpleNamespace(name="test_tool", arguments='{"query":"fuel"}')
    tool_call = SimpleNamespace(id="call-1", function=function)
    responses = iter(
        [
            _response(FakeMessage(tool_calls=[tool_call]), "tool_calls"),
            _response(FakeMessage(content="Answer from TEST24LA001.", tool_calls=None), "stop"),
        ]
    )
    completions = SimpleNamespace(create=lambda **_kwargs: next(responses))
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    trace = RecordingTrace()

    async def test_tool(**_kwargs):
        return {"total_results": 1, "results": []}

    settings = SimpleNamespace(
        agent_max_iterations=3,
        agent_temperature=0.1,
        llm_api_key="test-key",
        openai_api_key="",
        llm_base_url="https://example.invalid/v1",
        llm_model="test-model",
    )
    monkeypatch.setattr(agent, "get_settings", lambda: settings)
    monkeypatch.setattr(agent, "create_safety_trace", lambda **_kwargs: trace)
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)
    monkeypatch.setattr(agent, "TOOL_REGISTRY", {"test_tool": test_tool})

    result = await agent.run_agent("Find fuel incidents", session_id="session-1")

    assert result.trace_id == "b" * 32
    assert result.total_tokens == 14
    assert result.iterations == 2
    assert [record["type"] for record in trace.records if isinstance(record, dict)] == [
        "generation",
        "tool",
        "generation",
    ]
    assert trace.completed is result
