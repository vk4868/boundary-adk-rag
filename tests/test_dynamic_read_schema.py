"""Offline tests for request-scoped read_evidence argument allowlists."""

from dataclasses import dataclass
import json

import pytest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.flows.llm_flows import _output_schema_processor, basic
from google.adk.models import LlmRequest
from google.adk.models.lite_llm import _get_completion_inputs
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

from app.agents import (
    READ_EVIDENCE_ENUM_LIMIT,
    _request_token_estimate,
    _set_read_evidence_enum,
    build_agent,
)
from app.config import Settings
from app.index import IndexRepository
from app.models import CorpusIndex, EmbeddingDescriptor, PageRecord, SourceRecord
from app.tools import BudgetExceeded, RunLedger


@dataclass
class FakeContext:
    agent_name: str


@pytest.fixture
def schema_harness(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_embedding_provider="ollama",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "audit.jsonl",
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[
            SourceRecord(
                source_id="rules",
                title="Rules",
                version="test",
                scope="authorized",
                competition="MCC",
                allowed_roles=["analyst"],
                page_count=2,
                sha256="a" * 64,
            ),
            SourceRecord(
                source_id="secret",
                title="Secret",
                version="test",
                scope="restricted",
                competition="MCC",
                allowed_roles=["admin"],
                page_count=1,
                sha256="b" * 64,
            ),
        ],
        pages=[
            PageRecord(
                evidence_id="rules:p0001",
                source_id="rules",
                page=1,
                text="authorized page one",
            ),
            PageRecord(
                evidence_id="rules:p0002",
                source_id="rules",
                page=2,
                text="authorized page two",
            ),
            PageRecord(
                evidence_id="secret:p0001",
                source_id="secret",
                page=1,
                text="restricted page",
            ),
        ],
    )
    ledger = RunLedger("dynamic-schema")
    pipeline = build_agent(settings, repository, ledger, "analyst")
    return settings, repository, ledger, pipeline


async def _assembled_request(settings, researcher, invocation_id: str) -> LlmRequest:
    request = LlmRequest()
    invocation = InvocationContext(
        invocation_id=invocation_id,
        agent=researcher,
        session_service=InMemorySessionService(),
        session=Session(
            id=f"session-{invocation_id}",
            app_name="app",
            user_id="offline-user",
        ),
        run_config=RunConfig(max_llm_calls=settings.app_max_model_calls),
    )
    basic._build_basic_request(invocation, request)
    async for _event in _output_schema_processor.request_processor.run_async(
        invocation, request
    ):
        pass
    request.append_tools(researcher.tools)
    return request


def _read_declaration(request: LlmRequest):
    return next(
        (
            declaration
            for tool in request.config.tools or []
            if isinstance(tool, types.Tool)
            for declaration in tool.function_declarations or []
            if declaration.name == "read_evidence"
        ),
        None,
    )


def _json_enum(request: LlmRequest) -> list[str] | None:
    declaration = _read_declaration(request)
    if declaration is None:
        return None
    return declaration.parameters_json_schema["properties"]["evidence_ids"][
        "items"
    ].get("enum")


@pytest.mark.asyncio
async def test_actual_research_request_advertises_only_reauthorized_issued_ids(
    schema_harness,
):
    settings, _repository, ledger, pipeline = schema_harness
    researcher = pipeline.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_issued_ids = {"rules:p0001"}
    ledger.issued_evidence_ids = {
        "rules:p0001",
        "secret:p0001",
        "rules:p9999",
    }
    request = await _assembled_request(settings, researcher, "authorized")

    researcher.before_model_callback(FakeContext("document_researcher"), request)

    assert _json_enum(request) == ["rules:p0001"]
    assert "read_evidence" in request.tools_dict
    function_config = request.config.tool_config.function_calling_config
    assert function_config.allowed_function_names == ["read_evidence"]

    _messages, wire_tools, _response_format, _params, tool_choice = (
        await _get_completion_inputs(request, researcher.model.model)
    )
    wire_declaration = next(
        tool["function"]
        for tool in wire_tools or []
        if tool["function"]["name"] == "read_evidence"
    )
    assert tool_choice == "required"
    assert wire_declaration["parameters"]["properties"]["evidence_ids"]["items"] == {
        "type": "string",
        "enum": ["rules:p0001"],
    }


@pytest.mark.asyncio
async def test_forced_read_without_outbound_declaration_fails_before_dispatch(
    schema_harness,
):
    _settings, _repository, ledger, pipeline = schema_harness
    researcher = pipeline.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_issued_ids = {"rules:p0001"}
    ledger.issued_evidence_ids = {"rules:p0001"}
    request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="question")])],
        tools_dict={tool.name: tool for tool in researcher.tools},
    )

    with pytest.raises(BudgetExceeded, match="no authorized IDs"):
        researcher.before_model_callback(FakeContext("document_researcher"), request)

    assert request.config.tools is None
    assert ledger.model_calls == 0


@pytest.mark.asyncio
async def test_successive_requests_and_agents_do_not_share_dynamic_enums(
    schema_harness,
):
    settings, repository, ledger, pipeline = schema_harness
    researcher = pipeline.sub_agents[0]
    ledger.listed_sources_successfully = True
    ledger.successful_searches = 1
    ledger.last_search_issued_ids = {"rules:p0001"}
    ledger.issued_evidence_ids = {"rules:p0001"}
    first = await _assembled_request(settings, researcher, "first")
    researcher.before_model_callback(FakeContext("document_researcher"), first)
    assert _json_enum(first) == ["rules:p0001"]

    ledger.reset("second")
    second = await _assembled_request(settings, researcher, "second")
    researcher.before_model_callback(FakeContext("document_researcher"), second)
    assert _read_declaration(second) is None
    assert _json_enum(first) == ["rules:p0001"]
    original = next(
        tool for tool in researcher.tools if tool.name == "read_evidence"
    )._get_declaration()
    assert original.parameters_json_schema["properties"]["evidence_ids"][
        "items"
    ].get("enum") is None

    other_ledger = RunLedger("other-agent")
    other_ledger.listed_sources_successfully = True
    other_ledger.successful_searches = 1
    other_ledger.last_search_issued_ids = {"rules:p0002"}
    other_ledger.issued_evidence_ids = {"rules:p0002"}
    other = build_agent(settings, repository, other_ledger, "analyst").sub_agents[0]
    other_request = await _assembled_request(settings, other, "other")
    other.before_model_callback(FakeContext("document_researcher"), other_request)
    assert _json_enum(other_request) == ["rules:p0002"]
    assert _json_enum(first) == ["rules:p0001"]


def test_both_schema_representations_put_enum_on_string_items():
    json_request = LlmRequest(
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="read_evidence",
                            parameters_json_schema={
                                "type": "object",
                                "properties": {
                                    "evidence_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                },
                            },
                        )
                    ]
                )
            ]
        )
    )
    assert _set_read_evidence_enum(json_request, ["rules:p0001"])
    assert _json_enum(json_request) == ["rules:p0001"]

    sdk_request = LlmRequest(
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="read_evidence",
                            parameters=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "evidence_ids": types.Schema(
                                        type=types.Type.ARRAY,
                                        items=types.Schema(type=types.Type.STRING),
                                    )
                                },
                            ),
                        )
                    ]
                )
            ]
        )
    )
    assert _set_read_evidence_enum(sdk_request, ["rules:p0002"])
    declaration = _read_declaration(sdk_request)
    item_schema = declaration.parameters.properties["evidence_ids"].items
    assert item_schema.type == types.Type.STRING
    assert item_schema.enum == ["rules:p0002"]


def test_empty_allowlist_drops_read_only_tool_and_overflow_fails_closed():
    request = LlmRequest(
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="read_evidence",
                            parameters_json_schema={
                                "type": "object",
                                "properties": {
                                    "evidence_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                },
                            },
                        )
                    ]
                )
            ]
        )
    )
    assert _set_read_evidence_enum(request, [])
    assert request.config.tools is None
    assert '"tools"' not in request.config.model_dump_json(
        exclude_none=True, exclude_defaults=True
    )

    with pytest.raises(BudgetExceeded, match="declaration ID limit"):
        _set_read_evidence_enum(
            LlmRequest(),
            [f"rules:p{index:04d}" for index in range(READ_EVIDENCE_ENUM_LIMIT + 1)],
        )


def test_input_estimate_includes_dynamic_enum_values():
    base = LlmRequest(
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="read_evidence",
                            parameters_json_schema={
                                "type": "object",
                                "properties": {
                                    "evidence_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                },
                            },
                        )
                    ]
                )
            ]
        )
    )
    constrained = base.model_copy(deep=True)
    _set_read_evidence_enum(
        constrained,
        ["rules:p0001", "rules:p0002", "rules:p0003"],
    )
    assert _request_token_estimate(constrained) > _request_token_estimate(base)
