"""The builder agent's Data tools (#511): it reads what the data holds by name and fact, never a
path or a file's contents; what it changes is marked AI, with its reason, until a person keeps
it."""

import pytest
from mendel_api.agent.data import ApplyFixArgs, RuleArgs, apply_fix, read_data, set_reading_rule
from mendel_api.agent.tools import TOOLS, Nothing, ToolContext
from mendel_api.services.data import scan as scanning
from mendel_api_tests.building import clean as clean  # noqa: F401
from mendel_api_tests.data import PAIR, draft, pairs, tick, view
from mendel_api_tests.data import client as client  # noqa: F401
from mendel_api_tests.data import root as root  # noqa: F401
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def demo(client, root):
    d = draft(client)
    folder = pairs(root / "demo", "Y1", "Y2")
    (folder / "Y4_R1.fastq.gz").write_bytes(PAIR[0].read_bytes())
    (folder / "Y4_2.fq.gz").write_bytes(PAIR[1].read_bytes())
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    return d, ToolContext(draft_id=d, session_id=None, who="ana", expected_revision=0)


def test_the_tools_are_registered():
    assert {"read_data", "set_reading_rule", "apply_fix"} <= set(TOOLS)


def test_read_data_returns_names_and_facts_not_contents(clean, client, root):
    d, ctx = demo(client, root)
    got = read_data(ctx, Nothing())
    assert got.samples == ["Y1", "Y2", "Y4_2", "Y4_R1"] and got.kinds == ["fastq.reads"]
    [check] = got.checks
    assert (check.sample, check.kind, check.file) == ("Y4_R1", "missing_mate", "Y4_2.fq.gz")
    assert str(root) not in got.model_dump_json(), "no path reaches the model"


def test_set_reading_rule_is_ai_and_unconfirmed(clean, client, root):
    d, ctx = demo(client, root)
    set_reading_rule(ctx, RuleArgs(pattern="{sample}_R{read}.fastq.gz",
                                   because="names end _R1/_R2"))
    rule = view(client, d)["rule"]
    assert rule == {"pattern": "{sample}_R{read}.fastq.gz", "origin": "ai", "confirmed": False,
                    "reason": "names end _R1/_R2"}


def test_apply_fix_records_ai_with_reason(clean, client, root):
    d, ctx = demo(client, root)
    apply_fix(ctx, ApplyFixArgs(kind="use_file", sample="Y4_R1", file="Y4_2.fq.gz",
                                because="same stem, read 2"))
    [fix] = view(client, d)["fixes"]
    assert (fix["by"], fix["reason"]) == ("ai", "same stem, read 2")


def test_read_data_names_the_references_by_kind(clean, client, root):
    """#531 (walk 2026-11-16): the genome and annotation were set, and the agent said the Data
    page 'shows only the five assemblies'. References reach it by kind, never by path."""
    d, ctx = demo(client, root)
    ref = root / "ref"
    ref.mkdir()
    (ref / "genome.fasta").write_text(">chrI\nACGT\n")
    added = client.post(f"/api/data/{d}/references",
                        json={"path": str(ref / "genome.fasta"), "type_id": "genome.fasta"})
    assert added.status_code == 200
    got = read_data(ctx, Nothing())
    assert got.references == ["genome.fasta"]
    assert str(root) not in got.model_dump_json()
