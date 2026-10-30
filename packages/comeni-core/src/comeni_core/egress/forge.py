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


class ModuleFacts(EgressPayload):
    """The upstream module, as nf-core publishes it."""

    module: ModuleKey
    main_nf: Text
    meta_yml: Text


class KnownIds(EgressPayload):
    """What a reply may name: the registry's ids, and pending ones from assembled drafts."""

    types: list[TypeId] = []
    roles: list[RoleName] = []
    measurements: list[MeasurementId] = []
    contracts: list[ContractId] = []
    pending: list[TypeId] = []


class ForgeItemText(EgressPayload):
    """One item of this adaptation and its current value, as JSON text."""

    key: Text
    value: Text


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
