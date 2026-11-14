"""Review applicability follows a step's meaning and both generations of its wiring."""

from importlib import import_module

import pytest
from comeni_core.artifact.pipeline import StepInput
from comeni_core.plan.tiers import PremiseOrigin


def _reviews():
    return import_module("mendel_authoring.reviews")


def _changed(blueprint, node, **fields):
    steps = [s.model_copy(update=fields) if s.id == node else s for s in blueprint.pipeline.steps]
    return blueprint.model_copy(
        update={"pipeline": blueprint.pipeline.model_copy(update={"steps": steps})}
    )


def _changed_one(before, change):
    step = before.step("star_align")
    if change == "contract":
        return _changed(
            before,
            "star_align",
            module=step.module.model_copy(update={"contract_id": "nf-core/hisat2/align@2.2.2"}),
        )
    if change == "digest":
        return _changed(
            before,
            "star_align",
            module=step.module.model_copy(update={"digest": "sha256:" + "f" * 64}),
        )
    if change == "wire":
        return _changed(before, "star_align", inputs=[StepInput(port="reads", source="qc.out")])
    if change == "setting":
        return _changed(
            before, "star_align", ext_args=step.ext_args.model_copy(update={"template": "--new"})
        )
    if change == "source":
        return _changed(before, "star_align", why=step.why.model_copy(update={"premise": [
            step.why.premise[0].model_copy(update={"origin": PremiseOrigin.ASSERTED, "pieces": []})
        ]}))
    return _changed(before, "star_align", why=step.why.model_copy(
        update={"premise": [step.why.premise[0].model_copy(update={"value": 100})]}))


@pytest.mark.parametrize("change", ["contract", "digest", "wire"])
def test_a_new_tool_or_wiring_supersedes_the_review(rnaseq, change):
    reviews = _reviews()
    before = rnaseq(150)
    [outcome] = reviews.cascade(before, _changed_one(before, change),
                                [reviews.review(before, "star_align", "ana")])
    assert outcome.status.value == "superseded"
    assert outcome.reason.value == "meaning_changed"


@pytest.mark.parametrize("change", ["setting", "premise", "source"])
def test_a_step_whose_settings_alone_change_is_updated_in_place(rnaseq, change):
    """The operator's decision on issue 496: an answer that changes only a step's settings, or
    the facts behind them, updates the step; it does not send the walk back to it."""
    reviews = _reviews()
    before = rnaseq(150)
    [outcome] = reviews.cascade(before, _changed_one(before, change),
                                [reviews.review(before, "star_align", "ana")])
    assert outcome.status.value == "updated"
    assert outcome.reason.value == "settings_changed"


def test_a_settings_change_upstream_leaves_the_steps_after_it_reviewed(blueprint_of):
    """Strandedness changed Trim Galore's settings and sent STAR, sort and counts back (496)."""
    reviews = _reviews()
    before = blueprint_of({"producer": "lab/p@1.0.0", "consumer": "lab/c@1.0.0"})
    before = _changed(before, "consumer", inputs=[StepInput(port="reads", source="producer.out")])
    flags = before.step("producer").ext_args.model_copy(update={"template": "-x"})
    after = _changed(before, "producer", ext_args=flags)
    reviewed = [reviews.review(before, n, "ana") for n in before.order]
    outcomes = reviews.cascade(before, after, reviewed)
    assert [(o.node, o.status.value) for o in outcomes] == [
        ("producer", "updated"), ("consumer", "retained")]


def test_removing_an_old_producer_invalidates_a_surviving_consumer(blueprint_of):
    reviews = _reviews()
    before = blueprint_of({"producer": "lab/p@1.0.0", "consumer": "lab/c@1.0.0"})
    before = _changed(before, "consumer", inputs=[StepInput(port="reads", source="producer.out")])
    after = before.model_copy(
        update={
            "order": ["consumer"],
            "pipeline": before.pipeline.model_copy(update={"steps": [before.step("consumer")]}),
        }
    )
    outcomes = reviews.cascade(
        before, after, [reviews.review(before, n, "ana") for n in before.order]
    )
    assert [(o.node, o.status.value) for o in outcomes] == [
        ("producer", "removed"),
        ("consumer", "superseded"),
    ]
    assert outcomes[1].reason.value == "dependency_changed"


def test_layout_and_irrelevant_goal_facts_preserve_reviews(rnaseq):
    reviews = _reviews()
    before = rnaseq(150)
    after = before.model_copy(
        update={
            "placed": {"star_align": (9, 9)},
            "pipeline": before.pipeline.model_copy(
                update={"intent": before.pipeline.intent.model_copy(update={"want": ["qc.report"]})}
            ),
        }
    )
    reviewed = reviews.review(before, "star_align", "ana")
    [outcome] = reviews.cascade(before, after, [reviewed])
    assert outcome.status.value == "retained"
    assert reviews.fingerprint(before, "star_align") == reviews.fingerprint(after, "star_align")


def test_disconnected_review_is_preserved_when_another_branch_changes(blueprint_of):
    reviews = _reviews()
    before = blueprint_of({"one": "lab/a@1.0.0", "two": "lab/b@1.0.0"})
    after = _changed(before, "one", why=before.step("one").why.model_copy(update={"reason": "new"}))
    outcomes = reviews.cascade(
        before, after, [reviews.review(before, n, "ana") for n in before.order]
    )
    # A changed reason alone updates the step in place (issue 496); the other branch is untouched.
    assert [o.status.value for o in outcomes] == ["updated", "retained"]


def test_receipt_describes_changed_evidence_when_the_tool_list_is_unchanged(rnaseq):
    from mendel_authoring.diff import diff_of

    before = rnaseq(150)
    after = rnaseq(100)
    difference = diff_of(before, after)
    assert not difference.empty
    assert "star_align" in difference.updated
    assert "updates" in difference.sentence()


def test_a_tool_choice_that_falls_to_a_question_is_reviewed_again(rnaseq):
    """A rule miss makes the aligner a tier-4 question, which stays flagged for review."""
    from comeni_core.plan.tiers import Tier

    reviews = _reviews()
    before = rnaseq(150)
    step = before.step("star_align")
    after = _changed(before, "star_align", why=step.why.model_copy(update={"tier": Tier.AMBIGUOUS}))
    [outcome] = reviews.cascade(before, after, [reviews.review(before, "star_align", "ana")])
    assert outcome.status.value == "superseded"
