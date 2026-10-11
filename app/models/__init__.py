# Models
# One SQLAlchemy model per table in safeloop_mvp_schema.dbml.
# Every model is imported here so Base.metadata (and Alembic autogenerate) sees it.

# Plant model
from app.models.site_model import Site
from app.models.unit_model import Unit
from app.models.process_node_model import ProcessNode
from app.models.asset_model import Asset
from app.models.asset_link_model import AssetLink
from app.models.sensor_tag_model import SensorTag

# Telemetry & health
from app.models.replay_run_model import ReplayRun
from app.models.sensor_reading_model import SensorReading
from app.models.health_assessment_model import HealthAssessment

# HAZOP & risk
from app.models.hazop_row_model import HazopRow
from app.models.hazop_recommendation_model import HazopRecommendation
from app.models.safeguard_model import Safeguard
from app.models.hazop_row_safeguard_model import HazopRowSafeguard
from app.models.safeguard_dependency_model import SafeguardDependency
from app.models.risk_rule_set_model import RiskRuleSet
from app.models.risk_rescore_model import RiskRescore

# Knowledge base
from app.models.document_model import Document
from app.models.document_asset_model import DocumentAsset
from app.models.document_chunk_model import DocumentChunk

# AI & governance
from app.models.user_model import User
from app.models.prompt_template_model import PromptTemplate
from app.models.agent_run_model import AgentRun
from app.models.hazop_proposal_model import HazopProposal
from app.models.judge_verdict_model import JudgeVerdict
from app.models.approval_item_model import ApprovalItem
from app.models.chat_session_model import ChatSession
from app.models.chat_message_model import ChatMessage
from app.models.citation_model import Citation
from app.models.audit_log_model import AuditLog

# Evaluation
from app.models.golden_item_model import GoldenItem
from app.models.eval_run_model import EvalRun
from app.models.eval_result_model import EvalResult
from app.models.eval_item_result_model import EvalItemResult
