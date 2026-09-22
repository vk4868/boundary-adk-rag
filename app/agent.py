"""ADK CLI/dev/eval export with explicit local-run authorization."""

from app.agents import GovernedCliAgent
from app.audit import AuditLogger
from app.config import get_settings
from app.index import IndexRepository


settings = get_settings()
repository = IndexRepository(settings)
# The wrapper constructs an isolated governed SequentialAgent and RunLedger for
# every invocation, including concurrent ADK eval/dev requests.
root_agent = GovernedCliAgent(
    name="governed_document_assistant",
    description="Runs an isolated governed document research pipeline.",
    settings=settings,
    repository=repository,
    audit_logger=AuditLogger(settings.app_audit_path),
)
