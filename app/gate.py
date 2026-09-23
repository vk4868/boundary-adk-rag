"""Deterministic post-model gate for evidence, ACL, and source scope."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.index import IndexRepository
from app.models import (
    ChatResponse,
    CitationResponse,
    ClaimResponse,
    GovernanceResponse,
    PublicSource,
    ResearchDraft,
    ReviewDecision,
    TraceStep,
    UsageResponse,
)
from app.tools import RunLedger


GLOBAL_CLAIM_RE = re.compile(
    r"\b(all cricket|in cricket(?:,|\s)|always|worldwide|universal|official law)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GateResult:
    response: ChatResponse
    passed: bool
    reason: str


def _usage(ledger: RunLedger) -> UsageResponse:
    return UsageResponse(
        input_tokens=ledger.input_tokens,
        output_tokens=ledger.output_tokens,
        model_calls=ledger.model_calls,
        tool_calls=ledger.tool_calls,
    )


def _rejected(
    *,
    request_id: str,
    session_id: str,
    ledger: RunLedger,
    reason: str,
    trace: list[TraceStep],
    review_passed: bool,
    citation_passed: bool,
    scope_passed: bool,
) -> GateResult:
    trace.append(TraceStep(stage="deterministic_gate", status="failed"))
    return GateResult(
        response=ChatResponse(
            request_id=request_id,
            session_id=session_id,
            status="rejected",
            answer="The response was withheld because it did not pass the evidence review.",
            claims=[],
            citations=[],
            sources=[],
            trace=trace,
            usage=_usage(ledger),
            governance=GovernanceResponse(
                review_passed=review_passed,
                citation_gate_passed=citation_passed,
                scope_gate_passed=scope_passed,
            ),
            warnings=[reason],
        ),
        passed=False,
        reason=reason,
    )


def apply_gate(
    *,
    request_id: str,
    session_id: str,
    role: str,
    draft: ResearchDraft,
    review: ReviewDecision,
    ledger: RunLedger,
    repository: IndexRepository,
    trace: list[TraceStep],
) -> GateResult:
    review_passed = (
        review.verdict == "pass"
        and review.answer_status == draft.status
        and review.citation_support_ok
        and review.scope_and_version_ok
        and not review.issues
        and review.checked_claims == len(draft.claims)
    )
    if draft.status == "answered":
        coverage_passed = (
            review.all_parts_supported
            and review.conditions_preserved
            and not review.unsupported_absence_claim_indices
            and not review.abstention_justified
        )
        for part in review.parts:
            if not part.supported or not part.claim_indices:
                coverage_passed = False
                break
            for claim_index in part.claim_indices:
                if claim_index >= len(draft.claims):
                    coverage_passed = False
                    break
                if any(
                    evidence_id not in ledger.read_evidence_ids
                    for evidence_id in draft.claims[claim_index].evidence_ids
                ):
                    coverage_passed = False
                    break
            if not coverage_passed:
                break
        if any(
            claim_index >= len(draft.claims)
            for claim_index in review.unsupported_absence_claim_indices
        ):
            coverage_passed = False
        review_passed = review_passed and coverage_passed
    else:
        abstention_passed = (
            not draft.claims
            and review.checked_claims == 0
            and not review.all_parts_supported
            and all(
                not part.supported and not part.claim_indices
                for part in review.parts
            )
            and not review.unsupported_absence_claim_indices
            and review.abstention_justified
        )
        review_passed = review_passed and abstention_passed
    if not review_passed:
        return _rejected(
            request_id=request_id,
            session_id=session_id,
            ledger=ledger,
            reason="independent reviewer rejected the draft",
            trace=trace,
            review_passed=False,
            citation_passed=False,
            scope_passed=False,
        )

    if draft.status == "insufficient_evidence":
        trace.append(TraceStep(stage="deterministic_gate", status="passed"))
        return GateResult(
            response=ChatResponse(
                request_id=request_id,
                session_id=session_id,
                status="insufficient_evidence",
                answer="The authorized sources do not contain enough evidence to answer this question.",
                claims=[],
                citations=[],
                sources=[],
                trace=trace,
                usage=_usage(ledger),
                governance=GovernanceResponse(
                    review_passed=True,
                    citation_gate_passed=True,
                    scope_gate_passed=True,
                ),
                warnings=draft.limitations,
            ),
            passed=True,
            reason="insufficient evidence abstention passed",
        )

    citations: dict[str, CitationResponse] = {}
    used_sources: dict[str, PublicSource] = {}
    claim_responses: list[ClaimResponse] = []
    citation_passed = True
    scope_passed = True
    failure_reason = ""

    for claim in draft.claims:
        if not claim.evidence_ids or any(
            evidence_id not in ledger.read_evidence_ids
            for evidence_id in claim.evidence_ids
        ):
            citation_passed = False
            failure_reason = "claim cites evidence not read in this run"
            break
        claim_sources = {}
        try:
            for evidence_id in claim.evidence_ids:
                page, source = repository.page(evidence_id, role)
                claim_sources[source.source_id] = source
                citations[evidence_id] = CitationResponse(
                    id=evidence_id,
                    source_id=source.source_id,
                    title=source.title,
                    page=page.page,
                    text=page.text,
                )
                used_sources[source.source_id] = PublicSource(
                    source_id=source.source_id,
                    title=source.title,
                    version=source.version,
                    scope=source.scope,
                    page_count=source.page_count,
                )
        except (KeyError, PermissionError):
            citation_passed = False
            failure_reason = "claim cites missing or unauthorized evidence"
            break

        local_sources = [
            source for source in claim_sources.values() if source.competition != "MCC"
        ]
        if local_sources and GLOBAL_CLAIM_RE.search(claim.text):
            scope_passed = False
            failure_reason = "local rules were generalized beyond their source scope"
            break
        if local_sources and not all(
            source.competition.lower() in claim.text.lower()
            or source.title.lower() in claim.text.lower()
            for source in local_sources
        ):
            scope_passed = False
            failure_reason = "local-source claim does not identify its competition"
            break
        if len(claim_sources) > 1 and not all(
            source.title.lower() in claim.text.lower()
            or source.competition.lower() in claim.text.lower()
            for source in claim_sources.values()
        ):
            scope_passed = False
            failure_reason = "cross-source claim does not identify every source scope"
            break
        claim_responses.append(
            ClaimResponse(text=claim.text, evidence_ids=claim.evidence_ids)
        )

    if not citation_passed or not scope_passed:
        return _rejected(
            request_id=request_id,
            session_id=session_id,
            ledger=ledger,
            reason=failure_reason,
            trace=trace,
            review_passed=True,
            citation_passed=citation_passed,
            scope_passed=scope_passed,
        )

    trace.append(TraceStep(stage="deterministic_gate", status="passed"))
    answer = "\n\n".join(
        f"{claim.text} [{', '.join(claim.evidence_ids)}]" for claim in draft.claims
    )
    return GateResult(
        response=ChatResponse(
            request_id=request_id,
            session_id=session_id,
            status="answered",
            answer=answer,
            claims=claim_responses,
            citations=[citations[key] for key in sorted(citations)],
            sources=[used_sources[key] for key in sorted(used_sources)],
            trace=trace,
            usage=_usage(ledger),
            governance=GovernanceResponse(
                review_passed=True,
                citation_gate_passed=True,
                scope_gate_passed=True,
            ),
            warnings=draft.limitations,
        ),
        passed=True,
        reason="all gates passed",
    )
