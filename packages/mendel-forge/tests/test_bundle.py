"""One adaptation's directory, composed without a filesystem.

**Nothing here uses `tmp_path` except the two tests that are about writing**, and that is the
point of splitting composition from I/O: byte-identity, path validation and the host-path scan
are all claims about values, and a test that had to write a directory to check them would be
slower, harder to read, and would forgive differences a comparison of two tuples cannot.

The golden scaffolds are built from the same recorded upstream responses the adapter tests use,
so a change to either shows up as a reviewable diff rather than as a fixture nobody re-read.
"""

import json
from pathlib import Path

import pytest
from comeni_core.review import Candidate
from mendel_forge import bundle
from mendel_forge.bundle import Area, ScaffoldBundle, contains_a_host_path, joined
from mendel_forge.catalogue import (
    BundleFact,
    BundleFile,
    CatalogueItem,
    ContainerRef,
    NumberedExcerpt,
    SourceBundle,
    SourceCapabilities,
)
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole
from mendel_forge.observe import Excerpt
from mendel_forge.workspace import Workspace
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures" / "sources"

ADAPTATION = "a" * 32


def _hole(identifier: str = "roles", **overrides) -> ScaffoldHole:
    base = {
        "id": identifier,
        "pointer": "/roles",
        "kind": HoleKind.ROLE,
        "question": "what does this tool do",
        "why_open": "a role is a judgement",
        "legal_values": ("qc_per_sample",),
    }
    return ScaffoldHole(**{**base, **overrides})


def _item(**overrides) -> CatalogueItem:
    base = {
        "id": "d" * 64,
        "source": "nf-core",
        "ref": "fastqc",
        "display_name": "fastqc",
        "content_digest": "c" * 64,
        "capabilities": SourceCapabilities(supplies_nextflow=True),
    }
    return CatalogueItem(**{**base, **overrides})


def _source(*files: BundleFile, item: CatalogueItem | None = None, **overrides) -> SourceBundle:
    base = {
        "item": item or _item(),
        "source_digest": "s" * 64,
        "files": files,
    }
    return SourceBundle(**{**base, **overrides})


# ── the layout, and the paths inside it ────────────────────────────────────────────────


def test_every_area_is_a_directory_under_the_adaptation():
    """Six named areas, and the adaptation id is what separates two pieces of work.

    The plan asks for `workspace/forge/<adaptation-id>/` and for source, scaffold, candidate,
    prompt, response and validation to be split. A flat directory would let a model's candidate
    land beside the source it is supposed to be derived from, and the *immutable* half is only
    immutable if something can point at it.
    """
    for area in Area:
        assert joined(ADAPTATION, area, "x.json") == f"forge/{ADAPTATION}/{area.value}/x.json"
    assert len(set(Area)) == 6


@pytest.mark.parametrize(
    "part",
    ["../escape", "/etc/passwd", "", "  ", "a\\b", "nested/../../out"],
)
def test_a_path_that_escapes_the_bundle_is_refused(part):
    """**Every joined path goes through one function**, which is the plan's rule written as
    code rather than as a convention people follow.

    `a\\b` is in the list because a backslash is not a separator to `PurePosixPath` and would
    pass a check that only looked for `/` — then become one the moment the path reached a
    Windows filesystem or a naive string split.
    """
    with pytest.raises(ValueError, match="MF0008"):
        joined(ADAPTATION, Area.SOURCE, part)


@pytest.mark.parametrize("bad", ["../other", "a/b", "ADAPTATION", "", "abc"])
def test_an_adaptation_id_that_is_not_an_opaque_id_is_refused(bad):
    """The id becomes a directory name, so anything that could carry a separator is a traversal
    with extra steps. Prevention by construction, the same argument `MF0008` makes about a draft
    name — validating the joined path afterwards is detection, and the two are not the same
    guarantee."""
    with pytest.raises(ValueError, match="MF0008"):
        joined(bad, Area.SOURCE, "x.json")


# ── the host-path scan ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "locator: /home/rafael/Documents/repo/main.nf",
        'path = "/Users/someone/checkout/registry"',
        "read from /tmp/pytest-of-rafael/test0/main.nf",
    ],
)
def test_a_developer_machine_path_is_found(text):
    """The actual failure this exists for: `digest_of_directory` once made a layer digest depend
    on the checkout path while `make verify` stayed green, and the old nf-core adapter wrote
    absolute locators into every draft."""
    assert contains_a_host_path(text)


@pytest.mark.parametrize(
    "text",
    [
        "#!/usr/bin/env bash",
        "publishDir '/results', mode: 'copy'",
        "container 'quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0'",
        "no paths here at all",
    ],
)
def test_a_legitimate_absolute_string_is_not_a_finding(text):
    """**A pattern over named roots, not every leading slash.** Nextflow and container
    references are full of legitimate absolute-looking strings, and a scan that fired on all of
    them would be switched off within a week — which is a guard that exists and does nothing."""
    assert contains_a_host_path(text) == ()


def test_a_generated_file_carrying_a_host_path_cannot_be_constructed():
    """The plan asks for this as a test. It is a validator as well, so a bundle carrying one
    cannot exist rather than merely cannot be committed."""
    with pytest.raises(ValueError, match="absolute host path"):
        ScaffoldBundle(
            adaptation_id=ADAPTATION,
            item=_item(),
            source_digest="s" * 64,
            registry_digest="r" * 64,
            deterministic=((joined(ADAPTATION, Area.SCAFFOLD, "x.json"), "/home/rafael/x"),),
        )


def test_a_source_file_may_carry_an_absolute_path():
    """**Not an oversight.** Source files are upstream's bytes and we do not edit them: an
    nf-core module writes `/usr/bin/env`, a Dockerfile names paths inside its own image. What
    must not carry a host path is what *we* composed, because that is what differs between two
    machines."""
    built = ScaffoldBundle(
        adaptation_id=ADAPTATION,
        item=_item(),
        source_digest="s" * 64,
        registry_digest="r" * 64,
        source_files=((joined(ADAPTATION, Area.SOURCE, "Dockerfile"), "COPY x /home/user/x"),),
    )
    assert built.source_files


# ── determinism ────────────────────────────────────────────────────────────────────────


def _twice(**kwargs):
    source = _source(BundleFile(path="meta.yml", text="name: fastqc\n"))
    common = {
        "source": source,
        "registry_digest": "r" * 64,
        "holes": (_hole(),),
        "contract": {"id": "nf-core/fastqc@0.12.1", "settled": {"b": 2, "a": 1}},
        **kwargs,
    }
    return (
        bundle.scaffold(adaptation_id=ADAPTATION, **common),
        bundle.scaffold(adaptation_id=ADAPTATION, **common),
    )


def test_two_scaffolds_from_the_same_digests_are_byte_identical():
    """The plan's assertion, and it is `a.files() == b.files()` because composition is pure.

    A directory comparison would have to decide which differences to forgive — mtimes, ordering,
    a trailing newline — and every one of those decisions is a place a real difference hides.
    """
    first, second = _twice()
    assert first.files() == second.files()
    assert first.files(), "an empty bundle would make this pass while checking nothing"


def test_the_settled_contract_is_written_with_sorted_keys():
    """A mapping serialises in insertion order, which is parse order, which moves under a
    refactor nobody asked for. Determinism is a test here, not an aspiration."""
    built, _ = _twice()
    text = dict(built.files())[joined(ADAPTATION, Area.SCAFFOLD, "contract.yml.json")]
    assert text.index('"a"') < text.index('"b"')
    assert text.endswith("\n")


def test_files_are_sorted_by_path():
    """Two runs must list the same files in the same order, and the order must not depend on
    whether the deterministic half or the source half was appended first."""
    built, _ = _twice()
    paths = [path for path, _ in built.files()]
    assert paths == sorted(paths)


# ── what is generated, and what is copied ──────────────────────────────────────────────


def test_an_nf_core_source_is_copied_unchanged_and_gets_no_generated_module():
    """The plan says it twice, and it is the strongest property nf-core has: nf-core wrote the
    process, so nothing downstream may author one. A generated `main.nf` beside a real one is
    the forge overwriting upstream with a guess."""
    main_nf = "process FASTQC {\n    input:\n    tuple val(meta), path(reads)\n\n"
    main_nf += '    output:\n    tuple val(meta), path("*.html"), emit: html\n\n    script:\n'
    built = bundle.scaffold(
        adaptation_id=ADAPTATION,
        source=_source(BundleFile(path="main.nf", text=main_nf)),
        registry_digest="r" * 64,
        holes=(),
        contract={},
        module=bundle.module_for(_item(), process="FASTQC"),
    )
    files = dict(built.files())
    assert files[joined(ADAPTATION, Area.SOURCE, "main.nf")] == main_nf
    assert joined(ADAPTATION, Area.SCAFFOLD, "module", "main.nf") not in files


def test_a_source_with_no_nextflow_gets_a_module_with_open_sections():
    """The PEGiS case. A container and a README prove nothing about a process's shape, so the
    module is a skeleton whose input, output and script are marked — not a plausible one-input
    guess that `-stub-run` cannot tell from a checked one."""
    item = _item(
        source="pegi3s",
        ref="clustalw",
        capabilities=SourceCapabilities(supplies_nextflow=False, supplies_container_digest=True),
        container_refs=(
            ContainerRef(registry="docker.io", repository="pegi3s/clustalw", digest="sha256:abc"),
        ),
    )
    generated = bundle.module_for(item, process="CLUSTALW")
    assert generated is not None
    assert "MF0011" in generated
    assert "MF0005" in generated
    assert "docker.io/pegi3s/clustalw@sha256:abc" in generated


def test_a_container_digest_is_preferred_over_a_tag():
    """PEGiS beats nf-core on exactly one axis: it pins digests where nf-core pins tags. A
    generated module that reached for the tag would throw away the one guarantee the weaker
    source actually offers."""
    item = _item(
        capabilities=SourceCapabilities(supplies_nextflow=False),
        container_refs=(
            ContainerRef(
                registry="docker.io", repository="pegi3s/x", tag="1.2", digest="sha256:def"
            ),
        ),
    )
    assert "@sha256:def" in bundle.module_for(item, process="X")


def test_a_source_with_no_container_at_all_generates_nothing():
    """**A module with no container is not a module.** Emitting a skeleton with an empty
    `container ""` would produce a file that parses, passes a shape check, and cannot run —
    which is worse than the absence, because the absence is visible."""
    item = _item(capabilities=SourceCapabilities(supplies_nextflow=False))
    assert bundle.module_for(item, process="X") is None


def test_the_module_digest_is_the_one_a_vendored_module_would_get():
    """**`comeni_vendor.ops.digest_of_contents`, shared rather than reimplemented.** A
    scaffolded module and a vendored one have to be comparable, and two functions that agreed
    today would be two that stopped agreeing on the first change to either."""
    from comeni_vendor.ops import digest_of_contents

    built = bundle.scaffold(
        adaptation_id=ADAPTATION,
        source=_source(
            BundleFile(path="main.nf", text="process X {\n}\n"),
            BundleFile(path="meta.yml", text="name: x\n"),
        ),
        registry_digest="r" * 64,
        holes=(),
        contract={},
    )
    assert built.module_digest() == digest_of_contents(
        {"main.nf": b"process X {\n}\n", "meta.yml": b"name: x\n"}
    )


# ── deriving from a real module ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


@pytest.fixture
def fastqc_source() -> SourceBundle:
    """A bundle shaped like the nf-core adapter's, over the module that is actually vendored.

    Read from the registry rather than hand-written: a fixture module that no longer matches
    upstream is a fixture that tests a shape nothing produces, which is what
    `test_spine_contracts.py` exists to prevent one directory over.
    """
    module = ROOT / "registry" / "tools" / "nf-core" / "fastqc" / "module"
    return _source(
        BundleFile(path="main.nf", text=(module / "main.nf").read_text()),
        BundleFile(path="meta.yml", text=(module / "meta.yml").read_text()),
        facts=(
            BundleFact(name="nf_include", value="modules/nf-core/fastqc/main", evidence_id=None),
        ),
        evidence=(
            NumberedExcerpt(
                id="E001",
                excerpt=Excerpt(locator="meta.yml:description", text="Run FastQC on sequenced"),
            ),
        ),
    )


def test_the_module_is_read_by_the_same_parser_conformance_uses(fastqc_source):
    """`ModuleSpec.of` rather than a second reader. The adapters deliberately do not parse
    Nextflow — a sync reads sixteen hundred tools and has no business running a DSL parser over
    any of them — so the shape is derived here, once, for the tool being adapted."""
    observed = bundle.observation_of(fastqc_source, ident="nf-core/fastqc")
    assert observed.fact("process") == "FASTQC"
    assert observed.fact("emits")
    assert observed.fact("input_arity") == 1
    assert observed.fact("container") is not None


def test_a_fact_the_module_proves_does_not_become_a_hole(fastqc_source, stack):
    """**The fact names have to be `assemble`'s, and getting one wrong fails silently.**

    `DERIVED_FIELDS` maps the *fact* `process` onto the *field* `nf_process`. Naming the fact
    `nf_process` — after the field it fills — leaves the mapping looking for something nothing
    wrote, and `assemble` opens a hole for every fact it cannot find. So a module that plainly
    declares `process FASTQC {` produced a scaffold asking a human what the process was called,
    with every test green and one extra hole nobody counted.

    Found by printing a real derivation, not by a test. This is the standing version.
    """
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    settled = json.loads(
        dict(built.files())[joined(ADAPTATION, Area.SCAFFOLD, "contract.yml.json")]
    )["settled"]
    assert settled["nf_process"] == "FASTQC"
    assert "nf_process" not in [hole.id for hole in built.holes]
    assert settled["nf_include"] == "modules/nf-core/fastqc/main"
    assert settled["container"]


def test_a_hole_is_addressed_by_the_channel_and_not_by_its_index(fastqc_source, stack):
    """**The whole reason `hole_manifest` exists.** `consumes[0].type_id` renames every hole
    after a channel added upstream, so a stored answer, a review citing it, and a repair pass
    pointing at it all come to describe a different port.

    The pointer stays positional, because that is what addresses today's document.
    """
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    by_id = {hole.id: hole for hole in built.holes}
    assert "consumes.reads.type_id" in by_id, sorted(by_id)
    assert by_id["consumes.reads.type_id"].pointer == "/consumes/0/type_id"
    assert not any("[" in hole.id for hole in built.holes)


def test_the_holes_are_sorted_by_id(fastqc_source, stack):
    """`assemble` sorts by subject, which is a different order once the subjects are renamed.
    Keeping its order would make the manifest silently positional again."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    identifiers = [hole.id for hole in built.holes]
    assert identifiers == sorted(identifiers)


def test_a_port_name_hole_asks_with_its_own_instruction_fragment(fastqc_source, stack):
    """A name and a type are the same *sort* of question about the same port and are not the
    same question. `prompt_hint_id` is where that difference is written down once, rather than
    inside each draft — which is what `prompt_hint_id` is for."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    names = [hole for hole in built.holes if hole.id.endswith(".name")]
    assert names, "the port-name holes vanished"
    assert all(hole.hint == "ports.name.v1" for hole in names)


def test_a_derived_scaffold_names_no_host_path(fastqc_source, stack):
    """The plan's assertion, over a real module read from a real checkout — which is the case
    that would fail if a locator carried the path it was read from. The old nf-core adapter did
    exactly that until somebody noticed the golden files were machine-specific."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    for path, text in built.deterministic:
        assert contains_a_host_path(text) == (), f"{path} names a host path"


def test_deriving_twice_gives_the_same_bytes(fastqc_source, stack):
    """The claim, end to end: two derivations of one real module over one real registry."""
    common = {"adaptation_id": ADAPTATION, "registry_digest": "r" * 64}
    first = bundle.derive(fastqc_source, stack, **common)
    second = bundle.derive(fastqc_source, stack, **common)
    assert first.files() == second.files()
    assert len(first.files()) > 4


def test_the_manifest_lists_the_holes_the_contract_says_are_open(fastqc_source, stack):
    """Two documents that disagree about what is unanswered is how a page shows a green tick
    over an open hole. They are written from one list."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    contract = json.loads(
        dict(built.files())[joined(ADAPTATION, Area.SCAFFOLD, "contract.yml.json")]
    )
    assert contract["open"] == [hole.id for hole in built.holes]


# ── writing it ─────────────────────────────────────────────────────────────────────────


def test_writing_a_bundle_lays_out_the_areas(tmp_path, fastqc_source, stack):
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    root = Workspace(root=tmp_path).write_bundle(built)

    assert root == tmp_path / "forge" / ADAPTATION
    assert (root / "source" / "main.nf").exists()
    assert (root / "scaffold" / "holes.json").exists()
    manifest = json.loads((root / "bundle.json").read_text())
    assert manifest["source_digest"] == built.source_digest
    assert "source/main.nf" in " ".join(manifest["files"])


def test_the_manifest_does_not_repeat_every_file_it_lists(tmp_path, fastqc_source, stack):
    """Repeating the text inside a document that sits beside those files doubles the directory
    and gives a reader two copies that can disagree."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    root = Workspace(root=tmp_path).write_bundle(built)
    manifest = json.loads((root / "bundle.json").read_text())
    assert "deterministic" not in manifest
    assert "process FASTQC" not in (root / "bundle.json").read_text()


def test_writing_over_an_existing_adaptation_is_refused(tmp_path, fastqc_source, stack):
    """A source bundle is immutable by design. A second write is either a duplicate job — which
    `forge_state.claim` should already have refused — or a revision that has taken the wrong id,
    and both are better as a refusal than as a silently merged directory."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    workspace = Workspace(root=tmp_path)
    workspace.write_bundle(built)
    with pytest.raises(ValueError, match="MF0010"):
        workspace.write_bundle(built)


def test_a_bundle_built_by_model_validate_still_cannot_write_outside_the_workspace(tmp_path):
    """**The guarantee at the moment of writing is the check in `_inside`, not the one that
    happened in `joined`.** A `ScaffoldBundle` is a Pydantic model, and `model_validate` builds
    one from JSON that never went near the constructor — so a stored manifest with a doctored
    path is a real route in, and the writer has to refuse it itself.
    """
    smuggled = ScaffoldBundle.model_validate(
        {
            "adaptation_id": ADAPTATION,
            "item": _item().model_dump(mode="json"),
            "source_digest": "s" * 64,
            "registry_digest": "r" * 64,
            "source_files": [["../../escaped.txt", "x"]],
        }
    )
    with pytest.raises(ValueError, match="MF0008"):
        Workspace(root=tmp_path).write_bundle(smuggled)


def test_the_candidate_list_reaches_the_hole_as_legal_values(fastqc_source, stack):
    """A hole whose legal values were dropped is a hole a model may answer with anything, which
    is the one property the whole semi-deterministic claim rests on: *a model cannot produce a
    value outside the candidate set*."""
    built = bundle.derive(
        fastqc_source, stack, adaptation_id=ADAPTATION, registry_digest="r" * 64
    )
    typed = [hole for hole in built.holes if hole.kind is HoleKind.TYPE]
    assert typed
    assert all(hole.legal_values for hole in typed)


def test_an_exhaustive_hole_with_no_legal_value_is_refused():
    """*We listed everything* and *we listed nothing* are not the same claim, and an exhaustive
    list of nothing says no answer is legal — which is never what is meant. It is what an empty
    candidate set looks like when nobody set the flag."""
    with pytest.raises(ValueError, match="exhaustive"):
        _hole(legal_values=())


def test_a_suggestion_outside_the_legal_values_is_refused():
    """The suggestion is what a page offers first. One that is not offerable at all is a button
    the server would refuse — which is the disagreement `forge_state.onward` exists to prevent
    one layer up."""
    with pytest.raises(ValueError, match="not among its legal values"):
        _hole(legal_values=("a",), suggested="b")


def test_a_candidate_is_read_for_its_value_and_not_its_note():
    """`Candidate.note` says where a value is declared, for a reviewer. Letting it into
    `legal_values` would make the legal set contain sentences."""
    assert Candidate(value="qc_per_sample", note="declared in roles.yml").value == "qc_per_sample"
