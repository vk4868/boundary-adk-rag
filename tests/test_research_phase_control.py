"""Offline tests for required research phases and reviewer budget reservation."""

from dataclasses import dataclass

import pytest
from google.adk.models import LlmRequest
from google.adk.tools.set_model_response_tool import SetModelResponseTool
from google.genai import types

from app.agents import build_agent
from app.config import Settings
from app.index import IndexRepository
from app.models import ResearchDraft
from app.tools import BudgetExceeded, RunLedger


@dataclass
class FakeContext:
    agent_name: str


@pytest.fixture
def pipeline(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="vertex",
        google_cloud_project="offline-phase-test",
        google_cloud_location="global",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
        app_max_model_calls=8,
        app_max_output_tokens=7200,
    )
    ledger = RunLedger("offline-phase-run")
    agent = build_agent(
        settings,
        IndexRepository(settings),
        ledger,
        settings.app_server_role,
    )
    return settings, ledger, agent


def _request(researcher) -> LlmRequest:
    tools = {tool.name: tool for tool in researcher.tools}
    formatter = SetModelResponseTool(ResearchDraft)
    tools[formatter.name] = formatter
    return LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="question")])],
        tools_dict=tools,
    )


def _allowed(request: LlmRequest) -> tuple[str, list[str]]:
    config = request.config.tool_config.function_calling_config
    return config.mode.value, config.allowed_function_names or []


def test_required_tool_phases_use_native_function_calling(pipeline):
    _settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    callback = researcher.before_model_callback
    context = FakeContext("document_researcher")

    request = _request(researcher)
    callback(context, request)
    assert _allowed(request) == ("ANY", ["list_sources"])

    ledger.reset("search-phase")
    ledger.listed_sources_successfully = True
    request = _request(researcher)
    callback(context, request)
    assert _allowed(request) == ("ANY", ["search_documents"])

    ledger.reset("read-phase")
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    request = _request(researcher)
    callback(context, request)
    assert _allowed(request) == ("ANY", ["read_evidence"])


def test_zero_hit_search_forces_structured_abstention(pipeline):
    _settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = set()
    request = _request(researcher)

    researcher.before_model_callback(FakeContext("document_researcher"), request)

    assert _allowed(request) == ("ANY", ["set_model_response"])
    assert "insufficient_evidence" in str(request.config.system_instruction)


def test_read_evidence_allows_auto_until_reserved_formatter_call(pipeline):
    settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    ledger.read_evidence_ids = {"source:p0001"}

    request = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), request)
    assert _allowed(request) == ("AUTO", [])

    ledger.model_calls = settings.app_max_model_calls - 3
    request = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), request)
    assert _allowed(request) == ("ANY", ["set_model_response"])


def test_reviewer_slot_cannot_be_consumed_by_researcher(pipeline):
    settings, ledger, agent = pipeline
    researcher, reviewer = agent.sub_agents[:2]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    ledger.read_evidence_ids = {"source:p0001"}
    ledger.model_calls = settings.app_max_model_calls - 1

    with pytest.raises(BudgetExceeded, match="reviewer"):
        researcher.before_model_callback(
            FakeContext("document_researcher"), _request(researcher)
        )

    reviewer_request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="review")])],
    )
    reviewer.before_model_callback(FakeContext("evidence_reviewer"), reviewer_request)
    assert ledger.model_calls == settings.app_max_model_calls


def test_boundary_reads_then_formats_and_cannot_start_another_search(pipeline):
    settings, ledger, agent = pipeline
    researcher, reviewer = agent.sub_agents[:2]
    context = FakeContext("document_researcher")

    # At pre-call five, an already selected page may still be read on call six.
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 2
    ledger.last_search_hit_ids = {"source:p0002"}
    ledger.read_evidence_ids = {"source:p0001"}
    ledger.model_calls = settings.app_max_model_calls - 3
    request = _request(researcher)
    researcher.before_model_callback(context, request)
    assert _allowed(request) == ("ANY", ["read_evidence"])

    # Once that page is read, call seven must format instead of starting a new
    # search, leaving call eight for the independent reviewer.
    ledger.read_evidence_ids.add("source:p0002")
    ledger.model_calls = settings.app_max_model_calls - 2
    request = _request(researcher)
    researcher.before_model_callback(context, request)
    assert _allowed(request) == ("ANY", ["set_model_response"])

    ledger.model_calls = settings.app_max_model_calls - 1
    reviewer_request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="review")])],
    )
    reviewer.before_model_callback(
        FakeContext("evidence_reviewer"), reviewer_request
    )
    assert ledger.model_calls == settings.app_max_model_calls
