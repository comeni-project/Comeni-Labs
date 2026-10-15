"""`Blueprint` and `committed` live in the pure core; the shell only re-exports them."""

import pytest
from pydantic import ValidationError


def test_the_shell_reexports_the_blueprint_it_no_longer_owns():
    from mendel_api.services import blueprint as shell
    from mendel_authoring import blueprint as core

    assert shell.Blueprint is core.Blueprint
    assert shell.committed is core.committed


def test_a_blueprint_has_no_mode():
    """Nothing read it: every Build/Spawn branch reads the session row's mode."""
    from mendel_authoring.blueprint import Blueprint

    assert "mode" not in Blueprint.model_fields


def test_a_stored_blueprint_still_holding_mode_is_refused_until_migrated(rnaseq):
    """Why the migration exists: `extra="forbid"` refuses the old key."""
    from mendel_authoring.blueprint import Blueprint

    stored = rnaseq(read_length=150).model_dump(mode="json") | {"mode": "build"}
    with pytest.raises(ValidationError):
        Blueprint.model_validate(stored)
