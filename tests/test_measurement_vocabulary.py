"""Every declared measurement says whether anything can measure it. Issue #38.

*"A measurement is a claim that some property of the data is worth measuring **and can be**"*,
and the second half was invisible. A profiling contract produces a `measurement.<id>` type, so
the answer was always derivable from the registry — but nothing stated it, so a measurement
nobody could produce looked exactly like one somebody had wired a tool for, and a rule keyed on
it looked exactly as sound.

**This does not close the drafter half of #38.** Nothing drafts measurements, and the issue's
sharpest observation is that the drafter question and the measuring question are the same one:
a contract can be drafted from a module's `meta.yml` because the module is ground truth, and a
measurement has no equivalent source document. That is Plan 2's forge. What is closed here is
the floor: the vocabulary derived from twenty real rules, each cited, each declaring whether a
tool exists for it.
"""

import pathlib

from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def _loaded():
    return layers.load(ROOT / "registry")


def _measured_by(loaded) -> set[str]:
    """Every measurement some contract in the stack actually produces."""
    return {
        port.type_id.removeprefix("measurement.")
        for contract in loaded.registry.all()
        for port in contract.produces
        if port.type_id.startswith("measurement.")
    }


def test_every_measurement_declares_whether_a_tool_can_produce_it():
    """The declaration and the registry must agree. Declared rather than derived — even
    though it is derivable — because *"we have not wired a tool for this yet"* is a statement
    somebody should have to make, and the registry is data a curator approves."""
    loaded = _loaded()
    measurable = _measured_by(loaded)
    wrong = []
    for name in loaded.measurements.ids():
        measurement = loaded.measurements.get(name)
        if measurement.assertion_only and name in measurable:
            wrong.append(f"{name}: declares `assertion_only` and a contract produces it")
        if not measurement.assertion_only and name not in measurable:
            wrong.append(
                f"{name}: nothing in this stack produces `measurement.{name}`, so a goal can "
                f"only assert it — declare `assertion_only: true` and say why"
            )
    assert wrong == [], "the vocabulary and the registry disagree:\n  " + "\n  ".join(wrong)


def test_every_measurement_cites_something():
    """A measurement is domain judgement, and a claim about the world with no source is the
    shape `MD0301` refuses in a rule. The same standard, one layer down."""
    loaded = _loaded()
    uncited = [
        name for name in loaded.measurements.ids() if not loaded.measurements.get(name).cite
    ]
    assert uncited == [], (
        "these measurements assert that a property is worth measuring and name no source:\n  "
        + "\n  ".join(uncited)
    )


def test_every_measurement_describes_what_it_is_about():
    """`describes` says which type a measurement is a property of, and a measurement that
    describes nothing is a property of the study. Both are legitimate; being unable to tell
    which is not, because only the first can be carried into a module's `meta` map."""
    loaded = _loaded()
    for name in loaded.measurements.ids():
        measurement = loaded.measurements.get(name)
        if measurement.meta_key:
            assert measurement.describes, (
                f"{name} declares a `meta_key` and describes nothing — it would be carried "
                f"into the meta map of a thing it is not a property of"
            )
