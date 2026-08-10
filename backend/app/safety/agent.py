"""ReAct-style agent for aviation safety research."""

import json
import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Optional

from openai import OpenAI

from ..core.config import get_settings
from ..observability import SafetyTrace, create_safety_trace
from .citations import SourceCitation, extract_grounded_citations
from .prompts import SYSTEM_PROMPT, CITATION_INSTRUCTIONS
from .schemas import get_tool_definitions
from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: Any
    duration_ms: float


@dataclass
class AgentResponse:
    answer: str
    trace_id: str = ""
    trace_url: str | None = None
    citations: tuple[SourceCitation, ...] = ()
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


def _complete(trace: SafetyTrace, **response_fields: Any) -> AgentResponse:
    response = AgentResponse(
        trace_id=trace.trace_id,
        trace_url=trace.trace_url,
        **response_fields,
    )
    trace.complete(response)
    return response


def _call_model(
    *,
    client: OpenAI,
    trace: SafetyTrace,
    settings: Any,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    iteration: int,
) -> Any:
    with trace.generation(
        iteration=iteration,
        model=settings.llm_model,
        messages=messages,
        temperature=settings.agent_temperature,
    ) as generation:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=settings.agent_temperature,
        )
        choice = response.choices[0]
        generation.update(
            output=trace.content(
                choice.message.model_dump(mode="json"),
                {
                    "finish_reason": choice.finish_reason,
                    "has_tool_calls": bool(choice.message.tool_calls),
                },
            ),
            usage_details=(
                response.usage.model_dump(mode="json") if response.usage else None
            ),
        )
        return response


def _assistant_tool_message(message: Any) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ],
    }


async def _execute_tool(
    trace: SafetyTrace,
    *,
    name: str,
    arguments: dict[str, Any],
) -> ToolCall:
    with trace.tool(name=name, arguments=arguments) as tool_span:
        started = perf_counter()
        implementation = TOOL_REGISTRY.get(name)
        result = (
            await implementation(**arguments)
            if implementation
            else {"error": f"Unknown tool: {name}"}
        )
        duration_ms = (perf_counter() - started) * 1_000
        tool_span.update(
            output=trace.content(
                result,
                {
                    "result_keys": sorted(result),
                    "result_count": result.get("total_results"),
                    "error": bool(result.get("error")),
                },
            ),
            metadata={"duration_ms": duration_ms},
        )
    return ToolCall(name, arguments, result, duration_ms)


async def run_agent(
    query: str,
    session_id: str | None = None,
    max_iterations: Optional[int] = None,
) -> AgentResponse:
    """Run the aviation safety research agent."""
    settings = get_settings()
    trace = create_safety_trace(settings=settings)
    max_iter = max_iterations or settings.agent_max_iterations

    with trace.agent(query=query, session_id=session_id):
        api_key = settings.llm_api_key or settings.openai_api_key
        if not api_key:
            return _complete(
                trace,
                answer="",
                error="No LLM API key configured",
            )

        base_url = settings.llm_base_url if settings.llm_api_key else None
        client = OpenAI(api_key=api_key, base_url=base_url)
        tools = get_tool_definitions()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + CITATION_INSTRUCTIONS},
            {"role": "user", "content": query},
        ]

        tool_calls_made = []
        total_tokens = 0

        try:
            for iteration in range(max_iter):
                response = _call_model(
                    client=client,
                    trace=trace,
                    settings=settings,
                    messages=messages,
                    tools=tools,
                    iteration=iteration + 1,
                )

                if response.usage:
                    total_tokens += response.usage.total_tokens

                message = response.choices[0].message

                if message.tool_calls:
                    messages.append(_assistant_tool_message(message))

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                        completed_call = await _execute_tool(
                            trace,
                            name=tool_name,
                            arguments=tool_args,
                        )
                        tool_calls_made.append(completed_call)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(completed_call.result, default=str),
                        })
                else:
                    answer = message.content or ""
                    return _complete(
                        trace,
                        answer=answer,
                        citations=extract_grounded_citations(answer, tool_calls_made),
                        tool_calls=tool_calls_made,
                        iterations=iteration + 1,
                        total_tokens=total_tokens,
                    )

            return _complete(
                trace,
                answer="Max iterations reached.",
                tool_calls=tool_calls_made,
                iterations=max_iter,
                total_tokens=total_tokens,
            )

        except Exception as error:
            logger.error("Agent error: %s", error)
            return _complete(
                trace,
                answer="",
                tool_calls=tool_calls_made,
                error=str(error),
            )
