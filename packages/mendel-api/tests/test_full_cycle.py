"""The whole loop, once, against real storage: catalogue → scaffold → answer → approve → land.

**This is the walk Task 13 asks for, in the half a suite can run.** The plan's own boxes split
it: *a full nf-core adaptation with a fake/recorded model* is this file, and *a PEGiS adaptation
with local Ollama by hand* is a person driving a browser — a test cannot press Approve and mean
it, and a 9GB model is not something CI pulls.

**No step is faked except the two that reach outside the process.** The source adapter is a
fake, because the real one walks GitHub; the model is a fake, because a live one is what
`tests/guards/test_no_live_model.py` forbids. Everything between — the workflow's transitions,
the scaffold on disk, the compare-and-swap, the staged bundle, the git commit, the layer that
loads afterwards — is the real thing.

**The point is the seams, not the steps.** Each stage is exercised elsewhere; what only this
file can catch is a state one job leaves that the next refuses, a path one container writes and
another cannot find, or a contract that lands and then will not load.
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from comeni_core.review import ValueSource
from mendel_api.db import session_scope
from mendel_api.models import (
    ForgeAdaptation,
    ForgeCatalogueItem,
    ForgeRevision,
    ForgeSourceSnapshot,
)
from mendel_api.services import forge_adaptations, forge_candidate, forge_jobs, forge_state
from mendel_forge.workflow import AdaptationState, EventKind, RevisionState
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


# ── the world this walk happens in ────────────────────────────────────────────────────


def _registry(root: Path) -> Path:
    """A real git checkout with the minimum a layer needs, on a branch that is not `main`'s.

    A directory of files would be refused by `MF0107` — accepting a publication is a commit —
    and that refusal is one of the things this walk is meant to pass rather than skip.
    """
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    (root / "registry.yml").write_text("name: walk\n")
    (root / "types").mkdir()
    (root / "types" / "alignment.bam.yml").write_text(
        "declares: vocabulary\nid: alignment.bam\nstates: [unsorted, coordinate_sorted]\n"
    )
    # **A role, because roles are closed (invariant 7).** A contract naming one no layer
    # declares refuses with `MD0302`, which is the loader doing its job — and it caught this
    # fixture the first time it ran, which is the sort of thing a walk is for.
    (root / "roles").mkdir()
    (root / "roles" / "bam_sorting.yml").write_text("declares: role\nroles:\n  - bam_sorting\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch, clean_forge):
    """A workspace and a registry checkout, with `settings` pointing at both.

    **The same two paths for every consumer**, which is what `test_compose.py` asserts of the
    containers and what this asserts of the process: the scaffold job writes the workspace and
    the publish job reads it, and a test that gave them different roots would be testing two
    halves that never meet.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = _registry(tmp_path / "registry")
    monkeypatch.setattr(forge_jobs.settings, "workspace_root", workspace, raising=False)
    monkeypatch.setattr(forge_jobs.settings, "registry_root", registry, raising=False)
    monkeypatch.setattr(forge_candidate.settings, "workspace_root", workspace, raising=False)
    return workspace, registry


@pytest.fixture
def catalogued(world):
    """One tool in the catalogue, as a sync would leave it."""
    from mendel_forge.catalogue import CatalogueItem

    now = datetime.now(UTC)
    item = CatalogueItem(
        id="w" * 64,
        source="nf-core",
        ref="samtools/sort",
        display_name="samtools sort",
        summary="Sorts a BAM file.",
        content_digest="c" * 64,
    )
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id="w" * 32, source="nf-core", started_at=now, finished_at=now, ok=True
            )
        )
        session.flush()
        session.add(
            ForgeCatalogueItem(
                id=item.id,
                snapshot_id="w" * 32,
                source=item.source,
                ref=item.ref,
                display_name=item.display_name,
                summary=item.summary,
                metadata_json=item.model_dump(mode="json"),
                content_digest=item.content_digest,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    return item


# ── the walk ──────────────────────────────────────────────────────────────────────────


def _answer_every_hole(scaffold, by: str):
    """Fill each open hole from its own candidate set — a fake model that cannot invent.

    **This is what the real model path is bounded to**, and it is why a fake is honest here
    rather than a shortcut: `Scaffold.fill` refuses a value outside the candidates (`MF0003`),
    so a model and this fake are constrained by exactly the same thing. What is not exercised
    is whether a model *chooses well*, which is `evaluate.py`'s question and not a walk's.
    """
    while True:
        open_now = [hole for hole in scaffold.holes if hole.subject not in scaffold.filled]
        if not open_now:
            return scaffold
        hole = open_now[0]
        candidates = [candidate.value for candidate in hole.candidates]
        value = hole.suggested or (candidates[0] if candidates else f"{hole.subject}-answer")
        scaffold = scaffold.fill(
            hole.subject, value, ValueSource.MODEL, by=by, why="answered by the walk's stand-in"
        )


def test_the_loop_closes(world, catalogued):
    """**Catalogue → adaptation → candidate → approval → registry, and then the layer loads.**

    Each assertion is a seam rather than a step. What this can catch and no unit test can: an
    adaptation the workflow will not let out of a state, a scaffold written where the next job
    does not look, a bundle that stages and will not commit, and — the last one, which is the
    whole point — a contract that lands and then will not load back.
    """
    workspace, registry = world
    from mendel_forge.scaffold import Hole, Scaffold
    from mendel_forge.workspace import Draft, Workspace

    # 1. Somebody presses Adapt.
    row = forge_adaptations.begin(catalogued.id, who="rafael")
    assert row.state is AdaptationState.SCAFFOLDING

    # 2. The deterministic half derives a scaffold with holes. Composed here rather than run
    #    through `_derive_and_write`, which fetches the source over the network — the fetch is
    #    `test_source_nfcore_catalogue.py`'s subject, and this walk is about what happens to
    #    what it produces.
    scaffold = Scaffold(
        kind="contracts",
        target="tools/nf-core/samtools/sort.contract.yml",
        observation=_observation(),
        # **Candidates, because that is the whole claim.** A hole carries the legal answers and
        # `fill` refuses anything outside them, so the stand-in below is bounded by exactly what
        # a model would be. A hole with no candidates would let the walk invent a value, which
        # is the one thing this architecture says cannot happen.
        holes=[
            Hole(subject="consumes[0].type_id", candidates=_bam(), suggested="alignment.bam"),
            Hole(subject="produces[0].type_id", candidates=_bam(), suggested="alignment.bam"),
        ],
    )
    for field, value in _derived().items():
        scaffold = scaffold.model_copy(
            update={"holes": [*scaffold.holes, Hole(subject=field, closed=False)]}
        ).fill(field, value, ValueSource.DERIVED, by="nf-core", why="read from meta.yml")

    Workspace(root=workspace).save(Draft(name=row.id, scaffold=scaffold, module=None))
    # **The bundle too, because the review page reads it and the draft is not it.** The draft
    # is the contract being filled; the bundle is what upstream said — the evidence a citation
    # points at and the holes a curator answers. Saving only the draft is the shape of defect
    # this walk exists to find: every unit test passes and the review page 404s.
    _write_bundle(Workspace(root=workspace), row.id, catalogued)

    forge_state.move(
        row.id,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=row.row_version,
        actor="worker:walk",
        kind=EventKind.SCAFFOLDED,
    )

    # 3. The AI lane answers what is left, bounded to the candidate sets.
    forge_state.claim(row.id, row_version=2, worker="worker:walk")
    answered = _answer_every_hole(scaffold, by="a-model")
    Workspace(root=workspace).save(Draft(name=row.id, scaffold=answered, module=None))

    revision = forge_state.add_revision(row.id, state=RevisionState.VALIDATED, manifest={})
    forge_state.move(
        row.id,
        AdaptationState.VALIDATING,
        expect=AdaptationState.GENERATING,
        row_version=3,
        actor="worker:walk",
        kind=EventKind.GENERATED,
        revision_id=revision,
    )
    forge_state.move(
        row.id,
        AdaptationState.REVIEW,
        expect=AdaptationState.VALIDATING,
        row_version=4,
        actor="worker:walk",
        kind=EventKind.VALIDATED,
    )

    # 4. A reviewer reads the candidate. **Through the endpoint's own service**, because a walk
    #    that inspected the workspace directly would skip the projection the page depends on.
    candidate = forge_candidate.candidate(row.id)
    assert candidate.holes == (), "every hole was answered, so none should still be open"
    assert candidate.origins.model >= 2, "the model's answers must be attributable"
    assert candidate.origins.derived >= 1

    # 5. Approval, and then the publication.
    forge_state.move(
        row.id,
        AdaptationState.PUBLISHING,
        expect=AdaptationState.REVIEW,
        row_version=5,
        actor="rafael",
        kind=EventKind.APPROVED,
        detail="checked against meta.yml by hand",
    )
    landed = forge_jobs._land(row.id, {"job_id": "walk"})
    assert "forge/" in landed

    # 6. **The approver is the person, not the worker.** `Provenance.approved_by` outlives the
    #    deployment, and it read `worker:<job id>` until this task.
    contract = (registry / scaffold.target).read_text()
    assert "approved_by: rafael" in contract, contract
    assert "worker:" not in contract

    # 7. The registry carries a commit attributed to them, on a branch that is not the default.
    assert _git(registry, "branch", "--show-current").startswith("forge/")
    assert _git(registry, "log", "-1", "--format=%an") == "rafael"
    assert _git(registry, "status", "--porcelain") == "", "the walk left the tree clean"

    # 8. **The last seam, and the one everything else is for.** A contract that lands and will
    #    not load back is a publication that succeeded and produced nothing usable.
    from mendel_resolver import layers

    stack = layers.load(registry)
    assert any(
        found.id == str(answered.filled["id"].value) for found in stack.registry.all()
    ), [found.id for found in stack.registry.all()]


def _bam() -> list:
    """The one type this fixture registry declares. `types/alignment.bam.yml` is written by
    `_registry`, so the answer the walk gives is an answer the layer can actually load."""
    from comeni_core.review import Candidate

    return [Candidate(value="alignment.bam", note="the only type this layer declares")]


def _write_bundle(workspace, adaptation_id: str, item) -> None:
    """The immutable half of an adaptation, laid out the way the scaffold job lays it out."""
    from comeni_core.review import Excerpt
    from mendel_forge.bundle import ScaffoldBundle
    from mendel_forge.catalogue import NumberedExcerpt, SourceBundle

    source = SourceBundle(
        item=item,
        source_digest="c" * 64,
        evidence=(
            NumberedExcerpt(
                id="E001",
                excerpt=Excerpt(locator="meta.yml:14", text="Sorted BAM file"),
                kind="metadata",
            ),
        ),
    )
    workspace.write_bundle(
        ScaffoldBundle(
            adaptation_id=adaptation_id,
            item=item,
            source_digest=source.source_digest,
            registry_digest="r" * 64,
        ),
        source=source,
    )


def _observation():
    from mendel_forge.observe import Observation

    return Observation(source="nf-core", ref_id="samtools/sort")


def _derived() -> dict:
    """What the deterministic half reads off `meta.yml` and `main.nf`, with nothing invented."""
    return {
        "id": "nf-core/samtools/sort@1.21.0",
        "nf_process": "SAMTOOLS_SORT",
        "nf_include": "modules/nf-core/samtools/sort/main",
        "container": "quay.io/biocontainers/samtools:1.21--h50ea8bc_0",
        "consumes[0].name": "bam",
        "produces[0].name": "bam",
        "roles": ["bam_sorting"],
        "priority_because": "the only sorter this layer carries",
        "provenance.source": "nf-core",
    }


def test_a_second_publication_of_the_same_adaptation_does_not_commit_twice(world, catalogued):
    """**One approval, one commit.** ARQ delivers at least once and a redeploy re-delivers, so
    the second arrival has to find the row already `published` and stop — the job id makes the
    duplicate a no-op at the queue and the state check is what holds when the id has aged out."""
    _, registry = world
    row = forge_adaptations.begin(catalogued.id, who="rafael")
    with session_scope() as session:
        session.get(ForgeAdaptation, row.id).state = AdaptationState.PUBLISHED.value

    before = _git(registry, "rev-parse", "HEAD")
    import asyncio

    ended = asyncio.run(
        forge_jobs.publish_forge_adaptation({"job_id": "walk"}, row.id, "no-revision")
    )
    assert ended == AdaptationState.PUBLISHED.value
    assert _git(registry, "rev-parse", "HEAD") == before, "a second delivery committed again"


def test_a_candidate_can_become_approvable_through_the_front_door(world, catalogued):
    """**Nothing had ever been approvable through the API**, and this is the test that says so.

    `_record_verdict` hardcoded `green = False` beside `MI0108` — *the validation ladder is not
    wired to this worker yet* — and `approval_refusals` reads exactly that field. So every
    approval, on every candidate, refused on *validation did not pass*, and every walk that got
    past it did so by moving the row by hand. `verify.verify` was fully built the whole time;
    the worker simply did not call it.

    What this asserts is the join: the rungs run, the verdict is recorded, and
    `forge_state.standing` — the same six conditions the POST refuses on — stops naming
    validation.
    """
    from mendel_forge import verify

    workspace, registry = world
    from mendel_forge.scaffold import Hole, Scaffold
    from mendel_forge.workspace import Draft, Workspace

    row = forge_adaptations.begin(catalogued.id, who="rafael")
    scaffold = Scaffold(
        kind="contracts",
        target="tools/nf-core/samtools/sort.contract.yml",
        observation=_observation(),
        holes=[
            Hole(subject="consumes[0].type_id", candidates=_bam(), suggested="alignment.bam"),
            Hole(subject="produces[0].type_id", candidates=_bam(), suggested="alignment.bam"),
        ],
    )
    for field, value in _derived().items():
        scaffold = scaffold.model_copy(
            update={"holes": [*scaffold.holes, Hole(subject=field, closed=False)]}
        ).fill(field, value, ValueSource.DERIVED, by="nf-core", why="read from meta.yml")
    answered = _answer_every_hole(scaffold, by="a-model")
    Workspace(root=workspace).save(Draft(name=row.id, scaffold=answered, module=None))

    verdicts = verify.verify(answered, registry_root=registry, source_root=registry, module=None)
    assert verdicts, "the ladder produced no verdicts at all"

    revision = forge_state.add_revision(row.id, state=RevisionState.VALIDATED, manifest={})
    forge_jobs._record_verdict(
        revision, outcome=_NothingRefused(), owed=0, verdicts=verdicts
    )

    with session_scope() as session:
        stored = session.get(ForgeRevision, revision)
        assert stored.validation["ran"] is True, stored.validation
        assert stored.validation["rungs"], "a run that records no rungs is a run nobody can read"
        # **The rungs may legitimately refuse** — this fixture's contract has no module, so
        # `conforms` has nothing to check against. What must be true is that the *reason* is a
        # rung's, not `MI0108`'s, and that `green` follows the rungs rather than a constant.
        assert stored.green == (not verify.refuses(verdicts))
        assert "MI0108" not in str(stored.validation)


class _NothingRefused:
    """An `Outcome` reduced to what `_record_verdict` reads when the rungs did run."""

    def last_diagnostics(self):
        return ()

