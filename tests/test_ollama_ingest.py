"""Offline ingestion checks for deterministic page-level Ollama vectors."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.ingest import _embed_pages_ollama, build_index
from app.models import PageRecord


def test_ollama_ingest_chunks_and_pools_without_changing_evidence_ids(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        def embed(self, text, *, model, dimensions):
            calls.append((text, model, dimensions))
            return [1.0, float(len(text.encode("utf-8")))]

        def model_digest(self, model):
            assert model == "embeddinggemma:latest"
            return "a" * 64

    monkeypatch.setattr("app.ingest.OllamaEmbeddingClient", FakeClient)
    page = PageRecord(
        evidence_id="rules:p0001",
        source_id="rules",
        page=1,
        text="alpha beta gamma delta epsilon",
    )

    digest = _embed_pages_ollama(
        [page],
        base_url="http://127.0.0.1:11434",
        timeout_ms=30000,
        model="embeddinggemma:latest",
        dimensions=2,
        chunk_max_bytes=12,
    )

    assert page.evidence_id == "rules:p0001"
    assert digest == "a" * 64
    assert len([call for call in calls if call[0] != "client"]) == 3
    assert page.embedding is not None
    assert len(page.embedding) == 2
    assert sum(value * value for value in page.embedding) == pytest.approx(1.0)


def test_build_index_ollama_records_digest_and_embedding_contract(tmp_path, monkeypatch):
    pdf_path = tmp_path / "rules.pdf"
    pdf_path.write_bytes(b"offline fake PDF bytes")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "rules",
                        "title": "Rules",
                        "version": "test",
                        "scope": "test scope",
                        "competition": "test competition",
                        "allowed_roles": ["analyst"],
                        "path": "rules.pdf",
                        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakePage:
        def extract_text(self):
            return "complete page text"

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

        def __init__(self, path, *, strict):
            assert path == str(pdf_path)
            assert strict is True

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def model_digest(self, model):
            assert model == "embeddinggemma:latest"
            return "b" * 64

        def embed(self, text, *, model, dimensions):
            assert text == "complete page text"
            assert model == "embeddinggemma:latest"
            assert dimensions == 2
            return [3.0, 4.0]

    monkeypatch.setattr("app.ingest.PdfReader", FakeReader)
    monkeypatch.setattr("app.ingest.OllamaEmbeddingClient", FakeClient)

    index = build_index(
        manifest_path,
        embedding_provider="ollama",
        embedding_model="embeddinggemma:latest",
        embedding_dimensions=2,
    )

    assert index.embedding.model_digest == "b" * 64
    assert index.embedding.chunk_max_bytes == 1800
    assert index.embedding.context_window_tokens == 2048
    assert index.pages[0].evidence_id == "rules:p0001"
    assert index.pages[0].embedding == pytest.approx([0.6, 0.8])


def test_ollama_ingest_rejects_alias_change_during_build(monkeypatch):
    digests = iter(["a" * 64, "b" * 64])

    class MovingAliasClient:
        def __init__(self, **_kwargs):
            pass

        def model_digest(self, _model):
            return next(digests)

        def embed(self, _text, *, model, dimensions):
            assert model == "embeddinggemma:latest"
            assert dimensions == 2
            return [1.0, 0.0]

    monkeypatch.setattr("app.ingest.OllamaEmbeddingClient", MovingAliasClient)
    page = PageRecord(
        evidence_id="rules:p0001",
        source_id="rules",
        page=1,
        text="page text",
    )

    with pytest.raises(RuntimeError, match="digest changed during ingestion"):
        _embed_pages_ollama(
            [page],
            base_url="http://127.0.0.1:11434",
            timeout_ms=30000,
            model="embeddinggemma:latest",
            dimensions=2,
        )
