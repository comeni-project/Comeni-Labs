"""Exercise ``add`` and ``check`` without network access.

The tests build a local Git repository and use it through the same clone path as a remote source.
Real commits protect pin behavior without making the suite depend on an external service.
"""

import subprocess
from pathlib import Path

import pytest
import yaml
from comeni_core.declared.layered import layers_of, stack
from comeni_core.declared.module import Module
from comeni_vendor.cli import main
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
    """A generated declaration participates in ordinary layer loading and stacking."""
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
    """The offline digest check detects changes without contacting upstream."""
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


def test_upstream_check_compares_the_pin_and_uses_its_distinct_verdict(vendored):
    assert check(vendored, upstream=True)[0].verdict == "ok"

    module = vendored / "tools" / "nf-core" / "fastqc" / "module"
    (module / "main.nf").write_text(MAIN_NF.replace("process_medium", "process_high"))
    result = check(vendored, upstream=True)[0]

    assert result.verdict == "moved"
    assert "differs from" in result.detail


def test_check_names_a_missing_module_directory_as_moved(vendored):
    tool = vendored / "tools" / "nf-core" / "fastqc"
    (tool / "module").rename(tool / "module-away")

    result = check(vendored)[0]

    assert result.verdict == "moved"
    assert result.detail.endswith("module does not exist")


def test_an_upstream_declaration_without_a_digest_is_unpinned(vendored):
    manifest = vendored / "tools" / "nf-core" / "fastqc" / "module.yml"
    declaration = yaml.safe_load(manifest.read_text())
    declaration.pop("digest")
    manifest.write_text(yaml.safe_dump(declaration, sort_keys=False))

    result = check(vendored)[0]

    assert result.verdict == "unpinned"
    assert result.detail == "records no digest"


def test_a_module_nobody_vendored_is_unpinned_and_not_ok(tmp_path):
    """A module without comparison evidence is reported as unpinned, not successful."""
    layer = _layer(tmp_path / "layer")
    tool = layer / "tools" / "in-house" / "tidy"
    (tool / "module").mkdir(parents=True)
    (tool / "module.yml").write_text("declares: module\nid: in-house/tidy\nlicence: MIT\n")
    (tool / "module" / "main.nf").write_text("process TIDY {}\n")

    assert [one.verdict for one in check(layer)] == ["unpinned"]


def test_a_pin_that_no_longer_exists_says_so(tmp_path):
    """MV0001 identifies a requested commit that the repository cannot provide."""
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


def test_a_pinned_path_that_does_not_exist_says_so(tmp_path):
    sha = _upstream(tmp_path / "upstream")
    layer = _layer(tmp_path / "layer")

    with pytest.raises(VendorError, match="MV0001"):
        add(
            "nf-core:fastqc",
            sha=sha,
            registry=layer,
            licence="MIT",
            repo=str(tmp_path / "upstream"),
            path="modules/nf-core/not-there",
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
    """A source is required so the same identifier cannot resolve differently by installation."""
    with pytest.raises(VendorError, match="module reference"):
        add("fastqc", sha="0" * 40, registry=tmp_path, licence="MIT")


def test_an_unknown_source_requires_an_explicit_repository(tmp_path):
    with pytest.raises(VendorError, match="Pass --repo and --path"):
        add("private:fastqc", sha="0" * 40, registry=tmp_path, licence="MIT")


def test_a_licence_the_layer_does_not_carry_the_text_of_is_refused(tmp_path):
    """Licence validation happens before fetching so no partial module is written."""
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


def test_cli_add_reports_the_pin_and_destination(tmp_path, capsys):
    sha = _upstream(tmp_path / "upstream")
    layer = _layer(tmp_path / "layer")

    status = main(
        [
            "add",
            "nf-core:fastqc",
            "--sha",
            sha,
            "--registry",
            str(layer),
            "--licence",
            "MIT",
            "--repo",
            str(tmp_path / "upstream"),
        ]
    )

    captured = capsys.readouterr()
    assert status == 0 and captured.err == ""
    assert f"vendored nf-core:fastqc at {sha[:12]}" in captured.out
    assert (layer / "tools" / "nf-core" / "fastqc" / "module" / "main.nf").exists()


def test_cli_check_prints_results_and_fails_for_an_edited_module(vendored, capsys):
    assert main(["check", "--registry", str(vendored)]) == 0
    clean = capsys.readouterr()
    assert "ok  nf-core/fastqc" in clean.out and clean.err == ""

    module = vendored / "tools" / "nf-core" / "fastqc" / "module" / "main.nf"
    module.write_text(MAIN_NF.replace("process_medium", "process_high"))
    assert main(["check", "--registry", str(vendored)]) == 1
    edited = capsys.readouterr()
    assert "edited  nf-core/fastqc" in edited.out
    assert "MV0002" in edited.err


def test_cli_check_rejects_a_layer_with_no_modules(tmp_path, capsys):
    layer = _layer(tmp_path / "layer")

    assert main(["check", "--registry", str(layer)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "declares no modules" in captured.err


def test_cli_turns_an_operation_error_into_status_one(tmp_path, capsys):
    assert main(
        ["add", "fastqc", "--sha", "0" * 40, "--registry", str(tmp_path)]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("comeni-vendor: 'fastqc' is not a module reference")
