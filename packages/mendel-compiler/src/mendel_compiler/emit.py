"""Render a resolved ``Pipeline`` as deterministic Nextflow DSL2 and configuration."""

from pathlib import Path
from typing import NamedTuple

from comeni_core.artifact.pipeline import Grain, InputForm, Pipeline, Step
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import InputState
from comeni_core.plan.at_run import AtRunSource
from comeni_core.spell.marks import substitutable
from comeni_core.spell.routes import Join, Via
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from mendel_compiler.groovy_lookup import closure, literal

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


def _channel_name(name: str) -> str:
    """`gtf` -> `ch_gtf`. A prefix, and nothing else.

    ═══ IT USED TO DERIVE THE NAME AND THAT WAS THE DEFECT ═══════════════════════════════════

    This took a **type id** and built `ch_fastq_reads` from it, with a docstring explaining
    that the last segment alone was not injective — `qc.report` and `multiqc.report` both
    became `ch_report`, so one assignment shadowed the other and two ports were fed the same
    channel, silently.

    That docstring was right about the collision and wrong about where the fix belonged.
    Deriving a channel's identity **here** is what made a channel a property of the type: two
    channels of one type had one name, one `params.*` and one hole, whatever the drawing said.
    The name is derived once, at materialisation, recorded on `Channel.name`, and checked for
    uniqueness by `MD0226`. This function adds `ch_`.
    """
    return "ch_" + name


def _process_of(pipeline: Pipeline, node_id: str) -> str:
    return next(step.process for step in pipeline.steps if step.id == node_id)


def _port_expression(pipeline: Pipeline, step: Step, port_name: str,
                     measured: dict[str, str] | None = None) -> str:
    """Where this port's data comes from: an upstream process, or an entry channel.

    **`.collect()` when the port gathers**, which is fan-in: one invocation over the whole
    channel rather than one per item. MULTIQC is the case — it consumes `qc.report` from every
    sample, and without this the workflow says `MULTIQC(ch_qc_report)` and produces N reports
    where the point of the tool is to produce one.

    Distinct from phase 4.2's `.first()`, which is the *other* direction: `first()` takes one
    item and makes a value channel that can be consumed any number of times, and `collect()`
    gathers a whole channel into one list item. One stops a reference capping the run; the other
    stops an aggregator running per sample.
    """
    wiring = next(item for item in step.inputs if item.port == port_name)
    if wiring.source is not None:
        node_id, _, from_port = wiring.source.partition(".")
        expression = f"{_process_of(pipeline, node_id)}.out.{from_port}"
    else:
        # An input whose `meta` carries a fact the run measures reads the joined channel; the
        # steps that measure it read the raw one (#217).
        expression = (measured or {}).get(wiring.channel) or _channel_name(wiring.channel)
    return f"{expression}.collect()" if wiring.gather else expression


def _argument(pipeline: Pipeline, step: Step, arg, measured: dict[str, str] | None = None) -> str:
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
    # A port that is off has no channel: the tuple is built from the ports that are on, and
    # `[]` then takes each left-out port's position, so the order still matches the module's
    # input block (#464). The first port that is on stands in for the head.
    off = {r.port for r in step.input_states if r.state is InputState.OFF}
    on = [name for name in arg.ports if name not in off]
    expressions = [_port_expression(pipeline, step, name, measured) for name in on]
    if len(arg.ports) == 1:
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
    # A per-sample input a run may leave empty is refused where the samplesheet is built
    # (#466); with one sample-scoped channel there is no samplesheet, and nothing else is
    # per-sample to pair it with, so `.join` cannot mis-pair it.
    head, *rest = expressions
    joined = "".join(
        f".join({expr})" if arg.join_for(name) is Join.BY_SAMPLE
        else f".combine({expr}.map {{ it[1] }})"
        for name, expr in zip(on[1:], rest, strict=True))
    if len(on) == len(arg.ports):
        return f"{head}{joined}"
    names = [chr(ord("a") + n) for n in range(len(on))]
    given = iter(names)
    slots = ", ".join("[]" if port in off else next(given) for port in arg.ports)
    return f"{head}{joined}.map {{ meta, {', '.join(names)} -> [ meta, {slots} ] }}"


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
    """Every entry channel, as `(groovy name, expression)`.

    **A `RUN`-scoped channel is emitted as a VALUE channel, and that is a correctness fix.**

    A Nextflow process with several *queue* inputs runs as many times as the **shortest** one.
    Every entry channel used to be a queue, so a reference genome — one item — capped the whole
    run: with twenty-four samples `STAR_ALIGN` ran **once** and twenty-three were silently
    dropped. No error, no warning, a green gate, and a counts matrix for one sample.

    Nobody saw it because the stub profile globs **one** sample pair, so N = 1 and the shortest
    channel is every channel. `test_fan_out.py` runs two pairs, which is the smallest fixture
    that can tell the two apart — a determinism test over the spine passes either way, which is
    the guard-that-proves-nothing shape this repository has paid for twice already.

    `.first()` rather than `.collect()`: `first()` takes the one item and makes it a value
    channel, consumable any number of times. `collect()` gathers a whole channel into a single
    *list* item, which is fan-in — a different question, and `InputPort.cardinality`'s.
    """
    if pipeline.input_form is InputForm.SAMPLESHEET:
        return _from_samplesheet(pipeline)
    return [
        (
            _channel_name(channel.name),
            _optional(channel, _as_value(_with_meta(channel.expression, channel.meta),
                                         channel.grain)),
        )
        for channel in pipeline.channels
    ]


def _run_guards(pipeline: Pipeline) -> list[str]:
    """The constraints only a run can settle (#460), checked before any process starts, so a
    run that breaks one fails at once with the reason, however it was launched."""
    guards = set()
    for step in pipeline.steps:
        for rule in step.run_rules:
            when = [f"params.{p}" for p in rule.given]
            when += [f"!params.{p}" for p in rule.requires]
            when += [f"params.{p}" for p in rule.forbids]
            guards.add(f"if ({' && '.join(when)}) {{ error \"{_groovy_text(rule.says)}\" }}")
    return sorted(guards)


def _groovy_text(text: str) -> str:
    """Text inside a Groovy double-quoted string: no interpolation, no early end."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def _optional(channel, expression: str) -> str:
    """An input each run may leave empty (#460): its process gets the empty tuple it takes
    instead, so the same pipeline runs with or without the file."""
    if not channel.optional:
        return expression
    return f"params.{channel.param} ? ({expression}) : {_empty(channel.absent_width)}"


SAMPLESHEET = "ch_samplesheet"
"""The parsed table, which every sample-scoped channel is a projection of."""

SAMPLE_COLUMN = "sample"
"""The column carrying a sample's identifier. **Mendel never sees a value in it** — invariant
15: the pipeline references `params.input`, and the rows are the laboratory's."""


def _from_samplesheet(pipeline: Pipeline) -> list[tuple[str, str]]:
    """`params.input` is a CSV, and each sample-scoped channel is a projection of one column.

    ═══ WHY A TABLE AND NOT TWO GLOBS ════════════════════════════════════════════════════════

    Two `fromFilePairs` calls zip by position, so nothing ties a sample's reads to *its own*
    annotation — the pipeline would run, pair sample 1's reads with sample 3's GTF, and produce
    a counts matrix nobody could tell was wrong. A row is what makes *reads with their
    respective annotations* expressible at all.

    ═══ NO EXPLICIT JOIN TO DERIVE THEM, AND THAT IS DELIBERATE ═════════════════════════════

    Every sample-scoped channel derives from **one** `splitCsv`, so they emit in row order and
    a process consuming several of them sees one row's values together. Joining them back on
    `meta.id` would be re-deriving an alignment that was never lost — and `.join()` on a queue
    is a synchronisation point, so it would also make the pipeline wait for the whole table
    before the first sample could start. A shared slot whose contract pairs two per-sample
    ports (`by_sample`, #464) still joins them at the call; the projections share
    `[id: row.sample]` and duplicate ids are refused, so that join is exact.

    A run-scoped channel is untouched: it is one file for the whole analysis, it has its own
    `params.<name>`, and it has no column.
    """
    lines = [
        (
            SAMPLESHEET,
            f"Channel.fromPath(params.input, checkIfExists: true)"
            f".splitCsv(header: true){_no_duplicate_ids()}{_cells(pipeline)}",
        )
    ]
    carried = {f.describes for f in pipeline.sheet_facts}
    for channel in pipeline.channels:
        if channel.grain is not Grain.SAMPLE:
            lines.append(
                (
                    _channel_name(channel.name),
                    _optional(channel, _as_value(_with_meta(channel.expression, channel.meta),
                                                 channel.grain)),
                )
            )
            continue
        if channel.optional:
            # A column some rows may leave blank needs per-row placeholders (#466).
            raise ValueError(f"{channel.name} is a per-sample input each run may leave empty, "
                             "which a samplesheet cannot carry yet (#466)")
        files = ", ".join(f"file(row.{column})" for column in channel.columns)
        payload = files if len(channel.columns) == 1 else f"[ {files} ]"
        # The row's facts ride on the input they describe (#466), parsed and checked above.
        identity = (f"[id: row.{SAMPLE_COLUMN}] + row.comeni" if channel.type_id in carried
                    else f"[id: row.{SAMPLE_COLUMN}]")
        projection = f"{SAMPLESHEET}.map {{ row -> [ {identity}, {payload} ] }}"
        lines.append((_channel_name(channel.name), _with_meta(projection, channel.meta)))
    return lines


def _cells(pipeline: Pipeline) -> str:
    """Each row's facts, parsed and checked before any process starts (#466): every cell against
    its declared kind and values, a blank only where the fact is optional, `auto` only where a
    step measures it. A bad cell stops the run naming the row, the sample and the column. The
    parsed values sit on `row.comeni`: each fact under its id and under a module's key, and
    `comeni_from`, which facts the row stated."""
    if not pipeline.sheet_facts:
        return ""
    values = ",\n".join(f"                {f.column}: {_cell(f)}" for f in pipeline.sheet_facts)
    keys = [f"{m.key}: {_translated(f, m)}" for f in pipeline.sheet_facts for m in f.meta
            if m.key != f.measurement]
    module = (" + [" + ", ".join(keys) + "]") if keys else ""
    return (
        ".toList().flatMap { rows ->\n"
        "        rows.withIndex().collect { row, i ->\n"
        "            def n = i + 1\n"
        "            def v = [\n" + values + "\n            ]\n"
        "            row + [comeni: v" + module + " + [comeni_from: v.findAll { it.value != null }"
        ".collectEntries { [it.key, 'cell'] }]]\n"
        "        }\n"
        "    }"
    )


def _cell(fact) -> str:
    """One cell as a closure call: its value; `null` for a blank the fact may leave, or `auto`
    where a step measures it; otherwise a stop naming the row, the sample and the column. Only
    declared identifiers and values, each checked substitutable, reach the message."""
    where = f"samplesheet row ${{n}} (sample ${{row.{SAMPLE_COLUMN}}}), column {fact.column}"
    listed = ", ".join(literal(v, f"samplesheet column {fact.column}") for v in fact.values)
    kind = fact.kind.value
    if kind == "enum":
        parsed = (f"c in [{listed}] ? c : error(\"{where}: '${{c}}' is not one of "
                  f"{', '.join(fact.values)}\")")
    elif kind == "boolean":
        parsed = (f"c == 'true' ? true : c == 'false' ? false : "
                  f"error(\"{where}: '${{c}}' is not one of true, false\")")
    else:
        number = ("c ==~ /-?\\d+/ ? (c as long)" if kind == "integer"
                  else "c.isBigDecimal() ? (c as BigDecimal)")
        what = "a whole number" if kind == "integer" else "a number"
        parsed = f"{number} : error(\"{where}: '${{c}}' is not {what}\")"
        bounds = []
        if fact.minimum is not None:
            bounds.append(f"x < {float(fact.minimum)!r} ? error(\"{where}: '${{c}}' is below "
                          f"{_shown(fact.minimum)}\")")
        if fact.maximum is not None:
            bounds.append(f"x > {float(fact.maximum)!r} ? error(\"{where}: '${{c}}' is above "
                          f"{_shown(fact.maximum)}\")")
        if bounds:
            parsed = f"{{ -> def x = ({parsed}); " + " : ".join(bounds) + " : x }()"
    blank = "null" if not fact.required else f'error("{where} is required")'
    auto = ("null" if fact.auto
            else f'error("{where}: auto is allowed only where the run measures the fact")')
    return (f"({{ -> def c = (row.{fact.column} ?: '').trim(); "
            f"c == '' ? {blank} : c == 'auto' ? {auto} : ({parsed}) }}())")


def _shown(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _translated(fact, key) -> str:
    """The fact under a module's key, spelled as that module expects (`paired` true is
    `single_end` false)."""
    var = f"v.{fact.column}"
    if not key.translate:
        return var
    pairs = ", ".join(f"({literal(t.when, fact.column)}): {literal(t.then, fact.column)}"
                      for t in key.translate)
    return f"({var} == null ? null : [{pairs}][{var}])"


def _no_duplicate_ids() -> str:
    """Refuse a table whose sample ids repeat, naming them. Plan 5B §5.4.

    Two sample-scoped channels are aligned by row, so a sample split across lanes or flowcells —
    several rows carrying one id — silently becomes several independent samples with the same
    name, and every per-sample output overwrites the last.

    **Refusing is honest and cheap; merging is not.** nf-core's answer is `cat_fastq`, a grouping
    step before anything else, and a step that changes cardinality on its way through is exactly
    what §10.5 says the contract model cannot express at all. So this says so rather than
    guessing, and names the ids so the person can fix the table.

    Emitted into the pipeline because that is where the table is: Mendel never reads one
    (invariant 15), so the only place this check can run is the run itself.
    """
    return (
        ".toList().map { rows ->\n"
        "        def seen = rows.collect { it.sample }\n"
        "        def twice = seen.countBy { it }.findAll { _k, v -> v > 1 }.keySet()\n"
        # **The `+` goes at the END of a line, and running it is what found that.** Groovy
        # continues a statement when a line ends with an operator; a line *beginning* with `+`
        # is a new statement applying unary plus to a string, so the message silently truncated
        # to "samplesheet has duplicate sample ids: " — the words before the first break, with
        # no ids. `nextflow lint` passed it, because it is valid Groovy that means something
        # else.
        "        if (twice) {\n"
        "            error \"samplesheet has duplicate sample ids: ${twice.join(', ')}. \" +\n"
        "                \"Each row is one sample; a sample split across lanes needs \" +\n"
        "                \"merging before this pipeline, which Mendel does not emit.\"\n"
        "        }\n"
        "        rows\n"
        "    }.flatMap { it }"
    )


def _as_value(expression: str, grain: Grain) -> str:
    """A study's channel becomes a value channel; a per-sample one stays a queue."""
    return f"({expression}).first()" if grain is Grain.STUDY else expression


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


def _call(pipeline: Pipeline, step: Step, measured: dict[str, str] | None = None) -> str:
    args = [_argument(pipeline, step, arg, measured) for arg in step.call]
    injection = _meta_injection(step)
    if injection and args:
        args[0] = f"({args[0]}){injection}"
    return f"{step.process}({', '.join(args)})"


def _measuring_branch(pipeline: Pipeline) -> set[str]:
    """The steps that measure a run-time fact, and every step they descend from: they run on
    the raw inputs, before the measured fact can be joined into anyone's `meta` (#217)."""
    wanted = {m.measured_at for c in pipeline.channels for m in c.meta_at_run}
    by_id = {step.id: step for step in pipeline.steps}
    branch: set[str] = set()
    while wanted:
        node = wanted.pop()
        if node in branch:
            continue
        branch.add(node)
        wanted |= {i.source.partition(".")[0] for i in by_id[node].inputs if i.source}
    return branch


def _joined(pipeline: Pipeline) -> tuple[dict[str, str], list[str], dict[str, str], list[str]]:
    """Each input channel carrying run-measured facts, joined with them by `meta`: its name for
    the consumers outside the measuring branch and the lines that define it; and, for a channel
    whose measured facts the samplesheet may state (#466), the channel the measuring branch reads
    instead, of the rows that left a cell blank, with the lines defining it. A stated cell wins
    over a measurement, and `meta.comeni_from` says which each sample's value is."""
    auto = {f.measurement for f in pipeline.sheet_facts if f.auto}
    names, lines, unstated, before = {}, [], {}, []
    for channel in pipeline.channels:
        if not channel.meta_at_run:
            continue
        raw = _channel_name(channel.name)
        name = f"{raw}_measured"
        facts = [m.measurement for m in channel.meta_at_run]
        bypass = all(f in auto for f in facts)
        source = raw
        if bypass:
            blank = " || ".join(f"meta.{f} == null" for f in facts)
            source = f"{raw}_unstated"
            before.append(f"{source} = {raw}.filter {{ meta, data -> {blank} }}")
            unstated[channel.name] = source
        # `failOnMismatch`: a sample whose measurement never matches its input must stop the
        # run, not vanish from it with exit 0 (Task 7 review).
        joins = "".join(
            f".join({_process_of(pipeline, m.measured_at)}.out.{m.measured_port}.map {{ meta, "
            f"report -> [ meta, new groovy.json.JsonSlurper().parseText(report.text)"
            f".facts?.get('{m.measurement}')?.value ] }}, failOnMismatch: true, "
            "failOnDuplicate: true)"
            for m in channel.meta_at_run
        )
        values = [f"v{n}" for n in range(len(channel.meta_at_run))]
        merged = ", ".join(
            f"{m.meta_key}: (meta.{m.meta_key} != null ? meta.{m.meta_key} : {v})"
            for m, v in zip(channel.meta_at_run, values, strict=True))
        sources = ", ".join(
            f"{m.measurement}: (meta.{m.meta_key} != null ? 'cell' : 'measured')"
            for m in channel.meta_at_run)
        expression = (f"{source}{joins}.map {{ meta, data, {', '.join(values)} -> "
                      f"[ meta + [{merged}, comeni_from: (meta.comeni_from ?: [:]) + "
                      f"[{sources}]], data ] }}")
        if bypass:
            stated = " && ".join(f"meta.{f} != null" for f in facts)
            expression = f"{raw}.filter {{ meta, data -> {stated} }}.mix({expression})"
        names[channel.name] = name
        lines.append(f"{name} = {_as_value(expression, channel.grain)}")
    return names, lines, unstated, before


def _meta_root(pipeline: Pipeline, step: Step) -> str | None:
    """The input channel whose `meta` reaches this step's first input: its own, or, through
    upstream steps' first inputs, the one they read. nf-core passes `meta` along that way."""
    by_id = {s.id: s for s in pipeline.steps}
    seen: set[str] = set()
    while step.id not in seen and step.call and step.call[0].ports:
        seen.add(step.id)
        wiring = next(i for i in step.inputs if i.port == step.call[0].ports[0])
        if wiring.source is None:
            return wiring.channel
        step = by_id[wiring.source.partition(".")[0]]
    return None


def _check_measuring(pipeline: Pipeline, branch: set[str], measured: dict[str, str]) -> None:
    """What would make a measured fact miss the step it is for, refused at emit (MD0330)."""
    for step in pipeline.steps:
        if step.id in branch and any(s.via is Via.META and s.value is not None
                                     for s in step.settings):
            raise ValueError(coded(
                "MD0330", f"{step.id} measures a run-time fact and adds to `meta` itself, so "
                "its measurement would not match its input's `meta` — `mendel explain MD0330`."))
        for setting in (s for s in step.settings if s.at_run is not None):
            root = _meta_root(pipeline, step)
            channel = next((c for c in pipeline.channels if c.name == root), None)
            carried = {m.measurement for m in channel.meta_at_run} if channel else set()
            # Every fact a step measures must be joined into the `meta` this step reads; a fact
            # from the samplesheet arrives on the row itself (#466).
            missing = [f.measurement for f in setting.at_run.facts
                       if f.source is not AtRunSource.CELL and f.measurement not in carried]
            if root is None or missing:
                raise ValueError(coded(
                    "MD0330", f"{step.id} is decided at run time, and its first input's `meta` "
                    f"does not carry {', '.join(missing) or 'its facts'}, so the setting would "
                    "read nothing — `mendel explain MD0330`."))
    seen: dict[tuple[str, str], str] = {}
    for channel in pipeline.channels:
        for m in channel.meta_at_run:
            key = (m.measured_at, m.measurement)
            if key in seen:
                raise ValueError(coded(
                    "MD0330", f"{m.measurement} is measured once, by {m.measured_at}, and two "
                    f"inputs carry it ({seen[key]}, {channel.name}): one of them could never "
                    "match its measurement — `mendel explain MD0330`."))
            seen[key] = channel.name


def _decided(pipeline: Pipeline, measured: dict[str, str]) -> list[str]:
    """Every run-time value the run used, per sample, beside its facts: what a setting became
    is recorded by the run itself, from the `meta` the step reads, not recomputed afterwards
    (#217)."""
    lines = []
    for step in pipeline.steps:
        for setting in sorted(step.settings, key=lambda s: s.name):
            if setting.at_run is None:
                continue
            root = _meta_root(pipeline, step)
            channel = measured.get(root, _channel_name(root))
            expr = closure(setting.at_run, where=f"{step.id}.{setting.name}")
            # Each fact beside the value, with where it came from (#466): `fact=value:source`.
            facts = " + ".join(
                f"\"\\t{f.measurement}=${{meta.{f.meta_key}}}:"
                f"${{meta.comeni_from?.get('{f.measurement}') ?: "
                f"(meta.{f.meta_key} == null ? 'missing' : 'measured')}}\""
                for f in setting.at_run.facts)
            lines.append(
                "if (params.outdir) {\n"
                f"        {channel}.map {{ meta, data -> \"${{meta.id}}\\t\" + "
                f"String.valueOf({expr}) + {facts} }}.collectFile(name: "
                f"'{step.id}.{setting.name}.tsv', storeDir: \"${{params.outdir}}/decided\", "
                "newLine: true, sort: true)\n"
                "    }"
            )
    return lines


def _calls(pipeline: Pipeline) -> list[str]:
    """Every statement after the entry channels: the measuring branch first, on the raw
    inputs (only the rows that left a cell blank, where the samplesheet may state the fact);
    then the inputs joined with what it measured; then every other step reading the joined
    inputs; then the record of each run-time value (#217, #466). A pipeline that decides
    nothing in the run gets exactly its calls in step order, as before."""
    _check_cells(pipeline)
    branch = _measuring_branch(pipeline)
    if not branch:
        return [*(_call(pipeline, step) for step in pipeline.steps), *_decided(pipeline, {})]
    measured, joined, unstated, before = _joined(pipeline)
    _check_measuring(pipeline, branch, measured)
    first = [_call(pipeline, step, unstated) for step in pipeline.steps if step.id in branch]
    rest = [_call(pipeline, step, measured) for step in pipeline.steps if step.id not in branch]
    return [*before, *first, *joined, *rest, *_decided(pipeline, measured)]


def _check_cells(pipeline: Pipeline) -> None:
    """Every fact a run-time lookup reads from the samplesheet has its column (MD0335): without
    it every sample would read nothing and take the fallback (Task 5 review)."""
    columns = {f.measurement for f in pipeline.sheet_facts}
    for step in pipeline.steps:
        for setting in step.settings:
            if setting.at_run is None:
                continue
            missing = [f.measurement for f in setting.at_run.facts
                       if f.source is not AtRunSource.MEASURED and f.measurement not in columns]
            if missing:
                raise ValueError(coded(
                    "MD0335", f"{step.id}.{setting.name} reads {', '.join(missing)} from the "
                    "samplesheet, and the samplesheet has no such column — "
                    "`mendel explain MD0335`."))


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
        guards=_run_guards(pipeline),
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
    table = pipeline.input_form is InputForm.SAMPLESHEET
    return [
        "    test {",
        SMOKE_LIMITS,
        "        // A smoke test on a small public dataset. It proves this pipeline runs",
        "        // end to end and produces output; it does not prove the analysis is",
        "        // correct, and it is not a substitute for the laboratory validating it.",
        "        // Pinned to a commit: a dataset that moves is one you cannot compare a",
        "        // result against next year.",
        # **A samplesheet's `input` is a FILE, and a config block cannot write one.**
        # `materialise_test_samplesheet` writes it beside the workflow at gate time, the same
        # way `materialise_stub_data` writes the stub fixtures — a pipeline must stay free of
        # data and of paths to data (invariant 15), so the validation harness is where fixtures
        # belong. The other parameters are unchanged: a run-scoped reference still gets its URL.
        *[
            f'        params.{name} = "${{projectDir}}/{TEST_SAMPLESHEET}"'
            if table and name == "input"
            else f"        params.{name} = {_render_test_data(by_param[name].test_data)}"
            for name in params
        ],
        "    }",
    ]


TEST_SAMPLESHEET = "test-samplesheet.csv"
"""What the `test` profile points `params.input` at when the pipeline takes a table.

Written by `gates.materialise_test_samplesheet`, never by the emitter: the pipeline references
a path and the harness supplies the file, which is the same split `stub-data/` already makes.
"""


def test_samplesheet(pipeline: Pipeline) -> str:
    """The `test` profile's samplesheet: **one row**, from each type's declared `test_data`.

    One row is enough and two would be a claim this repository cannot back. A second row needs a
    second sample's URLs and the vocabulary declares one per type — inventing a second by reusing
    the first would give the run two samples with identical data and identical results, which
    looks like a fan-out test and is not one. `tests/emit/test_fan_out.py` runs two *stub* pairs,
    where a fixture costs nothing; here the fixture is somebody else's dataset.

    What this row does prove is the thing `-stub-run` cannot: that each column is wired to the
    input it names. A stub never reads its inputs, so a column pointing at nothing is exactly as
    green as one pointing at a genome — which is how two modules shipped with hollow references.
    """
    by_param = {name: channel for channel in pipeline.channels for name in channel.params}
    columns: list[str] = [SAMPLE_COLUMN]
    values: list[str] = ["test"]
    for channel in pipeline.channels:
        if channel.grain is not Grain.SAMPLE:
            continue
        for column, url in zip(channel.columns, by_param[channel.param].test_data, strict=False):
            columns.append(column)
            values.append(url)
    # Each fact column gets a value its check accepts (#466): `auto` where the run measures it,
    # the first allowed value, `true`, or the smallest number allowed.
    for fact in pipeline.sheet_facts:
        columns.append(fact.column)
        values.append(_test_cell(fact))
    return ",".join(columns) + "\n" + ",".join(values) + "\n"


def _test_cell(fact) -> str:
    if fact.auto:
        return "auto"
    if fact.values:
        return fact.values[0]
    if fact.kind.value == "boolean":
        return "true"
    return _shown(fact.minimum if fact.minimum is not None else 1)


def _at_run_fragment(step: Step, setting) -> str:
    """The setting's flag with its value from the lookup over `meta`, or nothing when the
    lookup gives nothing (an unanswered fallback and an undetermined fact) (#217)."""
    where = f"{step.id}.{setting.name}"
    expr = closure(setting.at_run, where=where)
    template = setting.template or "{value}"
    if template.count("{value}") != 1 or "${" in template:
        raise ValueError(coded(
            "MD0330",
            f"{where} is decided at run time and its template {template!r} does not hold "
            "`{value}` once, plainly — `mendel explain MD0330`."))
    before, _, after = template.partition("{value}")
    return (f"${{ ({expr}) == null ? '' : {_render_literal(before)} + ({expr}) + "
            f"{_render_literal(after)} }}")


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
            if setting.at_run is not None:
                raise ValueError(coded(
                    "MD0330",
                    f"{step.id}.{setting.name} is decided at run time and routes through "
                    f"`{setting.via.value}`; only an `ext` setting can read the measured fact "
                    "from its task's `meta` — `mendel explain MD0330`."))
            continue
        if setting.at_run is not None:
            fragments.setdefault(setting.key.value, []).append(_at_run_fragment(step, setting))
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


RETRY_ON_RESOURCE = [
    "    // Retry once on the exit codes that mean *not enough of something* — 137 is the OOM",
    "    // kill, 130-145 are the signals, 104 is a Slurm/LSF resource refusal. Anything else",
    "    // is a real failure and retrying it just costs time. nf-core's conf/base.config.",
    "    //",
    "    // **This is what makes `* task.attempt` above mean anything.** Without a retry the",
    "    // multiplier can never fire and the label's second attempt is decoration: a task",
    "    // killed for memory asks for the same amount again, forever.",
    "    errorStrategy = { task.exitStatus in ((130..145) + 104) ? 'retry' : 'finish' }",
    "    maxRetries    = 1",
]
"""A convention, and half of a pair: the labels say what a retry asks for and this is what
causes one. Emitting the first without the second is what shipped on 2026-08-24 for an hour —
found by a board panel that was empty because nothing in any run had ever reached attempt 2."""


PUBLISH_DIR = [
    "    // WHERE THE RESULTS GO. A CONVENTION, quoted from nf-core's own modules.config: one",
    "    // directory per process, named after the process, under whatever `params.outdir` is.",
    "    // It depends on no step — `task.process` is what Nextflow already knows — so this sits",
    "    // beside the labels rather than being emitted per `withName:`.",
    "    //",
    "    // **`params.outdir` is null in the artifact, and that is the whole design.** WHERE a",
    "    // laboratory keeps its results is a fact about a SITE, not about a pipeline — the same",
    "    // argument `process.resourceLimits` already makes about how big the machine is. A path",
    "    // baked in here would make `mendel emit` produce a different file per deployment, which",
    "    // breaks invariant 10 and invariant 13 at once. Wiener's launcher supplies it; a person",
    "    // running this by hand passes `--outdir`.",
    "    //",
    "    // `mode: 'copy'` rather than the default symlink: a link into a work directory that",
    "    // gets cleaned is a result that evaporates, and these are the files somebody keeps.",
    "    //",
    "    // `enabled` is an EXPRESSION and `path` is a CLOSURE, and the difference is not style:",
    "    // Nextflow evaluates `enabled` when it reads this file and never calls a closure given",
    "    // to it, so `enabled: { ... }` is an object that is merely truthy and publishes always.",
    "    // `path` is called per task, which is the only way it can see `task.process`.",
    "    publishDir = [",
    "        path:    { \"${params.outdir}/${task.process.tokenize(':').last().toLowerCase()}\" },",
    "        mode:    'copy',",
    "        enabled: params.outdir != null,",
    "    ]",
]
"""Every process publishes what it makes, under a directory named for the process.

**Until 2026-08-30 nothing did**, and a finished run left its outputs in `work/<hash>/` under
names nobody can read — which had blocked three separate screens by the time it was written:
the overview's *Results ready*, the run page's results link, and the loop's own ending. A grep
for `publishDir` across the whole repository returned one hit, in the list of directive names a
setting is *allowed* to route to.

**`enabled` is what keeps it honest when nobody said where.** `params.outdir` is `null` in the
artifact, so without the guard Nextflow would publish into a directory literally called `null`.
Absent is absent: no destination means nothing is published, not published somewhere wrong.

**It shipped as a closure first and published NOTHING, with all five processes green.**
`enabled: { params.outdir != null }` hands Nextflow a `Closure` where it expects a value; it is
never called. Found by running the stub gate and looking in `results/` rather than by reading the
config — every test passed, `nextflow config` printed the directive correctly, and the log said
nothing at all. A plain expression is evaluated when the config is read, and **a command-line
`--outdir` is visible by then**, which was the worry that made the closure look necessary. Both
branches were then checked against a real run: `--outdir` publishes, and no `outdir` leaves no
`results/` and no directory called `null`.
"""


def _label_scope() -> list[str]:
    # Publishing first, because it is what a reader of the emitted config wants to find and
    # because it is the one directive here that answers "where did my results go".
    lines = [
        *PUBLISH_DIR,
        "",
        "    // Resource requests by label, from nf-core's conf/base.config. A CONVENTION:",
        "    // every nf-core module declares `label 'process_*'` and this is what the",
        "    // ecosystem reads it against. Nextflow matches these against the module's own",
        "    // label, so nothing here depends on which steps this pipeline has.",
        "    //",
        "    // A site caps these with `process.resourceLimits` in its own config — how big",
        "    // the machine is, is not a fact about the pipeline.",
    ]
    lines += RETRY_ON_RESOURCE
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


MEASURING = "modules/comeni/measure/"
"""Where every generated measuring step's module is staged (#465)."""


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
    ]
    if any(step.include.startswith(MEASURING) for step in pipeline.steps):
        # A measuring step's runner is a module binary in its own `resources/usr/bin` (#465);
        # Nextflow stages it into the task only with this switched on. Emitted only then, so a
        # pipeline that measures nothing keeps exactly the config it had.
        lines += ["nextflow.enable.moduleBinaries = true", ""]
    lines += ["params {"]
    lines += [f"    {name} = null" for name in params]
    # **After the entry params, and outside their loop.** `outdir` is not an entry channel — it
    # is where results go, which is a site fact — so it must not join the loops below that give
    # every entry param a stub file and a test URL. Emitted last so the diff against a
    # pre-2026-08-30 config is one line in one place.
    lines += ["    outdir = null"]
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
        # The executor must not enter `pipeline.yml`
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
