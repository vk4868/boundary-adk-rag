"""Governed ADK document assistant."""

__version__ = "0.1.0"

# ADK CLI discovers `app.agent.root_agent` through the package import.
from app import agent  # noqa: E402,F401
