"""Drafts: a graph somebody is still drawing, and the moment one stops being one.

**A draft is server state; a pipeline is an artifact.** `keep` is the boundary — it validates,
refuses anything illegal, and writes the `pipeline.yml`. Everything before that is a row.

**`_load` and `_output_root` are seams, not indirection.** These tests need Postgres and CI has
none, so the rule most worth defending in CI — that `keep` refuses an illegal graph — is tested
with the storage monkeypatched. A `keep` that reached straight into a session would be a rule
only a developer machine could check.
"""

import secrets
from datetime import UTC, datetime
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline, Why
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from comeni_core.plan.ir import ValueSource
from comeni_core.spell.marks import NodeId, PortName
from mendel_compiler import pipeline_file, staging
from mendel_resolver.materialise import goal_of, ir_of
from pydantic import BaseModel, ConfigDict, Field

from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import registry
from mendel_api.services import validate as validation
from mendel_api.settings import settings


class Provenance(BaseModel):
    """How much of one pipeline was settled without judgement — a proportion of one whole.

    **Read from the stored artifact, never from a re-resolve.** The 2026-08-19 audit found every
    registry-touching screen cost ~250ms warm and one function was responsible; a front door that
    rebuilt four pipelines to draw four bars would be that finding arriving again, this time on
    the page a person opens first.

    `settled` is tiers 1 and 2 — **tier 3 is deliberately not in it.** A rule matched measured
    data, which is the machinery working, and the premise behind the measurement still needs a
    person. `frontend/src/build/Provenance.tsx` says the same thing in the same words, and
    counting tier 3 as settled would turn the one element carrying the product's claim into the
    one element overstating it.
    """

    model_config = ConfigDict(extra="forbid")

    settled: int
    """Tiers 1 and 2 — no choice existed, or a documented convention decided it."""
    measured: int
    """Tier 3. A rule matched measured data."""
    open: int
    """Tier 4 that **nobody has answered**. This is what needs a person."""

    by_person: int
    """Tier 4 that a person answered — `why.source: human`.

    **Found by running it, and it is a gap between the design and the data.** The artboard's bar
    has three bands and every pipeline it draws is one the *resolver* built, where steps exit at
    tiers 1–3 and this is zero. A **hand-drawn** pipeline is the opposite: every step is
    `tier: 4, source: human`, because a person chose it. Counting those as `open` reported *5
    open* on the canonical spine where exactly **one** value needs anybody — a five-fold
    overstatement, on the front door, on the element that carries the product's claim.

    Crying wolf is the same failure as hiding: invariant 6 flags tier 4 so that a flag means
    something, and a bar that flags four settled choices teaches people to ignore it.

    It is not folded into `settled`. That band is headlined *settled without judgement*, and a
    person's answer is judgement — the honest word for it is a different word.
    """
    by_model: int
    """Tier 4 that a model answered — `why.source: model`.

    **Separate from `by_person` on purpose**, and the schema was bumped 4→5 to make it possible:
    *a pipeline an agent assembled must not read as one a person drew by hand.* Merging them
    here would undo that at the last step, on the page most people read.
    """


class OpenValue(BaseModel):
    """One tier-4 value nobody has answered, named."""

    model_config = ConfigDict(extra="forbid")

    step: NodeId
    setting: PortName


class DraftRow(BaseModel):
    """One pipeline on the front door's *by pipeline* table.

    **Readiness, not history** — `ov-work`. A run's outcome belongs to the *by run* view, and
    leaking `last run 2d ago · M. Silva` onto a pipeline card is the actual bug that made two
    blocks read as one list rendered twice.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    who: str
    """ATTRIBUTION, not authentication — `PipelineDraft.who`, from `identity.default_author()`.

    **Every row carries a person even though there is only one.** When accounts arrive there
    will be two overviews and the second must be a *filter* rather than a second page; a row
    that ships without a person is what turns that filter into a rewrite (`ov-scope`).
    """
    updated_at: datetime
    steps: int
    makes: list[str] = Field(default_factory=list)
    """What this pipeline produces — the goal's `want`, as type ids.

    **Type ids and not prose**, because there is no prose to be had: issue #78 records that
    `ModuleContract` has no description field, and `impl-reuse` on the canvas is explicit that
    the type signature is the description that ships today and the slot is to be left empty
    rather than filled with something invented. `counts.matrix` is true; *"counts from paired
    RNA-seq reads"* is a sentence somebody would have to write.

    Empty for a draft that has never been kept — there is no goal until there is an artifact.
    """

    kept: bool
    """Whether `keep` has ever written an artifact for this draft."""
    digest: str | None = None
    """`Pipeline.content_digest()` of the kept artifact — **the join key to a run.**

    Wiener computes the same digest from the same file when the bundle is uploaded, so the
    browser can put runs beside pipelines **without either server learning the other exists**
    (`wiener.md` §12, and `useSubmit.ts`'s header). Content-addressed is what makes that work:
    neither half has to know the other's identifiers, only the bytes they both hold.

    `content_digest()` rather than `emitted.from_digest`: the recorded one is only present once
    a pipeline has been emitted, and a kept draft that has never been gated still deserves to be
    matched to its runs. The two agree by construction — `from_digest` records this value.

    `None` until the draft is kept.
    """

    provenance: Provenance | None = None
    """**Absent, not three zeroes**, for a draft that has never been kept.

    A bar of three empty segments claims a pipeline with nothing open, which is the opposite of
    *we have not looked*. Same rule as `ProcessRow.reported_resources`: a dash never means zero.
    """
    open_values: list[OpenValue] = Field(default_factory=list)
    """Which tier-4 values are unanswered, **named rather than counted**.

    `ov-settled`: *waiting on a person names the values — 'strandedness and fragment size', not
    '2 items'. A count is what you write when you have not looked.*
    """
    open_not_named: int = 0
    """How many more there are than `open_values` lists, so a cap never reads as the total."""


_NAMED_AT_MOST = 6
"""A sentence names a few things; past that it is a list wearing prose. The remainder is
carried as a number so the page can say *and four more* rather than silently truncating."""


def _provenance_of(pipeline: Pipeline) -> tuple[Provenance, list[OpenValue], int]:
    """Count tiers over every decision the artifact records — steps **and** settings.

    Both carry a tier and both can be tier 4. `services/build.py` makes the same argument at
    length: counting steps only reported *0 needing your decision* on a pipeline whose
    `seq_platform` exits at tier 4, understating on the one element that carries the claim.
    """
    tally = {"settled": 0, "measured": 0, "open": 0, "by_person": 0, "by_model": 0}
    named: list[OpenValue] = []
    unnamed = 0

    def count(why: Why, step: str | None = None, setting: str | None = None) -> None:
        nonlocal unnamed
        tier = int(why.tier)
        if tier in (1, 2):
            tally["settled"] += 1
            return
        if tier == 3:
            tally["measured"] += 1
            return
        # **Tier 4 is three different facts and only one of them needs a person.**
        # `why.source` is the discriminator the artifact already uses: `MD0220` says
        # `source: human` is what CLEARS a review, and it must be backed by a decision
        # recording the answer. Reading the tier alone reports every hand-drawn step as open.
        if why.source is ValueSource.HUMAN:
            tally["by_person"] += 1
            return
        if why.source is ValueSource.MODEL:
            tally["by_model"] += 1
            return
        tally["open"] += 1
        if step is None or setting is None:
            return
        if len(named) < _NAMED_AT_MOST:
            named.append(OpenValue(step=step, setting=setting))
        else:
            unnamed += 1

    for step in pipeline.steps:
        # A tier-4 *step* is an unanswered module choice rather than an unanswered value, so it
        # is counted and never named — the page's sentence is about values, and naming a step
        # there would read as a value called nothing.
        count(step.why)
        for setting in step.settings:
            count(setting.why, step=step.id, setting=setting.name)

    return Provenance(**tally), named, unnamed


def list_drafts(*, after: int = 0, limit: int = 50) -> tuple[list[DraftRow], int]:
    """Every pipeline this laboratory has, newest edit first.

    **Nothing here resolves anything.** Provenance comes off the artifact `keep` already wrote;
    a draft that has never been kept has none, and says so by absence.

    Measured warm at **35.5ms** for 21 pipelines of which 12 were kept, against the ~250ms the
    2026-08-19 audit found every registry-touching screen costing. The cost is one YAML parse
    per *kept* artifact and is linear in that, not in the registry — so it grows with the
    laboratory's own work rather than with how much the product knows, which is the right thing
    for it to grow with. Audit A138 records where a number like this stops being true.
    """
    with session_scope() as session:
        total = session.query(PipelineDraft).count()
        rows = (
            session.query(PipelineDraft)
            .order_by(PipelineDraft.updated_at.desc(), PipelineDraft.id)
            .offset(after)
            .limit(limit)
            .all()
        )
        listed = [
            (row.id, row.name, row.who, row.updated_at,
             len(DraftGraph.model_validate(row.graph).nodes))
            for row in rows
        ]

    out: list[DraftRow] = []
    for draft_id, name, who, updated_at, steps in listed:
        row = DraftRow(id=draft_id, name=name, who=who, updated_at=updated_at, steps=steps,
                       kept=False)
        artifact = _output_root() / draft_id / "pipeline.yml"
        if artifact.is_file():
            kept = pipeline_file.load(artifact)
            provenance, named, unnamed = _provenance_of(kept)
            row = row.model_copy(update={
                "kept": True,
                "digest": kept.content_digest(),
                "provenance": provenance,
                "open_values": named,
                "open_not_named": unnamed,
                "makes": list(kept.goal.want),
            })
        out.append(row)
    return out, total


def artifact_path(draft_id: str) -> Path | None:
    """Where `keep` wrote this draft's `pipeline.yml`, or `None` if it never has.

    **Returned, never accepted** — the same direction `Kept.path` travels. A server saying where
    it put something is the opposite of a client naming a file, which is what invariant 15
    refuses.
    """
    path = _output_root() / draft_id / "pipeline.yml"
    return path if path.is_file() else None


def create(graph: DraftGraph, name: str, who: str) -> str:
    """`token_hex(16)` rather than a serial: `routes/build.py` records that the API may not
    accept a path, and a guessable id is the next-worst thing."""
    draft_id = secrets.token_hex(16)
    with session_scope() as session:
        session.add(
            PipelineDraft(
                id=draft_id,
                who=who,
                name=name,
                graph=graph.model_dump(mode="json"),
                updated_at=datetime.now(UTC),
            )
        )
    return draft_id


def _load(draft_id: str) -> DraftGraph:
    """The storage seam. Raises `KeyError` for an unknown draft; the route maps it to 404."""
    with session_scope() as session:
        row = session.get(PipelineDraft, draft_id)
        if row is None:
            raise KeyError(draft_id)
        return DraftGraph.model_validate(row.graph)


def _output_root() -> Path:
    """The destination seam. Server-chosen, never client-supplied — invariant 15."""
    return settings.draft_root


def read(draft_id: str) -> PipelineDraft:
    with session_scope() as session:
        row = session.get(PipelineDraft, draft_id)
        if row is None:
            raise KeyError(draft_id)
        return row


def update(draft_id: str, graph: DraftGraph) -> None:
    with session_scope() as session:
        row = session.get(PipelineDraft, draft_id)
        if row is None:
            raise KeyError(draft_id)
        row.graph = graph.model_dump(mode="json")
        row.updated_at = datetime.now(UTC)


def keep(draft_id: str, *, by: str = "") -> Path:
    """Validate, refuse anything illegal, write the artifact.

    **`validate` reports and this refuses.** That split is the spec's, and it is the whole of
    why `validate` answers 200 on a broken graph: a person mid-gesture wants three problems at
    once, and a person pressing *keep* wants one answer.

    An `unmet` port is **not** refused. A half-drawn graph is a legal thing to hold, and the
    emitted Nextflow will simply have an input nothing fills — which the gates catch, loudly,
    at the point where that actually costs something.
    """
    graph = _load(draft_id)
    verdict = validation.of(graph)
    if verdict.illegal:
        first = verdict.illegal[0]
        raise ValueError(
            coded(
                first.code,
                f"this graph cannot be kept: {first.message}. "
                f"{len(verdict.illegal)} illegal finding(s) in total.",
            )
        )

    stack = registry.stack()
    out = _output_root() / draft_id
    out.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline.of(
        ir_of(graph, stack, by=by),
        stack.registry,
        stack.vocabulary,
        stack.measurements,
        stack.paths,
        goal=goal_of(graph, stack),
    )
    # The compiler's writer, not a second one: `mendel build` writes through this and a
    # kept draft must produce the same file, or `mendel emit` is only true of pipelines
    # the resolver wrote.
    pipeline_file.write(out, pipeline)

    # **MD0210 found this.** `mendel build` copies the vendored modules beside the artifact and
    # `keep` did not, so every `include` in the emitted workflow pointed at nothing and
    # `mendel emit` refused the file this had just written. A kept draft that cannot be emitted
    # is not a pipeline, whatever the header says.
    #
    # `nf_include` is where a module lands in the GENERATED pipeline; the layer is where the
    # source lives. Deliberately not the same path, and since Plan 5A the layer carries both —
    # so `staging.stage` is one implementation shared with `mendel build` rather than a second
    # `copytree` that can go missing again.
    staging.stage(pipeline, stack.modules, out)
    return out / "pipeline.yml"
