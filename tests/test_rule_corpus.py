"""The twenty rules the design audit could not write, run against the format that replaced it.

Stream 4 of the 2026-08-14 design audit took twenty real tier-3 rules from the literature and
tried to write each one. The result was **6 clean · 4 load and are wrong · 1 contortion · 9
cannot be written**, and `docs/internal/audits/fixtures/rule-attempts/` records it. That
directory says its own value is being *evidence, not tests*, and that a future task repairing
the format would turn them into tests. This is that task — and the originals stay frozen,
because a corpus rewritten in the new format cannot also be the record of what the old one
could not express.

So there are two directories and they answer different questions. `rule-attempts/` says what
broke. `tests/fixtures/rule-corpus/` says whether it is fixed, and this file is the assertion.

**Each rule loads alone**, stacked over the shipped registry plus the corpus layer's declared
data. Loading them together would collide by design — R01, R12 and R20 all decide
`implementation:alignment`, which `MD0309` refuses and rightly.
"""

import pathlib
import shutil

import pytest
import yaml
from mendel_resolver import layers
from mendel_resolver.rules import RuleValidationError

ROOT = pathlib.Path(__file__).parent.parent
CORPUS = ROOT / "tests" / "fixtures" / "rule-corpus"

LOADS = None
"""Expected outcome for a rule the format can now express."""

EXPECTED: dict[str, str | None] = {
    "R01": LOADS,   # aligner by read length — the control
    "R02": "MD0300",  # --sjdbOverhang = read_length - 1: arithmetic. Issue #39
    "R02b": "MD0311",  # the enumerated contortion: eight rows, and a hole below the lowest
    "R03": "MD0300",  # --genomeSAindexNbases: arithmetic, same mechanism as R02
    "R04": LOADS,   # trim length by read length
    "R05": LOADS,   # clip_R1 by library prep
    "R06": LOADS,   # twopass by purpose — A120
    "R07": LOADS,   # MAPQ floor by purpose — A120
    "R08": LOADS,   # skip trimming by adapter content — A119
    "R09": LOADS,   # ribo depletion — loads; forcing *insertion* is §4.1's open half
    "R10": LOADS,   # dedup policy, third branch "no step" — A119
    "R11": LOADS,   # quantifier by required_states — A120
    "R12": LOADS,   # aligner by node memory
    "R13": LOADS,   # cpus by genome size, now scoped to a role — A123
    "R14": LOADS,   # MultiQC above one sample — A119
    "R15": LOADS,   # infer strandedness where unmeasured — A122, as a derivation
    "R16": LOADS,   # strandedness != unstranded — A121
    "R17": LOADS,   # genome build by organism
    "R18": LOADS,   # paired AND read_length >= 100
    "R19": LOADS,   # cohort max read length — a derivation with an aggregate
    "R20": "MD0306",  # names a contract this stack does not hold — refused by design
}
"""What each rule does against the Plan 1.15 format, and why.

Four are refused and none of the four is a regression. **R02 and R03 are arithmetic**, which
this format still cannot express and refuses honestly — issue #39, and the plan says so.
**R02b is the contortion**, enumerating one row per read length, and it is *newly* caught:
`MD0311` sees that eight rows over an unbounded integer leave everything below the lowest one
uncovered, which is the defect the contortion was hiding. **R20 is refused by design.**
"""


@pytest.fixture(scope="module")
def corpus_data(tmp_path_factory):
    """The corpus layer's declared data, without its rules. Copied once."""
    layer = tmp_path_factory.mktemp("corpus") / "layer"
    shutil.copytree(CORPUS, layer)
    shutil.rmtree(layer / "rules")
    return layer


def _keys_declared_by(rule: str) -> set[str]:
    """The keys this corpus rule file claims, read from the file rather than from the loader.

    Read independently on purpose: asking the loader which keys it loaded and then asserting
    it loaded them is a tautology. The file says what it decides and the table has to agree.
    """
    raw = yaml.safe_load((CORPUS / "rules" / f"{rule}.yml").read_text()) or {}
    keys = {f"derive:{d['fact']}" for d in raw.get("derives", [])}
    for decision in raw.get("decisions", []):
        targets = decision["decides"]
        for target in targets if isinstance(targets, list) else [targets]:
            key = f"{target['effect']}:{target['of']}"
            keys.add(key + (f":{target['name']}" if target.get("name") else ""))
    return keys


def _load_one(corpus_data, tmp_path, rule: str):
    layer = tmp_path / "layer"
    shutil.copytree(corpus_data, layer)
    (layer / "rules").mkdir()
    shutil.copy(CORPUS / "rules" / f"{rule}.yml", layer / "rules")
    return layers.load([ROOT / "registry", layer])


@pytest.mark.parametrize("rule", sorted(EXPECTED))
def test_the_corpus_rule(rule, corpus_data, tmp_path):
    expected = EXPECTED[rule]
    if expected is LOADS:
        loaded = _load_one(corpus_data, tmp_path, rule)
        # **Every key the file claims is in force, and the corpus layer is what decided it.**
        # Counting entries instead does not work: R01 and R12 legitimately *replace* the
        # shipped `implementation:alignment` block, so the count does not move — and an empty
        # rule file passed a "contributed something" check because the base layer's own rule
        # satisfied it. A guard a base layer can satisfy on the fixture's behalf is not
        # watching the fixture.
        keys = _keys_declared_by(rule)
        assert keys, f"{rule} declares nothing, which is the dead-rule pathology itself"
        decided_by = {key: loaded.rules.layer_of.get(key) for key in keys}
        assert set(decided_by.values()) == {"layer"}, (
            f"{rule} loaded and is not in force: {decided_by}"
        )
        return
    with pytest.raises((RuleValidationError, ValueError)) as caught:
        _load_one(corpus_data, tmp_path, rule)
    assert expected in str(caught.value), str(caught.value)


def test_every_attempt_has_a_rewrite_and_an_expectation():
    """The corpus is twenty-one files answering twenty-one questions, and a rule that exists
    in one place and not the other is the kind of gap nobody notices.

    R02b makes twenty-one out of twenty: it is the *contortion* the audit recorded, kept as
    its own case because what it demonstrates — that enumerating around a missing feature
    produces a table with a hole — is now a diagnostic rather than a note.
    """
    written = {path.stem for path in (CORPUS / "rules").glob("*.yml")}
    assert written == set(EXPECTED)
    attempts = {
        path.name.split("-")[0]
        for path in (ROOT / "docs/internal/audits/fixtures/rule-attempts").glob("R*.yml")
    }
    assert attempts == written, "every recorded attempt has a rewrite, and no rewrite is orphaned"


def test_a_coded_refusal_tells_the_reader_how_to_read_it(corpus_data, tmp_path, capsys):
    """Issue #36, A75. `mendel explain` has existed since Plan 1.6, and nothing on this path
    mentioned it — so the one verb that explains a code was undiscoverable from the failure
    that needed it. This plan alone adds twelve codes to that path."""
    from mendel_compiler.cli import main

    layer = tmp_path / "layer"
    shutil.copytree(corpus_data, layer)
    (layer / "rules").mkdir()
    shutil.copy(CORPUS / "rules" / "R20.yml", layer / "rules")
    code = main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--registry", str(ROOT / "registry"), "--registry", str(layer),
        "--out", str(tmp_path / "out"), "--root", str(ROOT), "--gate", "lint",
    ])
    assert code == 2
    assert "run: mendel explain MD0306" in capsys.readouterr().err


def test_an_uncoded_refusal_gains_no_pointer():
    """The negative that keeps it honest: a message with no code gets no pointer, because
    `mendel explain` would then be advertised for a failure it cannot explain."""
    from mendel_compiler.cli import _with_pointer

    assert "mendel explain" not in _with_pointer("mendel: something went wrong")


def test_the_pointer_names_the_first_code_not_a_quoted_one():
    """A refusal names one thing. A message quoting a second code is quoting it as context —
    `MD0311`'s own fix block names `MD0313` — and pointing a reader at the context rather
    than at their error would be worse than pointing them nowhere."""
    from mendel_compiler.cli import _with_pointer

    pointed = _with_pointer("MD0311: a hole in the table. See also MD0313 for the tier.")
    assert pointed.endswith("run: mendel explain MD0311")
