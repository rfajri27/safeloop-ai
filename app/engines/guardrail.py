"""Guardrail, rules gr.v1 (spec Section 9.3).

`check(text)` runs before any model call. Rules are regular expressions from
guardrail_rules.yaml, matched case-insensitively in file order: injection first,
then the bypass rule, then the general control-verb rule. A rule's `allow_if`
lets a question about HOW a procedure works through.
"""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional
import yaml

ACTUATION_RULES = ("GR-ACT-01", "GR-ACT-02")


@dataclass(frozen=True)
class GuardRule:
    id: str
    description: str
    pattern: re.Pattern
    allow_if: Optional[re.Pattern]
    refusal: str


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    rule_id: Optional[str] = None
    reason: Optional[str] = None
    refusal: Optional[str] = None


@dataclass(frozen=True)
class Guardrail:
    version: str
    rules: tuple[GuardRule, ...]

    def check(self, text: str) -> GuardResult:
        """First matching rule blocks; `allow_if` exempts procedure questions."""
        for rule in self.rules:
            if rule.pattern.search(text):
                if rule.allow_if and rule.allow_if.search(text):
                    continue
                return GuardResult(blocked=True, rule_id=rule.id, reason=rule.description, refusal=rule.refusal)
        return GuardResult(blocked=False)

    def actuation_wording(self, text: str) -> Optional[str]:
        """Control-action wording in a draft (Judge check `no_control_action_wording`).

        GR-ACT-02 (bypass/disable) counts anywhere. GR-ACT-01 counts only when
        the control verb opens a sentence or clause, i.e. an instruction such as
        "Open TV-301 to 100%"; "test the P-101B auto-start, including FT-201"
        names equipment without telling anyone to operate it.
        """
        rules = {rule.id: rule for rule in self.rules}
        bypass = rules.get("GR-ACT-02")
        if bypass:
            match = bypass.pattern.search(text)
            if match:
                return match.group(0)
        control = rules.get("GR-ACT-01")
        if control:
            clauses = re.split(r"[.;:!?\n]|,\s*(?:then|and)\b|\b(?:and\s+)?then\b", text, flags=re.IGNORECASE)
            for clause in clauses:
                clause = re.sub(r"^\s*(?:please|immediately|now)\s+", "", (clause or "").strip(), flags=re.IGNORECASE)
                match = control.pattern.match(clause)
                if match:
                    return match.group(0)
        return None


def load_guardrail(path: Path) -> Guardrail:
    """Parse guardrail_rules.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = tuple(
        GuardRule(
            id=r["id"],
            description=r.get("description", ""),
            pattern=re.compile(r["pattern"], re.IGNORECASE),
            allow_if=re.compile(r["allow_if"], re.IGNORECASE) if r.get("allow_if") else None,
            refusal=" ".join(str(r.get("refusal", "")).split()),
        )
        for r in data["rules"]
    )
    return Guardrail(version=data.get("version", "gr.v1"), rules=rules)


@lru_cache(maxsize=4)
def get_guardrail(path: str) -> Guardrail:
    """Cached guardrail for a rules file path."""
    return load_guardrail(Path(path))
