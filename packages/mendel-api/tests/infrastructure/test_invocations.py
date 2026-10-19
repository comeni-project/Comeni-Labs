"""The vocabulary every recorded model call is written in (forge MVP part 0, #361).

It moved out of the old forge's `workflow.py` unchanged. A value lost in the move would break
`ai_invocation`'s check constraint when a call is recorded, not when the module is imported,
so the values are pinned here.
"""

from mendel_api.invocations import Agent, InvocationPurpose, InvocationState


def test_the_agents_are_the_builder_and_the_forge():
    assert {a.value for a in Agent} == {"builder", "forge"}


def test_the_forge_purposes_are_unchanged():
    assert {p.value for p in InvocationPurpose} == {"analysis", "implementation", "repair", "chat"}


def test_the_call_states_are_unchanged():
    assert {s.value for s in InvocationState} == {"queued", "running", "succeeded", "failed", "refused"}
