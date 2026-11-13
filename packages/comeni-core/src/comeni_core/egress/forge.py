"""What forging sends a model (forge MVP 3, #364): public tool files and registry ids in.

**No lab data.** A module's `main.nf` and `meta.yml` are nf-core's public files; the registry's
ids are declared data; items are what this adaptation has drafted or decided. Nothing from a
person's samples, runs or pipelines has a field here.
"""

from enum import StrEnum

from comeni_core.egress.authoring import AuthoringRole
from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import (
    ContractId,
    MeasurementId,
    ModuleKey,
    RoleName,
    Text,
    TypeId,
)


class ForgePiece(StrEnum):
    QUESTIONS = "questions"
    CONTRACT = "contract"
    PARAMETERS = "parameters"
    VOCABULARY = "vocabulary"
    RULES = "rules"
    TESTS = "tests"
    MEASURERS = "measurers"


class ModuleFacts(EgressPayload):
    """The upstream module, as nf-core publishes it."""

    module: ModuleKey
    main_nf: Text
    meta_yml: Text
    nf_test: Text = ""
    """Its `tests/main.nf.test`: public module source, which test files it uses and how."""


class TypeGrain(StrEnum):
    """How a type arrives: once for the whole study (a reference) or once per sample."""

    STUDY = "study"
    SAMPLE = "sample"


class KnownType(EgressPayload):
    """A registry type's declared meaning (#453): what the page shows beside each option."""

    id: TypeId
    name: Text = ""
    grain: TypeGrain = TypeGrain.SAMPLE
    explain: Text = ""


class KnownIds(EgressPayload):
    """What a reply may name: the registry's ids, and pending ones from assembled drafts."""

    types: list[TypeId] = []
    signatures: list[Text] = []
    roles: list[RoleName] = []
    measurements: list[MeasurementId] = []
    contracts: list[ContractId] = []
    pending: list[TypeId] = []
    families: list[TypeId] = []
    pending_families: list[TypeId] = []
    described: list[KnownType] = []
    """Each registry type with its name, grain and explanation, not the bare id alone."""


class ForgeItemStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REMOVED = "removed"
    REOPENED = "reopened"


class ForgeItemText(EgressPayload):
    """One item of this adaptation and its current value, as JSON text."""

    key: Text
    value: Text
    status: ForgeItemStatus = ForgeItemStatus.PROPOSED


class ForgeFinding(EgressPayload):
    """An engine check on a question (#452), computed from the items and registry above."""

    item: Text
    code: Text
    says: Text


class ForgeTurn(EgressPayload):
    role: AuthoringRole
    content: Text


class ForgeRequest(EgressPayload):
    prompt: Text
    piece: ForgePiece
    module: ModuleFacts
    known: KnownIds
    items: list[ForgeItemText] = []
    turns: list[ForgeTurn] = []
    findings: list[ForgeFinding] = []
