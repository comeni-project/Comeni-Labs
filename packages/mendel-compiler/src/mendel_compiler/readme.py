"""The README a downloaded pipeline carries: what it is, and how to run its test (#619).

Derived from `pipeline.yml` alone, like everything else in the bundle, and the same bytes for
the same pipeline: no clock, no paths, no samples. The test it describes is the `test` profile
the emitted config already holds, so this page cannot promise a test the config does not offer;
when an input type declares no public example it says which, and the config's own comment
says the same.
"""

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.tiers import InputForm

from mendel_compiler.emit import TEST_SAMPLESHEET, entry_params, test_profile_missing

DECISIONS = "decisions.html"
"""The decisions report beside this README in the bundle."""


def render(pipeline: Pipeline) -> str:
    """The README's Markdown."""
    produces = ", ".join(f"`{t}`" for t in pipeline.intent.want) or "nothing named"
    lines = [
        "# A pipeline built with Comeni Labs",
        "",
        f"It produces {produces}. Its steps, in order:",
        "",
        *[f"- `{step.id}`: `{step.module.contract_id}`" for step in pipeline.steps],
        "",
        f"Every choice behind it, who made it and why, is in `{DECISIONS}`: open it in a",
        "browser, and print it to keep a PDF. `pipeline.yml` is the same record as data.",
        "",
        "## Run its test",
        "",
        *_test(pipeline),
        "",
        "## Run it on your data",
        "",
        "```bash",
        f"nextflow run . -profile docker {_your_inputs(pipeline)} --outdir results",
        "```",
        "",
        "You need Nextflow and Docker. The curated tools are reference material for a laboratory",
        "to validate; this pipeline is not a validated clinical test.",
        "",
    ]
    return "\n".join(lines)


def _test(pipeline: Pipeline) -> list[str]:
    missing = test_profile_missing(pipeline)
    if missing:
        return [
            "This pipeline has no runnable test: no public example data is declared for "
            + ", ".join(f"`{name}`" for name in missing) + ".",
        ]
    sheet = (f" `{TEST_SAMPLESHEET}` lists them, one sample."
             if pipeline.input_form is InputForm.SAMPLESHEET else "")
    return [
        "A small public dataset, pinned to a commit, is downloaded when the test runs." + sheet,
        "It shows the pipeline runs end to end; it does not show the analysis is correct.",
        "",
        "```bash",
        "nextflow run . -profile test,docker --outdir results",
        "```",
    ]


def _your_inputs(pipeline: Pipeline) -> str:
    if pipeline.input_form is InputForm.SAMPLESHEET:
        return "--input <your-samplesheet.csv>"
    return " ".join(f"--{name} <{name}>" for name in entry_params(pipeline))
