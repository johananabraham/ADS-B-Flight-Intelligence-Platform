"""Grounded safety citation contract tests."""

from types import SimpleNamespace

import pytest

from app.api import safety as safety_api
from app.safety.agent import AgentResponse
from app.safety.citations import SourceCitation, SourceSpan, extract_grounded_citations


def _tool_call(name: str, result: dict):
    return SimpleNamespace(name=name, result=result)


def test_citations_require_both_retrieval_and_final_answer_reference():
    calls = [
        _tool_call(
            "search_faa_regulations",
            {
                "results": [
                    {
                        "cfr_reference": "14 CFR 91.103",
                        "document_id": "14:91:91.103:2026-07-24",
                        "text_excerpt": "Preflight action\nEach pilot in command shall...",
                        "section": "91.103",
                        "char_start": 0,
                        "char_end": 49,
                        "effective_date": "2026-07-24",
                        "source_url": "https://www.ecfr.gov/current/title-14/section-91.103",
                        "source_sha256": "a" * 64,
                        "source_run_id": "run-1",
                    }
                ]
            },
        ),
        _tool_call(
            "search_incident_narratives",
            {
                "results": [
                    {
                        "ntsb_id": "TEST24LA001",
                        "excerpt": "Probable Cause:\nA synthetic test narrative.",
                    }
                ]
            },
        ),
    ]

    citations = extract_grounded_citations(
        "The relevant preflight rule is 14 CFR 91.103.",
        calls,
    )

    assert len(citations) == 1
    assert citations[0].label == "14 CFR 91.103"
    assert citations[0].effective_date == "2026-07-24"
    assert citations[0].span.section == "91.103"


def test_unretrieved_reference_is_not_presented_as_grounded():
    assert extract_grounded_citations("See 14 CFR 91.103.", []) == ()


def test_non_http_source_url_is_not_exposed_to_the_frontend():
    calls = [
        _tool_call(
            "search_incident_narratives",
            {
                "results": [
                    {
                        "ntsb_id": "TEST24LA001",
                        "excerpt": "Synthetic evidence",
                        "source_url": "javascript:alert(1)",
                    }
                ]
            },
        )
    ]

    citation = extract_grounded_citations("See TEST24LA001.", calls)[0]

    assert citation.source_url is None


@pytest.mark.asyncio
async def test_query_api_returns_typed_citations(monkeypatch):
    citation = SourceCitation(
        source_type="ECFR_REGULATION",
        label="14 CFR 91.103",
        source_url="https://www.ecfr.gov/current/title-14/section-91.103",
        effective_date="2026-07-24",
        span=SourceSpan(section="91.103", char_start=0, char_end=16, text="Preflight action"),
    )

    async def fake_run_agent(_query: str):
        return AgentResponse(answer="See 14 CFR 91.103.", citations=(citation,))

    monkeypatch.setattr(safety_api, "run_agent", fake_run_agent)

    response = await safety_api.safety_query(
        safety_api.QueryRequest(query="What preflight rule applies?")
    )

    assert response.citations == [citation]
    assert response.citations[0].span.text == "Preflight action"
