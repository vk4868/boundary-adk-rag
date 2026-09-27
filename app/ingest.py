"""Deterministic PDF ingestion with explicit local or historical embeddings."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

from google import genai
from google.genai import types
from pydantic import ValidationError
from pypdf import PdfReader

from app.models import (
    CorpusIndex,
    CorpusManifest,
    EmbeddingDescriptor,
    PageRecord,
    SourceRecord,
)
from app.ollama_embeddings import (
    DEFAULT_CHUNK_BYTES,
    EMBEDDING_METHOD,
    OllamaEmbeddingClient,
    POOLING_METHOD,
    chunk_text,
    pool_embeddings,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()


def _resolved_pdf(manifest_dir: Path, relative_path: str) -> Path:
    candidate = (manifest_dir / relative_path).resolve()
    if not candidate.is_relative_to(manifest_dir.resolve()):
        raise ValueError(f"source path escapes manifest directory: {relative_path}")
    if candidate.suffix.lower() != ".pdf":
        raise ValueError(f"source is not a PDF: {relative_path}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _embed_pages(
    pages: Iterable[PageRecord],
    *,
    project: str,
    location: str,
    model: str,
    dimensions: int,
) -> tuple[int, int]:
    client = genai.Client(vertexai=True, project=project, location=location)
    config = types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=dimensions,
        auto_truncate=False,
    )
    total_billable_characters = 0
    truncated_page_count = 0
    for page in pages:
        # One text per request keeps the evidence-to-vector mapping unambiguous.
        response = client.models.embed_content(
            model=model,
            contents=page.text or f"Blank PDF page {page.evidence_id}",
            config=config,
        )
        if not response.embeddings or response.embeddings[0].values is None:
            raise RuntimeError(f"Vertex returned no embedding for {page.evidence_id}")
        statistics = response.embeddings[0].statistics
        if statistics is None or statistics.truncated is None:
            raise RuntimeError(
                f"Vertex returned no truncation status for {page.evidence_id}"
            )
        if statistics.truncated:
            truncated_page_count += 1
            raise RuntimeError(f"Vertex truncated input for {page.evidence_id}")
        if response.metadata and response.metadata.billable_character_count is not None:
            total_billable_characters += int(
                response.metadata.billable_character_count
            )
        values = [float(value) for value in response.embeddings[0].values]
        if len(values) != dimensions:
            raise RuntimeError(
                f"Vertex embedding dimension mismatch for {page.evidence_id}: "
                f"expected {dimensions}, got {len(values)}"
            )
        page.embedding = values
    return total_billable_characters, truncated_page_count


def _embed_pages_ollama(
    pages: Iterable[PageRecord],
    *,
    base_url: str,
    timeout_ms: int,
    model: str,
    dimensions: int,
    chunk_max_bytes: int = DEFAULT_CHUNK_BYTES,
) -> str:
    client = OllamaEmbeddingClient(base_url=base_url, timeout_ms=timeout_ms)
    model_digest = client.model_digest(model)
    for page in pages:
        chunks = chunk_text(
            page.text or f"Blank PDF page {page.evidence_id}",
            max_bytes=chunk_max_bytes,
        )
        vectors = [
            client.embed(chunk, model=model, dimensions=dimensions)
            for chunk in chunks
        ]
        page.embedding = pool_embeddings(
            vectors,
            [len(chunk.encode("utf-8")) for chunk in chunks],
            dimensions=dimensions,
        )
    if client.model_digest(model) != model_digest:
        raise RuntimeError("Ollama embedding model digest changed during ingestion")
    return model_digest


def build_index(
    manifest_path: Path,
    *,
    embedding_provider: str = "lexical",
    project: str | None = None,
    location: str = "us-central1",
    embedding_model: str = "embeddinggemma:latest",
    embedding_dimensions: int = 768,
    ollama_base_url: str = "http://127.0.0.1:11434",
    embedding_timeout_ms: int = 30_000,
) -> CorpusIndex:
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = CorpusManifest.model_validate(raw_manifest)
    manifest_dir = manifest_path.resolve().parent
    sources: list[SourceRecord] = []
    pages: list[PageRecord] = []

    for source in sorted(manifest.sources, key=lambda item: item.source_id):
        pdf_path = _resolved_pdf(manifest_dir, source.path)
        actual_sha = _sha256(pdf_path)
        if source.sha256 and actual_sha != source.sha256:
            raise ValueError(
                f"SHA-256 mismatch for {source.source_id}: "
                f"expected {source.sha256}, got {actual_sha}"
            )
        reader = PdfReader(str(pdf_path), strict=True)
        if reader.is_encrypted:
            raise ValueError(f"encrypted PDF is not supported: {source.source_id}")
        if not reader.pages:
            raise ValueError(f"PDF has no pages: {source.source_id}")
        for page_number, pdf_page in enumerate(reader.pages, start=1):
            text = _normalize_text(pdf_page.extract_text() or "")
            pages.append(
                PageRecord(
                    evidence_id=f"{source.source_id}:p{page_number:04d}",
                    source_id=source.source_id,
                    page=page_number,
                    text=text,
                )
            )
        sources.append(
            SourceRecord(
                source_id=source.source_id,
                title=source.title,
                version=source.version,
                scope=source.scope,
                competition=source.competition,
                allowed_roles=source.allowed_roles,
                page_count=len(reader.pages),
                sha256=actual_sha,
            )
        )

    if embedding_provider == "ollama":
        model_digest = _embed_pages_ollama(
            pages,
            base_url=ollama_base_url,
            timeout_ms=embedding_timeout_ms,
            model=embedding_model,
            dimensions=embedding_dimensions,
        )
        descriptor = EmbeddingDescriptor(
            provider="ollama",
            model=embedding_model,
            model_digest=model_digest,
            location="loopback",
            dimensions=embedding_dimensions,
            task_type="RETRIEVAL_DOCUMENT",
            truncated_page_count=0,
            embedding_method=EMBEDDING_METHOD,
            context_window_tokens=2048,
            chunk_max_bytes=DEFAULT_CHUNK_BYTES,
            pooling=POOLING_METHOD,
        )
    elif embedding_provider == "vertex":
        if not project:
            raise ValueError("--project is required for Vertex embeddings")
        billable_character_count, truncated_page_count = _embed_pages(
            pages,
            project=project,
            location=location,
            model=embedding_model,
            dimensions=embedding_dimensions,
        )
        descriptor = EmbeddingDescriptor(
            provider="vertex",
            model=embedding_model,
            location=location,
            dimensions=embedding_dimensions,
            task_type="RETRIEVAL_DOCUMENT",
            billable_character_count=billable_character_count,
            truncated_page_count=truncated_page_count,
        )
    elif embedding_provider == "lexical":
        descriptor = EmbeddingDescriptor(provider="lexical")
    else:
        raise ValueError(f"unsupported embedding provider: {embedding_provider}")

    return CorpusIndex(
        schema_version=1,
        embedding=descriptor,
        sources=sources,
        pages=pages,
    )


def write_index(index: CorpusIndex, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    payload = index.model_dump_json(indent=2, exclude_none=True) + "\n"
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, output_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--embedding-provider", choices=("lexical", "ollama", "vertex"), default="lexical"
    )
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument(
        "--location", default=os.getenv("EMBEDDING_LOCATION", "us-central1")
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("APP_EMBEDDING_MODEL", "embeddinggemma:latest"),
    )
    parser.add_argument("--embedding-dimensions", type=int, default=768)
    parser.add_argument(
        "--ollama-base-url",
        default=os.getenv("APP_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    parser.add_argument(
        "--embedding-timeout-ms",
        type=int,
        default=int(os.getenv("APP_EMBEDDING_TIMEOUT_MS", "30000")),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        index = build_index(
            args.manifest,
            embedding_provider=args.embedding_provider,
            project=args.project,
            location=args.location,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            ollama_base_url=args.ollama_base_url,
            embedding_timeout_ms=args.embedding_timeout_ms,
        )
        write_index(index, args.output)
    except (OSError, ValueError, RuntimeError, ValidationError) as exc:
        print(f"ingestion failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "sources": len(index.sources),
                "pages": len(index.pages),
                "embedding_provider": index.embedding.provider,
                "embedding_model": index.embedding.model,
                "embedding_dimensions": index.embedding.dimensions,
                "billable_character_count": index.embedding.billable_character_count,
                "truncated_page_count": index.embedding.truncated_page_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
