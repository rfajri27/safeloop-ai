"""Shared enums and pagination helpers used across SafeLoop API schemas.

DB enums are re-exported from app.models.enums so request validation and
the database share one definition of the allowed values.
"""
from enum import Enum
from app.models.enums import (  # noqa: F401 - re-exported for routes and schemas
    ApprovalDecision,
    ArtifactType,
    DocType,
    HealthBand,
    UserRole,
)


class RiskBand(str, Enum):
    """Risk matrix bands: Low 1-4, Medium 5-9, High 10-14, Extreme 15-25."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class AuditEventType(str, Enum):
    """Audit log filter types shown on the Audit screen."""
    REPLAY = "replay"
    HEALTH = "health"
    RE_SCORE = "re_score"
    PROPOSAL = "proposal"
    APPROVAL = "approval"
    ANSWER = "answer"
    GUARDRAIL = "guardrail"


class AuditActor(str, Enum):
    """Audit log actor filter values."""
    HEALTH_AGENT = "health_agent"
    RISK_ENGINE = "risk_engine"
    REDTEAM = "redteam"
    JUDGE = "judge"
    KNOWLEDGE_AGENT = "knowledge_agent"
    GUARDRAIL = "guardrail"
    USER = "user"


# Pagination defaults (API conventions, Section 4)
DEFAULT_SKIP = 0
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
