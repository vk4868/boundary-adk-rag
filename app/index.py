"""Read-only ACL-aware retrieval over a fixed corpus index."""

from __future__ import annotations

import json
import hashlib
import math
import re
import threading
from collections import Counter
from pathlib import Path

from google import genai
from google.genai import types

from app.config import Settings
from app.models import (
    AdjacentEvidencePreview,
    CorpusIndex,
    PageRecord,
    PublicSource,
    SearchHit,
    SourceRecord,
)


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
PHRASE_TOKEN_RE = re.compile(r"[a-z]+|[0-9]+(?:\.[0-9]+)*", re.IGNORECASE)
DOTTED_REFERENCE_RE = re.compile(r"\b[0-9]+(?:\.[0-9]+)+\b")
SNIPPET_EXCLUDED_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "current",
        "every",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "preserve",
        "question",
        "refinement",
        "search",
        "the",
        "to",
        "user",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)


class IndexUnavailable(RuntimeError):
    """Raised when the immutable index cannot be loaded or queried safely."""


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise IndexUnavailable("query/document embedding dimension mismatch")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _bm25_scores(query: str, pages: list[PageRecord]) -> tuple[list[float], Counter]:
    """Score exact terms once so a model paraphrase cannot repeat-weight them."""
    query_tokens = set(_tokens(query))
    document_tokens = [_tokens(page.text) for page in pages]
    document_frequency = Counter(
        token for tokens in document_tokens for token in set(tokens)
    )
    if not query_tokens or not pages:
        return [0.0] * len(pages), document_frequency
    average_length = sum(map(len, document_tokens)) / len(document_tokens)
    scores: list[float] = []
    for tokens in document_tokens:
        counts = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = counts[token]
            if not frequency:
                continue
            inverse_document_frequency = math.log(
                1
                + (len(pages) - document_frequency[token] + 0.5)
                / (document_frequency[token] + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * len(tokens) / max(average_length, 1)
            )
            score += (
                inverse_document_frequency * frequency * 2.5 / denominator
            )
        scores.append(score)
    return scores, document_frequency


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lowest = min(scores)
    highest = max(scores)
    if math.isclose(lowest, highest):
        return [1.0 if highest > 0 else 0.0] * len(scores)
    return [(score - lowest) / (highest - lowest) for score in scores]


def _query_focused_snippet(
    text: str,
    query: str,
    *,
    document_frequency: Counter,
    document_count: int,
    max_chars: int = 700,
) -> str:
    """Return the bounded passage with the densest substantive query overlap."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    query_tokens = {
        token
        for token in _tokens(query)
        if token not in SNIPPET_EXCLUDED_TOKENS
    }
    if not query_tokens:
        return normalized[:max_chars]

    def is_standalone_numeric_match(match: re.Match[str]) -> bool:
        token = match.group(0)
        if not token.isdigit():
            return True
        before = normalized[match.start() - 1] if match.start() else ""
        after = normalized[match.end()] if match.end() < len(normalized) else ""
        dotted_before = (
            before == "."
            and match.start() > 1
            and normalized[match.start() - 2].isdigit()
        )
        dotted_after = (
            after == "."
            and match.end() + 1 < len(normalized)
            and normalized[match.end() + 1].isdigit()
        )
        return not dotted_before and not dotted_after

    matches = [
        match
        for match in TOKEN_RE.finditer(normalized)
        if match.group(0).lower() in query_tokens
        and is_standalone_numeric_match(match)
    ]
    if not matches:
        return normalized[:max_chars]

    weights = {
        token: math.log(
            1
            + (document_count - document_frequency[token] + 0.5)
            / (document_frequency[token] + 0.5)
        )
        for token in query_tokens
    }
    phrase_query_tokens = [
        match.group(0).lower() for match in PHRASE_TOKEN_RE.finditer(query)
    ]
    numeric_phrases: list[tuple[str, ...]] = []
    for index, token in enumerate(phrase_query_tokens):
        if not any(character.isdigit() for character in token):
            continue
        phrase = tuple(
            phrase_query_tokens[
                max(0, index - 1) : min(len(phrase_query_tokens), index + 2)
            ]
        )
        if len(phrase) >= 2 and phrase not in numeric_phrases:
            numeric_phrases.append(phrase)

    def contains_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
        return any(
            tuple(tokens[index : index + len(phrase)]) == phrase
            for index in range(len(tokens) - len(phrase) + 1)
        )

    best: tuple[float, int, int] | None = None
    for anchor in matches:
        start = max(0, min(anchor.start() - max_chars // 3, len(normalized) - max_chars))
        end = min(len(normalized), start + max_chars)
        window_matches = [
            match
            for match in matches
            if match.start() >= start and match.end() <= end
        ]
        covered = {match.group(0).lower() for match in window_matches}
        coverage_score = sum(weights[token] for token in covered)
        density_score = sum(weights[match.group(0).lower()] for match in window_matches)
        phrase_window_tokens = [
            match.group(0).lower()
            for match in PHRASE_TOKEN_RE.finditer(normalized[start:end])
        ]
        numeric_phrase_score = sum(
            3.0
            for phrase in numeric_phrases
            if contains_phrase(phrase_window_tokens, phrase)
        )
        score = coverage_score + 0.05 * density_score + numeric_phrase_score
        candidate = (score, -start, start)
        if best is None or candidate > best:
            best = candidate

    assert best is not None
    start = best[2]
    end = min(len(normalized), start + max_chars)
    if start:
        next_space = normalized.find(" ", start)
        if 0 <= next_space < end:
            start = next_space + 1
    if end < len(normalized):
        previous_space = normalized.rfind(" ", start, end)
        if previous_space > start:
            end = previous_space
    return normalized[start:end]


def _adjacent_preview(
    text: str,
    query: str,
    *,
    relation: str,
    max_chars: int = 350,
) -> str:
    """Return reference-focused context, otherwise a boundary-facing fragment."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    references = list(dict.fromkeys(DOTTED_REFERENCE_RE.findall(query)))
    for reference in references:
        match = re.search(
            rf"(?<![0-9.]){re.escape(reference)}(?![0-9.])", normalized
        )
        if match is None:
            continue
        start = max(
            0,
            min(match.start() - max_chars // 3, len(normalized) - max_chars),
        )
        end = min(len(normalized), start + max_chars)
        return normalized[start:end].strip()
    if relation == "previous":
        return normalized[-max_chars:].strip()
    return normalized[:max_chars].strip()


class IndexRepository:
    """Loads the index once and never mutates it."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._index: CorpusIndex | None = None
        self._load_error: str | None = None
        self._vertex_client: genai.Client | None = None

    def load(self) -> CorpusIndex:
        if self._index is not None:
            return self._index
        with self._lock:
            if self._index is not None:
                return self._index
            try:
                raw = self.settings.app_index_path.read_bytes()
                actual_sha256 = hashlib.sha256(raw).hexdigest()
                if (
                    self.settings.app_index_sha256
                    and actual_sha256 != self.settings.app_index_sha256
                ):
                    raise IndexUnavailable("fixed index SHA-256 mismatch")
                payload = json.loads(raw)
                index = CorpusIndex.model_validate(payload)
                if index.embedding.provider != self.settings.app_embedding_provider:
                    raise IndexUnavailable(
                        "configured retrieval provider does not match the fixed index"
                    )
                if index.embedding.provider == "vertex":
                    if not self.settings.google_cloud_project:
                        raise IndexUnavailable(
                            "Vertex retrieval requires GOOGLE_CLOUD_PROJECT"
                        )
                    if index.embedding.model != self.settings.app_embedding_model:
                        raise IndexUnavailable(
                            "configured embedding model does not match the fixed index"
                        )
                    if index.embedding.dimensions != self.settings.app_embedding_dimensions:
                        raise IndexUnavailable(
                            "configured embedding dimensions do not match the fixed index"
                        )
                self._index = index
                self._load_error = None
            except Exception as exc:
                self._load_error = str(exc)
                raise IndexUnavailable("corpus index is unavailable") from exc
        return self._index

    def status(self) -> dict[str, object]:
        try:
            index = self.load()
            return {
                "ready": True,
                "sources": len(index.sources),
                "pages": len(index.pages),
                "retrieval_provider": index.embedding.provider,
            }
        except IndexUnavailable:
            return {
                "ready": False,
                "sources": 0,
                "pages": 0,
                "retrieval_provider": self.settings.app_embedding_provider,
                "error": "corpus index unavailable or incompatible",
            }

    def _allowed_sources(self, role: str) -> dict[str, SourceRecord]:
        if role not in self.settings.allowed_roles:
            return {}
        return {
            source.source_id: source
            for source in self.load().sources
            if role in source.allowed_roles
        }

    def list_sources(self, role: str) -> list[PublicSource]:
        return [
            PublicSource(
                source_id=source.source_id,
                title=source.title,
                version=source.version,
                scope=source.scope,
                page_count=source.page_count,
            )
            for source in sorted(
                self._allowed_sources(role).values(), key=lambda item: item.source_id
            )
        ]

    def page(self, evidence_id: str, role: str) -> tuple[PageRecord, SourceRecord]:
        allowed = self._allowed_sources(role)
        for page in self.load().pages:
            if page.evidence_id == evidence_id:
                source = allowed.get(page.source_id)
                if source is None:
                    raise PermissionError("evidence is not authorized for this role")
                return page, source
        raise KeyError(evidence_id)

    def _query_embedding(self, query: str, descriptor_model: str) -> list[float]:
        if self._vertex_client is None:
            self._vertex_client = genai.Client(
                vertexai=True,
                project=self.settings.google_cloud_project,
                location=self.settings.embedding_location,
            )
        response = self._vertex_client.models.embed_content(
            model=descriptor_model,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.settings.app_embedding_dimensions,
                auto_truncate=False,
                http_options=types.HttpOptions(
                    timeout=self.settings.app_embedding_timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            ),
        )
        if not response.embeddings or response.embeddings[0].values is None:
            raise IndexUnavailable("Vertex returned no query embedding")
        statistics = response.embeddings[0].statistics
        if statistics is None or statistics.truncated is None:
            raise IndexUnavailable("Vertex returned no query truncation status")
        if statistics.truncated:
            raise IndexUnavailable("Vertex truncated the retrieval query")
        values = [float(value) for value in response.embeddings[0].values]
        if len(values) != self.settings.app_embedding_dimensions:
            raise IndexUnavailable("Vertex query embedding dimension mismatch")
        if not all(math.isfinite(value) for value in values):
            raise IndexUnavailable("Vertex returned a non-finite query embedding")
        return values

    def search(
        self,
        query: str,
        *,
        role: str,
        top_k: int,
        source_ids: list[str] | None = None,
        lexical_query: str | None = None,
    ) -> list[SearchHit]:
        query = query.strip()
        if not query:
            raise ValueError("query cannot be blank")
        if len(query) > self.settings.app_max_effective_search_query_chars:
            raise ValueError("query exceeds the configured length limit")
        lexical_query = (lexical_query or query).strip()
        if not lexical_query:
            raise ValueError("lexical query cannot be blank")
        if len(lexical_query) > self.settings.app_max_effective_search_query_chars:
            raise ValueError("lexical query exceeds the configured length limit")
        top_k = max(1, min(top_k, self.settings.app_max_search_results))
        index = self.load()
        allowed = self._allowed_sources(role)
        context_query = lexical_query
        if source_ids is not None:
            requested = set(source_ids)
            unauthorized = requested.difference(allowed)
            if unauthorized:
                raise PermissionError("one or more requested sources are unauthorized")
            allowed = {key: value for key, value in allowed.items() if key in requested}
            # Explicit source filtering already supplies source identity. Remove
            # those identity terms from only the lexical channel so repeated
            # titles on short intro/closing pages cannot outrank the requested
            # topic. The full query remains unchanged for Vertex embedding.
            identity_tokens = {
                token
                for source in allowed.values()
                for token in _tokens(
                    f"{source.source_id} {source.title} {source.competition}"
                )
            }
            context_query = TOKEN_RE.sub(
                lambda match: (
                    ""
                    if match.group(0).lower() in identity_tokens
                    else match.group(0)
                ),
                lexical_query,
            )
            focused_tokens = _tokens(context_query)
            lexical_query = " ".join(focused_tokens)
        candidates = [page for page in index.pages if page.source_id in allowed]
        if not candidates:
            return []

        lexical_scores, document_frequency = _bm25_scores(lexical_query, candidates)
        if index.embedding.provider == "vertex":
            if not index.embedding.model:
                raise IndexUnavailable("fixed Vertex index has no model descriptor")
            query_vector = self._query_embedding(query, index.embedding.model)
            dense_scores = [
                _cosine(query_vector, page.embedding or []) for page in candidates
            ]
            normalized_dense = _normalize_scores(dense_scores)
            normalized_lexical = _normalize_scores(lexical_scores)
            # Exact constraints such as age, format, and requested attribute
            # receive more weight, while dense similarity still resolves
            # paraphrases. This reranks the fixed vectors locally and performs
            # no additional provider call.
            scored = [
                (
                    0.65 * normalized_lexical_score
                    + 0.35 * normalized_dense_score
                    if raw_lexical_score > 0 or raw_dense_score > 0
                    else 0.0,
                    page,
                )
                for page, raw_lexical_score, raw_dense_score,
                normalized_lexical_score, normalized_dense_score in zip(
                    candidates,
                    lexical_scores,
                    dense_scores,
                    normalized_lexical,
                    normalized_dense,
                    strict=True,
                )
            ]
            method = "vertex_hybrid"
        else:
            if not any(lexical_scores):
                return []
            scored = list(zip(lexical_scores, candidates, strict=True))
            method = "lexical"

        hits: list[SearchHit] = []
        pages_by_id = {page.evidence_id: page for page in candidates}
        for score, page in sorted(
            scored, key=lambda item: (-item[0], item[1].evidence_id)
        )[:top_k]:
            if score <= 0:
                continue
            source = allowed[page.source_id]
            adjacent_pages = [
                (adjacent_page, relation)
                for adjacent_page, relation in (
                    (page.page - 1, "previous"),
                    (page.page + 1, "next"),
                )
                if 1 <= adjacent_page <= source.page_count
            ]
            adjacent_evidence_ids = [
                f"{page.source_id}:p{adjacent_page:04d}"
                for adjacent_page, _relation in adjacent_pages
            ]
            adjacent_previews = [
                AdjacentEvidencePreview(
                    evidence_id=f"{page.source_id}:p{adjacent_page:04d}",
                    relation=relation,
                    snippet=_adjacent_preview(
                        pages_by_id[
                            f"{page.source_id}:p{adjacent_page:04d}"
                        ].text,
                        context_query,
                        relation=relation,
                    ),
                )
                for adjacent_page, relation in adjacent_pages
            ]
            hits.append(
                SearchHit(
                    evidence_id=page.evidence_id,
                    source_id=page.source_id,
                    title=source.title,
                    version=source.version,
                    scope=source.scope,
                    page=page.page,
                    snippet=_query_focused_snippet(
                        page.text,
                        context_query,
                        document_frequency=document_frequency,
                        document_count=len(candidates),
                    ),
                    adjacent_evidence_ids=adjacent_evidence_ids,
                    adjacent_previews=adjacent_previews,
                    score=round(score, 6),
                    retrieval_method=method,
                )
            )
        return hits
