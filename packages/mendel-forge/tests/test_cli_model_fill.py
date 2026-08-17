"""The `--model` flag, and the argument combinations it forbids.

argparse cannot express "these three are required unless that flag is set", so the check is
explicit and its message names the flag — a usage error that does not say which argument was
wrong is a usage error somebody guesses at.
"""

import pytest
from mendel_forge import ops
from mendel_forge.cli import parse, render
from mendel_forge.scaffold import FilledValue, Filler


def test_a_hand_fill_still_requires_value_by_and_why() -> None:
    args = parse.parse(["fill", "fastqc", "roles", "qc_per_sample", "--by", "me", "--why", "w"])
    assert args.model is None
    assert args.value == "qc_per_sample"


def test_model_takes_no_value_by_or_why() -> None:
    args = parse.parse(["fill", "fastqc", "--model", "test/model"])
    assert args.model == "test/model"
    assert args.value is None
    assert args.field is None


def test_model_with_one_field() -> None:
    args = parse.parse(["fill", "fastqc", "roles", "--model", "test/model"])
    assert args.field == "roles"
    assert args.value is None


def test_a_hand_fill_without_by_is_refused() -> None:
    with pytest.raises(SystemExit):
        parse.parse(["fill", "fastqc", "roles", "qc_per_sample", "--why", "w"])


def test_model_and_by_together_are_refused() -> None:
    """`--by` on a model fill is a person putting their name to a model's answer."""
    with pytest.raises(SystemExit):
        parse.parse(["fill", "fastqc", "--model", "test/model", "--by", "me"])


def test_model_and_a_value_together_are_refused() -> None:
    with pytest.raises(SystemExit):
        parse.parse(["fill", "fastqc", "roles", "qc_per_sample", "--model", "test/model"])


def _result() -> ops.ModelFillResult:
    return ops.ModelFillResult(
        name="fastqc",
        outcomes=[
            ops.ModelFillOutcome(
                field="roles", filled=True, value=["qc_per_sample"], why="it QCs"
            ),
            ops.ModelFillOutcome(
                field="priority_because",
                filled=False,
                declined_because="no candidates — free text, and a person answers it",
            ),
        ],
        remaining=["priority_because"],
    )


def test_it_renders_both_outcomes() -> None:
    text = render.model_fill(_result())
    assert "roles" in text and "qc_per_sample" in text
    assert "priority_because" in text
    assert "free text" in text


def test_a_declined_hole_is_visible_rather_than_omitted() -> None:
    text = render.model_fill(_result())
    assert "priority_because" in text
    assert "1 hole(s) still open" in text


def test_show_marks_a_model_fill_distinctly() -> None:
    """Landing a model fill as an answer is only honest if a reviewer can see which it was."""
    text = render.show(
        ops.ShowResult(
            name="fastqc",
            target="fastqc",
            holes=[],
            filled={
                "roles": FilledValue(
                    value=["qc_per_sample"], filler=Filler.MODEL, by="test/model", why="w"
                ),
                "nf_process": FilledValue(
                    value="FASTQC", filler=Filler.DERIVED, by="nf-core", why="read from main.nf"
                ),
            },
            module=None,
        )
    )
    assert "test/model" in text
    assert "model" in text.lower()


def test_show_does_not_mark_a_derived_fill_as_a_model_one() -> None:
    text = render.show(
        ops.ShowResult(
            name="fastqc",
            target="fastqc",
            holes=[],
            filled={
                "nf_process": FilledValue(
                    value="FASTQC", filler=Filler.DERIVED, by="nf-core", why="read from main.nf"
                )
            },
            module=None,
        )
    )
    assert "test/model" not in text


def test_show_names_who_settled_every_value() -> None:
    """All three fillers are marked. Marking only the model one would make the absence of a
    marker mean two different things."""
    text = render.show(
        ops.ShowResult(
            name="fastqc",
            target="fastqc",
            holes=[],
            filled={
                "a": FilledValue(value="x", filler=Filler.MODEL, by="test/model", why="w"),
                "b": FilledValue(value="y", filler=Filler.HAND, by="rafael", why="w"),
                "c": FilledValue(value="z", filler=Filler.DERIVED, by="nf-core", why="w"),
            },
            module=None,
        )
    )
    assert "test/model" in text and "rafael" in text and "nf-core" in text
