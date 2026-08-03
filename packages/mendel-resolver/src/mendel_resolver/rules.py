"""Tier 3: measured data properties matched against a declared rule table.

A miss is not an escalation to a model. It is a demotion to tier 4.
"""

import operator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from mendel_resolver.goal import DataProfile

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


class Rule(BaseModel):
    id: str
    subject: str
    when: dict[str, dict[str, Any]]
    then: dict[str, Any]
    citation: str | None = None

    def matches(self, profile: DataProfile) -> bool:
        for field, comparison in self.when.items():
            actual = getattr(profile, field, None)
            if actual is None:
                return False
            for symbol, expected in comparison.items():
                if not _OPS[symbol](actual, expected):
                    return False
        return True


class RuleTable(BaseModel):
    rules: list[Rule] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "RuleTable":
        return cls.model_validate(yaml.safe_load(path.read_text()) or {"rules": []})

    def match(self, subject: str, profile: DataProfile) -> Rule | None:
        for rule in self.rules:
            if rule.subject == subject and rule.matches(profile):
                return rule
        return None
