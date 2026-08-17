"""A Nextflow module for a source that does not ship one.

Everything here follows from the container and the process name. **The script body does
not, and it is a hole** — `MF0005`. A plausible command line would produce a module that
launches and does the wrong thing, and `-stub-run` cannot see a hollow input, so nothing
downstream would catch it either.

Deliberately a template string rather than Jinja: `mendel-compiler` owns the Jinja
templates for pipelines, and one module skeleton is not worth a second template loader
in a second package. If this grows a third shape, move it to Jinja and match
`emit.py`'s conventions — `{% endfor %}`, never `{%- endfor %}`.
"""

from comeni_core.diagnostics import coded

from mendel_forge.observe import Observation
from mendel_forge.scaffold import Scaffold

SCRIPT_HOLE = "// " + coded(
    "MF0005", "write the tool's command here, reading flags from task.ext.args"
)
"""The marker left in a generated `main.nf` where the command line belongs.

Built through `coded()` rather than written as a literal, for the reason the Global
Constraints give: a hand-typed code is one the ownership guard cannot tie to
`diagnostics.yml`. It caught this — `MF0005` was declared and the literal was invisible
to the scan, so `test_every_declared_code_is_emitted` went red. `verify.py` raises the
same code as a `Diagnostic` when it finds this marker still in place; this is the half
that puts it in the file.
"""


def needs_module(obs: Observation) -> bool:
    return obs.fact("nf_include") is None


def skeleton(scaffold: Scaffold) -> str:
    process = scaffold.filled["nf_process"].value
    container = scaffold.filled["container"].value
    tool = process.lower()
    return f"""process {process} {{
    tag "$meta.id"
    label 'process_medium'

    container "{container}"

    input:
    tuple val(meta), path(input)

    output:
    tuple val(meta), path("*.out"), emit: out
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
    touch ${{prefix}}.out

    cat <<-END_VERSIONS > versions.yml
    "${{task.process}}":
        {tool}: \\$(echo "unknown")
    END_VERSIONS
    \"\"\"
}}
"""
