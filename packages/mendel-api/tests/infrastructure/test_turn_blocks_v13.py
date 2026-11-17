"""A turn stored at shape 12 asks for `data` at shape 13, where it asked for an `upload` (#511)."""

import importlib.util

from mendel_api.authoring.types import parse_block
from support.paths import ROOT

PATH = ROOT / "packages/mendel-api/migrations/versions/a7d2c9e4f610_an_analysis_has_its_data.py"


def _upgrade():
    spec = importlib.util.spec_from_file_location("an_analysis_has_its_data", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.upgrade_pipeline_authoring_turn_12_to_13


def test_an_upload_question_becomes_a_data_question_and_nothing_else_moves():
    old = [
        {"kind": "message", "id": "m1", "text": "I need your reads."},
        {"kind": "ask", "id": "a1", "question_id": "q1", "question": "Your reads?",
         "shape": "upload", "options": [], "unit": "", "type_id": "fastq.reads"},
        {"kind": "ask", "id": "a2", "question_id": "q2", "question": "Paired?",
         "shape": "yes_no", "options": [], "unit": ""},
    ]
    new = _upgrade()(old)
    assert [b.get("shape") for b in new] == [None, "data", "yes_no"]
    assert new[0] == old[0] and new[2] == old[2]
    for block in new:
        parse_block(block)


def test_no_blocks_stay_no_blocks():
    assert _upgrade()(None) == [] and _upgrade()([]) == []
