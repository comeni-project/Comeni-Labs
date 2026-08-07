"""Content addressing. A lockfile pins contracts by digest, so the digest must be stable.

Stable means: across processes, across `PYTHONHASHSEED`, and across the order a filesystem
happens to hand files over. A digest that varied on any of those would make every lockfile
spuriously dirty and the reproducibility claim worthless.
"""

import hashlib
import os
import subprocess
import sys

import pytest
from comeni_core.contract import ModuleContract
from comeni_core.digest import digest_of, digest_of_directory
from comeni_core.vocabulary import Vocabulary

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
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted, indexed]\n")
    path = tmp_path / "c.yml"
    path.write_text(CONTRACT)
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
                "from comeni_core.contract import OutputPort;"
                "from comeni_core.digest import digest_of;"
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
    """The frozensets in `Vocabulary.types` are dict *values*, not fields of their own.

    Every other frozenset in the codebase had a sorting serialiser; these did not, because
    nothing had ever serialised a `Vocabulary`. `digest_of` is the first thing that does,
    and federation §4.1 has the lockfile pinning the vocabulary — so without this the same
    vocabulary digested three ways under three seeds and every lockfile would have been
    spuriously dirty, while looking perfectly stable inside any one process.
    """
    outputs = set()
    for seed in ("1", "7", "99999"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from comeni_core.vocabulary import Vocabulary;"
                "from comeni_core.digest import digest_of;"
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
    (layer / "contracts" / "a.yml").write_text("id: a\n")
    before = digest_of_directory(layer)
    (layer / "contracts" / "a.yml").write_text("id: b\n")
    assert digest_of_directory(layer) != before


def test_a_directory_digest_covers_file_names_too(tmp_path):
    """Renaming a file changes the layer, even if every byte is the same."""
    layer = tmp_path / "layer"
    layer.mkdir()
    (layer / "a.yml").write_text("x: 1\n")
    before = digest_of_directory(layer)
    (layer / "a.yml").rename(layer / "b.yml")
    assert digest_of_directory(layer) != before


def test_a_directory_digest_ignores_traversal_order(tmp_path):
    """Two directories with the same contents digest the same, whatever order they were built."""
    one, two = tmp_path / "one", tmp_path / "two"
    for d in (one, two):
        (d / "sub").mkdir(parents=True)
    for name in ("a.yml", "b.yml", "c.yml"):
        (one / name).write_text(name)
    for name in ("c.yml", "a.yml", "b.yml"):
        (two / name).write_text(name)
    (one / "sub" / "d.yml").write_text("d")
    (two / "sub" / "d.yml").write_text("d")
    assert digest_of_directory(one) == digest_of_directory(two)


def test_a_missing_directory_digests_to_the_empty_digest(tmp_path):
    """A layer may legitimately have no `rules/`. That is not an error."""
    assert digest_of_directory(tmp_path / "nope").startswith("sha256:")


def test_a_filename_cannot_forge_an_entry_boundary(tmp_path):
    """A forgeable digest is not a digest.

    The first version joined `f"{name}:{content_hash}"` with newlines, so a filename
    containing a colon and a newline could impersonate a second entry: one file named
    `a.yml:<sha of "alpha">\\nb.yml` holding "beta" digested identically to a two-file layer
    holding a.yml/"alpha" and b.yml/"beta". Task 8 makes layers something strangers
    distribute and a lockfile pins them by digest, so this is the whole guarantee.
    """
    honest, forged = tmp_path / "honest", tmp_path / "forged"
    honest.mkdir()
    forged.mkdir()
    (honest / "a.yml").write_text("alpha")
    (honest / "b.yml").write_text("beta")

    alpha_hash = hashlib.sha256(b"alpha").hexdigest()
    (forged / f"a.yml:{alpha_hash}\nb.yml").write_text("beta")

    assert digest_of_directory(honest) != digest_of_directory(forged)


def test_a_layer_may_not_contain_a_symlink(tmp_path):
    """A layer with a link in it is refused rather than hashed. Audit 2026-08-06, A9.

    Three tests used to live here, and all three asserted a design that was wrong. They
    checked that a link was hashed as its *target path* and never followed — reasoning
    that following one would make the digest depend on bytes outside the layer, so the
    same directory would digest differently on two machines. That reasoning is sound and
    the conclusion did not follow, because `Registry.load` opens the same path with
    `read_text()`, which *does* follow it. The bytes routed on were not the bytes pinned.

    The third of those tests came closest and still missed: it asserted that repointing a
    link changes the digest, "otherwise every symlink would be invisible to the digest" —
    the right worry, checked against the target's *path* and never against the target's
    *contents*. Rewriting the target's contents rerouted a whole pipeline to `priority: 999`
    with a byte-identical layer digest and zero drift.

    So the file-versus-symlink domain separation those tests also covered is gone with the
    branch it protected. `_FILE` stays; there is no longer a second kind to be confused with.
    """
    layer = tmp_path / "layer"
    layer.mkdir()
    outside = tmp_path / "outside.yml"
    outside.write_text("v1")
    (layer / "link.yml").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(layer)


def test_a_symlinked_directory_is_refused_too(tmp_path):
    """Never exploitable — `rglob` does not descend into one — but refused anyway.

    "The layer contains a link" is a simpler rule to state, and to check, than "the layer
    contains a link to a file". A rule with an exception is a rule someone will find the
    exception in.
    """
    layer = tmp_path / "layer"
    layer.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "a.yml").write_text("hello")
    (layer / "contracts").symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(layer)
