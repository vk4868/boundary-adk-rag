"""Offline tests for required research phases and reviewer budget reservation."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from google.adk.models import LlmRequest
from google.adk.tools.set_model_response_tool import SetModelResponseTool
from google.genai import types

from app.agents import build_agent
from app.config import Settings
from app.index import IndexRepository
from app.models import (
    CorpusIndex,
    EmbeddingDescriptor,
    PageRecord,
    ResearchDraft,
    SourceRecord,
)
from app.tools import BudgetExceeded, RunLedger


@dataclass
class FakeContext:
    agent_name: str


@pytest.fixture
def pipeline(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_embedding_provider="ollama",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
        app_max_model_calls=8,
        app_max_output_tokens=7200,
    )
    ledger = RunLedger("offline-phase-run")
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[
            SourceRecord(
                source_id="source",
                title="Test source",
                version="test",
                scope="test",
                competition="MCC",
                allowed_roles=["analyst"],
                page_count=3,
                sha256="a" * 64,
            )
        ],
        pages=[
            PageRecord(
                evidence_id=f"source:p{page:04d}",
                source_id="source",
                page=page,
                text=f"page {page}",
            )
            for page in (1, 2, 3)
        ],
    )
    agent = build_agent(
        settings,
        repository,
        ledger,
        settings.app_server_role,
    )
    return settings, ledger, agent


def _request(researcher) -> LlmRequest:
    formatter = SetModelResponseTool(ResearchDraft)
    request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="question")])],
    )
    request.append_tools([formatter, *researcher.tools])
    return request


def _allowed(request: LlmRequest) -> tuple[str, list[str]]:
    config = request.config.tool_config.function_calling_config
    return config.mode.value, config.allowed_function_names or []


def _declaration(request: LlmRequest, name: str):
    return next(
        declaration
        for tool in request.config.tools or []
        for declaration in tool.function_declarations or []
        if declaration.name == name
    )


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
    instruction = request.config.system_instruction
    assert "respond only with a tool call" in str(instruction)
    assert "`search_documents`" in str(instruction)
    assert request.contents[-1].role == "user"
    assert "`search_documents`" in request.contents[-1].parts[0].text
    search_declaration = _declaration(request, "search_documents")
    source_schema = search_declaration.parameters_json_schema["properties"][
        "source_ids"
    ]
    array_schema = next(
        choice for choice in source_schema["anyOf"] if choice.get("type") == "array"
    )
    assert array_schema["items"]["enum"] == ["source"]

    ledger.reset("read-phase")
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    ledger.issued_evidence_ids = {"source:p0001"}
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
    assert "`evidence_ids`" in request.contents[-1].parts[0].text
    formatter_schema = _declaration(
        request, "set_model_response"
    ).parameters_json_schema
    assert "$defs" not in formatter_schema
    claim_schema = formatter_schema["properties"]["claims"]["items"]
    assert "$ref" not in claim_schema
    assert claim_schema["required"] == ["text", "evidence_ids"]
    assert claim_schema["properties"]["evidence_ids"]["type"] == "array"


def test_invalid_search_source_is_rejected_before_tool_dispatch(pipeline):
    _settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    search_tool = next(tool for tool in researcher.tools if tool.name == "search_documents")

    result = researcher.before_tool_callback(
        search_tool,
        {"query": "overs", "source_ids": ["invented_source"]},
        SimpleNamespace(),
    )

    assert result == {
        "error": (
            "The source filter is invalid. Use exact source_id values returned by "
            "list_sources, or use an empty list to search all authorized sources."
        )
    }
    assert ledger.tool_calls == 1
    assert ledger.successful_searches == 0


def test_read_evidence_allows_auto_until_reserved_formatter_call(pipeline):
    settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    ledger.issued_evidence_ids = {"source:p0001"}
    ledger.read_evidence_ids = {"source:p0001"}

    request = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), request)
    assert _allowed(request) == ("AUTO", [])
    assert "respond only with one tool call" in request.contents[-1].parts[0].text
    assert "`set_model_response`" in request.contents[-1].parts[0].text
    formatter_schema = _declaration(
        request, "set_model_response"
    ).parameters_json_schema
    assert "$defs" not in formatter_schema
    claim_schema = formatter_schema["properties"]["claims"]["items"]
    assert "$ref" not in claim_schema
    assert claim_schema["required"] == ["text", "evidence_ids"]
    assert "exact field `evidence_ids`" in str(request.config.system_instruction)

    ledger.model_calls = settings.app_max_model_calls - 3
    request = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), request)
    assert _allowed(request) == ("ANY", ["set_model_response"])


def test_reading_explicit_adjacent_context_satisfies_current_search_read(pipeline):
    _settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0002"}
    ledger.last_search_issued_ids = {
        "source:p0001",
        "source:p0002",
        "source:p0003",
    }
    ledger.issued_evidence_ids = set(ledger.last_search_issued_ids)
    ledger.read_evidence_ids = {"source:p0003"}

    request = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), request)

    assert _allowed(request) == ("AUTO", [])


def test_ordinary_read_gets_one_correction_then_forces_abstention(pipeline):
    _settings, ledger, agent = pipeline
    researcher = agent.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0002"}
    ledger.last_search_issued_ids = {"source:p0001", "source:p0002"}
    ledger.issued_evidence_ids = set(ledger.last_search_issued_ids)
    ledger.ordinary_read_failures = 1

    corrective = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), corrective)
    assert _allowed(corrective) == ("ANY", ["read_evidence"])
    assert "one corrective read" in str(corrective.config.system_instruction)

    ledger.ordinary_read_failures = 2
    abstain = _request(researcher)
    researcher.before_model_callback(FakeContext("document_researcher"), abstain)
    assert _allowed(abstain) == ("ANY", ["set_model_response"])
    assert "insufficient_evidence" in str(abstain.config.system_instruction)


def test_original_question_state_is_overwritten_for_each_invocation(pipeline):
    _settings, ledger, agent = pipeline
    state = {"original_question": "stale prior question"}
    first = SimpleNamespace(
        invocation_id="first",
        user_content=types.Content(
            role="user", parts=[types.Part(text="current first question")]
        ),
        state=state,
    )
    agent.before_agent_callback(first)
    assert state["original_question"] == "current first question"
    assert ledger.original_question == "current first question"

    second = SimpleNamespace(
        invocation_id="second",
        user_content=types.Content(
            role="user", parts=[types.Part(text="new question")]
        ),
        state=state,
    )
    agent.before_agent_callback(second)
    assert state["original_question"] == "new question"
    assert ledger.original_question == "new question"
    assert "{original_question}" in agent.sub_agents[1].instruction


def test_reviewer_slot_cannot_be_consumed_by_researcher(pipeline):
    settings, ledger, agent = pipeline
    researcher, reviewer = agent.sub_agents[:2]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_hit_ids = {"source:p0001"}
    ledger.issued_evidence_ids = {"source:p0001"}
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


def test_invalid_reviewer_call_at_global_limit_cannot_start_ninth_call(pipeline):
    settings, ledger, agent = pipeline
    reviewer = agent.sub_agents[1]
    ledger.model_calls = settings.app_max_model_calls - 1

    reviewer.before_model_callback(
        FakeContext("evidence_reviewer"),
        LlmRequest(
            model="offline",
            contents=[types.Content(role="user", parts=[types.Part(text="review")])],
        ),
    )
    assert ledger.model_calls == settings.app_max_model_calls

    with pytest.raises(BudgetExceeded, match="model-call budget"):
        reviewer.before_model_callback(
            FakeContext("evidence_reviewer"), LlmRequest(model="offline")
        )


def test_reviewer_call_seven_permits_exactly_one_correction_on_call_eight(pipeline):
    settings, ledger, agent = pipeline
    reviewer = agent.sub_agents[1]
    ledger.model_calls = settings.app_max_model_calls - 2

    reviewer.before_model_callback(
        FakeContext("evidence_reviewer"), LlmRequest(model="offline")
    )
    assert ledger.model_calls == settings.app_max_model_calls - 1

    reviewer.after_tool_callback(
        reviewer.tools[0],
        {},
        SimpleNamespace(),
        {"error": "typed ReviewDecision validation failed"},
    )
    correction = LlmRequest(model="offline")
    reviewer.before_model_callback(FakeContext("evidence_reviewer"), correction)
    assert ledger.model_calls == settings.app_max_model_calls
    assert "typed ReviewDecision validation failed" in correction.contents[0].parts[0].text

    with pytest.raises(BudgetExceeded, match="model-call budget"):
        reviewer.before_model_callback(
            FakeContext("evidence_reviewer"), LlmRequest(model="offline")
        )


def test_boundary_reads_then_formats_and_cannot_start_another_search(pipeline):
    settings, ledger, agent = pipeline
    researcher, reviewer = agent.sub_agents[:2]
    context = FakeContext("document_researcher")

    # At pre-call five, an already selected page may still be read on call six.
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 2
    ledger.last_search_hit_ids = {"source:p0002"}
    ledger.issued_evidence_ids = {"source:p0001", "source:p0002"}
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
