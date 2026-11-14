"""Proposal shape 10 (#485): each port in a stored preview gains `accepts`, empty."""

import importlib.util

from support.paths import ROOT

_PATH = ROOT / "packages/mendel-api/migrations/versions/b7e3c1d9f046_accepted_types_on_ports.py"
_spec = importlib.util.spec_from_file_location("accepts_migration", _PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_each_stored_port_gains_an_empty_accepts():
    previews = [{"steps": [{"process": "QUAST", "settings": [],
                            "ports": [{"name": "fasta", "type_id": "genome.fasta"}]}]}]
    (step,) = migration.upgrade_pipeline_authoring_proposal_9_to_10(previews)[0]["steps"]
    assert step["ports"] == [{"accepts": [], "name": "fasta", "type_id": "genome.fasta"}]
    assert migration.upgrade_pipeline_authoring_proposal_9_to_10(None) is None
