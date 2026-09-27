"""Offline regression for the self-contained local-scope claim contract."""

from app.agents import RESEARCHER_INSTRUCTION, REVIEWER_INSTRUCTION
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


def _gate(tmp_path, second_claim: str):
    source = SourceRecord(
        source_id="local_rules",
        title="Local Tournament Rules",
        version="Supplied copy",
        scope="Local tournament only",
        competition="Local Tournament",
        allowed_roles=["analyst"],
        page_count=1,
        sha256="a" * 64,
    )
    page = PageRecord(
        evidence_id="local_rules:p0001",
        source_id="local_rules",
        page=1,
        text="Local Tournament match and over conditions.",
    )
    index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[source],
        pages=[page],
    )
    index_path = tmp_path / "index.json"
    index_path.write_text(index.model_dump_json(), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=index_path,
        app_audit_path=tmp_path / "audit.jsonl",
    )
    ledger = RunLedger("scope-contract-request")
    ledger.issued_evidence_ids.add(page.evidence_id)
    ledger.read_evidence_ids.add(page.evidence_id)
    draft = ResearchDraft(
        status="answered",
        claims=[
            ClaimDraft(
                text="In the Local Tournament, this match uses the supplied conditions.",
                evidence_ids=[page.evidence_id],
            ),
            ClaimDraft(text=second_claim, evidence_ids=[page.evidence_id]),
        ],
    )
    review = ReviewDecision(
        verdict="pass",
        answer_status="answered",
        checked_claims=2,
        citation_support_ok=True,
        scope_and_version_ok=True,
        parts=[
            QuestionPartAssessment(
                part_id="answer",
                description="requested answer",
                supported=True,
                claim_indices=[0, 1],
            )
        ],
        all_parts_supported=True,
        conditions_preserved=True,
        unsupported_absence_claim_indices=[],
        abstention_justified=False,
    )
    return apply_gate(
        request_id=ledger.request_id,
        session_id="scope-contract-session-000000",
        role="analyst",
        draft=draft,
        review=review,
        ledger=ledger,
        repository=IndexRepository(settings),
        trace=[],
    )


def test_prompts_require_scope_on_every_individual_claim():
    assert "EVERY individual" in RESEARCHER_INSTRUCTION
    assert "never rely on a prior claim or sentence" in RESEARCHER_INSTRUCTION
    assert "Every individual" in REVIEWER_INSTRUCTION


def test_prompts_assess_qualifiers_from_complete_read_page_context():
    assert "complete text of each read evidence page" in RESEARCHER_INSTRUCTION
    assert "combined statements on that page" in RESEARCHER_INSTRUCTION
    assert "complete text of each read evidence page" in REVIEWER_INSTRUCTION
    assert "limitations as claims to verify" in REVIEWER_INSTRUCTION
    assert "evidence IDs attached to that" in REVIEWER_INSTRUCTION
    assert "cannot supply a missing premise" in REVIEWER_INSTRUCTION


def test_reviewer_prompt_states_cross_field_part_mapping_contract():
    assert "`supported: false`" in REVIEWER_INSTRUCTION
    assert "`claim_indices` must be an empty array" in REVIEWER_INSTRUCTION
    assert "`supported: true`" in REVIEWER_INSTRUCTION
    assert "at least one zero-based" in REVIEWER_INSTRUCTION


def test_prompts_do_not_invent_exclusivity_requirements():
    for instruction in (RESEARCHER_INSTRUCTION, REVIEWER_INSTRUCTION):
        assert "general rule supports a specific case" in instruction
        assert "applicable exception changes it" in instruction
        assert "apply exclusively" in instruction
        assert "actual source scope" in instruction


def test_second_local_claim_cannot_rely_on_first_claim_scope(tmp_path):
    result = _gate(tmp_path, "The total may be reduced under the supplied conditions.")

    assert not result.passed
    assert result.response.status == "rejected"


def test_second_local_claim_passes_when_it_repeats_exact_scope(tmp_path):
    result = _gate(
        tmp_path,
        "In the Local Tournament, the total may be reduced under the supplied conditions.",
    )

    assert result.passed
    assert result.response.status == "answered"
