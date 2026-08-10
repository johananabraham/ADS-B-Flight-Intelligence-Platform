"""Aviation Safety Research module - RAG-powered NTSB/FAA research."""

from .tools import (
    tool_search_incident_narratives,
    tool_query_incident_database,
    tool_search_faa_regulations,
    tool_get_incident_detail,
    tool_get_aircraft_safety_context,
    TOOL_REGISTRY,
)
from .agent import run_agent, AgentResponse
from .schemas import get_tool_definitions
from .ingestion import get_ingestion_status
from .evaluation import (
    DEFAULT_RETRIEVAL_CONFIGURATION,
    RetrievalConfiguration,
    RetrievalDataset,
    RetrievalEvaluationReport,
    compare_retrieval_baseline,
    evaluate_retrieval_dataset,
    load_retrieval_dataset,
)

__all__ = [
    # Tools
    "tool_search_incident_narratives",
    "tool_query_incident_database",
    "tool_search_faa_regulations",
    "tool_get_incident_detail",
    "tool_get_aircraft_safety_context",
    "TOOL_REGISTRY",
    # Agent
    "run_agent",
    "AgentResponse",
    "get_tool_definitions",
    # Ingestion
    "get_ingestion_status",
    # Evaluation
    "DEFAULT_RETRIEVAL_CONFIGURATION",
    "RetrievalConfiguration",
    "RetrievalDataset",
    "RetrievalEvaluationReport",
    "compare_retrieval_baseline",
    "evaluate_retrieval_dataset",
    "load_retrieval_dataset",
]
