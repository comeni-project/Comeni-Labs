"""A turn stored at shape 11 keeps the agent's blocks and the walk's words at shape 12 (#463)."""

import importlib.util

from mendel_api.authoring.types import parse_block
from support.paths import ROOT

PATH = ROOT / "packages/mendel-api/migrations/versions/e5a9c3f1b742_the_scripted_walk_goes.py"


def _upgrade():
    spec = importlib.util.spec_from_file_location("the_scripted_walk_goes", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.upgrade_pipeline_authoring_turn_11_to_12


def test_the_walks_words_become_messages_and_its_cards_go():
    old = [
        {"kind": "narrative", "id": "n1", "text": "Five steps; one needs you.", "refers_to": []},
        {"kind": "goal_summary", "id": "g1", "have": "reads", "do": "align", "get": "counts"},
        {"kind": "receipt", "id": "r1", "summary": "HISAT2 chosen", "revision": 3, "by": "person"},
        {"kind": "notice", "id": "p1", "notice": "pending", "text": "Working on it"},
        {"kind": "notice", "id": "x1", "notice": "refusal", "text": "No reply", "code": "MA0001"},
        {"kind": "message", "id": "m1", "text": "I chose STAR."},
        {"kind": "question", "id": "q1", "asks": "Paired?", "options": []},
    ]
    new = _upgrade()(old)
    assert new, "nothing kept: the conversion measures nothing"
    assert [(b["kind"], b["id"]) for b in new] == [
        ("message", "n1"), ("message", "r1"), ("message", "p1"), ("notice", "x1"),
        ("message", "m1")]
    for block in new:
        parse_block(block)


def test_a_turn_with_no_blocks_stays_empty():
    assert _upgrade()([]) == [] and _upgrade()(None) == []
