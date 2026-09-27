"""Strict loopback-only client and deterministic pooling for Ollama embeddings."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from urllib.parse import urlsplit

import httpx


# A byte is never less than one input token for a UTF-8 tokenizer. Keeping the
# payload below 2,048 bytes leaves room for the model's framing tokens without
# relying on an approximate tokenizer or accepting server-side truncation.
DEFAULT_CHUNK_BYTES = 1_800
EMBEDDING_METHOD = "deterministic_utf8_chunks_length_weighted_l2_pool"
POOLING_METHOD = "utf8_byte_length_weighted_mean_then_l2_normalize"
MODEL_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")


class OllamaEmbeddingError(RuntimeError):
    """Raised when a local embedding request cannot be validated safely."""


def validate_loopback_base_url(base_url: str) -> str:
    """Return a canonical HTTP base URL after enforcing a loopback host."""
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Ollama base URL is invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Ollama base URL must be a plain loopback HTTP origin")
    if port is None:
        raise ValueError("Ollama base URL must include an explicit port")
    hostname = parsed.hostname.lower()
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"http://{host}:{port}"


def chunk_text(text: str, *, max_bytes: int = DEFAULT_CHUNK_BYTES) -> list[str]:
    """Split text deterministically on whitespace without discarding content."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    source = text or "Blank PDF page"
    tokens = source.split()
    if not tokens:
        tokens = ["Blank", "PDF", "page"]
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for token in tokens:
        pieces: list[str] = []
        remaining = token
        while len(remaining.encode("utf-8")) > max_bytes:
            end = 0
            used = 0
            for character in remaining:
                size = len(character.encode("utf-8"))
                if used + size > max_bytes:
                    break
                used += size
                end += 1
            if end == 0:
                raise ValueError("max_bytes cannot hold one UTF-8 character")
            pieces.append(remaining[:end])
            remaining = remaining[end:]
        if remaining:
            pieces.append(remaining)
        for piece in pieces:
            piece_bytes = len(piece.encode("utf-8"))
            separator_bytes = 1 if current else 0
            if current and current_bytes + separator_bytes + piece_bytes > max_bytes:
                chunks.append(" ".join(current))
                current = []
                current_bytes = 0
                separator_bytes = 0
            current.append(piece)
            current_bytes += separator_bytes + piece_bytes
    if current:
        chunks.append(" ".join(current))
    return chunks


def pool_embeddings(
    vectors: Iterable[list[float]], weights: Iterable[int], *, dimensions: int
) -> list[float]:
    """Length-weight and L2-normalize chunk vectors into one page vector."""
    vector_list = list(vectors)
    weight_list = list(weights)
    if not vector_list or len(vector_list) != len(weight_list):
        raise OllamaEmbeddingError("cannot pool missing or mismatched embeddings")
    if any(weight <= 0 for weight in weight_list):
        raise OllamaEmbeddingError("embedding weights must be positive")
    pooled = [0.0] * dimensions
    for vector, weight in zip(vector_list, weight_list, strict=True):
        if len(vector) != dimensions or not all(math.isfinite(value) for value in vector):
            raise OllamaEmbeddingError("cannot pool an invalid embedding vector")
        for index, value in enumerate(vector):
            pooled[index] += value * weight
    norm = math.sqrt(sum(value * value for value in pooled))
    if not math.isfinite(norm) or norm == 0:
        raise OllamaEmbeddingError("pooled embedding has no finite magnitude")
    return [value / norm for value in pooled]


class OllamaEmbeddingClient:
    """Small synchronous client for Ollama's local ``/api/embed`` endpoint."""

    def __init__(self, *, base_url: str, timeout_ms: int):
        self.base_url = validate_loopback_base_url(base_url)
        self.timeout_seconds = timeout_ms / 1_000

    def _request_json(
        self, method: str, path: str, *, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            with httpx.Client(trust_env=False, follow_redirects=False) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaEmbeddingError("Ollama embedding request failed") from exc
        if not isinstance(body, dict):
            raise OllamaEmbeddingError("Ollama returned an invalid JSON object")
        return body

    def model_digest(self, model: str) -> str:
        """Resolve the exact current local model digest from Ollama tags."""
        models = self._request_json("GET", "/api/tags").get("models")
        if not isinstance(models, list):
            raise OllamaEmbeddingError("Ollama returned no model tag list")
        matches = [
            item
            for item in models
            if isinstance(item, dict) and item.get("name") == model
        ]
        if len(matches) != 1 or not isinstance(matches[0].get("digest"), str):
            raise OllamaEmbeddingError("configured Ollama embedding model is unavailable")
        digest = matches[0]["digest"]
        if not MODEL_DIGEST_RE.fullmatch(digest):
            raise OllamaEmbeddingError("Ollama returned an invalid model digest")
        return digest

    def require_model_digest(self, model: str, expected_digest: str) -> None:
        if self.model_digest(model) != expected_digest:
            raise OllamaEmbeddingError("Ollama embedding model digest changed")

    def embed(self, text: str, *, model: str, dimensions: int) -> list[float]:
        payload = {
            "model": model,
            "input": text,
            "truncate": False,
            "dimensions": dimensions,
        }
        # Ignore proxy environment variables and redirects so a validated
        # loopback origin cannot be escaped by transport configuration.
        body = self._request_json("POST", "/api/embed", payload=payload)
        if body.get("model") != model:
            raise OllamaEmbeddingError("Ollama returned an unexpected embedding model")
        embeddings = body.get("embeddings")
        if (
            not isinstance(embeddings, list)
            or len(embeddings) != 1
            or not isinstance(embeddings[0], list)
        ):
            raise OllamaEmbeddingError("Ollama returned no unambiguous embedding")
        try:
            values = [float(value) for value in embeddings[0]]
        except (TypeError, ValueError) as exc:
            raise OllamaEmbeddingError("Ollama returned a non-numeric embedding") from exc
        if len(values) != dimensions:
            raise OllamaEmbeddingError("Ollama embedding dimension mismatch")
        if not all(math.isfinite(value) for value in values):
            raise OllamaEmbeddingError("Ollama returned a non-finite embedding")
        return values
