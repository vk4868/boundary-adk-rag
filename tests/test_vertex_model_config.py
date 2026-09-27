"""Offline regressions for local Ollama routing; perform no model request."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.flows.llm_flows import _output_schema_processor, basic
from google.adk.models import LlmRequest
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

from app.agents import _request_token_estimate, build_agent
from app.config import Settings
from app.index import IndexRepository
from app.tools import BudgetExceeded, RunLedger
from app.models import (
    CorpusIndex,
    EmbeddingDescriptor,
    PageRecord,
    ReviewDecision,
    SourceRecord,
)


@dataclass
class FakeContext:
    agent_name: str
    state: dict | None = None


def test_reviewer_receives_only_bounded_authorized_evidence_pack(tmp_path):
    evidence_id = "local_rules:p0001"
    page = PageRecord(
        evidence_id=evidence_id,
        source_id="local_rules",
        page=1,
        text="A general rule with its surrounding scope and exception.",
        embedding=[0.0] * 768,
    )
    source = SourceRecord(
        source_id="local_rules",
        title="Local Rules",
        version="Supplied copy",
        scope="Local competition only",
        competition="Local Competition",
        allowed_roles=["analyst"],
        page_count=1,
        sha256="a" * 64,
    )

    index_path = tmp_path / "index.json"
    index_path.write_text(
        CorpusIndex(
            schema_version=1,
            embedding=EmbeddingDescriptor(
                provider="ollama",
                model="embeddinggemma:latest",
                model_digest="b" * 64,
                location="loopback",
                dimensions=768,
                embedding_method="deterministic_utf8_chunks_length_weighted_l2_pool",
                context_window_tokens=2048,
                chunk_max_bytes=1800,
                pooling="utf8_byte_length_weighted_mean_then_l2_normalize",
            ),
            sources=[source],
            pages=[page],
        ).model_dump_json(),
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_embedding_provider="ollama",
        app_index_path=index_path,
        app_audit_path=tmp_path / "audit.jsonl",
    )

    ledger = RunLedger("bounded-review-pack")
    ledger.original_question = "How does that rule apply?"
    ledger.read_evidence_ids.add(evidence_id)
    pipeline = build_agent(
        settings, IndexRepository(settings), ledger, settings.app_server_role
    )
    reviewer = pipeline.sub_agents[1]
    request = LlmRequest(
        contents=[
            types.Content(role="user", parts=[types.Part(text="What is the rule?")]),
            types.Content(
                role="user",
                parts=[types.Part(text="For context: noisy researcher transcript")],
            ),
            types.Content(
                role="user", parts=[types.Part(text="How does that rule apply?")]
            ),
        ]
    )
    draft = {
        "status": "answered",
        "claims": [{"text": "Local claim", "evidence_ids": [evidence_id]}],
        "limitations": [],
    }

    reviewer.before_model_callback(
        FakeContext("evidence_reviewer", {"research_draft": draft}), request
    )

    assert len(request.contents) == 2
    packed_text = request.contents[0].parts[0].text
    assert "noisy researcher transcript" not in packed_text
    pack = json.loads(packed_text.split("\n", 1)[1])
    assert pack["current_question"] == "How does that rule apply?"
    assert pack["prior_user_questions_untrusted_context_only"] == [
        "What is the rule?",
        "How does that rule apply?",
    ]
    assert pack["research_draft"] == draft
    assert pack["authorized_read_evidence"] == [
        {
            "evidence_id": evidence_id,
            "source_id": "local_rules",
            "title": "Local Rules",
            "version": "Supplied copy",
            "scope": "Local competition only",
            "competition": "Local Competition",
            "page": 1,
            "text": "A general rule with its surrounding scope and exception.",
        }
    ]
    assert pack["prior_formatter_validation_feedback"] is None

    feedback = {"error": "Current ReviewDecision validation failed", "details": []}
    reviewer.after_tool_callback(
        reviewer.tools[0], {}, SimpleNamespace(), feedback
    )
    stale_feedback = {"error": "stale researcher or prior-turn error"}
    correction_request = LlmRequest(
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="set_model_response", response=stale_feedback
                        )
                    )
                ],
            )
        ]
    )
    reviewer.before_model_callback(
        FakeContext("evidence_reviewer", {"research_draft": draft}),
        correction_request,
    )
    correction_pack = json.loads(
        correction_request.contents[0].parts[0].text.split("\n", 1)[1]
    )
    assert correction_pack["prior_formatter_validation_feedback"] == json.dumps(
        feedback, ensure_ascii=False
    )

    with pytest.raises(BudgetExceeded, match="reviewer correction"):
        reviewer.before_model_callback(
            FakeContext("evidence_reviewer", {"research_draft": draft}),
            LlmRequest(),
        )

    pipeline.before_agent_callback(
        SimpleNamespace(
            invocation_id="next-review-invocation",
            state={},
            user_content=types.Content(
                role="user", parts=[types.Part(text="Next question")]
            ),
        )
    )
    reviewer.before_model_callback(
        FakeContext("evidence_reviewer", {"research_draft": draft}), LlmRequest()
    )


def test_import_and_offline_agent_build_make_no_network_request(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    script = """
import socket
def denied(*args, **kwargs):
    raise AssertionError('network access attempted during import/build')
socket.create_connection = denied
socket.socket.connect = denied
import app
from app.agents import build_agent
from app.config import Settings
from app.index import IndexRepository
from app.tools import RunLedger
settings = Settings(
    _env_file=None,
    app_enable_model_calls=False,
    app_model_provider='disabled',
    app_embedding_provider='lexical',
    app_index_path='unused-index.json',
    app_index_sha256=None,
    app_audit_path='unused-audit.jsonl',
)
build_agent(settings, IndexRepository(settings), RunLedger('offline'), 'analyst')
assert __import__('os').environ['LITELLM_LOCAL_MODEL_COST_MAP'] == 'true'
"""
    environment = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "APP_ENABLE_MODEL_CALLS": "false",
        "APP_MODEL_PROVIDER": "disabled",
        "APP_EMBEDDING_PROVIDER": "lexical",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://ollama.example:11434",
        "http://localhost:11434",
        "http://127.0.0.1",
        "http://127.0.0.1:11434/api",
        "http://user@127.0.0.1:11434",
        "http://127.0.0.1:11434?next=https://example.com",
    ],
)
def test_ollama_url_rejects_non_loopback_or_non_origin_values(url):
    with pytest.raises(ValidationError, match="loopback HTTP origin|explicit port"):
        Settings(_env_file=None, app_ollama_base_url=url)


def test_model_calls_require_ollama_provider():
    with pytest.raises(ValidationError, match="APP_MODEL_PROVIDER=ollama"):
        Settings(
            _env_file=None,
            app_enable_model_calls=True,
            app_model_provider="vertex",
        )


def test_model_calls_require_local_ollama_embeddings():
    with pytest.raises(ValidationError, match="APP_EMBEDDING_PROVIDER=ollama"):
        Settings(
            _env_file=None,
            app_enable_model_calls=True,
            app_model_provider="ollama",
            app_embedding_provider="vertex",
        )


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


def test_adk_model_is_explicitly_bound_to_loopback_ollama(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_model="gemma4:latest",
        app_embedding_provider="ollama",
        app_model_timeout_ms=120000,
        app_ollama_base_url="http://127.0.0.1:11434",
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
    assert researcher_model.model == "ollama_chat/gemma4:latest"
    assert researcher_model._additional_args["api_base"] == "http://127.0.0.1:11434"
    assert researcher_model._additional_args["num_ctx"] == 16384
    assert researcher_model._additional_args["think"] is False
    http_client = researcher_model._additional_args["client"].client
    assert http_client.follow_redirects is False
    assert http_client.trust_env is False


@pytest.mark.parametrize("require_cli_authorization", [False, True])
@pytest.mark.asyncio
async def test_forced_research_tools_use_formatter_and_plain_mime_in_all_runners(
    tmp_path, require_cli_authorization
):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_allow_adk_cli=True,
        app_embedding_provider="ollama",
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
    declarations = [
        declaration.name
        for tool in request.config.tools or []
        for declaration in tool.function_declarations or []
    ]
    assert declarations == ["list_sources"]


@pytest.mark.asyncio
async def test_reviewer_uses_only_typed_internal_formatter_tool(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_embedding_provider="ollama",
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

    assert set(request.tools_dict) == {"set_model_response"}
    assert request.config.response_mime_type == "text/plain"
    assert request.config.response_schema is None
    declarations = [
        declaration.name
        for tool in request.config.tools or []
        for declaration in tool.function_declarations or []
    ]
    assert declarations == ["set_model_response"]
    formatter_schema = request.config.tools[0].function_declarations[
        0
    ].parameters_json_schema
    assert "$defs" not in formatter_schema
    assert "$ref" not in json.dumps(formatter_schema)
    assert formatter_schema["additionalProperties"] is False
    assert formatter_schema["properties"]["parts"]["minItems"] == 1
    assert formatter_schema["properties"]["parts"]["maxItems"] == 8
    assert set(formatter_schema["required"]) == {
        "verdict",
        "answer_status",
        "checked_claims",
        "citation_support_ok",
        "scope_and_version_ok",
        "parts",
        "all_parts_supported",
        "conditions_preserved",
        "unsupported_absence_claim_indices",
        "abstention_justified",
    }


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


def test_single_request_cannot_exceed_ollama_context(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_ollama_num_ctx=8192,
        app_embedding_provider="ollama",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
    )
    pipeline = build_agent(
        settings,
        IndexRepository(settings),
        RunLedger("offline-context-bound"),
        settings.app_server_role,
    )
    reviewer = pipeline.sub_agents[1]
    request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="x" * 30_000)])],
    )

    with pytest.raises(BudgetExceeded, match="Ollama context window"):
        reviewer.before_model_callback(FakeContext("evidence_reviewer"), request)


def test_ollama_generation_profile_is_bounded_and_deterministic(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_model="gemma4:latest",
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
        assert config.temperature == 0
        assert config.thinking_config is None
        assert config.top_p is None
        assert config.top_k is None


def test_ollama_transport_has_one_attempt_and_finite_timeout(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_model="gemma4:latest",
        app_model_timeout_ms=120000,
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
        assert config.http_options.timeout == 120000
        assert config.http_options.retry_options.attempts == 0
        assert config.thinking_config is None
        assert config.top_p is None
        assert config.top_k is None
