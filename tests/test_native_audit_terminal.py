"""Offline terminal-audit tests for native ADK wrapper failures."""

import json
from types import SimpleNamespace

import pytest

from app.agents import GovernedCliAgent
from app.audit import AuditLogger
from app.config import Settings
from app.index import IndexRepository
from app.tools import BudgetExceeded


def _wrapper(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused-index.json",
        app_audit_path=tmp_path / "audit.jsonl",
    )
    return (
        GovernedCliAgent(
            name="native_test_wrapper",
            settings=settings,
            repository=IndexRepository(settings),
            audit_logger=AuditLogger(settings.app_audit_path),
        ),
        settings,
    )


@pytest.mark.parametrize(
    ("caller_cap", "expected_cap"), [(None, 8), (0, 8), (3, 3), (500, 8)]
)
@pytest.mark.asyncio
async def test_native_wrapper_preserves_stricter_positive_caller_cap(
    tmp_path, monkeypatch, caller_cap, expected_cap
):
    wrapper, _settings = _wrapper(tmp_path)

    class SuccessfulPipeline:
        async def run_async(self, _ctx):
            ledger.terminal_audit_written = True
            if False:
                yield

    ledger = None

    def fake_build(*_args, **_kwargs):
        nonlocal ledger
        ledger = _args[2]
        return SuccessfulPipeline()

    monkeypatch.setattr("app.agents.build_agent", fake_build)
    context = SimpleNamespace(
        invocation_id="native-cap-run",
        session=SimpleNamespace(id="native-session"),
        run_config=SimpleNamespace(max_llm_calls=caller_cap),
    )

    assert [event async for event in wrapper._run_async_impl(context)] == []
    assert context.run_config.max_llm_calls == expected_cap


@pytest.mark.asyncio
async def test_native_failure_before_gate_writes_one_terminal_audit(
    tmp_path, monkeypatch
):
    wrapper, settings = _wrapper(tmp_path)

    class FailingPipeline:
        async def run_async(self, _ctx):
            raise BudgetExceeded("offline failure")
            yield

    def fake_build(*_args, **_kwargs):
        ledger = _args[2]
        ledger.model_calls = 1
        return FailingPipeline()

    monkeypatch.setattr("app.agents.build_agent", fake_build)
    context = SimpleNamespace(
        invocation_id="native-failure-run",
        session=SimpleNamespace(id="native-session"),
        run_config=SimpleNamespace(max_llm_calls=500),
    )

    with pytest.raises(BudgetExceeded):
        [event async for event in wrapper._run_async_impl(context)]

    records = [
        json.loads(line)
        for line in settings.app_audit_path.read_text(encoding="utf-8").splitlines()
    ]
    terminal = [record for record in records if record["event"] == "adk_cli_run"]
    assert len(terminal) == 1
    assert terminal[0]["status"] == "error"
    assert terminal[0]["error_code"] == "BudgetExceeded"
    assert terminal[0]["model_calls"] == 1
    assert terminal[0]["unmetered_model_calls"] == 1
    assert terminal[0]["model"] == settings.app_model
    assert terminal[0]["model_provider"] == settings.app_model_provider
    assert terminal[0]["model_location"] == settings.google_cloud_location
    assert context.run_config.max_llm_calls == settings.app_max_model_calls


@pytest.mark.asyncio
async def test_native_success_does_not_duplicate_gate_terminal(
    tmp_path, monkeypatch
):
    wrapper, settings = _wrapper(tmp_path)

    class SuccessfulPipeline:
        async def run_async(self, _ctx):
            ledger.terminal_audit_written = True
            wrapper.audit_logger.append_sync(
                {
                    "event": "adk_cli_run",
                    "request_id": ledger.request_id,
                    "session_ref": "native-session",
                    "role": settings.app_server_role,
                    "status": "answered",
                    "model_calls": 1,
                    "unmetered_model_calls": 0,
                    "tool_calls": 1,
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "evidence_count": 1,
                    "gate_passed": True,
                    **settings.audit_model_metadata,
                }
            )
            if False:
                yield

    ledger = None

    def fake_build(*_args, **_kwargs):
        nonlocal ledger
        ledger = _args[2]
        return SuccessfulPipeline()

    monkeypatch.setattr("app.agents.build_agent", fake_build)
    context = SimpleNamespace(
        invocation_id="native-success-run",
        session=SimpleNamespace(id="native-session"),
        run_config=SimpleNamespace(max_llm_calls=500),
    )

    assert [event async for event in wrapper._run_async_impl(context)] == []
    records = [
        json.loads(line)
        for line in settings.app_audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len([record for record in records if record["event"] == "adk_cli_run"]) == 1
    terminal = next(record for record in records if record["event"] == "adk_cli_run")
    assert {
        key: terminal[key]
        for key in ("model", "model_provider", "model_location")
    } == settings.audit_model_metadata
    assert context.run_config.max_llm_calls == settings.app_max_model_calls
