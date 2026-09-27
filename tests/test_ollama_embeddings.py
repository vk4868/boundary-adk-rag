"""Offline regressions for local, non-truncating Ollama embeddings."""

from __future__ import annotations

import json
import math

import httpx
import pytest

from app.config import Settings
from app.index import IndexRepository
from app.models import CorpusIndex, EmbeddingDescriptor, PageRecord, SourceRecord
from app.ollama_embeddings import (
    EMBEDDING_METHOD,
    OllamaEmbeddingClient,
    OllamaEmbeddingError,
    POOLING_METHOD,
    chunk_text,
    pool_embeddings,
    validate_loopback_base_url,
)
from app.tools import RunLedger, build_tools


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://192.168.1.2:11434",
        "http://127.0.0.1:11434/path",
        "http://user@127.0.0.1:11434",
        "http://127.0.0.1:11434?next=http://example.com",
        "http://127.0.0.1",
        "http://localhost:11434",
        "http://127.0.0.2:11434",
        "http://2130706433:11434",
        "http://0x7f000001:11434",
    ],
)
def test_ollama_embedding_url_rejects_non_loopback_origins(url):
    with pytest.raises(ValueError):
        validate_loopback_base_url(url)


def test_chunking_is_bounded_deterministic_and_preserves_tokens():
    text = " ".join(f"token-{number}" for number in range(80))

    first = chunk_text(text, max_bytes=75)
    second = chunk_text(text, max_bytes=75)

    assert first == second
    assert all(len(chunk.encode("utf-8")) <= 75 for chunk in first)
    assert " ".join(first).split() == text.split()


def test_chunking_handles_blank_text_and_rejects_impossible_utf8_bound():
    assert chunk_text("   \n\t", max_bytes=10) == ["Blank PDF", "page"]
    with pytest.raises(ValueError, match="UTF-8 character"):
        chunk_text("😀", max_bytes=1)


def test_ipv6_loopback_is_canonicalized():
    assert validate_loopback_base_url("http://[::1]:11434/") == "http://[::1]:11434"


def test_pooling_is_length_weighted_and_normalized():
    pooled = pool_embeddings(
        [[1.0, 0.0], [0.0, 1.0]], [3, 4], dimensions=2
    )

    assert pooled == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(value * value for value in pooled)) == pytest.approx(1.0)


def test_client_disables_truncation_redirects_and_environment_proxy(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "embeddinggemma:latest",
                "embeddings": [[1.0, 0.0]],
            }

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setattr("app.ollama_embeddings.httpx.Client", FakeClient)
    client = OllamaEmbeddingClient(
        base_url="http://127.0.0.1:11434", timeout_ms=1234
    )

    assert client.embed(
        "bounded input", model="embeddinggemma:latest", dimensions=2
    ) == [1.0, 0.0]
    assert captured["client"] == {"trust_env": False, "follow_redirects": False}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:11434/api/embed"
    assert captured["request"] == {
        "json": {
            "model": "embeddinggemma:latest",
            "input": "bounded input",
            "truncate": False,
            "dimensions": 2,
        },
        "timeout": 1.234,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"model": "wrong:latest", "embeddings": [[1.0, 0.0]]},
        {"model": "embeddinggemma:latest", "embeddings": []},
        {"model": "embeddinggemma:latest", "embeddings": [[1.0]]},
        {"model": "embeddinggemma:latest", "embeddings": [[float("nan"), 0.0]]},
    ],
)
def test_client_rejects_invalid_ollama_responses(monkeypatch, body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(body), request=request)

    class TransportClient(httpx.Client):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("app.ollama_embeddings.httpx.Client", TransportClient)
    client = OllamaEmbeddingClient(
        base_url="http://127.0.0.1:11434", timeout_ms=1000
    )

    with pytest.raises(OllamaEmbeddingError):
        client.embed("text", model="embeddinggemma:latest", dimensions=2)


def test_model_digest_is_refreshed_for_each_query_check(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {"name": "embeddinggemma:latest", "digest": "a" * 64}
                ]
            }

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request(self, method, url, **_kwargs):
            calls.append((method, url))
            return FakeResponse()

    monkeypatch.setattr("app.ollama_embeddings.httpx.Client", FakeClient)
    client = OllamaEmbeddingClient(
        base_url="http://127.0.0.1:11434", timeout_ms=1000
    )

    assert client.model_digest("embeddinggemma:latest") == "a" * 64
    client.require_model_digest("embeddinggemma:latest", "a" * 64)
    with pytest.raises(OllamaEmbeddingError, match="digest changed"):
        client.require_model_digest("embeddinggemma:latest", "b" * 64)
    assert calls == [
        ("GET", "http://127.0.0.1:11434/api/tags"),
        ("GET", "http://127.0.0.1:11434/api/tags"),
        ("GET", "http://127.0.0.1:11434/api/tags"),
    ]


def test_unauthorized_source_fails_before_ollama_query_embedding(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="ollama",
        app_embedding_model="embeddinggemma:latest",
        app_embedding_dimensions=2,
        app_index_path=tmp_path / "unused.json",
        app_audit_path=tmp_path / "audit.jsonl",
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="ollama",
            model="embeddinggemma:latest",
            model_digest="a" * 64,
            location="loopback",
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            truncated_page_count=0,
            embedding_method=EMBEDDING_METHOD,
            context_window_tokens=2048,
            chunk_max_bytes=1800,
            pooling=POOLING_METHOD,
        ),
        sources=[
            SourceRecord(
                source_id="restricted",
                title="Restricted",
                version="test",
                scope="test",
                competition="test",
                allowed_roles=["reviewer"],
                page_count=1,
                sha256="0" * 64,
            )
        ],
        pages=[
            PageRecord(
                evidence_id="restricted:p0001",
                source_id="restricted",
                page=1,
                text="restricted text",
                embedding=[1.0, 0.0],
            )
        ],
    )

    class UncalledClient:
        def embed(self, *_args, **_kwargs):
            raise AssertionError("ACL rejection must precede an embedding request")

    repository._ollama_client = UncalledClient()
    with pytest.raises(PermissionError):
        repository.search(
            "restricted query",
            role="analyst",
            top_k=1,
            source_ids=["restricted"],
        )


def test_empty_source_filter_means_all_authorized_sources(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=tmp_path / "unused.json",
        app_audit_path=tmp_path / "audit.jsonl",
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=[
            SourceRecord(
                source_id="rules",
                title="Rules",
                version="test",
                scope="test",
                competition="test",
                allowed_roles=["analyst"],
                page_count=1,
                sha256="0" * 64,
            )
        ],
        pages=[
            PageRecord(
                evidence_id="rules:p0001",
                source_id="rules",
                page=1,
                text="runner conditions",
            )
        ],
    )

    hits = repository.search(
        "runner conditions", role="analyst", top_k=1, source_ids=[]
    )

    assert [hit.evidence_id for hit in hits] == ["rules:p0001"]


def test_ollama_hybrid_search_returns_typed_hit_and_tool_result(tmp_path):
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="ollama",
        app_embedding_model="embeddinggemma:latest",
        app_embedding_dimensions=2,
        app_index_path=tmp_path / "unused.json",
        app_audit_path=tmp_path / "audit.jsonl",
    )
    repository = IndexRepository(settings)
    repository._index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(
            provider="ollama",
            model="embeddinggemma:latest",
            model_digest="a" * 64,
            location="loopback",
            dimensions=2,
            task_type="RETRIEVAL_DOCUMENT",
            truncated_page_count=0,
            embedding_method=EMBEDDING_METHOD,
            context_window_tokens=2048,
            chunk_max_bytes=1800,
            pooling=POOLING_METHOD,
        ),
        sources=[
            SourceRecord(
                source_id="rules",
                title="Rules",
                version="test",
                scope="test",
                competition="test",
                allowed_roles=["analyst"],
                page_count=1,
                sha256="0" * 64,
            )
        ],
        pages=[
            PageRecord(
                evidence_id="rules:p0001",
                source_id="rules",
                page=1,
                text="runner conditions",
                embedding=[1.0, 0.0],
            )
        ],
    )

    class FakeClient:
        def require_model_digest(self, model, digest):
            assert (model, digest) == ("embeddinggemma:latest", "a" * 64)

        def embed(self, text, *, model, dimensions):
            assert "runner conditions" in text
            assert model == "embeddinggemma:latest"
            assert dimensions == 2
            return [1.0, 0.0]

    repository._ollama_client = FakeClient()
    hits = repository.search(
        "runner conditions", role="analyst", top_k=1, source_ids=[]
    )
    assert hits[0].retrieval_method == "ollama_hybrid"

    ledger = RunLedger("ollama-tool-result")
    ledger.original_question = "runner conditions"
    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )
    result = search_tool.func(query="runner conditions", source_ids=[], top_k=1)
    assert result["results"][0]["evidence_id"] == "rules:p0001"
    assert result["results"][0]["retrieval_method"] == "ollama_hybrid"
