"""`mendel docs` writes a page per tool, and `--check` refuses a stale one.

`--check` is what `comeni-registry`'s CI runs on every pull request, so these are the tests
that stand between a contract edit and a documentation page that quietly disagrees with it.

comeni-registry#2.
"""


from mendel_compiler.cli import main
from support.paths import ROOT

REGISTRY = str(ROOT / "registry")

PAGES = [
    "comeni/profile.md",
    "nf-core/fastqc.md",
    "nf-core/hisat2.md",
    "nf-core/multiqc.md",
    "nf-core/samtools.md",
    "nf-core/star.md",
    "nf-core/subread.md",
    "nf-core/trimgalore.md",
]


def test_docs_writes_one_page_per_tool(tmp_path):
    assert main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)]) == 0
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.md"))
    assert written == PAGES


def test_check_passes_against_pages_just_written(tmp_path):
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)])
    assert main(["docs", "--registry", REGISTRY, "--out", str(tmp_path), "--check"]) == 0


def test_check_refuses_a_hand_edited_page(tmp_path, capsys):
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)])
    capsys.readouterr()
    page = tmp_path / "nf-core" / "star.md"
    page.write_text(page.read_text() + "\nhand written\n")
    assert main(["docs", "--registry", REGISTRY, "--out", str(tmp_path), "--check"]) == 1
    assert "star.md" in capsys.readouterr().out


def test_check_refuses_a_missing_page(tmp_path, capsys):
    """A deleted page and a stale page are the same failure to a reader, and neither may
    exit 0 — a check that passes on absence is how a whole directory goes missing quietly."""
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)])
    capsys.readouterr()
    (tmp_path / "nf-core" / "star.md").unlink()
    assert main(["docs", "--registry", REGISTRY, "--out", str(tmp_path), "--check"]) == 1
    assert "star.md" in capsys.readouterr().out


def test_check_refuses_a_page_for_a_tool_that_no_longer_exists(tmp_path, capsys):
    """The direction nothing else catches: a contract is removed, its page is not, and the
    page goes on describing a tool the registry no longer ships."""
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)])
    capsys.readouterr()
    (tmp_path / "nf-core" / "ghost.md").write_text("a tool that left\n")
    assert main(["docs", "--registry", REGISTRY, "--out", str(tmp_path), "--check"]) == 1
    assert "ghost.md" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path):
    """`--check` is a question. A check that repairs what it measures reports success the
    second time it runs and can never fail twice — which is how `make drift`'s "skipped"
    stayed green over twelve edited contracts."""
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path)])
    page = tmp_path / "nf-core" / "star.md"
    page.write_text("hand written\n")
    main(["docs", "--registry", REGISTRY, "--out", str(tmp_path), "--check"])
    assert page.read_text() == "hand written\n"


def test_docs_needs_an_out(capsys):
    """Every other writing verb says so; this one must not silently write into cwd."""
    code = None
    try:
        main(["docs", "--registry", REGISTRY])
    except SystemExit as exit_:
        code = exit_.code
    assert code == 2
    assert "--out" in capsys.readouterr().err


def test_docs_needs_a_registry(tmp_path, capsys):
    code = None
    try:
        main(["docs", "--out", str(tmp_path)])
    except SystemExit as exit_:
        code = exit_.code
    assert code == 2
    assert "--registry" in capsys.readouterr().err


def test_check_is_refused_on_a_verb_that_is_not_docs(tmp_path, capsys):
    """`--check` on `build` would silently mean nothing, which is the defect `--dry-run` and
    `--force` each carry a guard for."""
    code = None
    try:
        main(["build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
              "--out", str(tmp_path), "--check"])
    except SystemExit as exit_:
        code = exit_.code
    assert code == 2
    assert "--check" in capsys.readouterr().err
