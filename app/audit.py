"""Append-only metadata audit logging; content is deliberately excluded."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALLOWED_FIELDS = frozenset(
    {
        "event",
        "request_id",
        "session_ref",
        "principal_ref",
        "role",
        "status",
        "error_code",
        "duration_ms",
        "message_char_count",
        "model_calls",
        "unmetered_model_calls",
        "tool_calls",
        "input_tokens",
        "output_tokens",
        "evidence_count",
        "history_rotated",
        "event_flow",
        "gate_passed",
        "model",
        "model_provider",
        "model_location",
    }
)
ALLOWED_EVENTS = frozenset(
    {"chat_preflight", "chat_request", "adk_cli_preflight", "adk_cli_run"}
)
ALLOWED_AUTHORS = frozenset(
    {
        "document_research_pipeline",
        "document_researcher",
        "evidence_reviewer",
        "deterministic_evidence_gate",
        "governed_document_assistant",
        "__unknown_agent__",
    }
)
ALLOWED_TOOLS = frozenset(
    {
        "list_sources",
        "search_documents",
        "read_evidence",
        "set_model_response",
        "__unknown_tool__",
    }
)


AUDIT_STDOUT_LOGGER = logging.getLogger("app.audit.stdout")
AUDIT_STDOUT_LOGGER.setLevel(logging.INFO)
AUDIT_STDOUT_LOGGER.propagate = False
if not AUDIT_STDOUT_LOGGER.handlers:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    AUDIT_STDOUT_LOGGER.addHandler(stdout_handler)


class AuditWriteError(RuntimeError):
    """Raised when a required audit record cannot be made durable."""


class AuditLogger:
    def __init__(self, path: Path):
        self.path = path
        self._thread_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def append_sync(self, event: dict[str, Any]) -> None:
        unknown = set(event).difference(ALLOWED_FIELDS)
        if unknown:
            raise AuditWriteError("audit event contains non-metadata fields")
        if event.get("event") not in ALLOWED_EVENTS:
            raise AuditWriteError("audit event type is not allowlisted")
        flow = event.get("event_flow", [])
        if not isinstance(flow, list):
            raise AuditWriteError("audit event_flow must be a list")
        for item in flow:
            if not isinstance(item, dict) or set(item) != {
                "author",
                "function_calls",
            }:
                raise AuditWriteError("audit event_flow shape is invalid")
            if item["author"] not in ALLOWED_AUTHORS:
                raise AuditWriteError("audit author is not allowlisted")
            if not isinstance(item["function_calls"], list) or any(
                tool not in ALLOWED_TOOLS for tool in item["function_calls"]
            ):
                raise AuditWriteError("audit tool name is not allowlisted")
        for field_name in ("model", "model_provider", "model_location"):
            value = event.get(field_name)
            allowed_punctuation = "._/-:" if field_name == "model" else "._/-"
            if value is not None and (
                not isinstance(value, str)
                or not value
                or len(value) > 128
                or any(
                    not (character.isalnum() or character in allowed_punctuation)
                    for character in value
                )
            ):
                raise AuditWriteError("audit model metadata is invalid")
        record = {
            "schema_version": 1,
            "timestamp": datetime.now(UTC).isoformat(),
            **event,
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            with self._thread_lock:
                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(
                    self.path,
                    os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                    0o600,
                )
                try:
                    encoded = line.encode("utf-8")
                    written = 0
                    while written < len(encoded):
                        count = os.write(descriptor, encoded[written:])
                        if count <= 0:
                            raise OSError("short audit write")
                        written += count
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            AUDIT_STDOUT_LOGGER.info(line.rstrip())
        except OSError as exc:
            raise AuditWriteError("required audit write failed") from exc

    async def append(self, event: dict[str, Any]) -> None:
        async with self._async_lock:
            await asyncio.to_thread(self.append_sync, event)
