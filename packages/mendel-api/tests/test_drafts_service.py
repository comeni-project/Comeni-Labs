"""The rule, without the storage. **Runs in CI, where the route tests cannot.**

`test_drafts.py` needs Postgres and skips without it, following `test_visits.py`. The rule most
worth defending is that `keep` refuses an illegal graph, so it is tested here with `_load` and
`_output_root` monkeypatched — a rule only a developer machine can check is a rule CI cannot
defend.
"""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import drafts

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"


def _graph(nodes, edges=()):
    return DraftGraph.model_validate(
        {
            "nodes": [{"id": i, "contract_id": c} for i, c in nodes],
            "edges": [
                {"from_node": a, "from_port": b, "to_node": c, "to_port": d}
                for a, b, c, d in edges
            ],
        }
    )


def test_keep_refuses_an_illegal_graph(monkeypatch):
    """An unsorted BAM into featureCounts. The message carries the code, so
    `mendel explain MD0504` expands it exactly as it would from the CLI."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    with pytest.raises(ValueError, match="MD0504"):
        drafts.keep("whatever")


def test_the_refusal_says_how_many_problems_there_are(monkeypatch):
    """One answer, but not a lie about the size of the problem. `validate` is where you go to
    see them all, and the refusal should tell you there are more."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam"), ("align", "nope", "counts", "annotation")],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    with pytest.raises(ValueError, match="2 illegal finding"):
        drafts.keep("whatever")


def test_keep_allows_a_graph_with_only_unmet_ports(monkeypatch, tmp_path):
    """`unmet` is not `illegal`. A half-drawn graph is a legal thing to hold; the emitted
    Nextflow simply has an input nothing fills, which the gates catch where it costs something.
    """
    graph = _graph([("counts", COUNTS)])
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    written = drafts.keep("whatever")
    assert written.exists()
    assert written.name == "pipeline.yml"


def test_a_kept_draft_records_who_chose_each_step(monkeypatch, tmp_path):
    """Task 5's split, reaching the artifact. A model-assembled pipeline must not read as a
    hand-drawn one."""
    import yaml

    graph = _graph(
        [("index", GENOME), ("align", STAR), ("sort", SORT), ("counts", COUNTS)],
        [
            ("index", "index", "align", "index"),
            ("align", "bam", "sort", "bam"),
            ("sort", "bam", "counts", "bam"),
        ],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)

    written = drafts.keep("by-a-person")
    text = yaml.safe_load(written.read_text())
    producers = [d for d in text["decisions"] if d["kind"] == "producer"]
    assert producers
    assert all(d["human_override"] for d in producers)
    assert all(not d["model_override"] for d in producers)

    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path / "by-model")
    written = drafts.keep("by-a-model", by="claude-opus-5")
    text = yaml.safe_load(written.read_text())
    producers = [d for d in text["decisions"] if d["kind"] == "producer"]
    assert all(d["model_override"] for d in producers)
    assert all(d["model_override_by"] == "claude-opus-5" for d in producers)
    assert all(not d["human_override"] for d in producers)


# --- the listing: what the front door's *by pipeline* table reads ------------------------
#
# These exercise `_provenance_of` against a real kept artifact rather than the query, because
# the query needs Postgres and CI has none — the same split this file's header describes for
# `keep`. `test_drafts.py` covers the route where a database exists.


def _kept(monkeypatch, tmp_path):
    """Keep the canonical spine and hand back the `Pipeline` that was written."""
    from mendel_compiler import pipeline_file

    graph = _graph(
        [("index", GENOME), ("align", STAR), ("sort", SORT), ("counts", COUNTS)],
        [
            ("index", "index", "align", "index"),
            ("align", "bam", "sort", "bam"),
            ("sort", "bam", "counts", "bam"),
        ],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    return pipeline_file.load(drafts.keep("d1"))


def test_provenance_counts_every_decision_and_not_only_the_steps(monkeypatch, tmp_path):
    """Steps AND settings, because both carry a tier and both can be tier 4.

    `services/build.py` shipped the other version once: counting steps only reported *0 needing
    your decision* on a pipeline whose `seq_platform` exits at tier 4 — understating on the one
    element that carries the product's claim.
    """
    pipeline = _kept(monkeypatch, tmp_path)
    provenance, _, _ = drafts._provenance_of(pipeline)

    decisions = (provenance.settled + provenance.measured + provenance.open
                 + provenance.by_person + provenance.by_model)
    settings = sum(len(step.settings) for step in pipeline.steps)
    assert decisions == len(pipeline.steps) + settings, (
        "a decision was dropped: the bar must total every step and every setting"
    )


def test_a_tier_three_value_is_not_counted_as_settled(monkeypatch, tmp_path):
    """**The honesty of the whole bar.** A rule matched measured data, which is the machinery
    working — and the premise behind the measurement still needs a person. Counting tier 3 as
    settled turns the one element carrying the claim into the one element overstating it, which
    is what `Provenance.tsx` says in the same words on the other side of the wire."""
    pipeline = _kept(monkeypatch, tmp_path)
    provenance, _, _ = drafts._provenance_of(pipeline)

    whys = [step.why for step in pipeline.steps]
    whys += [s.why for step in pipeline.steps for s in step.settings]
    assert provenance.settled == sum(1 for w in whys if int(w.tier) in (1, 2))
    assert provenance.measured == sum(1 for w in whys if int(w.tier) == 3)


def test_a_choice_a_person_made_is_not_a_choice_waiting_on_one(monkeypatch, tmp_path):
    """**Tier 4 is three different facts and only one of them needs anybody.**

    Found by running it. On a HAND-DRAWN pipeline every step is `tier: 4, source: human` —
    because a person chose it, and `MD0220` says `source: human` is exactly what clears a
    review. Counting raw tier 4 reported *5 open* on the canonical spine where one value
    actually waits on somebody: a five-fold overstatement on the front door.

    Crying wolf is the same failure as hiding. Invariant 6 flags tier 4 so a flag means
    something, and a bar that flags four settled choices teaches people to ignore it.
    """
    pipeline = _kept(monkeypatch, tmp_path)
    provenance, named, _ = drafts._provenance_of(pipeline)

    drawn = [s for s in pipeline.steps if int(s.why.tier) == 4]
    assert drawn, "the fixture stopped being a hand-drawn graph"
    assert provenance.by_person >= len(drawn)
    assert provenance.open == 1, (
        f"only star_align.seq_platform waits on a person; got {provenance.open} "
        f"({[(v.step, v.setting) for v in named]})"
    )


def test_a_model_s_answer_is_not_a_person_s(monkeypatch, tmp_path):
    """The 4→5 schema bump exists so an agent-assembled pipeline does not read as one a person
    drew by hand. Folding both into one number here would undo that at the last step, on the
    page most people read."""
    pipeline = _kept(monkeypatch, tmp_path)
    provenance, _, _ = drafts._provenance_of(pipeline)

    assert provenance.by_person > 0
    assert provenance.by_model == 0, "nothing in this fixture was answered by a model"


def test_waiting_on_a_person_names_the_values(monkeypatch, tmp_path):
    """*'strandedness and fragment size', not '2 items'.* A count is what you write when you
    have not looked — `ov-settled`. The spine has exactly one tier-4 setting,
    `star_align.seq_platform`, and the page must be able to say its name."""
    pipeline = _kept(monkeypatch, tmp_path)
    provenance, named, unnamed = drafts._provenance_of(pipeline)

    assert provenance.open, "the spine has an unanswered value; the fixture stopped being one"
    assert named, "an open value was counted and not named"
    assert unnamed == 0, "nothing was capped, so nothing may be reported as unnamed"
    # The step id is the one DRAWN, not the one the resolver would have invented — a hand-drawn
    # graph names its own nodes, and this assertion said `star_align` until it was run.
    assert ("align", "seq_platform") in [(v.step, v.setting) for v in named]


def test_naming_open_values_is_capped_and_says_how_many_it_did_not_name(monkeypatch, tmp_path):
    """A cap that truncates silently is a count wearing a list's clothes."""
    pipeline = _kept(monkeypatch, tmp_path)
    monkeypatch.setattr(drafts, "_NAMED_AT_MOST", 0)
    provenance, named, unnamed = drafts._provenance_of(pipeline)

    assert named == []
    # `unnamed` accounts for open SETTINGS that were not named. A tier-4 *step* is counted and
    # never named — the page's sentence is about values — so it is not in this remainder.
    open_settings = sum(
        1 for step in pipeline.steps for s in step.settings
        if int(s.why.tier) == 4 and str(s.why.source) not in ("human", "model")
    )
    assert unnamed == open_settings
    assert provenance.open == open_settings
