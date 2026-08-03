"""Tier 3: measured data properties matched against a declared rule table.

A miss is not an escalation to a model. It is a demotion to tier 4.
"""

import operator
from collections.abc import Sequence
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
            actual = profile.get(field)
            if actual is None:
                return False
            for symbol, expected in comparison.items():
                if not _OPS[symbol](actual, expected):
                    return False
        return True


class RuleTable(BaseModel):
    rules: list[Rule] = Field(default_factory=list)

    @classmethod
    def load(cls, layers: "Path | Sequence[Path]") -> "RuleTable":
        """Every `*.yml` under every layer, in order. A single file still works.

        The CLI used to pin the literal filename `rnaseq.yml`, so a laboratory could not
        ship rules at all — audit 2026-08-03, I4.
        """
        if isinstance(layers, Path):
            layers = [layers]
        rules: list[Rule] = []
        for layer in layers:
            paths = [layer] if layer.is_file() else sorted(layer.glob("*.yml"))
            for path in paths:
                data = yaml.safe_load(path.read_text()) or {}
                rules += [Rule.model_validate(r) for r in data.get("rules", [])]
        return cls(rules=rules)

    def match(self, subject: str, profile: DataProfile) -> Rule | None:
        for rule in self.rules:
            if rule.subject == subject and rule.matches(profile):
                return rule
        return None
