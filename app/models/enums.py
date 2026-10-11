"""PostgreSQL enum types from safeloop_mvp_schema.dbml.

Each Python enum stores its *value* in the database (values_callable), and
each SQLAlchemy type is bound to Base.metadata so a type shared by several
tables (e.g. data_origin) is created once, not once per table.
"""
import enum
from sqlalchemy import Enum as SAEnum
from config.databases.postgresql import Base


class UserRole(str, enum.Enum):
    """`user_role` enum."""
    PROCESS_SAFETY_ENGINEER = "process_safety_engineer"
    RELIABILITY_ENGINEER = "reliability_engineer"
    OPERATOR = "operator"
    TRAINEE = "trainee"
    PLANT_MANAGER = "plant_manager"
    AUDITOR = "auditor"
    ADMIN = "admin"


class DataOrigin(str, enum.Enum):
    """`data_origin` enum."""
    SYNTHETIC = "synthetic"
    PUBLIC_PROXY = "public_proxy"
    REAL = "real"


class HealthBand(str, enum.Enum):
    """`health_band` enum: healthy HI >= 80, degraded 50-79, critical < 50."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class GuideWord(str, enum.Enum):
    """`guide_word` enum."""
    NO = "no"
    LESS = "less"
    MORE = "more"
    REVERSE = "reverse"
    AS_WELL_AS = "as_well_as"
    PART_OF = "part_of"
    OTHER_THAN = "other_than"
    HIGH = "high"
    LOW = "low"


class HazopParam(str, enum.Enum):
    """`hazop_param` enum."""
    FLOW = "flow"
    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    LEVEL = "level"
    COMPOSITION = "composition"
    OTHER = "other"


class SafeguardType(str, enum.Enum):
    """`safeguard_type` enum."""
    BPCS = "bpcs"
    ALARM = "alarm"
    IPL = "ipl"
    PROCEDURE = "procedure"
    SIS = "sis"


class RecordStatus(str, enum.Enum):
    """`record_status` enum."""
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DocType(str, enum.Enum):
    """`doc_type` enum."""
    MANUAL = "manual"
    SOP = "sop"
    ALARM_RESPONSE = "alarm_response"
    INCIDENT = "incident"
    MAINTENANCE_REPORT = "maintenance_report"
    HAZOP = "hazop"
    ASSET_MODEL = "asset_model"
    SHIFT_LOG = "shift_log"
    RCA_REPORT = "rca_report"


class AgentName(str, enum.Enum):
    """`agent_name` enum."""
    HEALTH_AGENT = "health_agent"
    RISK_ENGINE = "risk_engine"
    RED_TEAM = "red_team"
    JUDGE = "judge"
    KNOWLEDGE_AGENT = "knowledge_agent"
    GUARDRAIL = "guardrail"
    REPORTER = "reporter"


class Verdict(str, enum.Enum):
    """`verdict` enum."""
    PASS = "pass"
    BLOCK = "block"
    REVISE = "revise"


class ArtifactType(str, enum.Enum):
    """`artifact_type` enum."""
    HAZOP_CHANGE = "hazop_change"
    RISK_RESCORE = "risk_rescore"
    MAINTENANCE_RECOMMENDATION = "maintenance_recommendation"
    MOC_DRAFT = "moc_draft"
    RCA_REPORT = "rca_report"


class ApprovalDecision(str, enum.Enum):
    """`approval_decision` enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CitationTarget(str, enum.Enum):
    """`citation_target` enum."""
    CHUNK = "chunk"
    ASSET = "asset"
    TAG_WINDOW = "tag_window"
    HAZOP_ROW = "hazop_row"


def _pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a native PostgreSQL enum type that stores member values."""
    return SAEnum(
        enum_cls,
        name=name,
        metadata=Base.metadata,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


# SQLAlchemy column types (shared instances, one PG type each)
user_role_enum = _pg_enum(UserRole, "user_role")
data_origin_enum = _pg_enum(DataOrigin, "data_origin")
health_band_enum = _pg_enum(HealthBand, "health_band")
guide_word_enum = _pg_enum(GuideWord, "guide_word")
hazop_param_enum = _pg_enum(HazopParam, "hazop_param")
safeguard_type_enum = _pg_enum(SafeguardType, "safeguard_type")
record_status_enum = _pg_enum(RecordStatus, "record_status")
doc_type_enum = _pg_enum(DocType, "doc_type")
agent_name_enum = _pg_enum(AgentName, "agent_name")
verdict_enum = _pg_enum(Verdict, "verdict")
artifact_type_enum = _pg_enum(ArtifactType, "artifact_type")
approval_decision_enum = _pg_enum(ApprovalDecision, "approval_decision")
citation_target_enum = _pg_enum(CitationTarget, "citation_target")
