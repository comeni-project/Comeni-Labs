"""`mendel lint --registry X` — is this layer arranged the way it says it is?

**The loader stays free, and every test here says so by construction**: each fixture is a layer
that `layers.load` reads perfectly and the lint refuses. That gap is the whole subject.
comeni-registry#1 traded a guarantee for a freedom — a contract used to live in `contracts/`, so
a misfiled document was impossible *by construction* and a misspelled `contract/` was caught by
`MD0003` because nothing read it. A `declares:` line can only be **detected**. This is the other
half of that trade.

A layer whose `registry.yml` declares no `layout:` is unenforced, which is every private
overlay. The rule and the enforcement are different things.
"""

import shutil

import pytest
from mendel_compiler.registry_lint import lint
from support.paths import ROOT

REGISTRY = ROOT / "registry"


@pytest.fixture
def layer(tmp_path):
    """A copy of the shipped layer, which lints clean before anything is done to it."""
    where = tmp_path / "lab"
    shutil.copytree(REGISTRY, where)
    assert lint(where) == [], "the fixture must start clean or every test below is vacuous"
    return where


def codes(found) -> list[str]:
    return sorted(f.code for f in found)


def test_the_shipped_layer_is_arranged_as_it_says():
    """The check must not fire on the thing it guards."""
    assert lint(REGISTRY) == [], "\n".join(f.render(REGISTRY) for f in lint(REGISTRY))


def test_a_layer_with_no_layout_is_unenforced(tmp_path):
    """**Invariant 11, held by a test rather than by a sentence.** A private overlay arranges
    itself however it likes, and the lint has nothing to say about it."""
    where = tmp_path / "overlay"
    (where / "anywhere").mkdir(parents=True)
    (where / "registry.yml").write_text("name: lab\n")
    (where / "anywhere" / "x.yml").write_text(
        "declares: measurement\nid: read_length\nkind: integer\n"
    )
    assert lint(where) == []


def test_a_misfiled_document_is_refused(layer):
    """MD0013. It **loads perfectly** — the loader reads `declares:`, not the path — and is
    invisible to everyone reading the tree."""
    moved = layer / "measurements" / "sneaky.yml"
    moved.write_text((layer / "rules" / "alignment.yml").read_text())
    found = lint(layer)
    assert codes(found) == ["MD0013"]
    assert "rules/" in found[0].fix


def test_a_file_named_for_something_it_does_not_declare_is_refused(layer):
    """MD0014. Identity is the `id:` since `MD0012`, so the filename carries no meaning to the
    loader — which is exactly why it has to name its subject for a human."""
    target = layer / "measurements" / "read_length.yml"
    target.rename(layer / "measurements" / "how_long_the_reads_are.yml")
    assert codes(lint(layer)) == ["MD0014"]


def test_several_roles_in_one_file_are_refused(layer):
    """MD0015. `roles.yml` held all nine and a diff touching it said only that *some* job
    changed."""
    (layer / "roles" / "trimming.yml").write_text(
        "declares: role\nroles:\n  - trimming\n  - alignment\n"
    )
    assert "MD0015" in codes(lint(layer))


def test_a_module_nothing_declares_is_refused(layer):
    """MD0016, and it is the quiet one. Nothing under `module/` is layer data, so a directory
    with no `module.yml` is not in the stack's modules — and `MD0100` reports every contract
    binding to it as *unverified*, which is a diagnostic rather than a refusal, so the build
    goes green with the source sitting right there unread."""
    (layer / "tools" / "nf-core" / "fastqc" / "module.yml").unlink()
    found = lint(layer)
    assert "MD0016" in codes(found)


def test_a_shared_type_hidden_inside_a_tool_is_refused(layer):
    """MD0017. The next person to move or delete that tool takes a type six other contracts
    depend on with it."""
    (layer / "tools" / "nf-core" / "star" / "alignment.bam.yml").write_text(
        "declares: vocabulary\nid: alignment.bam\nstates: []\n"
    )
    assert "MD0017" in codes(lint(layer))


def test_a_type_namespaced_by_its_tool_is_fine(layer):
    """The other half — `genome.index.star` under `tools/nf-core/star/` is the arrangement
    this layout exists to produce, and it must not fire on it."""
    assert lint(layer) == []
    assert (layer / "tools" / "nf-core" / "star" / "genome.index.star.yml").exists()


def test_two_versions_of_one_module_in_one_layer_are_refused(layer):
    """MD0018. One `module/` holds one commit, so one of the two is checked against source
    that is not its own — the drift `MD0104` exists to catch, by a route it cannot see."""
    where = layer / "tools" / "nf-core" / "star" / "align"
    body = (where / "contract.yml").read_text()
    (where / "contract-2.yml").write_text(body.replace("@1.11.0", "@2.0.0"))
    found = lint(layer)
    assert "MD0018" in codes(found)
    assert "higher layer" in next(f for f in found if f.code == "MD0018").fix


def test_a_path_leaving_a_tool_s_directory_is_refused(layer):
    """MD0019 — **what makes `self-isolated` checked rather than hoped.**

    The argument for the tool/subtool layout is that everything about one tool is in one place
    and can be reviewed, moved or deleted as a unit. A `../../other-tool/thing` makes that
    false quietly, and the next person to move a directory finds out at build time.
    """
    target = layer / "tools" / "nf-core" / "fastqc" / "contract.yml"
    target.write_text(target.read_text() + "# see ../../samtools/sort/contract.yml\n")
    # A comment is not a reference — the scan reads what is left after `#`.
    assert lint(layer) == []

    target.write_text(target.read_text().replace("# see ../../", "test_data: ../../"))
    assert "MD0019" in codes(lint(layer))


def test_the_lint_is_not_vacuous(layer):
    """A scan that reaches no files reports nothing and passes — the failure mode every guard
    in this repository has had at least once."""
    from mendel_compiler.registry_lint import _declared_files

    assert len(list(_declared_files(layer))) > 30
