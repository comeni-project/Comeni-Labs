"""A step's card: what it does, why it is here, what it makes, and what to check.

Every field comes from declared data or from the resolver's own record, **used as written**: no
model rewords it (spec §2, option a) and a missing source leaves the field out rather than
filling it. Each line says where it came from — `curated` (declared, approved data) or `engine`
(the resolver's record) — so the marks part 4 draws have something to read.
"""

from enum import StrEnum

from comeni_core.artifact.pipeline import Step, Why
from comeni_core.declared.families import family_of
from comeni_core.plan.tiers import Tier
from pydantic import BaseModel, ConfigDict

from mendel_authoring.ports import Declared

OPEN_STEP = "no rule could decide which tool fills this step"


class TextSource(StrEnum):
    ENGINE = "engine"
    CURATED = "curated"


class Said(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    source: TextSource


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    does: Said | None = None
    why: list[Said]
    makes: list[Said]
    check: list[Said] = []


def tool_of(contract_id: str) -> str:
    """`nf-core/star/align@1.11.0` → `nf-core/star`: the key `tool.yml` is declared under."""
    return "/".join(contract_id.split("@", 1)[0].split("/")[:2])


def family_said(type_id: str, declared: Declared) -> Said | None:
    """A type in its family's words; types carry no description of their own."""
    described = declared.family(family_of(type_id))
    return Said(text=described, source=TextSource.CURATED) if described else None


def brief_of(step: Step, declared: Declared) -> Brief:
    described = declared.tool(tool_of(step.module.contract_id))
    return Brief(
        does=Said(text=described, source=TextSource.CURATED) if described else None,
        why=_why(step.why),
        makes=_unique(
            family_said(type_id, declared) for type_id in declared.outputs(step.module.contract_id)
        ),
        check=_unique(_checks(step)),
    )


def _why(why: Why) -> list[Said]:
    said = [Said(text=why.reason, source=TextSource.ENGINE)]
    if why.axis_reason:
        said.append(Said(text=why.axis_reason, source=TextSource.ENGINE))
    return said


def _checks(step: Step):
    """Tier 3: each premise's own sentence. Tier 4: the open question. Tiers 1–2: nothing."""
    for why, name in [(step.why, None), *((s.why, s.name) for s in step.settings)]:
        if why.tier is Tier.DATA_PROFILED:
            for premise in why.premise:
                yield Said(text=premise.prose(), source=TextSource.ENGINE)
        elif why.tier is Tier.AMBIGUOUS:
            text = OPEN_STEP if name is None else f"no rule decided {name}"
            yield Said(text=text, source=TextSource.ENGINE)


def _unique(said) -> list[Said]:
    """In order, each line once, `None` dropped."""
    seen: list[Said] = []
    for line in said:
        if line is not None and line not in seen:
            seen.append(line)
    return seen
