"""Judge: rule-based grounding checks for Red Team proposals (spec Section 9.2).

`check(proposal, context)` runs three checks in order and reports all of them:

| entities_in_asset_model   | every tag in entities + safeguards exists in the unit's assets or safeguards |
| citations_resolve         | >= 1 citation, and every doc:/asset_model: reference resolves                |
| no_control_action_wording | title and recommendation contain no actuation wording                        |

Verdict is `pass` only if all three pass; otherwise `block` with the first
failure as the reason. Tag matching is case-insensitive and ignores hyphens and
spaces, so `P101B` resolves to `P-101B`.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

CHECKS = ("entities_in_asset_model", "citations_resolve", "no_control_action_wording")


def normalize_tag(tag: str) -> str:
    """Judge tag key: upper case, no hyphens, no spaces."""
    return "".join(ch for ch in tag.upper() if ch not in "- _")


@dataclass(frozen=True)
class JudgeContext:
    """Everything the Judge resolves against, loaded once per run."""
    asset_tags: frozenset[str]
    safeguard_refs: frozenset[str]
    link_codes: frozenset[str]
    doc_sections: dict[str, frozenset[str]] = field(default_factory=dict)
    actuation: Optional[Callable[[str], Optional[str]]] = None

    @property
    def known_entities(self) -> set[str]:
        return {normalize_tag(t) for t in self.asset_tags} | {normalize_tag(r) for r in self.safeguard_refs}

    def resolve_citation(self, ref: str) -> bool:
        """`asset_model:L-104` -> asset link; `doc:CODE#section` -> current document section."""
        ref = ref.strip()
        if ref.startswith("asset_model:"):
            return ref.split(":", 1)[1].strip() in self.link_codes
        if ref.startswith("doc:"):
            doc, _, section = ref[4:].partition("#")
            sections = self.doc_sections.get(doc.strip())
            if sections is None:
                return False
            return not section or section.strip().lower() in sections
        return False


@dataclass(frozen=True)
class JudgeCheck:
    check: str
    passed: bool
    detail: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"check": self.check, "passed": self.passed}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


@dataclass(frozen=True)
class JudgeResult:
    verdict: str
    checks: tuple[JudgeCheck, ...]
    reason: Optional[str]
    unknown_entities: tuple[str, ...]
    unresolved_citations: tuple[str, ...]
    actuation_wording: bool

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"verdict": self.verdict, "checks": [c.as_dict() for c in self.checks]}
        if self.reason:
            out["reason"] = self.reason
        return out


def check(proposal: dict[str, Any], context: JudgeContext) -> JudgeResult:
    """Run the three checks on one proposal (a HazopProposalDraft as a dict)."""
    known = context.known_entities
    named: Sequence[str] = list(dict.fromkeys([*proposal.get("entities", []), *proposal.get("safeguards", [])]))
    unknown = tuple(tag for tag in named if normalize_tag(tag) not in known)
    entities = JudgeCheck(
        "entities_in_asset_model",
        not unknown,
        f"{', '.join(unknown)} not found" if unknown else f"{len(named)} / {len(named)}",
    )

    citations = [str(c) for c in proposal.get("citations", [])]
    unresolved = tuple(c for c in citations if not context.resolve_citation(c))
    if not citations:
        cited = JudgeCheck("citations_resolve", False, "no citations")
    elif unresolved:
        cited = JudgeCheck("citations_resolve", False, f"{', '.join(unresolved)} not found")
    else:
        cited = JudgeCheck("citations_resolve", True, f"{len(citations)} / {len(citations)}")

    wording = None
    if context.actuation:
        wording = context.actuation(proposal.get("title", "")) or context.actuation(proposal.get("recommendation", ""))
    action = JudgeCheck(
        "no_control_action_wording",
        wording is None,
        f'"{wording}" reads as a control action' if wording else None,
    )

    checks = (entities, cited, action)
    failed = next((c for c in checks if not c.passed), None)
    reason = None
    if failed is entities:
        reason = f"{', '.join(unknown)} not found in asset model"
    elif failed is not None:
        reason = failed.detail
    return JudgeResult(
        verdict="block" if failed else "pass",
        checks=checks,
        reason=reason,
        unknown_entities=unknown,
        unresolved_citations=unresolved,
        actuation_wording=wording is not None,
    )
