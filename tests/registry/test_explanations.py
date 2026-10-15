"""Every question the shipped registry can ask says what it is about (Part I.1 §3).

A test of our own data, not a rule a lab's layer must pass: a lab's type with no explanation
still loads, and its question shows the engine's half alone."""

from mendel_api.services import gaps, registry


def _askable():
    stack = registry.stack()
    found = {}
    for type_id in sorted(stack.vocabulary.types):
        result = gaps.gaps([type_id], [], stack)
        if isinstance(result, gaps.Unreachable):
            continue
        for gap in result:
            found[(gap.kind.value, gap.subject)] = gap
    assert found, "no want in the shipped registry produced a gap — measuring nothing"
    return stack, found


def test_every_declared_type_has_a_name():
    """`measurement.<id>` types are derived from measurements (`with_measurements`), not
    declared in a file; a measurement's name is its description."""
    stack = registry.stack()
    declared = {t for t in stack.vocabulary.types if not t.startswith("measurement.")}
    assert declared, "no declared type — measuring nothing"
    assert sorted(declared - set(stack.vocabulary.names)) == []


def test_every_question_the_registry_can_ask_is_explained():
    stack, found = _askable()
    missing = [subject for (kind, subject) in found
               if (kind == "input" and subject not in stack.vocabulary.explains)
               or (kind == "measurement" and not stack.measurements.get(subject).explain)]
    assert missing == []
