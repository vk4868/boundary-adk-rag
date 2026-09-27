"""Offline integration tests for the one-shot formatter citation repair."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from google.adk.agents import LlmAgent
from google.adk.events import EventActions
from google.adk.models import BaseLlm, LlmCapabilities, LlmRequest, LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.set_model_response_tool import SetModelResponseTool
from google.genai import types

from app.agents import _state_model, build_agent
from app.config import Settings
from app.gate import apply_gate
from app.index import IndexRepository
from app.models import (
    CorpusIndex,
    EmbeddingDescriptor,
    PageRecord,
    ResearchDraft,
    ReviewDecision,
    QuestionPartAssessment,
    SourceRecord,
)
from app.tools import RunLedger


@dataclass
class FakeContext:
    agent_name: str


@dataclass
class RepairHarness:
    settings: Settings
    repository: IndexRepository
    ledger: RunLedger
    researcher: object
    reviewer: object


@pytest.fixture
def harness(tmp_path) -> RepairHarness:
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=True,
        app_model_provider="ollama",
        app_embedding_provider="ollama",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "unused-audit.jsonl",
        app_allowed_roles="analyst,admin",
        app_server_role="analyst",
        app_max_model_calls=8,
        app_max_output_tokens=7200,
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[
            SourceRecord(
                source_id="local_rules",
                title="Local Tournament supplied rules",
                version="Supplied copy",
                scope="Local tournament",
                competition="Local Tournament",
                allowed_roles=["analyst"],
                page_count=2,
                sha256="a" * 64,
            ),
            SourceRecord(
                source_id="secret_rules",
                title="Restricted tournament rules",
                version="Supplied copy",
                scope="Restricted tournament",
                competition="Restricted Tournament",
                allowed_roles=["admin"],
                page_count=1,
                sha256="b" * 64,
            ),
        ],
        pages=[
            PageRecord(
                evidence_id="local_rules:p0001",
                source_id="local_rules",
                page=1,
                text="Local Tournament rule on page one.",
            ),
            PageRecord(
                evidence_id="local_rules:p0002",
                source_id="local_rules",
                page=2,
                text="Local Tournament rule on page two.",
            ),
            PageRecord(
                evidence_id="secret_rules:p0001",
                source_id="secret_rules",
                page=1,
                text="Restricted Tournament private rule.",
            ),
        ],
    )
    ledger = RunLedger("repair-run")
    pipeline = build_agent(settings, repository, ledger, "analyst")
    return RepairHarness(
        settings=settings,
        repository=repository,
        ledger=ledger,
        researcher=pipeline.sub_agents[0],
        reviewer=pipeline.sub_agents[1],
    )


def _draft_args(*evidence_ids: str) -> dict[str, object]:
    return {
        "status": "answered",
        "claims": [
            {
                "text": "In the Local Tournament, this rule applies.",
                "evidence_ids": list(evidence_ids),
            }
        ],
        "limitations": [],
    }


def _tool_context() -> SimpleNamespace:
    return SimpleNamespace(
        actions=EventActions(),
        tool_confirmation=None,
        request_confirmation=lambda **_kwargs: None,
    )


def _request(researcher: object) -> LlmRequest:
    formatter = SetModelResponseTool(ResearchDraft)
    request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="question")])],
    )
    request.append_tools([formatter, *researcher.tools])
    return request


def _forced_function(request: LlmRequest) -> str:
    config = request.config.tool_config.function_calling_config
    assert config.mode.value == "ANY"
    assert config.allowed_function_names is not None
    assert len(config.allowed_function_names) == 1
    return config.allowed_function_names[0]


async def _invoke_with_callback(researcher, tool, args, tool_context):
    override = researcher.before_tool_callback(tool, args, tool_context)
    if override is not None:
        return override
    return await tool.run_async(args=args, tool_context=tool_context)


def _passing_review(claim_count: int = 1) -> ReviewDecision:
    return ReviewDecision(
        verdict="pass",
        answer_status="answered",
        checked_claims=claim_count,
        citation_support_ok=True,
        scope_and_version_ok=True,
        parts=[
            QuestionPartAssessment(
                part_id="answer",
                description="requested answer",
                supported=True,
                claim_indices=list(range(claim_count)),
            )
        ],
        all_parts_supported=True,
        conditions_preserved=True,
        unsupported_absence_claim_indices=[],
        abstention_justified=False,
    )


@pytest.mark.asyncio
async def test_reviewer_formatter_returns_feedback_then_sets_valid_typed_state():
    formatter = SetModelResponseTool(ReviewDecision)
    invalid_context = _tool_context()
    invalid = _passing_review().model_dump()
    invalid["conditions_preserved"] = False

    feedback = await formatter.run_async(args=invalid, tool_context=invalid_context)

    assert "error" in feedback
    assert invalid_context.actions.set_model_response is None

    valid_context = _tool_context()
    valid = _passing_review().model_dump()
    result = await formatter.run_async(args=valid, tool_context=valid_context)

    assert result == valid
    assert valid_context.actions.set_model_response == valid


@pytest.mark.asyncio
async def test_adk_reviewer_formatter_loop_repairs_invalid_then_saves_valid_state():
    invalid = _passing_review().model_dump()
    invalid["conditions_preserved"] = False
    valid = _passing_review().model_dump()

    class TwoTurnModel(BaseLlm):
        calls: int = 0

        @property
        def capabilities(self):
            return LlmCapabilities(output_schema_and_tools=False)

        async def generate_content_async(self, llm_request, stream=False):
            del llm_request, stream
            payload = invalid if self.calls == 0 else valid
            self.calls += 1
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id=f"review-{self.calls}",
                                name="set_model_response",
                                args=payload,
                            )
                        )
                    ],
                ),
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=1, candidates_token_count=1
                ),
            )

    model = TwoTurnModel(model="offline-review-loop")
    agent = LlmAgent(
        name="reviewer",
        model=model,
        instruction="Return the typed review using set_model_response.",
        tools=[SetModelResponseTool(ReviewDecision)],
        output_key="review_decision",
    )
    sessions = InMemorySessionService()
    session = await sessions.create_session(
        app_name="review-test", user_id="review-user"
    )
    runner = Runner(agent=agent, app_name="review-test", session_service=sessions)
    events = [
        event
        async for event in runner.run_async(
            user_id="review-user",
            session_id=session.id,
            new_message=types.Content(
                role="user", parts=[types.Part(text="review")]
            ),
        )
    ]

    assert model.calls == 2
    assert any(
        response.name == "set_model_response" and "error" in response.response
        for event in events
        for response in event.get_function_responses()
    )
    saved = await sessions.get_session(
        app_name="review-test", user_id="review-user", session_id=session.id
    )
    assert ReviewDecision.model_validate_json(saved.state["review_decision"]) == (
        ReviewDecision.model_validate(valid)
    )
    assert _state_model(ReviewDecision, saved.state["review_decision"]) == (
        ReviewDecision.model_validate(valid)
    )


@pytest.mark.asyncio
async def test_first_eligible_draft_is_intercepted_before_formatter_state(harness):
    evidence_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.add(evidence_id)
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    context = _tool_context()

    result = await _invoke_with_callback(
        harness.researcher, formatter, _draft_args(evidence_id), context
    )

    assert "required read_evidence" in result["error"]
    assert context.actions.set_model_response is None
    assert harness.ledger.citation_repair_attempted
    assert harness.ledger.citation_repair_pending_ids == {evidence_id}
    assert not harness.ledger.citation_repair_read_attempted


@pytest.mark.asyncio
async def test_terminal_ordinary_read_failure_cannot_open_formatter_repair(harness):
    evidence_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.add(evidence_id)
    harness.ledger.ordinary_read_failures = 2
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    context = _tool_context()

    result = await _invoke_with_callback(
        harness.researcher, formatter, _draft_args(evidence_id), context
    )

    assert "error" not in result
    assert context.actions.set_model_response == result
    assert not harness.ledger.citation_repair_attempted
    assert not harness.ledger.citation_repair_pending_ids


@pytest.mark.asyncio
async def test_wrong_or_subset_repair_read_is_blocked_and_not_retried(harness):
    first = "local_rules:p0001"
    second = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.update({first, second})
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(first, second),
        _tool_context(),
    )
    read_tool = next(
        tool for tool in harness.researcher.tools if tool.name == "read_evidence"
    )

    subset_result = await _invoke_with_callback(
        harness.researcher,
        read_tool,
        {"evidence_ids": [first]},
        _tool_context(),
    )
    second_result = await _invoke_with_callback(
        harness.researcher,
        read_tool,
        {"evidence_ids": [first, second]},
        _tool_context(),
    )

    assert "exactly" in subset_result["error"]
    assert "already used" in second_result["error"]
    assert not harness.ledger.read_evidence_ids
    assert harness.ledger.tool_calls == 2
    assert harness.ledger.read_evidence_attempts == 2
    request = _request(harness.researcher)
    harness.researcher.before_model_callback(
        FakeContext("document_researcher"), request
    )
    assert _forced_function(request) == "set_model_response"


@pytest.mark.asyncio
async def test_failed_actual_repair_read_does_not_create_read_evidence(
    harness, monkeypatch
):
    evidence_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.add(evidence_id)
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(evidence_id),
        _tool_context(),
    )
    original_page = harness.repository.page
    calls = 0

    def fail_after_validation(requested_id: str, role: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_page(requested_id, role)
        raise KeyError(requested_id)

    # Re-run formatter eligibility under the wrapper so the first repository
    # access is the authorization validation, then fail the real tool access.
    harness.ledger.citation_repair_attempted = False
    harness.ledger.citation_repair_pending_ids.clear()
    monkeypatch.setattr(harness.repository, "page", fail_after_validation)
    await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(evidence_id),
        _tool_context(),
    )
    read_tool = next(
        tool for tool in harness.researcher.tools if tool.name == "read_evidence"
    )

    result = await _invoke_with_callback(
        harness.researcher,
        read_tool,
        {"evidence_ids": [evidence_id]},
        _tool_context(),
    )
    assert result["error"] == (
        "One or more requested evidence pages are unavailable for this invocation."
    )
    assert result["retry_allowed"] is False

    assert harness.ledger.citation_repair_read_attempted
    assert evidence_id not in harness.ledger.read_evidence_ids
    assert harness.ledger.tool_calls == 1


@pytest.mark.asyncio
async def test_invented_unauthorized_and_late_ids_are_not_repairable(harness):
    formatter = SetModelResponseTool(ResearchDraft)

    cases = [
        ("invented:p0001", {"invented:p0001"}, 4),
        ("secret_rules:p0001", {"secret_rules:p0001"}, 4),
        ("local_rules:p0002", {"local_rules:p0002"}, 6),
    ]
    for evidence_id, issued, model_calls in cases:
        harness.ledger.reset(f"case-{evidence_id}")
        harness.ledger.issued_evidence_ids.update(issued)
        harness.ledger.model_calls = model_calls
        context = _tool_context()

        result = await _invoke_with_callback(
            harness.researcher,
            formatter,
            _draft_args(evidence_id),
            context,
        )

        assert "error" not in result
        assert context.actions.set_model_response == result
        assert not harness.ledger.citation_repair_attempted
        gated = apply_gate(
            request_id=harness.ledger.request_id,
            session_id="s" * 24,
            role="analyst",
            draft=ResearchDraft.model_validate(result),
            review=_passing_review(),
            ledger=harness.ledger,
            repository=harness.repository,
            trace=[],
        )
        assert not gated.passed
        assert gated.response.status == "rejected"


@pytest.mark.asyncio
async def test_repair_state_is_run_scoped_and_reset_clears_stale_ids(harness):
    evidence_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.add(evidence_id)
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(evidence_id),
        _tool_context(),
    )

    harness.ledger.reset("new-run")

    assert not harness.ledger.citation_repair_attempted
    assert not harness.ledger.citation_repair_pending_ids
    assert not harness.ledger.citation_repair_read_attempted
    context = _tool_context()
    result = await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(evidence_id),
        context,
    )
    assert "error" not in result
    assert context.actions.set_model_response == result


@pytest.mark.asyncio
async def test_earlier_same_invocation_search_hit_can_be_repaired(harness):
    old_id = "local_rules:p0001"
    current_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.update({old_id, current_id})
    harness.ledger.last_search_hit_ids = {current_id}
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    context = _tool_context()

    result = await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(old_id),
        context,
    )

    assert "error" in result
    assert context.actions.set_model_response is None
    assert harness.ledger.citation_repair_pending_ids == {old_id}
    read_tool = next(
        tool for tool in harness.researcher.tools if tool.name == "read_evidence"
    )
    read_result = await _invoke_with_callback(
        harness.researcher,
        read_tool,
        {"evidence_ids": [old_id]},
        _tool_context(),
    )
    assert read_result["evidence"][0]["evidence_id"] == old_id
    assert old_id in harness.ledger.read_evidence_ids


@pytest.mark.asyncio
async def test_exact_repair_uses_actual_read_then_passes_on_seventh_call(harness):
    read_id = "local_rules:p0001"
    unread_id = "local_rules:p0002"
    harness.ledger.issued_evidence_ids.update({read_id, unread_id})
    harness.ledger.read_evidence_ids.add(read_id)
    # Calls one through three were the governed list/search/read sequence; call
    # four produced the intercepted structured draft.
    harness.ledger.model_calls = 4
    formatter = SetModelResponseTool(ResearchDraft)
    first_context = _tool_context()
    first_result = await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(read_id, unread_id),
        first_context,
    )
    assert "error" in first_result
    assert first_context.actions.set_model_response is None

    read_request = _request(harness.researcher)
    harness.researcher.before_model_callback(
        FakeContext("document_researcher"), read_request
    )
    assert _forced_function(read_request) == "read_evidence"
    assert harness.ledger.model_calls == 5
    read_tool = next(
        tool for tool in harness.researcher.tools if tool.name == "read_evidence"
    )
    read_result = await _invoke_with_callback(
        harness.researcher,
        read_tool,
        {"evidence_ids": [unread_id]},
        _tool_context(),
    )
    assert read_result["evidence"][0]["evidence_id"] == unread_id
    assert unread_id in harness.ledger.read_evidence_ids
    assert harness.ledger.tool_calls == 1

    format_request = _request(harness.researcher)
    harness.researcher.before_model_callback(
        FakeContext("document_researcher"), format_request
    )
    assert _forced_function(format_request) == "set_model_response"
    assert harness.ledger.model_calls == 6
    final_context = _tool_context()
    final_draft = await _invoke_with_callback(
        harness.researcher,
        formatter,
        _draft_args(read_id, unread_id),
        final_context,
    )
    assert final_context.actions.set_model_response == final_draft

    reviewer_request = LlmRequest(
        model="offline",
        contents=[types.Content(role="user", parts=[types.Part(text="review")])],
    )
    harness.reviewer.before_model_callback(
        FakeContext("evidence_reviewer"), reviewer_request
    )
    assert harness.ledger.model_calls == 7

    gated = apply_gate(
        request_id=harness.ledger.request_id,
        session_id="s" * 24,
        role="analyst",
        draft=ResearchDraft.model_validate(final_draft),
        review=_passing_review(),
        ledger=harness.ledger,
        repository=harness.repository,
        trace=[],
    )
    assert gated.passed
    assert gated.response.status == "answered"
    assert {citation.id for citation in gated.response.citations} == {
        read_id,
        unread_id,
    }
