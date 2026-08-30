"""The gloss says what happened, never why. §18.1."""

import pathlib

from wiener_core.signals import signal_of


def test_the_convention_and_only_the_convention():
    assert signal_of(137) == "SIGKILL"
    assert signal_of(143) == "SIGTERM"
    assert signal_of(0) is None
    assert signal_of(1) is None, "an ordinary failure is not a signal"
    assert signal_of(None) is None


def test_an_unnamed_signal_is_absent_rather_than_invented():
    """`"signal 43"` reads as knowledge. Absence reads as absence."""
    assert signal_of(128 + 43) is None


def test_it_never_names_a_cause():
    """**The tempting sentence, held out by a scan.**

    *Killed by the OOM killer* is what a reader wants under a 137 and it is an inference — a
    scheduler preemption, a `kill -9` and a cgroup limit are the same code. A verdict added
    here would be W3 arriving early and unlabelled, so the words are refused by name rather
    than by discipline.
    """
    source = pathlib.Path(signal_of.__module__.replace(".", "/"))
    text = (pathlib.Path(__file__).parents[1] / "src" / f"{source}.py").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    body = code.split('"""', 2)[-1]  # past the module docstring, which discusses these words

    # Words that name a CAUSE, not words that explain a design. "because" was in this list
    # for one run and caught the sentence explaining why an unnamed signal is absent — a scan
    # broad enough to hit its own rationale is a scan that gets deleted rather than obeyed.
    for forbidden in ("oom", "out of memory", "ran out", "killed by", "caused by",
                      "exceeded", "the reason"):
        assert forbidden not in body.lower(), f"the gloss names a cause: {forbidden!r}"
