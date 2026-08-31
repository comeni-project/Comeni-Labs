"""`add` and `check`, offline.

Nothing here reaches the network: `add`'s fetch is exercised against a **local git repository**
this file builds, which is the same code path a GitHub URL takes — `git clone` does not care
that the remote is a directory. That keeps the tests in the fast lane, and it exercises the pin
honestly rather than against a recorded fixture, because a fixture cannot have the wrong commit.
"""

import subprocess
from pathlib import Path

import pytest
from comeni_core.declared.layered import layers_of, stack
from comeni_core.declared.module import Module
from comeni_vendor.ops import VendorError, add, check, digest_of_module

MAIN_NF = """\
process FASTQC {
    label 'process_medium'
    script:
    \"\"\"
    fastqc $reads
    \"\"\"
}
"""


def _upstream(root: Path) -> str:
    """A git repository shaped like nf-core/modules, with two commits."""
    root.mkdir(parents=True)
    module = root / "modules" / "nf-core" / "fastqc"
    (module / "tests").mkdir(parents=True)
    (module / ".conda-lock").mkdir()
    (module / "main.nf").write_text(MAIN_NF)
    (module / "meta.yml").write_text("name: fastqc\n")
    (module / ".conda-lock" / "linux_amd64.txt").write_text("fastqc=0.12.1\n")
    # nf-core ships this beside every module and we do not take it — the whole reason
    # `excluded:` is a recorded field rather than a constant in the fetcher.
    (module / "tests" / "main.nf.test").write_text("nextflow_process {}\n")

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    git("init", "--quiet")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("add", "-A")
    git("commit", "--quiet", "-m", "one")
    return git("rev-parse", "HEAD")


def _layer(root: Path, *, licences: tuple[str, ...] = ("MIT",)) -> Path:
    root.mkdir(parents=True)
    (root / "registry.yml").write_text("name: scratch\n")
    for one in licences:
        (root / "LICENSES").mkdir(exist_ok=True)
        (root / "LICENSES" / f"{one}.txt").write_text(f"the {one} licence text\n")
    return root


@pytest.fixture
def vendored(tmp_path):
    """One module vendored out of a local repository, at a real commit."""
    sha = _upstream(tmp_path / "upstream")
    layer = _layer(tmp_path / "layer")
    add(
        "nf-core:fastqc",
        sha=sha,
        registry=layer,
        licence="MIT",
        repo=str(tmp_path / "upstream"),
    )
    return layer


def test_add_writes_the_module_and_the_declaration_beside_it(vendored):
    tool = vendored / "tools" / "nf-core" / "fastqc"
    assert (tool / "module" / "main.nf").read_text() == MAIN_NF
    assert (tool / "module.yml").exists()
    assert not (tool / "module" / "module.yml").exists(), (
        "the declaration went inside module/, where the next `add` will delete it"
    )


def test_what_was_not_copied_is_recorded_rather_than_assumed(vendored):
    """Without `excluded:` a drift check reports every module as differing forever.

    nf-core ships a `tests/` directory beside each module and we do not take it, so the
    honest comparison is *upstream minus what we said we would skip* rather than *upstream*.
    """
    tool = vendored / "tools" / "nf-core" / "fastqc"
    assert not (tool / "module" / "tests").exists()
    declared = stack(layers_of([vendored]), Module.kind()).entries["nf-core/fastqc"]
    assert declared.excluded == ["tests"]


def test_the_declaration_loads_as_declared_data(vendored):
    """It has to stack like every other kind (invariant 11), not be read by a hand-written
    walk — which is what audit root B was."""
    stacked = stack(layers_of([vendored]), Module.kind())
    declared = stacked.entries["nf-core/fastqc"]
    assert declared.licence == "MIT"
    assert declared.upstream is not None
    assert declared.excluded == ["tests"]


def test_check_passes_on_what_add_just_wrote(vendored):
    assert [(one.module_id, one.verdict) for one in check(vendored)] == [
        ("nf-core/fastqc", "ok")
    ]


def test_check_catches_a_hand_edit(vendored):
    """**The defect the verb exists for.** `module/` is upstream's tree and is never
    hand-edited; that used to be a comment somebody read after they had already edited it.

    Offline on purpose: recomputing the digest asks about a hand-edit and needs no network, so
    it runs in `comeni-registry`'s CI in the same lane as everything else. The question about a
    bad `add` — does this still match upstream — is `--upstream` and is a different question.
    """
    edited = vendored / "tools" / "nf-core" / "fastqc" / "module" / "main.nf"
    edited.write_text(MAIN_NF.replace("process_medium", "process_high"))

    found = check(vendored)
    assert [(one.module_id, one.verdict) for one in found] == [("nf-core/fastqc", "edited")]


def test_check_sees_an_edit_to_a_dotfile_too(vendored):
    """`.conda-lock/` pins which build of the tool runs, and it is as much the module's as
    `main.nf` is. `digest_of_module` has no allowlist for exactly this reason."""
    pinned = (
        vendored / "tools" / "nf-core" / "fastqc" / "module" / ".conda-lock" / "linux_amd64.txt"
    )
    pinned.write_text("fastqc=0.11.9\n")
    assert check(vendored)[0].verdict == "edited"


def test_a_module_nobody_vendored_is_unpinned_and_not_ok(tmp_path):
    """Reporting a pass would claim a check that never ran — the same reason `MD0100` marks a
    contract `unverified` rather than trusting it."""
    layer = _layer(tmp_path / "layer")
    tool = layer / "tools" / "in-house" / "tidy"
    (tool / "module").mkdir(parents=True)
    (tool / "module.yml").write_text("declares: module\nid: in-house/tidy\nlicence: MIT\n")
    (tool / "module" / "main.nf").write_text("process TIDY {}\n")

    assert [one.verdict for one in check(layer)] == ["unpinned"]


def test_a_pin_that_no_longer_exists_says_so(tmp_path):
    """MV0001. A `sha` that is not in the repository is a question about that commit, not
    about the branch it is on."""
    _upstream(tmp_path / "upstream")
    layer = _layer(tmp_path / "layer")
    with pytest.raises(VendorError, match="MV0001"):
        add(
            "nf-core:fastqc",
            sha="0" * 40,
            registry=layer,
            licence="MIT",
            repo=str(tmp_path / "upstream"),
        )


def test_add_replaces_wholesale_rather_than_merging(vendored, tmp_path):
    """A merge would leave a file upstream removed sitting in the layer forever, still hashed
    into the layer digest and still shipped to whoever installs it."""
    stale = vendored / "tools" / "nf-core" / "fastqc" / "module" / "gone.nf"
    stale.write_text("process GONE {}\n")
    before = digest_of_module(stale.parent)

    done = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path / "upstream",
        capture_output=True,
        text=True,
        check=True,
    )
    add(
        "nf-core:fastqc",
        sha=done.stdout.strip(),
        registry=vendored,
        licence="MIT",
        repo=str(tmp_path / "upstream"),
    )
    assert not stale.exists()
    assert digest_of_module(stale.parent) != before


def test_a_reference_with_no_source_is_refused(tmp_path):
    """`fastqc` means different things on two machines the moment a second source exists —
    the argument `MF0001` already makes for the forge."""
    with pytest.raises(VendorError, match="module reference"):
        add("fastqc", sha="0" * 40, registry=tmp_path, licence="MIT")


def test_a_licence_the_layer_does_not_carry_the_text_of_is_refused(tmp_path):
    """REUSE, and it is checked **before** the fetch so nothing half-written is left on disk.

    One file per licence rather than one NOTICE per module: at 1,600 tools that is 1,600
    near-identical copies of the MIT text, in every diff, that nobody reads.
    """
    sha = _upstream(tmp_path / "upstream")
    layer = _layer(tmp_path / "layer", licences=())
    with pytest.raises(VendorError, match="LICENSES/MIT.txt"):
        add(
            "nf-core:fastqc",
            sha=sha,
            registry=layer,
            licence="MIT",
            repo=str(tmp_path / "upstream"),
        )
    assert not (layer / "tools").exists(), "the fetch ran before the licence was checked"
