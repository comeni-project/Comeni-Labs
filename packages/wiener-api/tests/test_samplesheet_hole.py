"""`params.input` is one null whether it is a glob or a CSV, so the form has to be told.

Plan 5B §5.3, and the asymmetry is the finding.

**Two same-type channels work here by construction and needed nothing.** `declared_holes` reads
the artifact's *nulls*, so `params.gtf` and `params.gtf_2` are two nulls, the run sheet asks for
two files, and this side never had to learn what a channel is.

**The samplesheet does not.** `params.input` is one null either way, so without `input_form` the
form asks the same question for a glob and for a table — somebody answers with the wrong kind of
thing, the run fails inside Nextflow minutes later, and the one place that could have said so is
the form that asked.
"""

import json
import pathlib

from wiener_api.services.artifacts import input_shape
from wiener_api.services.launcher import _materialise_tables
from wiener_api.settings import settings

HERE = pathlib.Path(__file__).parent


def _artifact(tmp_path, body: str) -> str:
    settings.artifact_root = tmp_path
    (tmp_path / "a1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "a1" / "pipeline.yml").write_text(body)
    return "a1"


def _pipeline(form: str, channels: str) -> str:
    return f"""version: 6
goal: {{have: [], want: [], constraints: {{}}, profile: {{measurements: []}}}}
registry: {{layers: [], displaced: [], unverified: []}}
ai: {{available: [], used: []}}
steps: []
channels:
{channels}
input_form: {form}
decisions: []
emitted: null
gate: null
"""


def _channel(name: str, param: str, scope: str, columns: list[str]) -> str:
    cols = "".join(f"\n    - {c}" for c in columns) or " []"
    return (
        f"- name: {name}\n  param: {param}\n  scope: {scope}\n"
        f"  columns:{cols}\n  type_id: a.b\n  params: [{param}]\n"
        f"  expression: \"Channel.of(params.{param})\"\n  meta: []\n  test_data: []\n"
    )


def test_a_direct_pipeline_says_so(tmp_path):
    """The glob case, which is every pipeline this repository has ever emitted."""
    body = _pipeline("direct", _channel("reads", "input", "sample", []))
    assert input_shape(_artifact(tmp_path, body)) == ("direct", [])


def test_a_samplesheet_pipeline_names_its_columns(tmp_path):
    """What the run sheet needs to render a table rather than a path box."""
    body = _pipeline(
        "samplesheet",
        _channel("reads", "input", "sample", ["reads_1", "reads_2"])
        + _channel("gtf", "gtf", "sample", ["gtf"]),
    )
    form, columns = input_shape(_artifact(tmp_path, body))
    assert form == "samplesheet"
    assert columns == ["gtf", "reads_1", "reads_2"]


def test_a_run_scoped_channel_contributes_no_column(tmp_path):
    """A reference is one file for the whole analysis. It keeps its own `params.<name>` — one
    more null the form already asks about — and has no place in a per-sample table."""
    body = _pipeline(
        "samplesheet",
        _channel("reads", "input", "sample", ["reads_1", "reads_2"])
        + _channel("gtf", "gtf", "sample", ["gtf"])
        + _channel("fasta", "fasta", "run", ["fasta"]),
    )
    _, columns = input_shape(_artifact(tmp_path, body))
    assert "fasta" not in columns


def test_an_unreadable_artifact_says_direct_rather_than_failing(tmp_path):
    """Same posture as `pipeline_digest`: an artifact with no readable `pipeline.yml` is a thing
    somebody uploaded, and refusing to describe it is worse than saying nothing."""
    settings.artifact_root = tmp_path
    (tmp_path / "gone").mkdir()
    assert input_shape("gone") == ("direct", [])


def test_a_submitted_table_becomes_a_csv_in_the_workdir(tmp_path):
    """**Wiener writes it and Mendel never sees it.** A samplesheet is sample identifiers and
    paths — data — and Wiener is the half that launches runs and is allowed to hold it.

    Into the **workdir**, never a table: `docs/design/wiener.md` §7.1 says no table holds a
    samplesheet, and a workdir is transient and deleted with the run.
    """
    rows = [
        {"sample": "A", "reads_1": "/lab/a_1.fq", "reads_2": "/lab/a_2.fq"},
        {"sample": "B", "reads_1": "/lab/b_1.fq", "reads_2": "/lab/b_2.fq"},
    ]
    written = _materialise_tables({"input": rows, "fasta": "/lab/ref.fa"}, tmp_path)

    assert written["fasta"] == "/lab/ref.fa", "a plain path must pass through untouched"
    csv = pathlib.Path(str(written["input"]))
    assert csv.parent == tmp_path
    assert csv.read_text() == (
        "sample,reads_1,reads_2\n"
        "A,/lab/a_1.fq,/lab/a_2.fq\n"
        "B,/lab/b_1.fq,/lab/b_2.fq\n"
    )


def test_a_path_is_still_accepted_for_the_samplesheet(tmp_path):
    """A laboratory that already has a samplesheet gives its path. The table editor is a
    convenience over that, not a gate in front of it."""
    written = _materialise_tables({"input": "/lab/samples.csv"}, tmp_path)
    assert written == {"input": "/lab/samples.csv"}
    assert not list(tmp_path.glob("*.csv"))


def test_the_csv_is_json_serialisable_after_materialising(tmp_path):
    """`launch` writes `params.json` from this, so a value that survives here and not there
    would fail at the last step with a message about JSON."""
    rows = [{"sample": "A", "gtf": "/lab/a.gtf"}]
    written = _materialise_tables({"input": rows}, tmp_path)
    assert json.loads(json.dumps(written))["input"].endswith("input.csv")
