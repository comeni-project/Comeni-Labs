import json

from mendel_forge.cli import main


def test_sources_lists_nf_core(capsys):
    assert main(["sources"]) == 0
    assert "nf-core" in capsys.readouterr().out


def test_json_output_is_the_result_model_verbatim(capsys, tmp_path):
    code = main(
        [
            "--json",
            "draft",
            "nf-core:fastqc",
            "--name",
            "fastqc",
            "--version",
            "0.12.1",
            "--workspace",
            str(tmp_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "fastqc"
    assert isinstance(payload["holes"], list)


def test_a_refusal_exits_nonzero_and_points_at_forge_explain(capsys, tmp_path):
    code = main(["draft", "nonesuch:x", "--name", "x", "--workspace", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert "MF0001" in err
    assert "forge explain MF0001" in err


def test_explain_prints_the_long_form(capsys):
    """`explain` renders the code and its `explanation`, and nothing else.

    Not `says` and not `fix` — that is `comeni_core.diagnostics.explain`'s behaviour for
    every code in the project, so this asserts against it rather than against what the
    plan guessed it printed. Whether `fix:` belongs in the long form is a question about
    every MD code at once, not something the forge should answer on its own.
    """
    assert main(["explain", "MF0004"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("MF0004")
    assert "a half-built contract" in out


def test_show_renders_every_hole_with_its_reason(capsys, tmp_path):
    main(["draft", "nf-core:fastqc", "--name", "f", "--version", "0.12.1",
          "--workspace", str(tmp_path)])
    main(["show", "f", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out
    assert "roles" in out
    assert "a module declares no role" in out, "a hole prints why it is open, not just its name"


def test_the_cli_refuses_to_land_without_an_explicit_registry(capsys, tmp_path):
    """Exit 2, argparse's own code for a missing required argument — not a diagnostic.
    There is nothing for `forge explain` to say about a flag you did not type."""
    import pytest

    with pytest.raises(SystemExit) as caught:
        main(["land", "fastqc", "--workspace", str(tmp_path), "--by", "rafael"])
    assert caught.value.code == 2
    assert "--registry" in capsys.readouterr().err
