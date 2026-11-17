"""The builder agent's Data tools (#511): read the analysis's data by name and fact, change how
its files are read into samples, and apply what *Check these* offers. **What the agent changes is
marked AI, with its reason, until a person keeps it**; the data is read again at once, so the
agent sees what its change did."""

from typing import Literal

from comeni_core.egress.agent import DataCheckLine, DataView, TextView
from comeni_core.spell.marks import Digest, TypeId
from pydantic import BaseModel, Field

from mendel_api.agent.tools import Nothing, Tool, ToolContext, register
from mendel_api.db import session_scope
from mendel_api.models import AnalysisData
from mendel_api.services.data import rule, scan
from mendel_api.services.data.rule import Fix, Rule


def _row(db, draft_id: str) -> AnalysisData:
    row = db.get(AnalysisData, draft_id)
    if row is None:
        raise ValueError("no data yet: ask the person to tick folders in Data")
    return row


def read_data(ctx: ToolContext, _: Nothing) -> DataView:
    from mendel_api.services.data.references import candidates

    with session_scope() as db:
        row = db.get(AnalysisData, ctx.draft_id)
        if row is None:
            return DataView()
        samples = list(row.samples or [])
        reading = Rule(**row.rule) if row.rule else Rule()
        unfit = list(row.unfit or [])
        fixes = list(row.fixes or [])
        references = sorted(r["type_id"] for r in (row.references or []))
        reference_files = candidates(row)
    found = rule.checks(samples, unfit, [Fix(**f) for f in fixes])
    return DataView(
        samples=[s["name"] for s in samples],
        left_out=[s["name"] for s in samples if s.get("left_out")],
        kinds=sorted({s["type_id"] for s in samples if s.get("type_id")}),
        unfit=len(unfit), rule=reading.pattern, rule_by=reading.origin,
        rule_confirmed=reading.confirmed,  # a rule the AI set is AI until the person keeps it
        checks=[DataCheckLine(sample=c.sample, kind=c.kind, measurement=c.measurement,
                              file=next((f.file for f in c.fixes if f.file), None))
                for c in found],
        references=references, reference_files=reference_files)


class ReferenceArgs(BaseModel):
    file_id: Digest
    type_id: TypeId
    because: str = Field(min_length=1, max_length=300)


def add_reference(ctx: ToolContext, args: ReferenceArgs) -> TextView:
    from mendel_api.services.data.references import choose

    name = choose(ctx.draft_id, args.file_id, args.type_id, args.because)
    from mendel_api.agent import chat

    chat.rebuild_for_data(ctx.draft_id, ctx.who)
    return TextView(text=f"selected {name} as {args.type_id}; set by the AI: {args.because}")


def _rescan(ctx: ToolContext, change) -> int:
    with session_scope() as db:
        row = _row(db, ctx.draft_id)
        change(row)
        row.revision = (row.revision or 0) + 1
        revision = row.revision
    scan.scan(ctx.draft_id, who=ctx.who, revision=revision)
    from mendel_api.agent import chat

    chat.rebuild_for_data(ctx.draft_id, ctx.who)
    return revision


class RuleArgs(BaseModel):
    pattern: str | None = Field(description="e.g. {sample}_R{read}.fastq.gz; null: by name")
    because: str = Field(min_length=1, max_length=300)


def set_reading_rule(ctx: ToolContext, a: RuleArgs) -> TextView:
    chosen = Rule(pattern=a.pattern, origin="ai", reason=a.because)
    if chosen.pattern is not None:
        rule.group([], chosen, [])  # a bad pattern is refused now, with MI0223
    _rescan(ctx, lambda row: setattr(row, "rule", chosen.model_dump()))
    with session_scope() as db:
        row = _row(db, ctx.draft_id)
        return TextView(text=f"read again: {len(row.samples or [])} samples, "
                             f"{len(row.unfit or [])} files did not fit; marked AI until kept")


class ApplyFixArgs(BaseModel):
    kind: Literal["use_file", "leave_out"]
    sample: str = Field(min_length=1, max_length=256)
    file: str | None = Field(default=None, max_length=256, description="for use_file")
    because: str = Field(min_length=1, max_length=300)


def apply_fix(ctx: ToolContext, a: ApplyFixArgs) -> TextView:
    from mendel_api.services.data import edits

    made = Fix(kind=a.kind, sample=a.sample, file=a.file, by="ai", reason=a.because)
    edits.change(ctx.draft_id, fix=made)
    from mendel_api.agent import chat

    chat.rebuild_for_data(ctx.draft_id, ctx.who)
    said = f"used {a.file} as {a.sample}'s mate" if a.kind == "use_file" else f"left {a.sample} out"
    return TextView(text=f"{said}; marked AI until kept")


for _tool in (
    Tool("read_data", "The person's samples, how files were read, what to check.", Nothing,
         read_data),
    Tool("add_reference", "Choose a reference from read_data's reference_files.",
         ReferenceArgs, add_reference, writes=True),
    Tool("set_reading_rule", "Read files into samples by a pattern.", RuleArgs, set_reading_rule,
         writes=True),
    Tool("apply_fix", "Use a file as a sample's mate, or leave a sample out.", ApplyFixArgs,
         apply_fix, writes=True),
):
    register(_tool)
