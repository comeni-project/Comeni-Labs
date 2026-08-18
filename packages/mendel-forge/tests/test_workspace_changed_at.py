"""When a draft last moved.

The queue's maintenance view — "what changed since I last looked" — needs a time per draft,
and the workspace is the only thing that knows where a draft is stored.
"""

from datetime import UTC, datetime

import pytest
from mendel_forge.workspace import Workspace


def test_it_reports_when_the_draft_was_written(tmp_path):
    workspace = Workspace(root=tmp_path)
    directory = tmp_path / "fastqc"
    directory.mkdir()
    (directory / "draft.json").write_text("{}")

    got = workspace.changed_at("fastqc")

    assert got.tzinfo is not None, "a naive datetime cannot be compared with a stored visit"
    assert abs((datetime.now(UTC) - got).total_seconds()) < 60


def test_a_draft_that_is_not_there_is_a_refusal_rather_than_a_guess(tmp_path):
    """Returning `None` or epoch zero for a missing draft makes it look ancient, which in
    a "what changed" filter means it silently never appears."""
    with pytest.raises(ValueError, match="MF0008"):
        Workspace(root=tmp_path).changed_at("nothing")
