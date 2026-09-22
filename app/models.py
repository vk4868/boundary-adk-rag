"""Typed contracts shared by ingestion, retrieval, agents, and the API."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RoleName = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManifestSource(StrictModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    title: str = Field(min_length=1, max_length=300)
    version: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=500)
    competition: str = Field(min_length=1, max_length=200)
    allowed_roles: list[RoleName] = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("allowed_roles")
    @classmethod
    def validate_roles(cls, roles: list[str]) -> list[str]:
        cleaned = [role.strip() for role in roles]
        if any(not role or len(role) > 64 for role in cleaned):
            raise ValueError("allowed_roles entries must be 1-64 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("allowed_roles entries must be unique")
        return cleaned


class CorpusManifest(StrictModel):
    schema_version: Literal[1]
    sources: list[ManifestSource] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_source_ids(self) -> "CorpusManifest":
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source_id values must be unique")
        return self


class SourceRecord(StrictModel):
    source_id: str
    title: str
    version: str
    scope: str
    competition: str
    allowed_roles: list[str]
    page_count: int = Field(ge=1)
    sha256: str


class PageRecord(StrictModel):
    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}:p\d{4,}$")
    source_id: str
    page: int = Field(ge=1)
    text: str
    embedding: list[float] | None = None


class EmbeddingDescriptor(StrictModel):
    provider: Literal["lexical", "vertex"]
    model: str | None = None
    location: str | None = None
    dimensions: int | None = Field(default=None, ge=1)
    task_type: str | None = None
    billable_character_count: int | None = Field(default=None, ge=0)
    truncated_page_count: int | None = Field(default=None, ge=0)


class CorpusIndex(StrictModel):
    schema_version: Literal[1]
    embedding: EmbeddingDescriptor
    sources: list[SourceRecord]
    pages: list[PageRecord]

    @model_validator(mode="after")
    def validate_references(self) -> "CorpusIndex":
        ordered_source_ids = [source.source_id for source in self.sources]
        source_ids = set(ordered_source_ids)
        if len(source_ids) != len(ordered_source_ids):
            raise ValueError("index source_id values must be unique")
        evidence_ids: set[str] = set()
        page_numbers = {source.source_id: set() for source in self.sources}
        for page in self.pages:
            if page.source_id not in source_ids:
                raise ValueError(f"unknown page source_id: {page.source_id}")
            if page.evidence_id in evidence_ids:
                raise ValueError(f"duplicate evidence_id: {page.evidence_id}")
            if page.evidence_id != f"{page.source_id}:p{page.page:04d}":
                raise ValueError(f"non-canonical evidence_id: {page.evidence_id}")
            evidence_ids.add(page.evidence_id)
            page_numbers[page.source_id].add(page.page)
            if self.embedding.provider == "vertex" and page.embedding is None:
                raise ValueError(f"missing embedding: {page.evidence_id}")
            if page.embedding is not None:
                if self.embedding.dimensions is None:
                    raise ValueError("embedding dimensions descriptor is missing")
                if len(page.embedding) != self.embedding.dimensions:
                    raise ValueError(f"embedding dimension mismatch: {page.evidence_id}")
                if not all(math.isfinite(value) for value in page.embedding):
                    raise ValueError(f"non-finite embedding value: {page.evidence_id}")
        for source in self.sources:
            expected_pages = set(range(1, source.page_count + 1))
            if page_numbers[source.source_id] != expected_pages:
                raise ValueError(f"page set is not contiguous: {source.source_id}")
        return self


class PublicSource(StrictModel):
    source_id: str
    title: str
    version: str
    scope: str
    page_count: int


class SearchHit(StrictModel):
    evidence_id: str
    source_id: str
    title: str
    version: str
    scope: str
    page: int
    snippet: str
    score: float
    retrieval_method: Literal["lexical", "vertex_hybrid"]


class ClaimDraft(StrictModel):
    text: str = Field(min_length=1, max_length=1400)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, evidence_ids: list[str]) -> list[str]:
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("claim evidence_ids must be unique")
        return evidence_ids


class ResearchDraft(StrictModel):
    status: Literal["answered", "insufficient_evidence"]
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def claims_match_status(self) -> "ResearchDraft":
        if self.status == "answered" and not self.claims:
            raise ValueError("answered drafts require at least one cited claim")
        if self.status == "insufficient_evidence" and self.claims:
            raise ValueError("insufficient_evidence drafts cannot contain claims")
        return self


class ReviewDecision(StrictModel):
    verdict: Literal["pass", "fail"]
    checked_claims: int = Field(ge=0, le=12)
    citation_support_ok: bool
    scope_and_version_ok: bool
    issues: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def pass_is_consistent(self) -> "ReviewDecision":
        if self.verdict == "pass" and (
            not self.citation_support_ok or not self.scope_and_version_ok or self.issues
        ):
            raise ValueError("pass verdict must have both checks true and no issues")
        return self


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=6000)
    session_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{24,96}$"
    )
    role: str | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, message: str) -> str:
        cleaned = message.strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class ClaimResponse(StrictModel):
    text: str
    evidence_ids: list[str]


class CitationResponse(StrictModel):
    id: str
    source_id: str
    title: str
    page: int
    text: str


class TraceStep(StrictModel):
    stage: str
    status: Literal["passed", "failed", "skipped"]
    duration_ms: int | None = Field(default=None, ge=0)


class UsageResponse(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)


class GovernanceResponse(StrictModel):
    review_passed: bool
    citation_gate_passed: bool
    scope_gate_passed: bool


class ChatResponse(StrictModel):
    request_id: str
    session_id: str
    status: Literal["answered", "insufficient_evidence", "rejected"]
    answer: str
    claims: list[ClaimResponse]
    citations: list[CitationResponse]
    sources: list[PublicSource]
    trace: list[TraceStep]
    usage: UsageResponse
    governance: GovernanceResponse
    warnings: list[str]


class SourceListResponse(StrictModel):
    sources: list[PublicSource]
