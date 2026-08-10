"""ReAct-style agent for aviation safety research."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import OpenAI

from .citations import SourceCitation, extract_grounded_citations
from .prompts import SYSTEM_PROMPT, CITATION_INSTRUCTIONS
from .schemas import get_tool_definitions
from .tools import TOOL_REGISTRY
from ..core.config import get_settings

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
    citations: tuple[SourceCitation, ...] = ()
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


async def run_agent(
    query: str,
    max_iterations: Optional[int] = None,
) -> AgentResponse:
    """Run the aviation safety research agent."""
    settings = get_settings()
    max_iter = max_iterations or settings.agent_max_iterations

    api_key = settings.llm_api_key or settings.openai_api_key
    if not api_key:
        return AgentResponse(answer="", error="No LLM API key configured")

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
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=settings.agent_temperature,
            )

            if response.usage:
                total_tokens += response.usage.total_tokens

            message = response.choices[0].message

            if message.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in message.tool_calls
                    ],
                })

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    start = time.time()
                    if tool_name in TOOL_REGISTRY:
                        result = await TOOL_REGISTRY[tool_name](**tool_args)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    duration = (time.time() - start) * 1000

                    tool_calls_made.append(ToolCall(tool_name, tool_args, result, duration))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    })
            else:
                answer = message.content or ""
                return AgentResponse(
                    answer=answer,
                    citations=extract_grounded_citations(answer, tool_calls_made),
                    tool_calls=tool_calls_made,
                    iterations=iteration + 1,
                    total_tokens=total_tokens,
                )

        return AgentResponse(
            answer="Max iterations reached.",
            tool_calls=tool_calls_made,
            iterations=max_iter,
            total_tokens=total_tokens,
        )

    except Exception as e:
        logger.error(f"Agent error: {e}")
        return AgentResponse(answer="", tool_calls=tool_calls_made, error=str(e))
