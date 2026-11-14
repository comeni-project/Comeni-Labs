"""What proposing a rule sends a model (#462): past decisions and the study facts they rested on.

**No sample data.** A case is a decision a person made and the study-wide facts it was made on
(an organism, a read length), with the reason they typed. No sample names, keys, references,
file names or sample text have a field here, and a fact is only one of the kinds a rule can test.
"""

from enum import StrEnum

from comeni_core.declared.measurement import MeasurementKind
from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import ContractId, Line, MeasurementId, ParamValue, RoleName, Text


class RuleEffect(StrEnum):
    """What a learned rule decides: which tool fills a role, or a setting's value."""

    IMPLEMENTATION = "implementation"
    PARAM = "param"


class RuleTarget(EgressPayload):
    effect: RuleEffect
    of: RoleName
    name: MeasurementId | None = None
    """The setting, for a `param` target: an identifier, as a measurement id is."""
    when_implementation: list[ContractId] = []


class FactKind(EgressPayload):
    """A fact a row may test: its kind, and its allowed values for an enum."""

    id: MeasurementId
    kind: MeasurementKind
    values: list[ParamValue] = []


class FactValue(EgressPayload):
    measurement: MeasurementId
    value: ParamValue


class CaseText(EgressPayload):
    """One person's answer, and the facts it was given on."""

    facts: list[FactValue] = []
    answer: ParamValue
    reason: Line = ""


class RuleProposalRequest(EgressPayload):
    prompt: Text
    target: RuleTarget
    existing: list[Text] = []
    """The existing table's rows, each as JSON, in order."""
    facts: list[FactKind] = []
    answers: list[ParamValue] = []
    """The legal answers: the candidate tools, or the setting's domain."""
    cases: list[CaseText] = []
