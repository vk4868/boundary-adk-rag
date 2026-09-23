"""Offline regressions for question coverage and condition preservation."""

import json

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.gate import apply_gate
from app.index import IndexRepository
from app.models import (
    ClaimDraft,
    CorpusIndex,
    EmbeddingDescriptor,
    PageRecord,
    QuestionPartAssessment,
    ResearchDraft,
    ReviewDecision,
    SourceRecord,
)
from app.tools import RunLedger


@pytest.fixture
def governed_context(tmp_path):
    source = SourceRecord(
        source_id="rules",
        title="Supplied Rules",
        version="test",
        scope="test scope",
        competition="MCC",
        allowed_roles=["analyst"],
        page_count=2,
        sha256="a" * 64,
    )
    pages = [
        PageRecord(
            evidence_id=f"rules:p{page_number:04d}",
            source_id="rules",
            page=page_number,
            text=f"Supporting rule part {page_number} with its conditions.",
        )
        for page_number in (1, 2)
    ]
    index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[source],
        pages=pages,
    )
    path = tmp_path / "index.json"
    path.write_text(index.model_dump_json(), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=path,
        app_audit_path=tmp_path / "audit.jsonl",
    )
    ledger = RunLedger("coverage-request")
    ledger.issued_evidence_ids.update(page.evidence_id for page in pages)
    ledger.read_evidence_ids.update(page.evidence_id for page in pages)
    return IndexRepository(settings), ledger


def _answered_draft() -> ResearchDraft:
    return ResearchDraft(
        status="answered",
        claims=[
            ClaimDraft(text="The first requested side is conditional.", evidence_ids=["rules:p0001"]),
            ClaimDraft(text="The second requested side differs.", evidence_ids=["rules:p0002"]),
        ],
    )


def _passing_answer_review() -> ReviewDecision:
    return ReviewDecision(
        verdict="pass",
        answer_status="answered",
        checked_claims=2,
        citation_support_ok=True,
        scope_and_version_ok=True,
        parts=[
            QuestionPartAssessment(
                part_id="first",
                description="first comparison side",
                supported=True,
                claim_indices=[0],
            ),
            QuestionPartAssessment(
                part_id="second",
                description="second comparison side",
                supported=True,
                claim_indices=[1],
            ),
        ],
        all_parts_supported=True,
        conditions_preserved=True,
        unsupported_absence_claim_indices=[],
        abstention_justified=False,
    )


def _gate(context, draft, review):
    repository, ledger = context
    return apply_gate(
        request_id=ledger.request_id,
        session_id="s" * 24,
        role="analyst",
        draft=draft,
        review=review,
        ledger=ledger,
        repository=repository,
        trace=[],
    )


def test_answer_requires_nonvacuous_question_part_mapping(governed_context):
    result = _gate(governed_context, _answered_draft(), _passing_answer_review())
    assert result.passed

    review = _passing_answer_review()
    review.parts[1].claim_indices = [2]
    assert not _gate(governed_context, _answered_draft(), review).passed


@pytest.mark.parametrize("bad_index", [True, 1.0, "1"])
def test_claim_indices_are_strict_integers(bad_index):
    with pytest.raises(ValidationError):
        QuestionPartAssessment(
            part_id="part",
            description="requested part",
            supported=True,
            claim_indices=[bad_index],
        )


def test_duplicate_or_vacuous_part_coverage_is_rejected():
    common = dict(
        verdict="fail",
        answer_status="answered",
        checked_claims=1,
        citation_support_ok=False,
        scope_and_version_ok=True,
        all_parts_supported=False,
        conditions_preserved=False,
        unsupported_absence_claim_indices=[],
        abstention_justified=False,
        issues=["incomplete"],
    )
    duplicate = QuestionPartAssessment(
        part_id="part",
        description="requested part",
        supported=False,
        claim_indices=[],
    )
    with pytest.raises(ValidationError):
        ReviewDecision(parts=[duplicate, duplicate.model_copy()], **common)
    with pytest.raises(ValidationError):
        QuestionPartAssessment(
            part_id="part",
            description="  --  ",
            supported=False,
            claim_indices=[],
        )


def test_pass_cannot_hide_missing_conditions_or_unsupported_absence():
    values = _passing_answer_review().model_dump()
    values["conditions_preserved"] = False
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate(values)

    values = _passing_answer_review().model_dump()
    values["unsupported_absence_claim_indices"] = [1]
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate(values)


def test_legitimate_abstention_uses_separate_zero_claim_policy(governed_context):
    draft = ResearchDraft(
        status="insufficient_evidence",
        claims=[],
        limitations=["The requested condition was not found."],
    )
    review = ReviewDecision(
        verdict="pass",
        answer_status="insufficient_evidence",
        checked_claims=0,
        citation_support_ok=True,
        scope_and_version_ok=True,
        parts=[
            QuestionPartAssessment(
                part_id="condition",
                description="requested condition",
                supported=False,
                claim_indices=[],
            )
        ],
        all_parts_supported=False,
        conditions_preserved=False,
        unsupported_absence_claim_indices=[],
        abstention_justified=True,
    )
    result = _gate(governed_context, draft, review)
    assert result.passed
    assert result.response.status == "insufficient_evidence"

    invalid = review.model_dump()
    invalid["parts"][0]["supported"] = True
    invalid["parts"][0]["claim_indices"] = [0]
    invalid["all_parts_supported"] = True
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate(invalid)


def test_compact_six_part_review_is_well_below_output_budget_shape():
    review = ReviewDecision(
        verdict="pass",
        answer_status="answered",
        checked_claims=12,
        citation_support_ok=True,
        scope_and_version_ok=True,
        parts=[
            QuestionPartAssessment(
                part_id=f"part{i}",
                description=f"requested comparison part {i}",
                supported=True,
                claim_indices=[2 * i, 2 * i + 1],
            )
            for i in range(6)
        ],
        all_parts_supported=True,
        conditions_preserved=True,
        unsupported_absence_claim_indices=[],
        abstention_justified=False,
    )
    serialized = json.dumps(review.model_dump(), separators=(",", ":"))
    assert len(serialized) < 1800
