"""`mendel conformance --registry X` — does every contract agree with its module?

**This verb could not have existed before Plan 5A**, and its absence is the argument for that
plan. `MD0104`, `MD0105` and container drift compare a contract against a `main.nf`, and until
the modules moved into the layer that file lived in another repository on another release
cadence — so the only way to run the check was to build a pipeline, with a goal, in a checkout
that had both. `comeni-registry`'s own CI could not ask the question about its own data, and its
`CONTRIBUTING.md` said so in a paragraph beginning *"Not checked, and it cannot be here"*.

It runs in that CI now, which is what these tests stand between.
"""

import shutil

from mendel_compiler.cli import main
from support.paths import ROOT

REGISTRY = str(ROOT / "registry")


def test_the_shipped_layer_is_conformant(capsys):
    assert main(["conformance", "--registry", REGISTRY]) == 0
    assert "0 unverified" in capsys.readouterr().out


def test_a_contract_that_disagrees_with_its_module_exits_1(tmp_path, capsys):
    """**The one worth having**, and it is the check the whole move exists for.

    `nf_process` is what the emitted workflow writes into `include { X }`, so a contract naming
    a process the module does not define is a pipeline that dies at launch — and `-stub-run`
    cannot catch it either, because it dies at the same place.
    """
    layer = tmp_path / "lab"
    shutil.copytree(ROOT / "registry", layer)
    contract = layer / "tools" / "nf-core" / "star" / "align" / "contract.yml"
    contract.write_text(contract.read_text().replace("STAR_ALIGN\n", "STAR_ALIGNMENT\n"))

    assert main(["conformance", "--registry", str(layer)]) == 1

    said = capsys.readouterr().out
    assert "MD0101" in said
    assert "STAR_ALIGN" in said, "the diagnostic must say what to write"
    assert "module/main.nf" in said, "and name the file it read that from"


def test_a_contract_with_no_module_is_reported_and_does_not_fail_the_run(tmp_path, capsys):
    """A laboratory wrapping bare containers is legitimate — invariant 13, and `MD0100` is a
    *diagnostic* rather than a refusal.

    Failing here would make the verb unusable by exactly the people who need the rest of it,
    and reporting nothing would be worse: a green run over contracts nobody checked is the
    silent downgrade this plan's own move had to be measured against.
    """
    layer = tmp_path / "bare"
    shutil.copytree(ROOT / "registry", layer, ignore=shutil.ignore_patterns("module*"))

    assert main(["conformance", "--registry", str(layer)]) == 0

    said = capsys.readouterr().out
    assert "MD0100" in said
    assert "0 contract(s) checked against their modules, 12 unverified" in said


def test_it_checks_every_contract_and_not_only_the_ones_that_route(capsys):
    """Deliberately not `mendel build --gate lint`, which resolves a goal and therefore only
    ever reaches the contracts that happen to route.

    The shipped spine resolves five modules. There are twelve contracts, and all twelve are
    checked — including the two `comeni/` wrappers, which no goal in this repository routes to.
    """
    main(["conformance", "--registry", REGISTRY])
    assert "12 contract(s) checked" in capsys.readouterr().out


def test_it_needs_a_registry(capsys):
    """It acts on a layer and nothing else, so an empty stack is a caller error rather than a
    silent pass over zero contracts."""
    try:
        main(["conformance"])
    except SystemExit as exit:
        assert exit.code == 2
    else:
        raise AssertionError("conformance with no --registry should be a usage error")
