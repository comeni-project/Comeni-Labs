"""Drafts: a graph somebody is still drawing, and the moment one stops being one.

**A draft is server state; a pipeline is an artifact.** `keep` is the boundary — it validates,
refuses anything illegal, and writes the `pipeline.yml`. Everything before that is a row.

**`_load` and `_output_root` are seams, not indirection.** These tests need Postgres and CI has
none, so the rule most worth defending in CI — that `keep` refuses an illegal graph — is tested
with the storage monkeypatched. A `keep` that reached straight into a session would be a rule
only a developer machine could check.
"""

import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_compiler import pipeline_file
from mendel_resolver.materialise import goal_of, ir_of

from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import registry
from mendel_api.services import validate as validation
from mendel_api.settings import settings


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
    # `nf_include` is where a module lands in the GENERATED pipeline; `source_root` is where
    # this installation keeps the source. Deliberately not the same path.
    vendored = settings.source_root / "modules"
    if vendored.exists():
        shutil.copytree(vendored, out / "modules", dirs_exist_ok=True)
    return out / "pipeline.yml"
