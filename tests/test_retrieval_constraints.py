"""Offline regressions for constraint-preserving hybrid retrieval."""

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.index import (
    IndexRepository,
    _adjacent_preview,
    _bm25_scores,
    _query_focused_snippet,
)
from app.models import CorpusIndex, EmbeddingDescriptor, PageRecord, SourceRecord
from app.tools import RunLedger, build_tools


def _settings(tmp_path, **overrides):
    values = {
        "_env_file": None,
        "app_embedding_provider": "lexical",
        "app_index_path": tmp_path / "unused.json",
        "app_audit_path": tmp_path / "audit.jsonl",
    }
    values.update(overrides)
    return Settings(**values)


def test_search_tool_preserves_exact_current_question_and_refinement(tmp_path):
    settings = _settings(tmp_path)
    ledger = RunLedger("constraint-run")
    ledger.original_question = (
        "How many players can bat and bowl in the Under 12 pathways format?"
    )

    class CapturingRepository:
        query = None
        lexical_query = None

        def search(self, query, **kwargs):
            self.query = query
            self.lexical_query = kwargs["lexical_query"]
            return []

    repository = CapturingRepository()
    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )
    search_tool.func(query="Under 12 batting and bowling rules")

    assert ledger.original_question in repository.query
    assert "Under 12 batting and bowling rules" in repository.query
    assert repository.query.index(ledger.original_question) < repository.query.index(
        "Under 12 batting and bowling rules"
    )
    assert ledger.original_question in repository.lexical_query
    assert "Under 12 batting and bowling rules" in repository.lexical_query
    assert "Current user question" not in repository.lexical_query
    assert "Search refinement" not in repository.lexical_query


def test_combined_query_fails_instead_of_silently_truncating_constraints(tmp_path):
    settings = _settings(
        tmp_path,
        app_max_search_query_chars=80,
        app_max_effective_search_query_chars=1250,
    )
    ledger = RunLedger("bounded-query-run")
    ledger.original_question = "x" * 1220

    class UncalledRepository:
        def search(self, *_args, **_kwargs):
            raise AssertionError("oversized query must fail before retrieval")

    search_tool = next(
        tool
        for tool in build_tools(UncalledRepository(), settings, ledger, "analyst")
        if tool.name == "search_documents"
    )
    with pytest.raises(ValueError, match="question plus query refinement"):
        search_tool.func(query="specific final constraint")


def test_focused_snippet_selects_relevant_later_passage():
    prefix = "length and width of unrelated equipment " + "filler " * 115
    relevant = (
        "requested pitch dimensions are 22 units in length and 10 units in width"
    )
    page = PageRecord(
        evidence_id="rules:p0001",
        source_id="rules",
        page=1,
        text=prefix + relevant + " trailing " * 80,
    )
    pages = [page]
    _scores, frequencies = _bm25_scores("pitch length width", pages)

    snippet = _query_focused_snippet(
        page.text,
        "pitch length width",
        document_frequency=frequencies,
        document_count=1,
    )

    assert len(snippet) <= 700
    assert relevant in snippet


def test_focused_snippet_keeps_numeric_qualifier_atomic():
    opening = (
        "The changed rule for Under 11 boys requires the bowling end to remain "
        "the same for the innings. "
    )
    page = PageRecord(
        evidence_id="rules:p0001",
        source_id="rules",
        page=1,
        text=(
            opening
            + "unrelated filler " * 80
            + "Under 12 boys junior rules Rule 11.2 changed. " * 25
        ),
    )
    query = "What changed for Under 11 boys about the bowling end?"
    _scores, frequencies = _bm25_scores(query, [page])

    snippet = _query_focused_snippet(
        page.text,
        query,
        document_frequency=frequencies,
        document_count=1,
    )

    assert opening.strip() in snippet
    assert "Rule 11.2 changed" not in snippet


def test_source_filtered_search_preserves_dotted_reference_for_neighbor_preview(
    tmp_path, monkeypatch
):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    source = SourceRecord(
        source_id="mcc_rules",
        title="MCC Laws of Cricket",
        version="test",
        scope="general laws",
        competition="MCC",
        allowed_roles=["analyst"],
        page_count=3,
        sha256="4" * 64,
    )
    exact_rule = (
        "LAW 17 THE OVER 17.1 Number of balls. The ball shall be bowled from "
        "each end alternately in overs of 6 valid balls."
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="vertex",
            model=settings.app_embedding_model,
            location=settings.embedding_location,
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=1,
            truncated_page_count=0,
        ),
        sources=[source],
        pages=[
            PageRecord(
                evidence_id="mcc_rules:p0001",
                source_id="mcc_rules",
                page=1,
                text="prefix " * 100 + exact_rule + " suffix " * 100,
                embedding=[-1.0, 0.0],
            ),
            PageRecord(
                evidence_id="mcc_rules:p0002",
                source_id="mcc_rules",
                page=2,
                text="Compare the bowling end rule and bowler changing ends.",
                embedding=[1.0, 0.0],
            ),
            PageRecord(
                evidence_id="mcc_rules:p0003",
                source_id="mcc_rules",
                page=3,
                text="Unrelated scoring material.",
                embedding=[0.0, 1.0],
            ),
        ],
    )
    monkeypatch.setattr(repository, "_query_embedding", lambda *_args: [1.0, 0.0])
    query = "Compare the bowling-end rule in MCC Law 17.1"

    hits = repository.search(
        query,
        lexical_query=query,
        role="analyst",
        top_k=1,
        source_ids=["mcc_rules"],
    )

    assert hits[0].evidence_id == "mcc_rules:p0002"
    assert hits[0].adjacent_previews[0].evidence_id == "mcc_rules:p0001"
    assert exact_rule in hits[0].adjacent_previews[0].snippet


def test_neighbor_preview_does_not_prefix_match_longer_dotted_reference():
    text = (
        "head material " * 80
        + "WRONG ANCHOR 17.10 unrelated provision "
        + "middle material " * 80
        + "TAIL MARKER relevant boundary context"
    )

    preview = _adjacent_preview(
        text,
        "requested Law 17.1",
        relation="previous",
    )

    assert "TAIL MARKER" in preview
    assert "WRONG ANCHOR" not in preview


def test_vertex_search_hybrid_reranks_exact_constraints_without_provider_call(
    tmp_path, monkeypatch
):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    source = SourceRecord(
        source_id="rules",
        title="Rules",
        version="test",
        scope="test scope",
        competition="test competition",
        allowed_roles=["analyst"],
        page_count=3,
        sha256="0" * 64,
    )
    pages = [
        PageRecord(
            evidence_id="rules:p0001",
            source_id="rules",
            page=1,
            text="General junior batting rules and introductory material.",
            embedding=[1.0, 0.0],
        ),
        PageRecord(
            evidence_id="rules:p0002",
            source_id="rules",
            page=2,
            text=(
                "Under 12 pathways boys: the number of players permitted to "
                "bat and bowl is stated here."
            ),
            embedding=[0.96, 0.28],
        ),
        PageRecord(
            evidence_id="rules:p0003",
            source_id="rules",
            page=3,
            text="Senior fielding restrictions and match duration.",
            embedding=[0.0, 1.0],
        ),
    ]
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="vertex",
            model=settings.app_embedding_model,
            location=settings.embedding_location,
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=1,
            truncated_page_count=0,
        ),
        sources=[source],
        pages=pages,
    )
    monkeypatch.setattr(repository, "_query_embedding", lambda *_args: [1.0, 0.0])

    hits = repository.search(
        "How many players can bat and bowl in Under 12 pathways boys?",
        role="analyst",
        top_k=3,
    )

    assert hits[0].evidence_id == "rules:p0002"
    assert all(hit.retrieval_method == "vertex_hybrid" for hit in hits)


def test_selected_source_identity_cannot_outscore_cross_source_topic(
    tmp_path, monkeypatch
):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    sources = [
        SourceRecord(
            source_id="mcc_rules",
            title="MCC Laws of Cricket",
            version="test",
            scope="general laws",
            competition="MCC",
            allowed_roles=["analyst"],
            page_count=2,
            sha256="1" * 64,
        ),
        SourceRecord(
            source_id="usig_rules",
            title="US Ismaili Games Cricket Rules",
            version="test",
            scope="tournament rules",
            competition="US Ismaili Games",
            allowed_roles=["analyst"],
            page_count=2,
            sha256="2" * 64,
        ),
    ]
    pages = [
        PageRecord(
            evidence_id="mcc_rules:p0001",
            source_id="mcc_rules",
            page=1,
            text="MCC Laws of Cricket",
            embedding=[1.0, 0.0],
        ),
        PageRecord(
            evidence_id="mcc_rules:p0002",
            source_id="mcc_rules",
            page=2,
            text="An injured batter may have a runner.",
            embedding=[1.0, 0.0],
        ),
        PageRecord(
            evidence_id="usig_rules:p0001",
            source_id="usig_rules",
            page=1,
            text="US Ismaili Games Cricket Rules",
            embedding=[1.0, 0.0],
        ),
        PageRecord(
            evidence_id="usig_rules:p0002",
            source_id="usig_rules",
            page=2,
            text="An injured batter must not use a runner.",
            embedding=[1.0, 0.0],
        ),
    ]
    query = (
        "Compare an injured batter runner under the MCC Laws of Cricket and "
        "US Ismaili Games Cricket Rules"
    )
    raw_scores, _frequencies = _bm25_scores(query, pages)
    raw_ranking = [
        page.evidence_id
        for _score, page in sorted(
            zip(raw_scores, pages, strict=True), key=lambda item: -item[0]
        )
    ]
    assert raw_ranking[0].endswith("p0001")

    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="vertex",
            model=settings.app_embedding_model,
            location=settings.embedding_location,
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=1,
            truncated_page_count=0,
        ),
        sources=sources,
        pages=pages,
    )
    embedded_queries = []
    monkeypatch.setattr(
        repository,
        "_query_embedding",
        lambda embedded_query, _model: embedded_queries.append(embedded_query)
        or [1.0, 0.0],
    )

    hits = repository.search(
        query,
        lexical_query=query,
        role="analyst",
        top_k=4,
        source_ids=["mcc_rules", "usig_rules"],
    )

    assert embedded_queries == [query]
    assert {hit.evidence_id for hit in hits[:2]} == {
        "mcc_rules:p0002",
        "usig_rules:p0002",
    }
    assert all(hit.evidence_id.endswith("p0002") for hit in hits[:2])


def test_lexical_focus_keeps_original_format_qualifier(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    source = SourceRecord(
        source_id="junior_rules",
        title="Junior Cricket Rules",
        version="test",
        scope="junior age divisions",
        competition="Junior Competition",
        allowed_roles=["analyst"],
        page_count=2,
        sha256="3" * 64,
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="vertex",
            model=settings.app_embedding_model,
            location=settings.embedding_location,
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=1,
            truncated_page_count=0,
        ),
        sources=[source],
        pages=[
            PageRecord(
                evidence_id="junior_rules:p0001",
                source_id="junior_rules",
                page=1,
                text="Under 10 pathways players permitted to bat and bowl.",
                embedding=[1.0, 0.0],
            ),
            PageRecord(
                evidence_id="junior_rules:p0002",
                source_id="junior_rules",
                page=2,
                text="Under 12 pathways players permitted to bat and bowl.",
                embedding=[1.0, 0.0],
            ),
        ],
    )
    embedded_queries = []
    monkeypatch.setattr(
        repository,
        "_query_embedding",
        lambda embedded_query, _model: embedded_queries.append(embedded_query)
        or [1.0, 0.0],
    )
    ledger = RunLedger("format-constraint-run")
    ledger.original_question = (
        "How many players may bat and bowl in the Under 12 pathways format?"
    )
    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )

    result = search_tool.func(
        query="players permitted to bat and bowl",
        source_ids=["junior_rules"],
        top_k=2,
    )

    assert result["results"][0]["evidence_id"] == "junior_rules:p0002"
    assert ledger.original_question in embedded_queries[0]
    assert "players permitted to bat and bowl" in embedded_queries[0]


def test_vertex_hybrid_does_not_normalize_negative_nonmatches_into_hits(
    tmp_path, monkeypatch
):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    source = SourceRecord(
        source_id="rules",
        title="Rules",
        version="test",
        scope="test scope",
        competition="test competition",
        allowed_roles=["analyst"],
        page_count=2,
        sha256="0" * 64,
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="vertex",
            model=settings.app_embedding_model,
            location=settings.embedding_location,
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=1,
            truncated_page_count=0,
        ),
        sources=[source],
        pages=[
            PageRecord(
                evidence_id="rules:p0001",
                source_id="rules",
                page=1,
                text="alpha content",
                embedding=[-0.9, 0.435889894],
            ),
            PageRecord(
                evidence_id="rules:p0002",
                source_id="rules",
                page=2,
                text="beta content",
                embedding=[-0.5, 0.866025404],
            ),
        ],
    )
    monkeypatch.setattr(repository, "_query_embedding", lambda *_args: [1.0, 0.0])

    assert repository.search("unmatched terms", role="analyst", top_k=2) == []


def test_query_embedding_explicitly_disables_retry_and_truncation(tmp_path):
    settings = _settings(
        tmp_path,
        app_embedding_provider="vertex",
        google_cloud_project="offline-never-call",
        app_embedding_dimensions=2,
    )
    captured = {}

    class FakeModels:
        def embed_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                embeddings=[
                    SimpleNamespace(
                        values=[1.0, 0.0],
                        statistics=SimpleNamespace(truncated=False),
                    )
                ]
            )

    repository = IndexRepository(settings)
    repository._vertex_client = SimpleNamespace(models=FakeModels())
    assert repository._query_embedding("bounded query", "embedding-model") == [
        1.0,
        0.0,
    ]
    config = captured["config"]
    assert config.auto_truncate is False
    assert config.http_options.retry_options.attempts == 1
