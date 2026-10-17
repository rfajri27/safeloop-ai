"""Audit record helpers shared by every service that writes or reads audit_log.

Writers build rows with `audit_entry()` and add them in the same transaction as
the action they record (PO-5). The display fields the Audit screen shows
(event text, outcome, number of sources) are stored in `detail` at write time,
so the log reads the same way later even if templates change.
"""
from typing import Any, Iterable, Optional
from app.models.audit_log_model import AuditLog
from app.models.enums import AgentName

# Audit screen filter type -> audit_log.action values
AUDIT_TYPES: dict[str, tuple[str, ...]] = {
    "replay": (
        "replay_started", "replay_paused", "replay_resumed", "replay_speed_changed",
        "replay_reset", "replay_finished", "asset_trip",
    ),
    "health": ("health_band_changed",),
    "re_score": ("risk_rescore", "rescore_withdrawn"),
    "proposal": ("draft_created", "judge_block", "schema_invalid", "red_team_failed"),
    "approval": ("approved", "rejected"),
    "answer": ("answer", "insufficient", "answer_cancelled", "answer_failed"),
    "guardrail": ("guardrail_refusal",),
}
ACTION_TYPES = {action: kind for kind, actions in AUDIT_TYPES.items() for action in actions}

AGENT_LABELS = {
    AgentName.HEALTH_AGENT: "Health Agent",
    AgentName.RISK_ENGINE: "Risk Engine",
    AgentName.RED_TEAM: "Red Team",
    AgentName.JUDGE: "Judge",
    AgentName.KNOWLEDGE_AGENT: "Knowledge Agent",
    AgentName.GUARDRAIL: "Guardrail",
    AgentName.REPORTER: "Reporter",
}

# Actor filter value (API enum, or the label the UI shows) -> agent; "user" = any person
ACTOR_FILTERS: dict[str, Optional[AgentName]] = {
    "health_agent": AgentName.HEALTH_AGENT,
    "risk_engine": AgentName.RISK_ENGINE,
    "redteam": AgentName.RED_TEAM,
    "red_team": AgentName.RED_TEAM,
    "judge": AgentName.JUDGE,
    "knowledge_agent": AgentName.KNOWLEDGE_AGENT,
    "guardrail": AgentName.GUARDRAIL,
    "user": None,
    **{label.lower(): agent for agent, label in AGENT_LABELS.items()},
}

# Actions that come from a model call must name the model and prompt version.
MODEL_ACTIONS = {"draft_created", "judge_block", "answer"}


def audit_id(event_id: Optional[int]) -> Optional[str]:
    """Display id: AUD- plus the zero-padded audit_log id."""
    return f"AUD-{event_id:04d}" if event_id is not None else None


def audit_entry(
    action: str,
    entity_table: str,
    entity_id: str,
    text: str,
    outcome: str,
    sources: int = 0,
    actor_agent: Optional[AgentName] = None,
    actor_user: Optional[str] = None,
    model_id: Optional[str] = None,
    prompt_version: Optional[str] = None,
    rule_set_version: Optional[str] = None,
    replay_run_id: Optional[str] = None,
    replay_hour: Optional[int] = None,
    **detail: Any,
) -> AuditLog:
    """Build an audit_log row; add it in the caller's transaction."""
    return AuditLog(
        action=action,
        actor_agent=actor_agent,
        actor_user=actor_user,
        entity_table=entity_table,
        entity_id=entity_id,
        model_id=model_id,
        prompt_version=prompt_version,
        rule_set_version=rule_set_version,
        replay_run_id=replay_run_id,
        replay_hour=replay_hour,
        detail={"text": text, "outcome": outcome, "sources": sources, **detail},
    )


def actor_label(event: AuditLog, user_names: dict[str, str]) -> str:
    """Who acted, as shown on the Audit screen."""
    if event.actor_agent:
        return AGENT_LABELS.get(event.actor_agent, event.actor_agent.value)
    if event.actor_user:
        return user_names.get(event.actor_user, "Unknown user")
    return "System"


def audit_event_view(event: AuditLog, user_names: dict[str, str]) -> dict[str, Any]:
    """One audit_log row in the GET /audit-events shape."""
    detail = dict(event.detail or {})
    text = detail.pop("text", None) or event.action.replace("_", " ").capitalize()
    outcome = detail.pop("outcome", "logged")
    sources = detail.pop("sources", 0)
    rule_set = None
    if event.rule_set_version:
        rules = detail.get("rules_applied") or []
        rule_set = f"rules {event.rule_set_version}" + (f" · {', '.join(rules)}" if rules else "")
    return {
        "audit_id": audit_id(event.id),
        "at": event.occurred_at.isoformat(),
        "replay_hour": event.replay_hour,
        "type": ACTION_TYPES.get(event.action, "other"),
        "action": event.action,
        "event": text,
        "actor": actor_label(event, user_names),
        "model": event.model_id,
        "prompt_version": event.prompt_version,
        "rule_set_version": rule_set,
        "sources": sources,
        "outcome": outcome,
        "entity": {"table": event.entity_table, "id": event.entity_id},
        "run_id": event.replay_run_id,
        "detail": detail,
    }


def is_complete(event: AuditLog) -> bool:
    """PO-5 completeness: actor, text and outcome always; model fields for model output."""
    detail = event.detail or {}
    if not (event.actor_agent or event.actor_user) or not detail.get("text") or not detail.get("outcome"):
        return False
    if event.action in MODEL_ACTIONS and (not event.model_id or not event.prompt_version):
        return False
    if event.action == "risk_rescore" and not event.rule_set_version:
        return False
    if event.action == "health_band_changed" and not event.model_id:
        return False
    return True


def completeness_pct(events: Iterable[AuditLog]) -> float:
    """Share of complete records, 100 for an empty log."""
    events = list(events)
    if not events:
        return 100.0
    return round(100 * sum(is_complete(e) for e in events) / len(events), 1)
