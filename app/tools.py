"""Run-scoped governed ADK tools."""

from __future__ import annotations

import time
import re
import hashlib
from dataclasses import dataclass, field

from google.adk.tools import FunctionTool

from app.config import Settings
from app.index import IndexRepository
from app.models import EVIDENCE_ID_PATTERN


class BudgetExceeded(RuntimeError):
    """Raised when a request exceeds an application hard limit."""


EVIDENCE_ID_RE = re.compile(EVIDENCE_ID_PATTERN)
READ_UNAVAILABLE_ERROR = (
    "One or more requested evidence pages are unavailable for this invocation."
)
READ_SUGGESTION_LIMIT = 24


@dataclass
class RunLedger:
    request_id: str
    started_at: float = field(default_factory=time.monotonic)
    issued_evidence_ids: set[str] = field(default_factory=set)
    search_exposure_fingerprints: set[str] = field(default_factory=set)
    read_evidence_ids: set[str] = field(default_factory=set)
    listed_sources_successfully: bool = False
    successful_searches: int = 0
    last_search_hit_ids: set[str] = field(default_factory=set)
    last_search_issued_ids: set[str] = field(default_factory=set)
    read_evidence_attempts: int = 0
    ordinary_read_failures: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    evidence_chars: int = 0
    metered_model_calls: int = 0
    terminal_audit_written: bool = False
    original_question: str | None = None
    citation_repair_attempted: bool = False
    citation_repair_pending_ids: set[str] = field(default_factory=set)
    citation_repair_read_attempted: bool = False

    def reset(self, request_id: str) -> None:
        self.request_id = request_id
        self.started_at = time.monotonic()
        self.issued_evidence_ids.clear()
        self.search_exposure_fingerprints.clear()
        self.read_evidence_ids.clear()
        self.listed_sources_successfully = False
        self.successful_searches = 0
        self.last_search_hit_ids.clear()
        self.last_search_issued_ids.clear()
        self.read_evidence_attempts = 0
        self.ordinary_read_failures = 0
        self.model_calls = 0
        self.tool_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.evidence_chars = 0
        self.metered_model_calls = 0
        self.terminal_audit_written = False
        self.original_question = None
        self.citation_repair_attempted = False
        self.citation_repair_pending_ids.clear()
        self.citation_repair_read_attempted = False

    def check_time(self, settings: Settings) -> None:
        if time.monotonic() - self.started_at > settings.app_max_request_seconds:
            raise BudgetExceeded("request time budget exceeded")

    def begin_tool(self, settings: Settings) -> None:
        self.check_time(settings)
        if self.tool_calls >= settings.app_max_tool_calls:
            raise BudgetExceeded("tool-call budget exceeded")
        self.tool_calls += 1

    def add_evidence(self, settings: Settings, evidence_id: str, text: str) -> None:
        fingerprint = hashlib.sha256(
            f"{evidence_id}\0{text}".encode("utf-8")
        ).hexdigest()
        if fingerprint in self.search_exposure_fingerprints:
            return
        projected = self.evidence_chars + len(text)
        if projected > settings.app_max_evidence_chars:
            raise BudgetExceeded("evidence character budget exceeded")
        self.evidence_chars = projected
        self.issued_evidence_ids.add(evidence_id)
        self.search_exposure_fingerprints.add(fingerprint)

    def add_evidence_batch(
        self, settings: Settings, evidence: list[tuple[str, str]]
    ) -> None:
        new_evidence: list[tuple[str, str, str]] = []
        new_fingerprints = set(self.search_exposure_fingerprints)
        for evidence_id, text in evidence:
            fingerprint = hashlib.sha256(
                f"{evidence_id}\0{text}".encode("utf-8")
            ).hexdigest()
            if fingerprint in new_fingerprints:
                continue
            new_evidence.append((evidence_id, text, fingerprint))
            new_fingerprints.add(fingerprint)
        projected = self.evidence_chars + sum(
            len(text) for _evidence_id, text, _fingerprint in new_evidence
        )
        if projected > settings.app_max_evidence_chars:
            raise BudgetExceeded("evidence character budget exceeded")
        self.evidence_chars = projected
        for evidence_id, _text, fingerprint in new_evidence:
            self.issued_evidence_ids.add(evidence_id)
            self.search_exposure_fingerprints.add(fingerprint)

    def issue_evidence_references(self, evidence_ids: set[str]) -> None:
        """Issue visible evidence references without pretending text was returned."""
        self.issued_evidence_ids.update(evidence_ids)

    def add_read_evidence(
        self, settings: Settings, evidence_id: str, text: str
    ) -> None:
        if evidence_id in self.read_evidence_ids:
            return
        projected = self.evidence_chars + len(text)
        if projected > settings.app_max_evidence_chars:
            raise BudgetExceeded("evidence character budget exceeded")
        self.evidence_chars = projected
        self.issued_evidence_ids.add(evidence_id)
        self.read_evidence_ids.add(evidence_id)

    def add_read_evidence_batch(
        self, settings: Settings, evidence: list[tuple[str, str]]
    ) -> None:
        new_evidence = [
            (evidence_id, text)
            for evidence_id, text in evidence
            if evidence_id not in self.read_evidence_ids
        ]
        projected = self.evidence_chars + sum(
            len(text) for _evidence_id, text in new_evidence
        )
        if projected > settings.app_max_evidence_chars:
            raise BudgetExceeded("evidence character budget exceeded")
        self.evidence_chars = projected
        for evidence_id, _text in new_evidence:
            self.issued_evidence_ids.add(evidence_id)
            self.read_evidence_ids.add(evidence_id)


def build_tools(
    repository: IndexRepository,
    settings: Settings,
    ledger: RunLedger,
    role: str,
) -> list[FunctionTool]:
    if role != settings.app_server_role or role not in settings.allowed_roles:
        raise PermissionError("server role is not authorized")

    def effective_search_queries(refinement: str) -> tuple[str, str]:
        refinement = refinement.strip()
        if not refinement:
            raise ValueError("query cannot be blank")
        if len(refinement) > settings.app_max_search_query_chars:
            raise ValueError("query refinement exceeds the configured length limit")
        original = (ledger.original_question or "").strip()
        if not original or original.casefold() == refinement.casefold():
            combined = original or refinement
            lexical = combined
        else:
            combined = (
                "Current user question; preserve every constraint:\n"
                f"{original}\nSearch refinement:\n{refinement}"
            )
            # Keep the model refinement alongside every original constraint,
            # without letting the fixed transport labels become BM25 terms.
            lexical = f"{original}\n{refinement}"
        if len(combined) > settings.app_max_effective_search_query_chars:
            raise ValueError(
                "current question plus query refinement exceeds the configured "
                "retrieval length limit"
            )
        return combined, lexical

    def list_sources() -> dict[str, object]:
        """List sources authorized for this server-assigned role and their scopes."""
        ledger.begin_tool(settings)
        sources = repository.list_sources(role)
        ledger.listed_sources_successfully = True
        return {"sources": [source.model_dump() for source in sources]}

    def search_documents(
        query: str, source_ids: list[str] | None = None, top_k: int = 5
    ) -> dict[str, object]:
        """Search authorized documents. Returns page evidence IDs and scoped snippets."""
        ledger.begin_tool(settings)
        bounded_top_k = max(1, min(top_k, settings.app_max_search_results))
        effective_query, lexical_query = effective_search_queries(query)
        hits = repository.search(
            effective_query,
            role=role,
            top_k=bounded_top_k,
            source_ids=source_ids,
            lexical_query=lexical_query,
        )
        adjacent_ids = {
            evidence_id
            for hit in hits
            for evidence_id in hit.adjacent_evidence_ids
        }
        ledger.add_evidence_batch(
            settings,
            [(hit.evidence_id, hit.snippet) for hit in hits]
            + [
                (preview.evidence_id, preview.snippet)
                for hit in hits
                for preview in hit.adjacent_previews
            ],
        )
        ledger.issue_evidence_references(adjacent_ids)
        ledger.successful_searches += 1
        ledger.last_search_hit_ids = {hit.evidence_id for hit in hits}
        ledger.last_search_issued_ids = ledger.last_search_hit_ids | adjacent_ids
        return {"results": [hit.model_dump() for hit in hits]}

    def read_evidence(evidence_ids: list[str]) -> dict[str, object]:
        """Read up to eight authorized pages by exact evidence ID."""
        ledger.begin_tool(settings)
        ledger.read_evidence_attempts += 1

        def unavailable_response(*, formatter_repair: bool) -> dict[str, object]:
            suggestions: list[str] = []
            for evidence_id in sorted(ledger.last_search_issued_ids):
                try:
                    repository.page(evidence_id, role)
                except (KeyError, PermissionError):
                    continue
                suggestions.append(evidence_id)
                if len(suggestions) >= READ_SUGGESTION_LIMIT:
                    break
            if not formatter_repair and ledger.ordinary_read_failures < 2:
                ledger.ordinary_read_failures += 1
            retry_allowed = (
                not formatter_repair
                and ledger.ordinary_read_failures == 1
                and bool(suggestions)
                and ledger.model_calls + 3 <= settings.app_max_model_calls
                and ledger.tool_calls < settings.app_max_tool_calls
            )
            if not retry_allowed and not formatter_repair:
                ledger.ordinary_read_failures = 2
            guidance = (
                "Retry read_evidence once using exact IDs from allowed_evidence_ids."
                if retry_allowed
                else "No further read retry is available; finalize with insufficient_evidence."
            )
            return {
                "error": READ_UNAVAILABLE_ERROR,
                "allowed_evidence_ids": suggestions,
                "retry_allowed": retry_allowed,
                "guidance": guidance,
            }

        formatter_repair = bool(ledger.citation_repair_pending_ids)
        if ledger.ordinary_read_failures >= 2 and not formatter_repair:
            return unavailable_response(formatter_repair=False)
        invalid_request = (
            type(evidence_ids) is not list
            or not evidence_ids
            or len(evidence_ids) > 8
            or any(
                type(evidence_id) is not str
                or EVIDENCE_ID_RE.fullmatch(evidence_id) is None
                for evidence_id in evidence_ids
            )
            or len(evidence_ids) != len(set(evidence_ids))
            or not set(evidence_ids).issubset(ledger.issued_evidence_ids)
        )
        resolved = None
        if not invalid_request:
            try:
                resolved = [
                    repository.page(evidence_id, role) for evidence_id in evidence_ids
                ]
            except (KeyError, PermissionError):
                resolved = None
        if resolved is None:
            return unavailable_response(formatter_repair=formatter_repair)
        ledger.add_read_evidence_batch(
            settings,
            [(page.evidence_id, page.text) for page, _source in resolved],
        )
        records: list[dict[str, object]] = []
        for page, source in resolved:
            records.append(
                {
                    "evidence_id": page.evidence_id,
                    "source_id": page.source_id,
                    "title": source.title,
                    "version": source.version,
                    "scope": source.scope,
                    "competition": source.competition,
                    "page": page.page,
                    "text": page.text,
                }
            )
        return {"evidence": records}

    return [
        FunctionTool(list_sources),
        FunctionTool(search_documents),
        FunctionTool(read_evidence),
    ]
