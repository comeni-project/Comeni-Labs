"""A role check nothing calls is a role check that does not exist.

`packages/comeni-core/tests/test_roles.py` exercises `RoleVocabulary.check` directly, which
proves the function works and proves nothing about whether anything *calls* it. Deleting the
loop in `layers.load()` left all four of those tests green — an inert guard in code written
the same hour, which is the shape A14 is about and the shape Plan 1.9 found three times.

So this file loads a real layer stack through the real loader, which is the only thing that
can fail when the call goes away.
"""

import pathlib
import shutil

import pytest
from comeni_core.roles import UnknownRoleError
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parents[3]
REGISTRY = ROOT / "registry"


def _registry_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    layer = tmp_path / "layer"
    shutil.copytree(REGISTRY, layer)
    return layer


def test_the_shipped_registry_loads_with_every_contract_classified():
    loaded = layers.load(REGISTRY)
    unclassified = [c.id for c in loaded.registry.all() if not c.roles]
    assert unclassified == [], f"these contracts fill no role: {unclassified}"


def test_a_contract_naming_an_undeclared_role_stops_the_build(tmp_path):
    """The typo a person actually makes: one transposed pair in a hand-typed key."""
    layer = _registry_copy(tmp_path)
    star = next(layer.rglob("star-align.yml"))
    star.write_text(star.read_text().replace("roles: [alignment]", "roles: [alignmnet]"))

    with pytest.raises(UnknownRoleError) as exc:
        layers.load(layer)
    message = str(exc.value)
    assert "MD0302" in message
    assert "alignmnet" in message
    assert "alignment" in message, "the message must name what does exist"


def test_a_role_declared_only_by_an_overlay_satisfies_a_base_contract(tmp_path):
    """Why the check runs after the whole stack is assembled rather than during parse.

    A laboratory may reclassify a base contract into a role only their layer declares. If
    the check ran inside `Registry.kind`'s parse it would see one layer at a time and refuse
    a stack that is in fact consistent.
    """
    base = _registry_copy(tmp_path)
    star = next(base.rglob("star-align.yml"))
    # Added rather than substituted. Since Task 4 the shipped `implementation: alignment`
    # rule refuses a row naming a contract that does not fill that role, so replacing
    # STAR's role here would make the fixture inconsistent and this test would fail for
    # `MD0306` rather than for anything it is about. That refusal is the point of Task 4 and
    # it found this fixture the hour it landed.
    star.write_text(
        star.read_text().replace("roles: [alignment]", "roles: [alignment, long_read_alignment]")
    )

    overlay = tmp_path / "lab"
    (overlay / "roles").mkdir(parents=True)
    (overlay / "roles" / "extra.yml").write_text("roles: [long_read_alignment]\n")

    loaded = layers.load([base, overlay])
    assert "long_read_alignment" in loaded.roles.names
    assert "long_read_alignment" in loaded.registry.get("nf-core/star/align@1.11.0").roles
