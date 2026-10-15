"""What the review page reads, against a real workspace on disk.

**Every claim here is about a join.** The scaffold addresses a field positionally
(`consumes[0].type_id`) and a hole addresses it semantically (`consumes.reads.type_id`); the
graph, the inspector and the diff all need those to be one thing, and nothing else in the
system has to make that join. A test that constructed the response directly would assert the
shape of an object rather than that the two addressings meet.
"""

import pytest
from comeni_core.review import Excerpt, ValueSource
from mendel_api.services import forge_candidate
from mendel_forge.bundle import ScaffoldBundle
from mendel_forge.catalogue import (
    BundleFile,
    CatalogueItem,
    NumberedExcerpt,
    SourceBundle,
)
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole
from mendel_forge.observe import Observation
from mendel_forge.scaffold import Hole, Scaffold
from mendel_forge.workspace import Draft, Workspace

ONE = "a" * 32
TWO = "b" * 32
"""Adaptation ids are **32 hex characters and nothing else** — `bundle.joined` refuses anything
else, because the id becomes a directory name. A readable `ad1` here would fail in the fixture
rather than in the code under test."""


def _item() -> CatalogueItem:
    return CatalogueItem(
        id="a" * 64,
        source="nf-core",
        ref="samtools/sort",
        display_name="samtools/sort",
        content_digest="d" * 64,
    )


def _source(*, module: str | None = "process SAMTOOLS_SORT {\n}\n") -> SourceBundle:
    return SourceBundle(
        item=_item(),
        source_digest="7be1" + "0" * 60,
        files=((BundleFile(path="main.nf", text=module),) if module is not None else ()),
        evidence=(
            NumberedExcerpt(
                id="E004",
                excerpt=Excerpt(locator="meta.yml:12", text="input BAM file"),
                kind="metadata",
            ),
        ),
    )


def _hole(field: str, index: int, channel: str, *, required: bool = True) -> ScaffoldHole:
    return ScaffoldHole(
        id=f"consumes.{channel}.{field}",
        pointer=f"/consumes/{index}/{field}",
        kind=HoleKind.TYPE,
        question="what does this input carry?",
        why_open="the source names a file pattern, not a semantic type",
        required=required,
        legal_values=("alignment.bam", "fastq.reads"),
        exhaustive=True,
        suggested="alignment.bam",
        evidence_ids=("E004",),
    )


def _scaffold(**filled) -> Scaffold:
    """`consumes__0_X_type_id` spells `consumes[0].type_id`, because a keyword argument cannot
    carry brackets. The mangling is ugly and local; the alternative is a dict literal at every
    call site."""
    fields = [name.replace("__", "[").replace("_X_", "].") for name in filled]
    scaffold = Scaffold(
        kind="contracts",
        target="samtools/sort",
        observation=Observation(source="nf-core", ref_id="samtools/sort"),
        # **`fill` only settles a hole that exists**, which is `MF0002` and the guarantee that
        # nothing writes a field the scaffold never opened. So the fixture opens them first,
        # `closed=False` so any value is legal — the candidate-set refusal is `MF0003`'s job
        # and is tested where it lives.
        holes=[Hole(subject=field, closed=False) for field in fields],
    )
    for field, (value, how) in filled.items():
        scaffold = scaffold.fill(
            field.replace("__", "[").replace("_X_", "]."),
            value,
            how,
            by="nf-core" if how is ValueSource.DERIVED else "a-model",
            why="read from meta.yml" if how is ValueSource.DERIVED else "proposed",
        )
    return scaffold


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A workspace rooted in `tmp_path`, and `settings` pointed at it.

    The service reads `settings.workspace_root` at call time rather than taking a root, because
    every other forge service does — a browser may not choose a path, and a parameter here would
    be the one place that rule is not enforced by construction.
    """
    monkeypatch.setattr(
        "mendel_api.services.forge_candidate.settings",
        type("S", (), {"workspace_root": tmp_path})(),
    )
    return Workspace(root=tmp_path)


def _write(
    workspace: Workspace,
    adaptation_id: str,
    *,
    scaffold: Scaffold,
    module: str | None = None,
    holes: tuple[ScaffoldHole, ...] = (),
    source: SourceBundle | None = None,
) -> None:
    """Lay out one adaptation the way the jobs do.

    **Through `write_bundle` rather than by writing files**, because the layout is the thing
    under test on the read side: a fixture that placed `bundle.json` by hand would keep passing
    on the day the writer moved it.

    **And through one call, because two was the defect.** This said the same sentence while
    calling `workspace.save(Draft(...))` first — which writes `<root>/<name>/draft.json`, the
    layout the `forge draft` CLI uses and the scaffold job does not. So the fixture supplied
    the file the job never wrote, every test here passed, and `candidate()` answered 404 for
    every real adaptation. Found by scaffolding `seqkit/fq2fa` from the real catalogue and
    opening it; a fixture that sets up more than its subject does is a fixture that hides what
    the subject forgot.
    """
    source = source or _source()
    workspace.write_bundle(
        ScaffoldBundle(
            adaptation_id=adaptation_id,
            item=source.item,
            source_digest=source.source_digest,
            registry_digest="41a9" + "0" * 60,
            holes=holes,
            source_files=tuple(
                (f"forge/{adaptation_id}/source/{file.path}", file.text) for file in source.files
            ),
        ),
        source=source,
        draft=Draft(name=adaptation_id, scaffold=scaffold, module=module),
    )


def test_a_missing_workspace_is_a_key_error(workspace):
    """**404, not an empty candidate.** An adaptation in `scaffolding` has none, and answering
    with an empty one would tell the page the scaffold produced nothing rather than that it has
    not run."""
    with pytest.raises(KeyError):
        forge_candidate.candidate("never-scaffolded")


def test_a_hole_and_its_field_address_one_thing(workspace):
    """**The join this module exists to make.** `Scaffold.filled` is keyed `consumes[0].type_id`
    and `ScaffoldHole.id` is `consumes.reads.type_id`; the pointer is the only bridge, and every
    part of the review page depends on it holding."""
    scaffold = _scaffold(consumes__0_X_type_id=("alignment.bam", ValueSource.MODEL))
    _write(workspace, ONE, scaffold=scaffold, holes=(_hole("type_id", 0, "reads"),))

    found = forge_candidate.candidate(ONE)
    field = next(f for f in found.fields if f.field == "consumes[0].type_id")
    assert field.hole_id == "consumes.reads.type_id"
    assert field.evidence_ids == ("E004",)


def test_an_answered_hole_stops_being_open(workspace):
    """A hole whose field is filled is not a question any more. Reporting it would put a red
    mark on a port the reviewer is looking at the answer to."""
    scaffold = _scaffold(consumes__0_X_type_id=("alignment.bam", ValueSource.MODEL))
    _write(workspace, ONE, scaffold=scaffold, holes=(_hole("type_id", 0, "reads"),))

    assert forge_candidate.candidate(ONE).holes == ()


def test_an_unanswered_hole_is_carried_in_full(workspace):
    """§8.4 asks each hole to link to its evidence and its prompt hint, so a page given only an
    id would have to invent the sentence."""
    _write(workspace, ONE, scaffold=_scaffold(), holes=(_hole("type_id", 0, "reads"),))

    hole = forge_candidate.candidate(ONE).holes[0]
    assert hole.question == "what does this input carry?"
    assert hole.legal_values == ("alignment.bam", "fastq.reads")
    assert hole.exhaustive is True
    assert hole.evidence_ids == ("E004",)


def test_a_port_says_whether_it_was_read_or_proposed(workspace):
    """**The single failure a review exists to catch.** A model's proposal drawn like a source
    fact is a guess a reviewer approves without noticing, and the graph's three marks are the
    whole mechanism."""
    scaffold = _scaffold(
        consumes__0_X_type_id=("alignment.bam", ValueSource.DERIVED),
        produces__0_X_type_id=("alignment.bam", ValueSource.MODEL),
    )
    _write(workspace, ONE, scaffold=scaffold, holes=())

    graph = forge_candidate.candidate(ONE).graph
    assert [port.origin for port in graph.consumes] == ["derived"]
    assert [port.origin for port in graph.produces] == ["model"]


def test_a_port_with_nothing_settled_is_open_rather_than_absent(workspace):
    """A port that exists only as three open questions still has to be drawn, or the graph
    reports a tool with fewer inputs than it has."""
    _write(workspace, ONE, scaffold=_scaffold(), holes=(_hole("type_id", 0, "reads"),))

    graph = forge_candidate.candidate(ONE).graph
    assert [(port.channel, port.origin) for port in graph.consumes] == [("reads", "open")]


def test_a_value_keeps_its_json_spelling(workspace):
    """`['coordinate_sorted']` and `coordinate_sorted` render identically under `str`, on a
    screen whose job is to show exactly what will be written."""
    scaffold = _scaffold(consumes__0_X_state=(["coordinate_sorted"], ValueSource.MODEL))
    _write(workspace, ONE, scaffold=scaffold, holes=())

    field = forge_candidate.candidate(ONE).fields[0]
    assert field.value == '["coordinate_sorted"]'


def test_a_copied_module_is_not_reported_as_authored(workspace):
    """**A rule being checked, not a label.** A source that ships Nextflow gets a contract bound
    to its process and nothing downstream may author one, so an authored `main.nf` beside a
    source that shipped one is that rule broken — and the pane is the only place it shows."""
    _write(workspace, ONE, scaffold=_scaffold(), module=None, holes=())
    copied = forge_candidate.candidate(ONE).files[0]
    assert (copied.path, copied.authored) == ("main.nf", False)

    _write(
        workspace,
        TWO,
        scaffold=_scaffold(),
        module="process X {}\n",
        holes=(),
        source=_source(module=None),
    )
    written = forge_candidate.candidate(TWO).files[0]
    assert written.authored is True


def test_the_origins_count_open_holes_beside_settled_values(workspace):
    """A summary of only what was decided makes a candidate with nine open holes look as
    finished as one with none."""
    scaffold = _scaffold(
        consumes__0_X_type_id=("alignment.bam", ValueSource.DERIVED),
        produces__0_X_type_id=("alignment.bam", ValueSource.MODEL),
    )
    _write(workspace, ONE, scaffold=scaffold, holes=(_hole("state", 1, "index"),))

    origins = forge_candidate.candidate(ONE).origins
    assert (origins.derived, origins.model, origins.human, origins.open) == (1, 1, 0, 1)


def test_no_path_leaves_the_service(workspace):
    """`ForgeRevision.manifest` holds workspace-relative paths so a host path never reaches a
    row; the same claim has to hold on the way out. An absolute path in a response is a path in
    a screenshot, in a bug report, and eventually in a prompt."""
    _write(workspace, ONE, scaffold=_scaffold(), holes=(_hole("type_id", 0, "reads"),))

    body = forge_candidate.candidate(ONE).model_dump_json()
    assert str(workspace.root) not in body
    assert "/tmp" not in body


def test_the_scaffold_job_writes_everything_the_review_page_reads():
    """**The seam that shipped broken twice, held from the writer's side.**

    `_derive_and_write` is monkeypatched in every test that touches it, so no test had ever
    watched it lay out a directory. Two things were missing and both failed one layer away from
    the omission: `source=` was never passed, so `read_source` refused and a generation could
    not build a dossier without going back to the network; and nothing wrote the derived
    `Scaffold` at all, so `candidate()` answered 404 for every real adaptation.

    Asserted by reading the job's own call rather than by running it — running it needs a
    network fetch, a registry and a database, which is why it was monkeypatched in the first
    place. What can be checked cheaply is that the call names every argument the readers need,
    and that is exactly what was missing.
    """
    import ast
    import inspect

    from mendel_api.services import forge_jobs

    tree = ast.parse(inspect.getsource(forge_jobs._derive_and_write))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_bundle"
    ]
    assert len(calls) == 1, "the scaffold job no longer writes exactly one bundle"
    passed = {keyword.arg for keyword in calls[0].keywords}
    assert {"source", "draft"} <= passed, (
        f"write_bundle called with {sorted(passed)}; `read_source` and `read_draft` each refuse "
        "when their half was not written, and both refusals surface far from this line"
    )
