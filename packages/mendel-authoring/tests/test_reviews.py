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


@pytest.mark.parametrize("change", ["contract", "digest", "setting", "wire", "premise", "source"])
def test_same_id_does_not_reuse_a_review_of_changed_meaning(rnaseq, change):
    reviews = _reviews()
    before = rnaseq(150)
    step = before.step("star_align")
    if change == "contract":
        after = _changed(
            before,
            "star_align",
            module=step.module.model_copy(update={"contract_id": "nf-core/hisat2/align@2.2.2"}),
        )
    elif change == "digest":
        after = _changed(
            before,
            "star_align",
            module=step.module.model_copy(update={"digest": "sha256:" + "f" * 64}),
        )
    elif change == "wire":
        after = _changed(before, "star_align", inputs=[StepInput(port="reads", source="qc.out")])
    elif change == "setting":
        after = _changed(
            before, "star_align", ext_args=step.ext_args.model_copy(update={"template": "--new"})
        )
    elif change == "source":
        after = _changed(
            before,
            "star_align",
            why=step.why.model_copy(
                update={
                    "premise": [
                        step.why.premise[0].model_copy(
                            update={"origin": PremiseOrigin.ASSERTED, "pieces": []}
                        )
                    ]
                }
            ),
        )
    else:
        after = _changed(
            before,
            "star_align",
            why=step.why.model_copy(
                update={"premise": [step.why.premise[0].model_copy(update={"value": 100})]}
            ),
        )
    [outcome] = reviews.cascade(before, after, [reviews.review(before, "star_align", "ana")])
    assert outcome.status.value == "superseded"
    assert outcome.reason.value == "meaning_changed"


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
    assert [o.status.value for o in outcomes] == ["superseded", "retained"]


def test_receipt_describes_changed_evidence_when_the_tool_list_is_unchanged(rnaseq):
    from mendel_authoring.diff import diff_of

    before = rnaseq(150)
    after = rnaseq(100)
    difference = diff_of(before, after)
    assert not difference.empty
    assert "star_align" in difference.updated
    assert "updates" in difference.sentence()
