"""The grain migration (#466) renames a stored channel's `scope` and reads `run` as `study`."""

import importlib.util

from support.paths import ROOT

_PATH = ROOT / "packages/mendel-api/migrations/versions/e6c4a2f8b913_grain.py"
_spec = importlib.util.spec_from_file_location("grain_migration", _PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_a_drawn_channel_scope_becomes_its_grain():
    graph = {"nodes": [], "channels": [{"scope": "run", "why": "one per study", "ports": ["a.b"]},
                                       {"scope": "sample", "ports": ["c.d"]}]}
    assert migration.upgrade_pipeline_draft_2_to_3(graph)["channels"] == [
        {"grain": "study", "why": "one per study", "ports": ["a.b"]},
        {"grain": "sample", "ports": ["c.d"]},
    ]


def test_a_resolved_scope_in_a_preview_keeps_its_provenance():
    previews = [{"ir": {"channels": [{"name": "gtf", "scope": {"value": "run", "tier": 1}}]}}]
    upgraded = migration.upgrade_pipeline_authoring_proposal_4_to_5(previews)
    assert upgraded == [{"ir": {"channels": [{"name": "gtf",
                                               "grain": {"value": "study", "tier": 1}}]}}]


def test_nothing_else_moves_and_none_stays_none():
    assert migration.upgrade_pipeline_draft_2_to_3(None) is None
    unrelated = {"nodes": [{"id": "x", "params": [{"name": "scope_x", "value": "run"}]}]}
    assert migration.upgrade_pipeline_draft_2_to_3(unrelated) == unrelated


def test_the_downgrade_restores_the_old_names():
    graph = {"channels": [{"scope": "run"}]}
    up = migration.upgrade_pipeline_draft_2_to_3(graph)
    assert migration._renamed(up, "grain", "scope", migration._DOWN) == graph


_PATH_2 = (ROOT / "packages/mendel-api/migrations/versions"
           / "b3d9f5a1c7e2_grain_blueprints_and_forge.py")
_spec_2 = importlib.util.spec_from_file_location("grain_migration_2", _PATH_2)
second = importlib.util.module_from_spec(_spec_2)
_spec_2.loader.exec_module(second)


def test_a_session_saved_before_grain_still_opens():
    """A blueprint is a whole `pipeline.yml`; one at version 8 is refused by today's reader, so
    the session holding it would not open (Task 1 review)."""
    import json

    from mendel_authoring.blueprint import Blueprint

    old = json.loads((ROOT / "packages/mendel-api/tests/fixtures/blueprint-v8.json").read_text())
    upgraded = second.upgrade_pipeline_authoring_session_1_to_2(old)
    blueprint = Blueprint.model_validate(upgraded)
    assert {c.grain.value for c in blueprint.pipeline.channels} == {"study", "sample"}


def test_a_forged_type_and_port_take_grain():
    assert second.upgrade_forge_revision_1_to_2(
        {"id": "genome.fasta", "states": [], "scope": "run"}) == {
        "id": "genome.fasta", "states": [], "grain": "study"}
    assert second.upgrade_forge_revision_1_to_2(
        {"name": "reports", "type_id": "qc.report", "cardinality": "*"}) == {
        "name": "reports", "type_id": "qc.report", "grain": "study", "many": True}
    assert second.upgrade_forge_revision_1_to_2(
        {"name": "reads", "type_id": "fastq.reads", "cardinality": "1"}) == {
        "name": "reads", "type_id": "fastq.reads"}
