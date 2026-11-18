"""A tool's `KeyError` is a refusal only when the model named the missing key (#505).

Every `KeyError` used to come back to the model as a refusal, which hid a programming error
behind something that read like the engine declining."""

import pytest
from mendel_api.agent import tools
from pydantic import BaseModel


class _Args(BaseModel):
    contract: str


def _context():
    return tools.ToolContext(draft_id="d", session_id=None, who="t", expected_revision=0)


@pytest.fixture
def raising(monkeypatch):
    from contextlib import nullcontext

    from mendel_api.services import decisions

    monkeypatch.setattr(decisions, "revision", lambda draft_id: 0)
    monkeypatch.setattr(decisions, "expecting", lambda revision: nullcontext())

    def tool(error):
        def run(ctx, given):
            raise error
        monkeypatch.setitem(tools.TOOLS, "probe", tools.Tool(
            name="probe", description="", input=_Args, run=run))
    return tool


def test_a_key_the_model_named_is_a_refusal(raising):
    raising(KeyError("nf-core/nothing@1"))
    result = tools.call(_context(), "probe", {"contract": "nf-core/nothing@1"})
    assert not result.ok and "nf-core/nothing@1" in result.refusal


def test_a_coded_key_error_is_a_refusal(raising):
    raising(KeyError("MI0204: no such setting"))
    assert not tools.call(_context(), "probe", {"contract": "x"}).ok


def test_a_key_the_model_never_named_is_the_engines_error(raising):
    raising(KeyError("pieces"))
    with pytest.raises(KeyError, match="pieces"):
        tools.call(_context(), "probe", {"contract": "x"})
