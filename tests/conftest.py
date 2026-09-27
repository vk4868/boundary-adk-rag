"""Hermetic defaults applied before test modules import the application."""

from __future__ import annotations

import os


# Importing ``app`` constructs the ADK entry point. Keep that import offline and
# independent of an operator's active private index or model configuration.
def _apply_offline_environment() -> None:
    for key, value in {
        "APP_ENABLE_MODEL_CALLS": "false",
        "APP_MODEL_PROVIDER": "disabled",
        "APP_EMBEDDING_PROVIDER": "ollama",
    }.items():
        # pydantic-settings is case-insensitive here, while macOS environment
        # keys are not. Set both spellings so a differently-cased private .env
        # entry cannot override the hermetic test process.
        os.environ[key] = value
        os.environ[key.lower()] = value
    for key in ("APP_INDEX_SHA256", "APP_INDEX_PATH"):
        os.environ.pop(key, None)
        os.environ.pop(key.lower(), None)


_apply_offline_environment()

# ADK/LiteLLM package import may populate process variables from a local .env.
# Import once under safe values, then restore the hermetic environment before
# pytest imports any test module or constructs synthetic Settings instances.
import app  # noqa: E402,F401

_apply_offline_environment()
