import json
import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def _goal_file(tmp_path):
    path = tmp_path / "g.yml"
    path.write_text("have: [{type_id: fastq.reads}]\nwant: [measurement.read_length]\n")
    return path


def test_profile_emits_a_pipeline_that_measures(tmp_path):
    code = main([
        "profile", "--have", "fastq.reads",
        "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ])
    assert code == 0
    source = (tmp_path / "p" / "main.nf").read_text()
    assert "FASTQC" in source


def test_profile_is_the_same_operation_as_a_measurement_build(tmp_path):
    """`mendel profile` is sugar. One resolver, one emitter, one set of records."""
    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "a"), "--root", str(ROOT)])
    main([
        "build", "--goal", str(_goal_file(tmp_path)),
        "--out", str(tmp_path / "b"), "--root", str(ROOT),
    ])
    assert (tmp_path / "a" / "main.nf").read_text() == (tmp_path / "b" / "main.nf").read_text()


def test_a_profiling_build_resolves_against_an_empty_profile(tmp_path):
    """Otherwise profiling needs a profile, which is the regress this rule stops."""
    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    tiers = {b["value"]["tier"] for n in ir["nodes"] for b in n["params"]}
    tiers |= {n["selection"]["tier"] for n in ir["nodes"]}
    assert 3 not in tiers, "a profiling build must not resolve anything at tier 3"


def test_profile_wants_only_measurements_something_can_produce(tmp_path, capsys):
    """`paired` and `strandedness` are declared but nothing in this registry measures them.

    Wanting every declared measurement would make `mendel profile` unroutable the moment
    a laboratory declares one it has no tool for — which is the normal case, since
    declaring a measurement is how you start. What it cannot reach it names, rather than
    dropping silently.
    """
    assert main([
        "profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ]) == 0
    err = capsys.readouterr().err
    assert "read_length" in err
    assert "paired" in err and "strandedness" in err


def test_a_registry_with_no_profiling_contract_says_so(tmp_path, capsys):
    """Emitting an empty pipeline would look like success and measure nothing."""
    layer = tmp_path / "bare"
    (layer / "measurements").mkdir(parents=True)
    (layer / "measurements" / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    assert main([
        "profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"),
        "--root", str(ROOT), "--registry", str(layer),
    ]) == 2
    assert "nothing can measure" in capsys.readouterr().err


def test_a_generated_profile_records_its_tool(tmp_path):
    import yaml

    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    profile = yaml.safe_load((tmp_path / "p" / "profile.yml").read_text())
    entry = next(m for m in profile["measurements"] if m["measurement"] == "read_length")
    assert entry["source"] == "measured"
    assert entry["by"].startswith("comeni/profile/")


def test_a_generated_profile_claims_no_value_it_has_not_seen(tmp_path):
    """The pipeline has been emitted, not run. Anything else would be Mendel reporting a
    number it has never looked at, which is what invariant 15 exists to prevent."""
    import yaml

    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    profile = yaml.safe_load((tmp_path / "p" / "profile.yml").read_text())
    assert all(m["value"] is None for m in profile["measurements"])


def test_the_emitted_profile_is_a_profile_mendel_will_accept_back(tmp_path):
    """The round trip is the point: measure, fill the values in, build against them."""
    import yaml
    from comeni_core.measurement import MeasurementRegistry
    from mendel_resolver.goal import DataProfile

    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    raw = yaml.safe_load((tmp_path / "p" / "profile.yml").read_text())
    for measurement in raw["measurements"]:
        measurement["value"] = 150
    profile = DataProfile.model_validate(raw)
    assert profile.get("read_length") == 150
    MeasurementRegistry.load(ROOT / "examples" / "measurements").profile(
        {m.measurement: m.value for m in profile.measurements}
    )


def test_a_hand_written_profile_is_asserted():
    """A scalar in a file a person wrote is an assertion by that person."""
    from comeni_core.tiers import ValueSource
    from mendel_resolver.goal import DataProfile

    assert DataProfile(read_length=150).measurements[0].source is ValueSource.GOAL


def test_profiling_from_an_input_the_measurer_cannot_reach_fails_clearly(tmp_path, capsys):
    """`--have annotation.gtf` cannot feed FASTQC, and the message says which port."""
    assert main([
        "profile", "--have", "annotation.gtf", "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ]) == 2
    err = capsys.readouterr().err
    assert "nothing produces fastq.reads" in err
    # One alternative, so the message is stated once rather than once per routing level.
    assert err.count("cannot route this goal") == 1
