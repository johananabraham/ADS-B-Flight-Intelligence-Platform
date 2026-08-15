# Safety Agent Observability v1

## Trace structure

Every `POST /api/v1/safety/query` response contains a 32-character trace ID. The
ID exists even when external export is disabled, so API logs and user bug reports
can still refer to one request consistently.

When Langfuse export is enabled, the trace contains:

```text
aviation-safety-query (agent)
├── agent-generation-1 (generation)
├── search_incident_narratives (tool)
├── agent-generation-2 (generation)
├── search_faa_regulations (tool)
└── agent-generation-3 (generation)
```

Generation observations record model, temperature, iteration, token usage, and
whether a tool was requested. Tool observations record tool name, argument names,
result shape/count, errors, and measured duration. The root records final answer
length, citation count, tool-call count, and error state.

## Privacy default

Prompt text, model output, tool arguments, and retrieved source text are not
exported by default. Set `LANGFUSE_CAPTURE_CONTENT=true` only for data that is
approved for the configured Langfuse project. This switch is separate from
`LANGFUSE_ENABLED` so enabling operational telemetry does not silently enable
content collection.

## Configuration

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_ENVIRONMENT=development
LANGFUSE_CAPTURE_CONTENT=false
```

Queries can include an optional `session_id` (maximum 200 characters). The web UI
creates one session ID while the research panel is mounted, allowing related
questions to be grouped without storing a user identity.

The integration uses Langfuse Python SDK v4 context-managed observations and W3C
trace IDs. Relevant upstream references are the Langfuse
[Get Started](https://langfuse.com/docs/observability/get-started),
[Trace IDs](https://langfuse.com/docs/observability/features/trace-ids-and-distributed-tracing),
and [Sessions](https://langfuse.com/docs/observability/features/sessions) guides.

## Evidence boundary

Unit tests prove local trace IDs, disabled-export behavior, privacy redaction,
explicit content capture, and nested generation/tool lifecycle recording. A real
Langfuse cloud trace cannot be claimed until project credentials are configured
and a live query is inspected in that project.
