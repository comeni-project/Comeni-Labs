"""Fixtures shared by the forge's tests.

Two complete scaffolds, deliberately different tools. `complete_scaffold` is FASTQC and is
checked against the **real vendored module** by the verification ladder, so its process name
and container have to be the ones on disk. `widget_scaffold` is the module-less case and
exists to be generated rather than matched — pointing both at FASTQC would make the
modulegen tests assert against a module that already exists, which is not the case they are
about.
"""

import pytest
from comeni_core.declared.layered import DeclaredKind
from comeni_core.review import ValueSource
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.scaffold import FilledValue, Scaffold


def _derived(value):
    return FilledValue(value=value, how=ValueSource.DERIVED, by="nf-core", why="main.nf")


def _hand(value, why):
    return FilledValue(value=value, how=ValueSource.HUMAN, by="rafael", why=why)


@pytest.fixture
def complete_scaffold() -> Scaffold:
    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/nf-core/fastqc/fastqc.contract.yml",
        observation=Observation(
            source="nf-core",
            ref_id="nf-core:fastqc",
            facts={"process": Fact(value="FASTQC", evidence=Excerpt(locator="m:1", text="t"))},
        ),
        filled={
            "id": _derived("nf-core/fastqc@0.12.1"),
            "nf_process": _derived("FASTQC"),
            "nf_include": _derived("modules/nf-core/fastqc/main"),
            "container": _derived("quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0"),
            "consumes[0].name": _derived("reads"),
            "consumes[0].type_id": _hand("fastq.reads", "FastQC reads FASTQs"),
            "produces[0].name": _derived("zip"),
            "produces[0].type_id": _hand("qc.report", "it is a report"),
            "roles": _hand(["qc_per_sample"], "it QCs a sample"),
            "priority_because": _hand("the only QC tool", "no alternative"),
            "provenance.source": _derived("nf-core"),
        },
        holes=[],
    )


@pytest.fixture
def widget_scaffold() -> Scaffold:
    """The module-less case: a container and a name, and no Nextflow anywhere."""
    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/opaque/widget/widget.contract.yml",
        observation=Observation(source="opaque", ref_id="opaque:widget"),
        filled={
            "id": _derived("opaque/widget@1.4.0"),
            "nf_process": _hand("WIDGET", "named for the tool, since no module declares one"),
            "nf_include": _hand("modules/opaque/widget/main", "where the generated module lands"),
            "container": _derived("docker.io/example/widget:1.4.0"),
            "consumes[0].name": _hand("input", "the skeleton's single input channel"),
            "consumes[0].type_id": _hand("fastq.reads", "whatever the widget counts"),
            "produces[0].name": _hand("out", "the skeleton's single emit"),
            "produces[0].type_id": _hand("counts.matrix", "it writes a table"),
            "roles": _hand(["quantification"], "it counts things"),
            "priority_because": _hand("the only widget", "no alternative"),
            "provenance.source": _derived("opaque"),
        },
        holes=[],
    )


@pytest.fixture
def incomplete_scaffold(complete_scaffold) -> Scaffold:
    """One hole put back, so the ladder stops on the first rung."""
    from mendel_forge.scaffold import Hole

    return complete_scaffold.model_copy(
        update={
            "holes": [
                Hole(
                    subject="roles",
                    what="the job this contract does",
                    why_open="a module declares no role",
                )
            ]
        }
    )


@pytest.fixture
def orphan_scaffold(complete_scaffold) -> Scaffold:
    """A contract producing a type nothing in the layer consumes.

    `counts.matrix` is produced by featureCounts and consumed by nothing — it is the end
    of the RNA-seq spine. That makes it the honest fixture for the inert case: a real
    terminal output, not an invented type.
    """
    return complete_scaffold.model_copy(
        update={
            "filled": {
                **complete_scaffold.filled,
                "produces[0].type_id": complete_scaffold.filled[
                    "produces[0].type_id"
                ].model_copy(update={"value": "counts.matrix"}),
            }
        }
    )


@pytest.fixture
def broken_registry(tmp_path):
    """A copy of the shipped registry with one contract made to disagree with its module.

    **A factory, not a directory**, because phase 5 needs several breakages: a value drift on
    `nf_process`, a structural one on a `produces[].name`, and two of them on one file. It was
    a module-private helper in `test_ops_maintain.py` until three files needed it.

    The copy is made once and mutated in place, so two calls break two fields of one registry.

    `.git` is excluded: the registry is a submodule, so the copy would otherwise carry a
    `gitdir:` pointer at a worktree that has nothing to do with `tmp_path` — the same defect
    issue #46 found in `digest_of_directory`.
    """
    import shutil
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]

    def _break(relative: str, was: str, now: str) -> Path:
        copy = tmp_path / "registry"
        if not copy.exists():
            shutil.copytree(root / "registry", copy, ignore=shutil.ignore_patterns(".git"))
        contract = copy / relative
        text = contract.read_text()
        assert was in text, f"{relative} does not contain {was!r} — the fixture is stale"
        contract.write_text(text.replace(was, now))
        return copy

    return _break
