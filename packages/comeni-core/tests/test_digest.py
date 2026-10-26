"""Content addressing. A lockfile pins contracts by digest, so the digest must be stable.

Stable means: across processes, across `PYTHONHASHSEED`, and across the order a filesystem
happens to hand files over. A digest that varied on any of those would make every lockfile
spuriously dirty and the reproducibility claim worthless.
"""

import hashlib
import os
import pathlib
import subprocess
import sys

import pytest
from comeni_core.artifact.digest import content_hash, digest_of, digest_of_directory, entry_hash
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.vocabulary import Vocabulary

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Add an idempotent declaration header inferred from a fixture's parent directory."""
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

CONTRACT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted, indexed]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-04"}
"""


@pytest.fixture
def contract(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text(
        _declared(vocab_dir / "alignment.bam.yml", "states: [coordinate_sorted, indexed]\n")
    )
    path = tmp_path / "c.yml"
    # Explicit, because this one sits at the layer root with no kind directory above it to
    # derive from — which is exactly the arrangement comeni-registry#1 makes legal.
    path.write_text("declares: contract\n" + CONTRACT)
    return ModuleContract.load(path, Vocabulary.load(tmp_path))


def test_a_digest_is_prefixed_and_hex(contract):
    d = digest_of(contract)
    algorithm, _, hexdigest = d.partition(":")
    assert algorithm == "sha256"
    assert len(hexdigest) == 64
    assert int(hexdigest, 16) >= 0


def test_the_same_contract_digests_the_same(contract):
    assert digest_of(contract) == digest_of(contract.model_copy(deep=True))


def test_a_changed_field_changes_the_digest(contract):
    assert digest_of(contract) != digest_of(contract.model_copy(update={"priority": 1}))


def test_a_digest_is_stable_across_hash_seeds():
    """A four-element frozenset is what makes this bite.

    `frozenset` iterates in hash order and hash order varies with PYTHONHASHSEED, so a
    digest built from an unsorted set would vary per process and make every lockfile
    spuriously dirty. Digesting an `OutputPort` directly rather than rebuilding a whole
    `ModuleContract` in the subprocess: reconstructing one needs a vocabulary, which would
    make this a test about vocabulary loading.
    """
    outputs = set()
    for seed in ("1", "7", "99999"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from comeni_core.declared.contract import OutputPort;"
                "from comeni_core.artifact.digest import digest_of;"
                "print(digest_of(OutputPort(name='bam', type_id='alignment.bam',"
                " state=frozenset({'coordinate_sorted','indexed','filtered','deduplicated'}))))",
            ],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1, f"digest varies with PYTHONHASHSEED: {outputs}"


def test_a_vocabulary_digest_is_stable_across_hash_seeds():
    """Nested frozenset values must serialize consistently across process hash seeds."""
    outputs = set()
    for seed in ("1", "7", "99999"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from comeni_core.declared.vocabulary import Vocabulary;"
                "from comeni_core.artifact.digest import digest_of;"
                "print(digest_of(Vocabulary(types={'alignment.bam': frozenset("
                "{'coordinate_sorted','indexed','filtered','deduplicated','name_sorted'}),"
                " 'fastq.reads': frozenset({'trimmed','raw'})})))",
            ],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1, f"vocabulary digest varies with PYTHONHASHSEED: {outputs}"


def test_a_directory_digest_covers_its_files(tmp_path):
    layer = tmp_path / "layer"
    (layer / "contracts").mkdir(parents=True)
    (layer / "contracts" / "a.yml").write_text(_declared(layer / "contracts" / "a.yml", "id: a\n"))
    before = digest_of_directory(layer)
    (layer / "contracts" / "a.yml").write_text(_declared(layer / "contracts" / "a.yml", "id: b\n"))
    assert digest_of_directory(layer) != before


def test_a_directory_digest_covers_file_names_too(tmp_path):
    """Renaming a file changes the layer, even if every byte is the same."""
    layer = tmp_path / "layer"
    (layer / "contracts").mkdir(parents=True)
    (layer / "contracts" / "a.yml").write_text(_declared(layer / "contracts" / "a.yml", "x: 1\n"))
    before = digest_of_directory(layer)
    (layer / "contracts" / "a.yml").rename(layer / "contracts" / "b.yml")
    assert digest_of_directory(layer) != before


def test_a_directory_digest_ignores_traversal_order(tmp_path):
    """Two directories with the same contents digest the same, whatever order they were built."""
    one, two = tmp_path / "one", tmp_path / "two"
    for d in (one, two):
        (d / "contracts" / "sub").mkdir(parents=True)
    for name in ("a.yml", "b.yml", "c.yml"):
        (one / "contracts" / name).write_text(_declared(one / "contracts" / name, name))
    for name in ("c.yml", "a.yml", "b.yml"):
        (two / "contracts" / name).write_text(_declared(two / "contracts" / name, name))
    (one / "contracts" / "sub" / "d.yml").write_text(
        _declared(one / "contracts" / "sub" / "d.yml", "d")
    )
    (two / "contracts" / "sub" / "d.yml").write_text(
        _declared(two / "contracts" / "sub" / "d.yml", "d")
    )
    assert digest_of_directory(one) == digest_of_directory(two)


def test_a_missing_directory_digests_to_the_empty_digest(tmp_path):
    """A layer may legitimately have no `rules/`. That is not an error."""
    assert digest_of_directory(tmp_path / "nope").startswith("sha256:")


def test_a_filename_cannot_forge_an_entry_boundary(tmp_path):
    """A newline-bearing filename cannot impersonate two fixed-width digest entries."""
    honest, forged = tmp_path / "honest", tmp_path / "forged"
    (honest / "contracts").mkdir(parents=True)
    (forged / "contracts").mkdir(parents=True)
    (honest / "contracts" / "a.yml").write_text(_declared(honest / "contracts" / "a.yml", "alpha"))
    (honest / "contracts" / "b.yml").write_text(_declared(honest / "contracts" / "b.yml", "beta"))

    # Exactly what the code writes for an honest first entry, asked of the code.
    impersonated = entry_hash("contracts/a.yml", content_hash(b"alpha"))
    (forged / "contracts" / f"{impersonated}\nb.yml").write_text(
        _declared(forged / "contracts" / f"{impersonated}\nb.yml", "beta")
    )

    assert digest_of_directory(honest) != digest_of_directory(forged)


def test_the_streaming_and_in_memory_content_hashes_agree(tmp_path):
    """The public in-memory helper matches the directory digester's streaming calculation."""
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "a.yml").write_text(
        "alpha"
    )
    honest = digest_of_directory(tmp_path)
    one_entry = entry_hash("contracts/a.yml", content_hash(b"alpha"))
    rebuilt = f"sha256:{hashlib.sha256(one_entry.encode()).hexdigest()}"
    assert honest == rebuilt


def test_a_layer_may_not_contain_a_symlink(tmp_path):
    """A link is refused because the loader would consume target bytes outside the layer."""
    layer = tmp_path / "layer"
    (layer / "contracts").mkdir(parents=True)
    outside = tmp_path / "outside.yml"
    outside.write_text(_declared(outside, "v1"))
    (layer / "contracts" / "link.yml").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(layer)


def test_a_symlinked_directory_is_refused_too(tmp_path):
    """The no-symlinks rule applies consistently to directories and files."""
    layer = tmp_path / "layer"
    layer.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "a.yml").write_text(_declared(elsewhere / "a.yml", "hello"))
    (layer / "contracts").symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(layer)


def _layer(root: pathlib.Path) -> pathlib.Path:
    """A minimal but real layer: one declared kind with one file, and a manifest."""
    (root / "contracts").mkdir(parents=True)
    (root / "contracts" / "a.yml").write_text(
        _declared(root / "contracts" / "a.yml", "id: nf-core/a@1.0.0\n")
    )
    (root / "registry.yml").write_text(_declared(root / "registry.yml", "name: example\n"))
    return root


def test_a_layer_digests_what_it_declares_and_not_what_git_leaves_beside_it(tmp_path):
    """Repository metadata beside declarations does not make a layer machine-dependent."""
    bare = _layer(tmp_path / "bare")
    dressed = _layer(tmp_path / "dressed")
    (dressed / ".git").write_text(
        _declared(
            dressed / ".git",
            "gitdir: ../../../.git/worktrees/some-plan/modules/registry\n"))
    (dressed / "LICENSE").write_text(_declared(dressed / "LICENSE", "CC-BY-4.0\n"))
    (dressed / "README.md").write_text(_declared(dressed / "README.md", "# the layer\n"))
    (dressed / ".github").mkdir()
    (dressed / ".github" / "ci.yml").write_text(
        _declared(
            dressed / ".github" / "ci.yml",
            "on: push\n"))

    assert digest_of_directory(bare) == digest_of_directory(dressed)


def test_the_layer_digest_covers_a_tool_s_own_source(tmp_path):
    """Vendored executable module sources are part of the pinned layer content."""
    one = _layer(tmp_path / "one")
    two = _layer(tmp_path / "two")
    for layer in (one, two):
        source = layer / "tools" / "nf-core" / "fastqc" / "module"
        source.mkdir(parents=True)
        (source / "main.nf").write_text("process FASTQC {\n    // one\n}\n")

    assert digest_of_directory(one) == digest_of_directory(two)

    (two / "tools" / "nf-core" / "fastqc" / "module" / "main.nf").write_text(
        "process FASTQC {\n    // two\n}\n"
    )
    assert digest_of_directory(one) != digest_of_directory(two), (
        "one byte of a vendored main.nf moved and the layer digest did not — the digest "
        "pins the declarations and not the code they describe"
    )


def test_the_module_clause_is_by_directory_and_not_by_extension(tmp_path):
    """Every file under a module source directory is covered, regardless of extension."""
    one = _layer(tmp_path / "one")
    two = _layer(tmp_path / "two")
    for layer in (one, two):
        source = layer / "tools" / "in-house" / "tidy" / "module"
        source.mkdir(parents=True)
        (source / "main.nf").write_text("process TIDY {}\n")
        (source / "tidy.R").write_text("x <- 1\n")

    assert digest_of_directory(one) == digest_of_directory(two)

    (two / "tools" / "in-house" / "tidy" / "module" / "tidy.R").write_text("x <- 2\n")
    assert digest_of_directory(one) != digest_of_directory(two), (
        "a helper script beside main.nf changed and the layer digest did not"
    )


def test_a_dotfile_inside_a_module_is_the_module_s_and_is_covered(tmp_path):
    """Dotfiles inside a module, including environment locks, remain part of its content."""
    one = _layer(tmp_path / "one")
    two = _layer(tmp_path / "two")
    for layer in (one, two):
        source = layer / "tools" / "nf-core" / "fastqc" / "module" / ".conda-lock"
        source.mkdir(parents=True)
        (source / "linux_amd64.txt").write_text("fastqc=0.12.1\n")

    assert digest_of_directory(one) == digest_of_directory(two)

    (two / "tools" / "nf-core" / "fastqc" / "module" / ".conda-lock" / "linux_amd64.txt"
     ).write_text("fastqc=0.11.9\n")
    assert digest_of_directory(one) != digest_of_directory(two), (
        "the pinned conda environment changed and the layer digest did not — a different "
        "build of the tool now runs under a digest that says nothing moved"
    )


def test_the_allowlist_did_not_make_the_digest_constant(tmp_path):
    """The obvious way to break the test above is to digest nothing at all."""
    one = _layer(tmp_path / "one")
    two = _layer(tmp_path / "two")
    assert digest_of_directory(one) == digest_of_directory(two)

    (two / "contracts" / "a.yml").write_text(
        _declared(two / "contracts" / "a.yml", "id: nf-core/a@2.0.0\n")
    )
    assert digest_of_directory(one) != digest_of_directory(two)

    (two / "contracts" / "a.yml").write_text(
        _declared(two / "contracts" / "a.yml", "id: nf-core/a@1.0.0\n")
    )
    (two / "registry.yml").write_text(_declared(two / "registry.yml", "name: other\n"))
    assert digest_of_directory(one) != digest_of_directory(two), "registry.yml must count"


def test_the_file_tag_separates_entry_kinds():
    """The persisted file prefix distinguishes identical bytes under another entry kind."""
    from comeni_core.artifact import digest as module

    payload = b"alpha"
    as_file = content_hash(payload)
    as_another_kind = hashlib.sha256(b"link\x00" + payload).hexdigest()

    assert as_file != as_another_kind, (
        "`_FILE` does not separate entry kinds: a second kind over the same bytes collides "
        "with a file, which is the whole thing the tag exists to prevent"
    )
    assert module._FILE != b"", "the tag is empty, so it separates nothing"
    assert as_file == hashlib.sha256(module._FILE + payload).hexdigest(), (
        "`content_hash` no longer applies the tag it is supposed to apply"
    )
