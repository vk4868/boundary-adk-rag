"""Authenticated session orchestration around the run-scoped ADK pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents import build_agent
from app.audit import ALLOWED_AUTHORS, ALLOWED_TOOLS, AuditLogger, AuditWriteError
from app.config import Settings
from app.index import IndexRepository
from app.models import ChatResponse
from app.models import TraceStep
from app.tools import RunLedger


APP_NAME = "adk_document_assistant"


class ServiceUnavailable(RuntimeError):
    pass


class UnknownSession(KeyError):
    pass


class SessionOwnershipError(PermissionError):
    pass


@dataclass
class SessionRecord:
    public_id: str
    internal_id: str
    owner: str
    turns: int = 0
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ChatService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = IndexRepository(settings)
        self.audit = AuditLogger(settings.app_audit_path)
        self.sessions = InMemorySessionService()
        self._registry: dict[str, SessionRecord] = {}
        self._registry_lock = asyncio.Lock()

    @staticmethod
    def principal_for_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]

    async def _cleanup_expired(self, now: float) -> None:
        expired = [
            record
            for record in self._registry.values()
            if now - record.last_used > self.settings.app_session_ttl_seconds
            and not record.lock.locked()
        ]
        for record in expired:
            self._registry.pop(record.public_id, None)
            await self.sessions.delete_session(
                app_name=APP_NAME,
                user_id=record.owner,
                session_id=record.internal_id,
            )

    async def _resolve_session(
        self, requested_id: str | None, principal: str
    ) -> tuple[SessionRecord, bool]:
        now = time.monotonic()
        async with self._registry_lock:
            await self._cleanup_expired(now)
            if requested_id is not None:
                record = self._registry.get(requested_id)
                if record is None:
                    raise UnknownSession("unknown or expired session")
                if not secrets.compare_digest(record.owner, principal):
                    raise SessionOwnershipError("session belongs to another principal")
                record.last_used = now
                return record, False

            public_id = secrets.token_urlsafe(24)
            internal_id = secrets.token_urlsafe(24)
            record = SessionRecord(
                public_id=public_id,
                internal_id=internal_id,
                owner=principal,
            )
            await self.sessions.create_session(
                app_name=APP_NAME,
                user_id=principal,
                session_id=internal_id,
                state={"server_role": self.settings.app_server_role},
            )
            self._registry[public_id] = record
            return record, True

    async def _rotate_if_bounded(self, record: SessionRecord) -> bool:
        if record.turns < self.settings.app_max_session_turns:
            return False
        await self.sessions.delete_session(
            app_name=APP_NAME,
            user_id=record.owner,
            session_id=record.internal_id,
        )
        record.internal_id = secrets.token_urlsafe(24)
        record.turns = 0
        await self.sessions.create_session(
            app_name=APP_NAME,
            user_id=record.owner,
            session_id=record.internal_id,
            state={"server_role": self.settings.app_server_role},
        )
        return True

    async def chat(
        self, *, message: str, requested_session_id: str | None, principal: str
    ) -> ChatResponse:
        if not self.settings.model_ready:
            raise ServiceUnavailable("model calls are disabled or not configured")
        self.repository.load()
        request_id = secrets.token_urlsafe(18)
        started = time.monotonic()
        record, _ = await self._resolve_session(requested_session_id, principal)
        ledger = RunLedger(request_id=request_id)
        response: ChatResponse | None = None
        error_code: str | None = None
        rotated = False
        event_flow: list[dict[str, Any]] = []
        stage_durations: dict[str, float] = {}
        tool_trace_names: list[str] = []

        await self.audit.append(
            {
                "event": "chat_preflight",
                "request_id": request_id,
                "session_ref": hashlib.sha256(
                    record.public_id.encode("utf-8")
                ).hexdigest()[:24],
                "principal_ref": principal,
                "role": self.settings.app_server_role,
                "status": "accepted",
                "message_char_count": len(message),
            }
        )

        try:
            async with record.lock:
                rotated = await self._rotate_if_bounded(record)
                # Count every dispatched turn, including timeouts and malformed
                # model output that may already have appended partial events.
                record.turns += 1
                record.last_used = time.monotonic()
                agent = build_agent(
                    self.settings,
                    self.repository,
                    ledger,
                    self.settings.app_server_role,
                    public_session_id=record.public_id,
                    original_question=message,
                )
                runner = Runner(
                    agent=agent,
                    app_name=APP_NAME,
                    session_service=self.sessions,
                )
                message_content = types.Content(
                    role="user", parts=[types.Part(text=message)]
                )
                try:
                    last_observed = time.monotonic()
                    async with asyncio.timeout(
                        self.settings.app_max_request_seconds
                    ):
                        async for _event in runner.run_async(
                            user_id=record.owner,
                            session_id=record.internal_id,
                            new_message=message_content,
                            state_delta={
                                "request_id": request_id,
                                "server_role": self.settings.app_server_role,
                                "research_draft": None,
                                "review_decision": None,
                                "governed_response": None,
                            },
                            run_config=RunConfig(
                                max_llm_calls=self.settings.app_max_model_calls
                            ),
                        ):
                            observed = time.monotonic()
                            raw_author = _event.author or ""
                            author = (
                                raw_author
                                if raw_author in ALLOWED_AUTHORS
                                else "__unknown_agent__"
                            )
                            duration = observed - last_observed
                            last_observed = observed
                            stage_durations[author] = (
                                stage_durations.get(author, 0.0) + duration
                            )
                            function_names = []
                            for call in _event.get_function_calls():
                                raw_name = call.name or ""
                                function_names.append(
                                    raw_name
                                    if raw_name in ALLOWED_TOOLS
                                    else "__unknown_tool__"
                                )
                            tool_trace_names.extend(function_names)
                            event_flow.append(
                                {
                                    "author": author,
                                    "function_calls": function_names,
                                    "observed_at": observed,
                                }
                            )
                finally:
                    await runner.close()
                session = await self.sessions.get_session(
                    app_name=APP_NAME,
                    user_id=record.owner,
                    session_id=record.internal_id,
                )
                if session is None or "governed_response" not in session.state:
                    raise ServiceUnavailable("agent run produced no governed response")
                response = ChatResponse.model_validate(
                    session.state["governed_response"]
                )
                if response.request_id != ledger.request_id:
                    raise ServiceUnavailable("stale governed response detected")
                if response.session_id != record.public_id:
                    raise ServiceUnavailable("governed response session mismatch")
                elapsed_ms = int((time.monotonic() - started) * 1000)
                response.trace = [
                    TraceStep(
                        stage=author,
                        status="passed",
                        duration_ms=int(duration * 1000),
                    )
                    for author, duration in stage_durations.items()
                ] + [
                    TraceStep(stage=f"tool:{name}", status="passed")
                    for name in tool_trace_names
                ] + [
                    TraceStep(
                        stage="deterministic_gate",
                        status=(
                            "passed"
                            if response.governance.citation_gate_passed
                            and response.governance.scope_gate_passed
                            else "failed"
                        ),
                        duration_ms=0,
                    )
                ]
                if rotated:
                    response.warnings.append(
                        "Session history was rotated at the configured turn limit."
                    )
        except Exception as exc:
            error_code = type(exc).__name__
            raise
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            audit_event: dict[str, Any] = {
                "event": "chat_request",
                "request_id": request_id,
                "session_ref": hashlib.sha256(
                    record.public_id.encode("utf-8")
                ).hexdigest()[:24],
                "principal_ref": principal,
                "role": self.settings.app_server_role,
                "status": response.status if response else "error",
                "error_code": error_code,
                "duration_ms": elapsed_ms,
                "message_char_count": len(message),
                "model_calls": ledger.model_calls,
                "unmetered_model_calls": max(
                    0, ledger.model_calls - ledger.metered_model_calls
                ),
                "tool_calls": ledger.tool_calls,
                "input_tokens": ledger.input_tokens,
                "output_tokens": ledger.output_tokens,
                "evidence_count": len(ledger.read_evidence_ids),
                "history_rotated": rotated,
                "event_flow": [
                    {
                        "author": event["author"],
                        "function_calls": event["function_calls"],
                    }
                    for event in event_flow
                ],
                **self.settings.audit_model_metadata,
            }
            # This is deliberately inside finally: if it fails it replaces any
            # answer/error, ensuring unlogged requests fail closed.
            await self.audit.append(audit_event)

        if response is None:
            raise ServiceUnavailable("agent run failed closed")
        return response
