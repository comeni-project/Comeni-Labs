"""IR to Nextflow DSL2. Deterministic: same IR, byte-identical output."""

from pathlib import Path
from typing import NamedTuple

from comeni_core.artifact.pipeline import Pipeline, Step
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import substitutable
from comeni_core.spell.routes import Join, Via
from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).parent / "templates"


class _ParamView(NamedTuple):
    """What the template needs from a resolved parameter.

    Was an anonymous `type("V", (), {...})()`, which the plan's own constraint — no
    dicts-as-models — forbids in spirit: the same idea wearing a class.
    """

    tier: object
    review_level: object
    reason: str
    rendered: str

def _empty(width: int) -> str:
    """An empty tuple of the arity the process declares."""
    return "Channel.value([" + ", ".join(["[:]"] + ["[]"] * (width - 1)) + "])"


def _render_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if any(ord(c) < 32 for c in text):
        raise ValueError(f"control character in parameter value: {text!r}")
    # Single-quoted Groovy. Unescaped, "it's fine" is a syntax error and a crafted value
    # closes the quote and runs code — and in Plan 2 these values come from a model.
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


# `_render_comment` lived here and is deleted. A27 needed it because `reason` was
# interpolated into `// {{ value.reason }}`, where a newline made the rest of the line
# Groovy. Nothing interpolates prose into `main.nf` any more — reasons live in
# `pipeline.yml`, beside the value they explain — so the renderer had no caller.
#
# Deleted rather than kept "in case": dead defensive code reads as protection and provides
# none, and a reader finding it would reasonably conclude prose still reaches this file.
# The property it defended is asserted at its new address, in the two A27 tests that watch
# `pipeline.yml`.


def _render_process_name(name: str) -> str:
    """A Groovy identifier, at the point it is written into a declaration.

    `nf_process` is an `NfIdentifier` and validated at contract load. This is the second
    half of the same argument as `_render_comment`: `nextflow.config` is assembled by
    Python f-strings, `withName: {nf_process}` was raw, and an emitter that trusts its
    input is one refactor away from being the only check.
    """
    if not (name.isascii() and name.isidentifier()):
        raise ValueError(
            f"{name!r} is not a Nextflow identifier and is about to be written into a "
            f"declaration. A contract cannot carry one; something bypassed the type."
        )
    return name


def _channel_name(type_id: str) -> str:
    """`fastq.reads` -> `ch_fastq_reads`.

    The last segment alone reads better but is not injective: `qc.report` and
    `multiqc.report` both became `ch_report`, so one assignment shadowed the other and
    two ports were fed the same channel, silently.
    """
    return "ch_" + type_id.replace(".", "_").replace("-", "_")


def _process_of(pipeline: Pipeline, node_id: str) -> str:
    return next(step.process for step in pipeline.steps if step.id == node_id)


def _port_expression(pipeline: Pipeline, step: Step, port_name: str) -> str:
    """Where this port's data comes from: an upstream process, or an entry channel."""
    wiring = next(item for item in step.inputs if item.port == port_name)
    if wiring.source is not None:
        node_id, _, from_port = wiring.source.partition(".")
        return f"{_process_of(pipeline, node_id)}.out.{from_port}"
    return _channel_name(wiring.channel)


def _argument(pipeline: Pipeline, step: Step, arg) -> str:
    if arg.empty_width:
        return _empty(arg.empty_width)
    if arg.from_setting is not None:
        # `via: positional` — a resolved value in a call position, the fourth destination.
        # A bare `val` in a module's input block has no name at the call site, so nothing in
        # `ext`, `meta` or `directive` could reach it and three real analysis decisions lived
        # as contract constants outside the tier ladder. A91.
        setting = next(
            (s for s in step.settings if s.name == arg.from_setting), None
        )
        if setting is None:
            raise ValueError(
                coded("MD0224", f"{step.id} declares a positional slot filled by "
                f"{arg.from_setting!r}, and no such setting exists. This pipeline cannot be "
                f"emitted — `mendel explain MD0224`.")
            )
        if setting.value is None:
            raise ValueError(
                coded("MD0224", f"{step.id}.{arg.from_setting} fills a positional argument and is "
                f"unanswered, so the call would read `null`. Nextflow fails at launch with a "
                f"message naming neither this setting nor this step. Answer it in "
                f"`pipeline.yml` — `mendel explain MD0224`.")
            )
        return _render_literal(setting.value)
    if not arg.ports:
        return _render_literal(arg.literal)
    expressions = [_port_expression(pipeline, step, name) for name in arg.ports]
    if len(expressions) == 1:
        return expressions[0]
    # Several semantic ports share one channel — featurecounts wants
    # tuple(meta, bams, annotation). The contract says how they meet, because the emitter
    # cannot know: `.combine()` pairs every sample against one shared reference and drops the
    # second tuple's meta, `.join()` matches two per-sample channels on the meta map.
    #
    # This combined unconditionally until A92. That is right for the one multi-port entry the
    # shipped registry has, and a Cartesian product for any second per-sample port — two
    # samples in gave four processes, half of them pairing one sample's data with another's,
    # and Nextflow exited 0. `--gate test` cannot see the class: the nf-core dataset has one
    # sample, so 1 x 1 == 1.
    head, *rest = expressions
    if arg.join is Join.BY_SAMPLE:
        joined = "".join(f".join({expr})" for expr in rest)
    else:
        joined = "".join(f".combine({expr}.map {{ it[1] }})" for expr in rest)
    return f"{head}{joined}"


def _render_meta(entries: list) -> str:
    """A Groovy map literal. Already sorted at materialisation."""
    rendered = ", ".join(f"{entry.key}: {_render_literal(entry.value)}" for entry in entries)
    return "[" + rendered + "]"


def _with_meta(expression: str, entries: list) -> str:
    """Merge measured facts into the channel's meta map.

    `meta + [...]` rather than replacing it: the entry channel already put an `id` there, and
    losing it would break `tag "$meta.id"` in every module.
    """
    if not entries:
        return expression
    return f"({expression}).map {{ meta, files -> [ meta + {_render_meta(entries)}, files ] }}"


def _entry_channels(pipeline: Pipeline) -> list[tuple[str, str]]:
    return [
        (_channel_name(channel.type_id), _with_meta(channel.expression, channel.meta))
        for channel in pipeline.channels
    ]


def _meta_injection(step: Step) -> str:
    """A `via: meta` setting rides into the module on the meta map of its first input.

    nf-core's convention is that the first input tuple is `[meta, …]`, so the resolved value is
    merged there. Arity-agnostic — `[ it[0] + [k: v] ] + it[1..-1]` reconstructs a tuple of any
    width — because a step's first input is a 2-tuple for most modules and wider for some, and a
    fixed `{ meta, files -> … }` pattern dies on the mismatch (the same arity trap `NfInput.empty`
    exists for). Sorted for byte-identical emission; `_render_literal` single-quotes the value.
    """
    entries = sorted(
        (s.name, s.value) for s in step.settings if s.via is Via.META and s.value is not None
    )
    if not entries:
        return ""
    rendered = ", ".join(f"{name}: {_render_literal(value)}" for name, value in entries)
    return f".map {{ it -> [ it[0] + [{rendered}] ] + it[1..-1] }}"


def _calls(pipeline: Pipeline) -> list[str]:
    calls = []
    for step in pipeline.steps:
        args = [_argument(pipeline, step, arg) for arg in step.call]
        injection = _meta_injection(step)
        if injection and args:
            args[0] = f"({args[0]}){injection}"
        calls.append(f"{step.process}({', '.join(args)})")
    return calls


def emit(pipeline: Pipeline) -> str:
    """`main.nf`, from one argument.

    No registry, no vocabulary, no measurements: everything they supplied is materialised on
    the `Pipeline`. That is what lets a laboratory regenerate a validated pipeline's Nextflow
    years later without the registry it was built against.
    """
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    nodes = [
        {"id": step.id, "process": step.process, "include": step.include}
        for step in pipeline.steps
    ]
    return env.get_template("main.nf.j2").render(
        nodes=nodes,
        entry_channels=_entry_channels(pipeline),
        calls=_calls(pipeline),
    )


def entry_params(pipeline: Pipeline) -> list[str]:
    """The `params.<name>` a generated pipeline expects the laboratory to supply."""
    return sorted({name for channel in pipeline.channels for name in channel.params})


def _render_test_data(value: list[str]) -> str:
    # A44: a `params.x = "…"` assignment is Groovy, not data, and a double-quoted string is a
    # GString. `_render_literal` single-quotes and escapes, so a value here is inert text even
    # if one reached the emitter — `TestDataRef`'s validator is the primary gate, this is the
    # second. The generated stub-data literals (`${projectDir}/…`) are rendered elsewhere.
    if len(value) == 1:
        return _render_literal(value[0])
    return "[" + ", ".join(_render_literal(item) for item in value) + "]"


def _test_profile(pipeline: Pipeline, params: list[str]) -> list[str]:
    """A `test` profile, when every entry type declares where a public example lives.

    All or nothing. A partial `test` profile would fail at run time with a null parameter,
    which looks like a pipeline bug rather than a missing declaration.
    """
    by_param = {
        name: channel for channel in pipeline.channels for name in channel.params
    }
    missing = sorted(name for name in params if not by_param[name].test_data)
    if missing:
        return [
            "    // No `test` profile: these inputs declare no `test_data` in the",
            f"    // vocabulary — {', '.join(missing)}. Add one to make `--gate test` runnable.",
        ]
    return [
        "    test {",
        SMOKE_LIMITS,
        "        // A smoke test on a small public dataset. It proves this pipeline runs",
        "        // end to end and produces output; it does not prove the analysis is",
        "        // correct, and it is not a substitute for the laboratory validating it.",
        "        // Pinned to a commit: a dataset that moves is one you cannot compare a",
        "        // result against next year.",
        *[
            f"        params.{name} = {_render_test_data(by_param[name].test_data)}"
            for name in params
        ],
        "    }",
    ]


def _ext_scope(step: Step) -> list[str]:
    """Every `ext.<key>` this step needs, composed.

    The contract's static flags first, then each routed setting in **name-sorted** order. With
    one setting that sort is unobservable, which is exactly why a test carrying one cannot see
    a sort bug — and byte-identical emission depends on it.

    A fragment mentioning `${…}` needs the task, so the whole key is emitted as a **closure**.
    Measured on Nextflow 25.10.4: a config GString is evaluated when the config is read, where
    no task exists, and `ext.args = "--rg ID:${meta.id}"` dies with `Unknown config attribute
    process.withName:FOO.meta.id`. A static fragment stays a plain single-quoted string, so a
    contract that needs no task keeps exactly the output it had.
    """
    fragments: dict[str, list[str]] = {}
    if step.ext_args.template:
        fragments.setdefault("args", []).append(step.ext_args.template)

    for setting in sorted(step.settings, key=lambda s: s.name):
        if setting.via is not Via.EXT:
            continue
        if setting.value is None:
            # An unanswered tier-4 setting contributes nothing, and must not block the build.
            # Invariant 6 says tier 4 is always *flagged*, not that it is fatal — the pipeline
            # still runs and `needs_review()` still names it. Omitting the fragment also leaves
            # the module's own fallback in charge, which is the right answer: STAR builds its
            # default read-group line when nobody has said which platform this was.
            #
            # MD0201 is for a value that exists and cannot be carried, not for absence. Refusing
            # here made `mendel publish` exit 2 on the shipped spine.
            continue
        if setting.template is None:
            # A39: append the raw value; the single `_render_literal` at the join quotes it,
            # exactly as the templated branch inserts raw fragments. Rendering here as well
            # double-quoted it — `alpha` became `'\'alpha\''`, quotes and all. Bool lowercased
            # to match the templated branch, so `true` stays `true` rather than `True`.
            #
            # A55: and it is *checked*, which it was not. The join below turns any fragment
            # mentioning `${` into a closure Nextflow evaluates per task, so an unchecked raw
            # value here is arbitrary Groovy on the host, outside any container. `Setting`
            # refuses this at load (MD0221); this is the second layer, because
            # `model_construct` skips validators and the emitter must not assume the file it
            # was handed was validated.
            if not substitutable(setting.value):
                raise ValueError(
                    coded(
                        "MD0221",
                        f"{step.id}.{setting.name} is {setting.value!r} on an untemplated "
                        f"`ext.{setting.key.value}` route, so it would be written into Nextflow "
                    "config verbatim. Use letters, digits and _ . : + - only, or a number, or "
                    "true/false — `mendel explain MD0221`.")
                )
            raw = (
                str(setting.value).lower()
                if isinstance(setting.value, bool)
                else str(setting.value)
            )
            fragments.setdefault(setting.key.value, []).append(raw)
            continue
        if not substitutable(setting.value):
            raise ValueError(
                coded(
                    "MD0201",
                    f"{step.id}.{setting.name} is {setting.value!r}, which is outside the "
                    "substitutable class. Use letters, digits and _ . : + - only, or a number, or "
                "true/false. If your value legitimately needs a space or a slash, that is a "
                "case we assumed did not exist — please report it.")
            )
        rendered = (
            str(setting.value).lower()
            if isinstance(setting.value, bool)
            else str(setting.value)
        )
        fragments.setdefault(setting.key.value, []).append(
            setting.template.replace("{value}", rendered)
        )

    lines = []
    for key in sorted(fragments):
        joined = " ".join(fragments[key])
        if "${" in joined:
            lines.append(f'    withName: {step.process} {{ ext.{key} = {{ "{joined}" }} }}')
        else:
            lines.append(
                f"    withName: {step.process} {{ ext.{key} = {_render_literal(joined)} }}"
            )
    return lines


def _directive_scope(step: Step) -> list[str]:
    """Every `via: directive` setting this step carries — `withName: X { cpus = 12 }`.

    The setting name is one of `LEGAL_DIRECTIVES` (enforced at contract load by `MD0209`) and the
    value goes through `_render_literal`, which single-quotes a string and leaves a number bare —
    `cpus = 7`, `memory = '8.GB'`. An unanswered tier-4 setting contributes nothing, exactly as on
    the `ext` route: invariant 6 flags it, it does not block the build.
    """
    lines = []
    for setting in sorted(step.settings, key=lambda s: s.name):
        if setting.via is not Via.DIRECTIVE or setting.value is None:
            continue
        lines.append(
            f"    withName: {step.process} {{ {setting.name} = {_render_literal(setting.value)} }}"
        )
    return lines


SMOKE_LIMITS = (
    "        // A smoke profile runs tiny data, so it caps what the labels ask for. nf-core's\n"
    "        // own test config does exactly this. **A cap is not a request**: the process still\n"
    "        // asks for what its label says, and `resourceLimits` is Nextflow clamping it to\n"
    "        // what is here — which is why a real run gets its ceiling from `-c site.config`\n"
    "        // and never from the artifact.\n"
    "        process.resourceLimits = [ cpus: 4, memory: 12.GB, time: 1.h ]"
)
"""Without this the labels below stop every smoke run dead: `process_high` asks for 72 GB and
`STAR_GENOMEGENERATE` carries that label, so `mendel build --gate test` failed with
`Process requirement exceeds available memory -- req: 72 GB; avail: 31.3 GB`.

**Found by `make verify` rather than by thinking**, which is the reason `CLAUDE.md` names
`emit.py` as one of the six files where `make check` is not enough.
"""


RESOURCE_LABELS: list[tuple[str, list[str]]] = [
    ("process_single", ["cpus   = { 1                   }",
                        "memory = { 6.GB  * task.attempt }",
                        "time   = { 4.h   * task.attempt }"]),
    ("process_low", ["cpus   = { 2     * task.attempt }",
                     "memory = { 12.GB * task.attempt }",
                     "time   = { 4.h   * task.attempt }"]),
    ("process_medium", ["cpus   = { 6     * task.attempt }",
                        "memory = { 36.GB * task.attempt }",
                        "time   = { 8.h   * task.attempt }"]),
    ("process_high", ["cpus   = { 12    * task.attempt }",
                      "memory = { 72.GB * task.attempt }",
                      "time   = { 16.h  * task.attempt }"]),
    ("process_long", ["time   = { 20.h  * task.attempt }"]),
    ("process_low_memory", ["memory = { 1.GB   * task.attempt }"]),
    ("process_high_memory", ["memory = { 200.GB * task.attempt }"]),
]
"""What a labelled process asks for. **nf-core's `conf/base.config`, quoted rather than
invented** — every vendored module carries a `label 'process_*'` and this is the mapping the
ecosystem reads it against.

**A tier-2 convention**: a documented default, nobody's judgement, and it says so in the emitted
comment. Nextflow matches these against the label in the module's own `main.nf`, so this is the
one part of the config that needs to know nothing about which steps are in the pipeline.

**Why it is not optional.** Without it Nextflow reports `memory: null` for every task, which
makes the asked-versus-used comparison — the thing that catches an OOM before it happens, and
the thing over-allocation is measured with — a number against a blank. A pipeline that requests
nothing cannot be over-provisioned or under-provisioned. Found on 2026-08-24 by querying a real
run's spans and seeing one half of every pair empty.

**`task.attempt` is the multiplier and it is the point**: a retry asks for more than the try
that failed, which is what makes `errorStrategy` worth having.
"""


def _label_scope() -> list[str]:
    lines = [
        "    // Resource requests by label, from nf-core's conf/base.config. A CONVENTION:",
        "    // every nf-core module declares `label 'process_*'` and this is what the",
        "    // ecosystem reads it against. Nextflow matches these against the module's own",
        "    // label, so nothing here depends on which steps this pipeline has.",
        "    //",
        "    // A site caps these with `process.resourceLimits` in its own config — how big",
        "    // the machine is, is not a fact about the pipeline.",
    ]
    for label, directives in RESOURCE_LABELS:
        lines.append(f"    withLabel: {label} {{")
        lines += [f"        {directive}" for directive in directives]
        lines.append("    }")
    return lines


def _process_scope(pipeline: Pipeline) -> list[str]:
    """`ext.*` and directives per process, for modules that declare flags or carry settings."""
    blocks: list[str] = []
    for step in pipeline.steps:
        blocks += _ext_scope(step)
        blocks += _directive_scope(step)
    return ["process {", *_label_scope(), *sorted(set(blocks)), "}", ""]


def emit_config(pipeline: Pipeline) -> str:
    """`nextflow.config` for the generated pipeline.

    Every input parameter defaults to `null`: the pipeline describes a shape and the laboratory
    supplies the data at run time, which is invariant 15 surviving into the configuration as
    well as the workflow.
    """
    params = entry_params(pipeline)
    lines = [
        "// Generated by Mendel. Do not edit by hand — edit the goal and recompile.",
        "",
        "params {",
    ]
    lines += [f"    {name} = null" for name in params]
    lines += ["}", ""]
    lines += _process_scope(pipeline)
    lines += ["profiles {", "    stub_data {", SMOKE_LIMITS]
    for name in params:
        pattern = (
            '"${projectDir}/stub-data/*_R{1,2}.fastq.gz"'
            if name == "input"
            else f'"${{projectDir}}/stub-data/{name}.txt"'
        )
        lines.append(f"        params.{name} = {pattern}")
    lines += ["    }"]
    lines += _test_profile(pipeline, params)
    lines += [
        "    docker {",
        "        docker.enabled = true",
        "        // Without this, containers write as root and the work directory",
        "        // cannot be deleted by the person who created it.",
        "        docker.runOptions = '-u $(id -u):$(id -g)'",
        "    }",
        "    singularity {",
        "        singularity.enabled = true",
        "        singularity.autoMounts = true",
        "    }",
        # **Executors, and they are a function of nothing.**
        #
        # `docs/design/execution-boundary.md` §6: the executor must not enter `pipeline.yml`
        # or `main.nf`, because a pipeline that differed per deployment target would break
        # invariant 10 and invariant 13 at once — and would make `Pipeline.emitted`'s digests
        # depend on a deployment choice, so `mendel emit` could not reproduce the file it is
        # handed. Every pipeline therefore carries all three whether or not anyone selects
        # one, the same posture `docker` and `singularity` already take.
        # `emit_config` takes one parameter and a test holds it there.
        #
        # Nextflow does the actual work: same workflow, same modules, same containers, and
        # the backend is configuration. What Mendel cannot know is the *site* — a queue name,
        # a storage class, a role ARN, where `workDir` lives — so each profile names what it
        # still needs and Nextflow layers `-c site.config` over the top. §5.
        "    local {",
        "        process.executor = 'local'",
        "    }",
        # `k8s` is also the name of a Nextflow config SCOPE — `k8s { namespace, ... }` — so a
        # profile called `k8s` that sets `k8s.*` inside itself reads like a recursion and is
        # not one. Kept anyway: `-profile k8s` is what somebody will type, and the alternative
        # is teaching a second word for one thing. This comment is the mitigation. A169.
        "    k8s {",
        "        process.executor = 'k8s'",
        "        // Needs site facts this file cannot know: a namespace, a service account,",
        "        // and the storage claim that backs workDir. Supply them with",
        "        //     nextflow run . -profile k8s,docker -c site.config",
        "    }",
        "    awsbatch {",
        "        process.executor = 'awsbatch'",
        "        // Needs site facts this file cannot know: process.queue, aws.region, and a",
        "        // workDir on S3 — Batch has no shared filesystem. Supply them with",
        "        //     nextflow run . -profile awsbatch,docker -c site.config -w s3://<bucket>/work",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)
