"""Offline regressions for explicit Vertex routing; perform no model request."""

from dataclasses import dataclass

import pytest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.flows.llm_flows import _output_schema_processor, basic
from google.adk.models import LlmRequest
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

from app.agents import _request_token_estimate, build_agent
from app.config import Settings
from app.index import IndexRepository
from app.tools import RunLedger
from app.models import ReviewDecision


@dataclass
class FakeContext:
    agent_name: str


async def _assembled_researcher_request(
    settings: Settings, *, require_cli_authorization: bool
) -> tuple[LlmRequest, object]:
    ledger = RunLedger("offline-request-shape")
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        ledger,
        settings.app_server_role,
        require_cli_authorization=require_cli_authorization,
    )
    researcher = pipeline.sub_agents[0]
    request = LlmRequest()
    session_service = InMemorySessionService()
    invocation = InvocationContext(
        invocation_id="offline-invocation",
        agent=researcher,
        session_service=session_service,
        session=Session(
            id="offline-session",
            app_name="app",
            user_id="offline-user",
        ),
        run_config=RunConfig(max_llm_calls=settings.app_max_model_calls),
    )
    basic._build_basic_request(invocation, request)
    request.append_tools(researcher.tools)
    async for _event in _output_schema_processor.request_processor.run_async(
        invocation, request
    ):
        pass
    researcher.before_model_callback(FakeContext("document_researcher"), request)
    return request, researcher


def test_adk_model_client_is_explicitly_bound_to_vertex(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="vertex",
        google_cloud_project="offline-project-no-request",
        google_cloud_location="global",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-construction-only"),
        settings.app_server_role,
    )
    researcher_model = pipeline.sub_agents[0].model
    reviewer_model = pipeline.sub_agents[1].model

    assert researcher_model is reviewer_model
    assert researcher_model.client is not None
    api_client = researcher_model.client._api_client
    assert api_client.vertexai is True
    assert api_client.project == "offline-project-no-request"
    assert api_client.location == "global"


@pytest.mark.parametrize("vertex_env", ["true", "false"])
@pytest.mark.parametrize("require_cli_authorization", [False, True])
@pytest.mark.asyncio
async def test_forced_research_tools_use_formatter_and_plain_mime_in_all_runners(
    tmp_path, monkeypatch, vertex_env, require_cli_authorization
):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", vertex_env)
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="vertex",
        google_cloud_project="offline-project-no-request",
        google_cloud_location="global",
        app_allow_adk_cli=True,
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )

    request, researcher = await _assembled_researcher_request(
        settings, require_cli_authorization=require_cli_authorization
    )

    assert researcher.model.capabilities.output_schema_and_tools is False
    assert "set_model_response" in request.tools_dict
    assert request.config.response_mime_type == "text/plain"
    assert request.config.response_schema is None
    assert request.config.response_json_schema is None
    function_config = request.config.tool_config.function_calling_config
    assert function_config.mode == types.FunctionCallingConfigMode.ANY
    assert function_config.allowed_function_names == ["list_sources"]


@pytest.mark.asyncio
async def test_reviewer_keeps_json_schema_without_research_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="vertex",
        google_cloud_project="offline-project-no-request",
        google_cloud_location="global",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-review-shape"),
        settings.app_server_role,
    )
    reviewer = pipeline.sub_agents[1]
    request = LlmRequest()
    invocation = InvocationContext(
        invocation_id="offline-review-invocation",
        agent=reviewer,
        session_service=InMemorySessionService(),
        session=Session(
            id="offline-review-session",
            app_name="app",
            user_id="offline-user",
        ),
        run_config=RunConfig(max_llm_calls=settings.app_max_model_calls),
    )

    basic._build_basic_request(invocation, request)
    reviewer.before_model_callback(FakeContext("evidence_reviewer"), request)

    assert not request.tools_dict
    assert request.config.response_mime_type == "application/json"
    assert request.config.response_schema is ReviewDecision


def test_budget_estimator_serializes_reviewer_pydantic_schema():
    request = LlmRequest(
        model="offline",
        contents=[
            types.Content(role="user", parts=[types.Part(text="review this draft")])
        ],
        config=types.GenerateContentConfig(
            system_instruction="review system instruction",
            response_schema=ReviewDecision,
        ),
    )

    assert _request_token_estimate(request) > 128


def test_budget_estimator_includes_function_tool_declarations(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-tools-only"),
        settings.app_server_role,
    )
    researcher = pipeline.sub_agents[0]
    base = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="question")])],
    )
    with_tools = LlmRequest(
        model="offline",
        contents=base.contents,
        tools_dict={tool.name: tool for tool in researcher.tools},
    )

    assert _request_token_estimate(with_tools) > _request_token_estimate(base)


def test_gemini_38_flash_uses_low_thinking_without_sampling_knobs(tmp_path):
    settings = Settings(
        _env_file=None,
        app_model="gemini-3.8-flash",
        app_max_output_tokens_per_call=2000,
        app_max_output_tokens=16000,
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-38-config"),
        settings.app_server_role,
    )

    for llm_agent in pipeline.sub_agents[:2]:
        config = llm_agent.generate_content_config
        assert config.max_output_tokens == 2000
        assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
        assert config.temperature is None
        assert config.top_p is None
        assert config.top_k is None


def test_flash_lite_generation_profile_is_unchanged(tmp_path):
    settings = Settings(
        _env_file=None,
        app_model="gemini-3.1-flash-lite",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-lite-config"),
        settings.app_server_role,
    )

    for llm_agent in pipeline.sub_agents[:2]:
        config = llm_agent.generate_content_config
        assert config.max_output_tokens == 900
        assert config.temperature == 0
        assert config.thinking_config is None
        assert config.top_p is None
        assert config.top_k is None
