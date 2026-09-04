"""A Nextflow module for a source that does not ship one.

Everything here follows from the container and the process name. **Three things do not, and all
three are marked** — the script body (`MF0005`), the input block and the output block
(`MF0011`). A generated module carrying any of those markers is a draft, and `open_sections`
is what lets a validation rung say so rather than hoping somebody reads the file.

**The input and output markers are new, and they replace a guess that had shipped.** The
skeleton used to declare exactly one input — `tuple val(meta), path(input)` — and exactly one
output, `path("*.out")`. Neither was read from anything. For a PEGiS image that takes a
reference and a query, or emits three files, both are simply wrong, and they are wrong in the
way this project exists to avoid: they look like facts. `-stub-run` cannot see a hollow input
and a stub never reads what it is given, so a module with the wrong arity is exactly as green
as a module with the right one, and the first honest signal is a real run on real data.

**The placeholders still parse.** `ModuleSpec` reads four shapes and raises on a fifth, and a
skeleton that could not be parsed could not be checked by conformance at all — so the markers
are comments beside a declaration rather than instead of one. What changed is that the
declaration is now labelled as unverified, and something can refuse it.

Deliberately a template string rather than Jinja: `mendel-compiler` owns the Jinja templates for
pipelines, and one module skeleton is not worth a second template loader in a second package. If
this grows a third shape, move it to Jinja and match `emit.py`'s conventions — `{% endfor %}`,
never `{%- endfor %}`.
"""

from comeni_core.diagnostics import coded

from mendel_forge.observe import Observation
from mendel_forge.scaffold import Scaffold

SCRIPT_HOLE = "// " + coded(
    "MF0005", "write the tool's command here, reading flags from task.ext.args"
)
"""The marker left where the command line belongs.

Built through `coded()` rather than written as a literal, for the reason the Global Constraints
give: a hand-typed code is one the ownership guard cannot tie to `diagnostics.yml`. It caught
this — `MF0005` was declared and the literal was invisible to the scan, so
`test_every_declared_code_is_emitted` went red.
"""

INPUT_HOLE = "// " + coded(
    "MF0011", "one channel is a placeholder — declare what this tool actually consumes"
)
"""The marker over a guessed input block.

**One code for both blocks, not two.** The fix is identical — read the tool's documentation and
declare what it takes — and a code is something a laboratory runbook cites, so splitting one
remedy across two codes makes a runbook longer without making it more precise. The message says
which block.
"""

OUTPUT_HOLE = "// " + coded(
    "MF0011", "one emit is a placeholder — declare what this tool actually produces"
)

OPEN_SECTIONS: tuple[str, ...] = (SCRIPT_HOLE, INPUT_HOLE, OUTPUT_HOLE)
"""Every marker a generated module can carry, for something that has to find them all.

**A tuple rather than three constants each importer remembers.** A rung that scanned for two of
three would pass a module whose outputs were still a guess, and it would pass silently — which
is the shape of defect the whole marker scheme exists to prevent.
"""


def open_sections(module: str) -> tuple[str, ...]:
    """Which markers are still in this module's text.

    Returned rather than asserted, because the caller decides what an open section means:
    `verify` reports it, `land` refuses it, and a page draws it as a hole. A function that
    raised would make all three callers catch to ask a question.
    """
    return tuple(marker for marker in OPEN_SECTIONS if marker in module)


def needs_module(obs: Observation) -> bool:
    return obs.fact("nf_include") is None


def skeleton(scaffold: Scaffold) -> str:
    process = scaffold.filled["nf_process"].value
    container = scaffold.filled["container"].value
    return module_text(process=process, container=container)


def module_text(*, process: str, container: str) -> str:
    """The skeleton, from the two facts a source can actually prove.

    Split out from `skeleton` so the bundle path can call it without building a `Scaffold`
    first — the new path holds a `CatalogueItem` and a hole manifest, and constructing the old
    scaffold shape to reach one template would be a conversion that exists only to satisfy a
    signature.
    """
    tool = process.lower()
    return f"""process {process} {{
    tag "$meta.id"
    label 'process_medium'

    container "{container}"

    input:
    {INPUT_HOLE}
    tuple val(meta), path(input)

    output:
    {OUTPUT_HOLE}
    tuple val(meta), path("*"), emit: out
    path "versions.yml",           emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${{meta.id}}"
    \"\"\"
    {SCRIPT_HOLE}

    cat <<-END_VERSIONS > versions.yml
    "${{task.process}}":
        {tool}: \\$(echo "unknown")
    END_VERSIONS
    \"\"\"

    stub:
    def prefix = task.ext.prefix ?: "${{meta.id}}"
    \"\"\"
    touch ${{prefix}}.placeholder

    cat <<-END_VERSIONS > versions.yml
    "${{task.process}}":
        {tool}: \\$(echo "unknown")
    END_VERSIONS
    \"\"\"
}}
"""
