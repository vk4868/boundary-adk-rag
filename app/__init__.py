"""Governed ADK document assistant."""

import os

# LiteLLM otherwise downloads its model-cost map during import. Boundary has a
# fixed local model profile, so import and offline construction must remain
# usable when every network connection is denied.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"

__version__ = "0.1.0"

# ADK CLI discovers `app.agent.root_agent` through the package import.
from app import agent  # noqa: E402,F401
