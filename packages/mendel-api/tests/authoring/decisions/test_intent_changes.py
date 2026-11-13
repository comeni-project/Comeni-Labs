"""A structural change (A1) arrives as a `DecisionChange`, like every other change, and is written
through `services.changes`: a role switched off, a tool excluded at a site, a port's source."""

import pytest
from comeni_core.goal.asked import ProducerExclusion, RoleAbsence, Site, SourcePin
from comeni_core.plan.draft import DraftGraph, DraftNode
from mendel_api.services import changes, decisions, drafts, registry
from mendel_api_tests.database import reachable
from mendel_authoring.intent import read_edit
from mendel_authoring.payloads import DecisionChange

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")

STAR = "nf-core/star/align@2.7.11b"
COUNTS = "nf-core/subread/featurecounts@2.1.1"
SORT = "nf-core/samtools/sort@1.24"
FASTQC = "nf-core/fastqc@0.12.1"
SITE = Site(type_id="alignment.bam")


def _draft():
    return drafts.create(DraftGraph(), "intent changes", "ana")


def _constraints(draft):
    return decisions.goal(draft).constraints


def test_a_role_change_switches_it_off_and_back_on():
    draft = _draft()
    assert changes.apply(draft, DecisionChange(kind="role", subject="trimming"), who="ana")
    assert _constraints(draft).absent_roles == [RoleAbsence(role="trimming")]
    assert changes.apply(draft, DecisionChange(kind="role", subject="trimming", retract=True),
                         who="ana")
    assert _constraints(draft).absent_roles == []


def test_an_exclude_change_excludes_at_the_site():
    draft = _draft()
    changes.apply(draft, DecisionChange(kind="exclude", subject="alignment.bam", value=STAR),
                  who="ana")
    assert _constraints(draft).exclusions == [ProducerExclusion(site=SITE, contract=STAR)]


def test_a_source_change_pins_the_port():
    draft = _draft()
    subject = decisions.source_key(COUNTS, "bam")
    changes.apply(draft, DecisionChange(kind="source", subject=subject, value=SORT), who="ana")
    assert _constraints(draft).sources == [SourcePin(consumer=COUNTS, port="bam", producer=SORT)]
    assert changes.describe(DecisionChange(kind="source", subject=subject, value=SORT)) == (
        "SUBREAD_FEATURECOUNTS reads its bam from SAMTOOLS_SORT")


@pytest.mark.parametrize("change", [
    DecisionChange(kind="role", subject="no_such_role"),
    DecisionChange(kind="exclude", subject="alignment.bam", value="nf-core/nothing@0.0.0"),
    DecisionChange(kind="source", subject=f"{COUNTS}|no_such_port", value=SORT),
    DecisionChange(kind="source", subject=f"{COUNTS}|bam", value="nf-core/nothing@0.0.0"),
])
def test_an_undeclared_role_tool_or_port_is_refused_with_MI0204(change):
    with pytest.raises(ValueError, match="MI0204"):
        changes.check(change)


def test_reading_change_round_trips():
    """Every kind a canvas edit is read as reaches the goal through the one writer."""
    stack = registry.stack()
    before = DraftGraph(nodes=[DraftNode(id="star_align", contract_id=STAR),
                               DraftNode(id="sort", contract_id=SORT)])
    after = DraftGraph(nodes=[DraftNode(id="sort", contract_id=SORT),
                              DraftNode(id="qc", contract_id=FASTQC)])
    readings = read_edit(before, after, {"star_align": SITE}, stack.registry)
    assert {r.kind for r in readings} >= {"want", "pin"}
    draft = _draft()
    for reading in readings:
        changes.apply(draft, reading.change(), who="ana")
    goal = decisions.goal(draft)
    assert "qc.report" in goal.want
    assert any(p.contract == FASTQC for p in goal.constraints.producers)


# ── a tool's optional input (#460) ──────────────────────────────────────────────────────────

QUAST = "nf-core/quast@5.3.0"


@pytest.fixture
def with_quast(tmp_path, monkeypatch):
    """The curated registry plus an overlay with QUAST, whose reference is optional."""
    from mendel_resolver import layers
    from support.paths import ROOT

    layer = tmp_path / "overlay"
    layer.mkdir()
    quast = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
    files = {
        "assembly.family.yml": "declares: family\nid: assembly\ndescription: assemblies\n",
        "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\n",
        "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\n",
        "quast.contract.yml": "declares: contract\n" + quast,
    }
    for name, body in files.items():
        (layer / name).write_text(body)
    stacked = layers.load([ROOT / "registry", layer])
    monkeypatch.setattr(registry, "stack", lambda: stacked)


def _switch(port: str, state: str | None, contract: str = QUAST) -> DecisionChange:
    from mendel_authoring.payloads import source_subject

    return DecisionChange(kind="optional_input", subject=source_subject(contract, port),
                          value=state, retract=state is None)


def test_an_optional_input_change_switches_it_on_and_back(with_quast):
    from comeni_core.goal.asked import InputChoice, InputState

    draft = _draft()
    assert changes.apply(draft, _switch("fasta", "optional"), who="ana")
    assert _constraints(draft).inputs == [
        InputChoice(contract=QUAST, port="fasta", state=InputState.OPTIONAL)]
    assert changes.describe(_switch("fasta", "optional")) == "QUAST may read a fasta"
    assert changes.apply(draft, _switch("fasta", None), who="ana")
    assert _constraints(draft).inputs == []


def test_switching_a_required_input_is_refused():
    with pytest.raises(ValueError, match="MI0204"):
        changes.check(_switch("reads", "optional", contract=STAR))


def test_a_units_change_says_an_input_may_span_several_rows(with_quast):
    """A sample may be sequenced over several lanes (#466, stage 5)."""
    draft = _draft()
    assert changes.apply(draft, DecisionChange(kind="input", subject="fastq.reads", value=True),
                         who="ana")
    lanes = DecisionChange(kind="units", subject="fastq.reads", value=True)
    assert changes.apply(draft, lanes, who="ana")
    assert _constraints(draft).units == ["fastq.reads"]
    assert changes.describe(lanes) == "a sample may span several rows of fastq.reads"
    assert changes.apply(draft, DecisionChange(kind="units", subject="fastq.reads",
                                               value=False), who="ana")
    assert _constraints(draft).units == []


def test_units_on_an_input_the_goal_does_not_have_are_refused():
    with pytest.raises(ValueError, match="MI0204"):
        changes.apply(_draft(), DecisionChange(kind="units", subject="fastq.reads", value=True),
                      who="ana")


@pytest.fixture
def with_parts(tmp_path, monkeypatch):
    """The curated registry plus a search step that can run on parts (#466, stage 6)."""
    from emit.fixtures.parts import layer
    from mendel_resolver import layers
    from support.paths import ROOT

    stacked = layers.load([ROOT / "registry", layer(tmp_path)])
    monkeypatch.setattr(registry, "stack", lambda: stacked)


SEARCH = "lab/search@1.0.0"


def test_a_whole_change_keeps_a_step_whole_and_back(with_parts):
    draft = _draft()
    whole = DecisionChange(kind="whole", subject=SEARCH)
    assert changes.apply(draft, whole, who="ana")
    assert _constraints(draft).whole == [SEARCH]
    assert changes.describe(whole) == "SEARCH runs on each sample whole"
    back = DecisionChange(kind="whole", subject=SEARCH, retract=True)
    assert changes.describe(back) == "SEARCH runs on parts of each sample"
    assert changes.apply(draft, back, who="ana")
    assert _constraints(draft).whole == []
    assert not changes.apply(draft, back, who="ana")


def test_keeping_whole_a_tool_that_never_runs_on_parts_is_refused(with_parts):
    with pytest.raises(ValueError, match="MI0204"):
        changes.check(DecisionChange(kind="whole", subject=STAR))
