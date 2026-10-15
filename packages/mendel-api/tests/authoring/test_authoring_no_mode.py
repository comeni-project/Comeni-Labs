"""Build and Spawn are retired (spec §13.1): one consultant build, tier 4 always stops."""

import importlib
import inspect

import pytest


def test_mode_is_gone_from_the_api():
    from mendel_api.authoring import types

    assert not hasattr(types, "Mode")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("mendel_api.services.spawn")


def test_resolving_takes_no_mode():
    from mendel_api.services import blueprint as bp

    assert "mode" not in inspect.signature(bp.resolve).parameters


def test_a_request_still_naming_a_mode_is_refused():
    """Review Focus 5: an old body is refused by name, not quietly accepted."""
    from mendel_api.routes.authoring import BeginAuthoring
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="mode"):
        BeginAuthoring.model_validate({"prompt": "RNA-seq counts", "mode": "spawn"})
    assert BeginAuthoring.model_validate({"prompt": "RNA-seq counts"})
