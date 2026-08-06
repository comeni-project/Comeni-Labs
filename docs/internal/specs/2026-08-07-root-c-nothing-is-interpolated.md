# Root C — every string the emitter writes has a declared kind

**Spec, 2026-08-07.** Closes A27, A34. Root C in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `b21f595`.

---

## The problem

Every string the emitter writes is one of five kinds. **The codebase distinguishes exactly one.**

| kind | fields | today | must be |
|---|---|---|---|
| Groovy **identifier** | `nf_process`, `node.id`, `Param.name`, port names, channel names | bare `str` | validated character class |
| **path fragment** | `nf_include` | bare `str` | relative, no `..`, no leading `/` |
| **prose** | `reason` | bare `str` | single line |
| **literal value** | `ParamValue`, `ext_args` | ✅ `_render_literal` | unchanged |
| **unbounded Groovy** | `entry_channel` | bare `str` | unchanged, but *marked* |

`ModuleContract` is almost entirely bare `str` — `id`, `nf_process`, `nf_include`, `container`,
`ext_args`, every provenance field. Nothing has ever inspected them, because contracts are not
reachable from an egress payload: the lockfile pins them by digest rather than embedding them, so
root A's guard never walked here.

**There are two output surfaces, not one.** `main.nf` goes through Jinja with six interpolation
points and one guarded (A34). `nextflow.config` is assembled by Python f-strings, and
`withName: {contract.nf_process}` is raw:

```
process {
    withName: LAB_SORT { ext.args = '' }
println 'CONFIG SURFACE ALSO INJECTABLE'
withName: OTHER { ext.args = '--flag' }
```

So **three escaping disciplines across two files**, and which field is which kind is written down
nowhere. A27 (prose) and A34 (identifier) are two of the unguarded kinds happening to get
exploited; `nf_include`, port names and `type_id` are the same kind and were never tried.

`type_id` deserves naming: it feeds `_channel_name()`, which replaces only `.` and `-`, so a type
id carrying a brace or newline reaches an assignment target. And a vocabulary type id is *a
filename stem* — filenames on Linux may contain newlines.

---

## The design

### 1. Classify at the type

New in `marks.py`, alongside root A's `Mark` enum:

```python
NfIdentifier = Annotated[str, Mark.NF_IDENTIFIER, AfterValidator(_groovy_identifier)]
"""A Groovy identifier: `[A-Za-z_][A-Za-z0-9_]*`. Emitted into declarations, so there is
no escaping option — an identifier is validated or it is not one."""

NfPath = Annotated[str, Mark.NF_PATH, AfterValidator(_relative_path)]
"""A relative path fragment under the emitted directory. No leading separator, no `..`
segment, no control characters."""

GroovyExpression = Annotated[str, Mark.GROOVY_EXPRESSION]
"""Unbounded Groovy, emitted verbatim. The **designed exception**: a laboratory bringing
its own type says how it arrives, and the compiler has no built-in idea what a FASTQ is.
Marked so that it is visibly the exception rather than merely being one."""
```

**The prose split is by destination, not by prose-ness:**

```python
Text = Annotated[str, Mark.FREE_TEXT]
"""Free prose that crosses a door and is never emitted into an artifact."""

Line = Annotated[str, Mark.FREE_TEXT, AfterValidator(_single_line)]
"""Free prose that reaches a generated file. No control characters."""
```

Both carry `Mark.FREE_TEXT`, so root A's `FREE_TEXT_FIELDS` allowlist is unaffected and its
count does not change. `GateFailure.tool_message` stays `Text` — **Nextflow stderr is inherently
multi-line and that field exists to carry it**, so a blanket control-character ban on `Text`
would have broken the one field it was proposed to protect.

### 2. Apply it

| field | becomes |
|---|---|
| `ModuleContract.nf_process` | `NfIdentifier` |
| `ModuleContract.nf_include` | `NfPath` |
| `ModuleContract.id` | `ContractId` |
| `ModuleContract.container` | `ContainerRef \| None` |
| `Param.name`, `InputPort.name`, `OutputPort.name` | `NfIdentifier` |
| `InputPort.type_id`, `OutputPort.type_id`, `GoalInput.type_id` | `TypeId`, itself validated identifier-safe |
| `Vocabulary` type ids (filename stems) | validated on load |
| `Vocabulary.entry_channels` values | `GroovyExpression` |
| `ResolvedValue.reason`, `DecisionRecord.reason` | `Line` |
| `GateFailure.tool_message` | `Text`, unchanged |

`nf_process` is then validated **at load**, before conformance runs — which is why A34's
`unverified` path stops mattering. A contract whose module source is absent is still emitted;
it simply can no longer carry a newline. Refusing unverified contracts outright was considered
and rejected: it would break the legitimate case (a lab's own module, not vendored here) to
close a hole the type already closes.

### 3. The emitter renders by class, and prose gets defence in depth

`_render_comment(text)` re-prefixes any continuation line with `// ` and refuses control
characters, as `_render_literal` already does for values. Belt and braces with `Line`: the
emitter must not depend on its input being clean, and the boundary must not depend on the
emitter being careful. That argument does not apply to identifiers, where validation is the only
available move.

### 4. `nextflow.config` stays Python, and routes through the renderers

`emit_config` keeps its logic — profiles, stub data, sorted dedup read well as Python and would
read worse as Jinja — but every interpolation goes through a renderer rather than an f-string.
Once `nf_process` is an `NfIdentifier` a raw f-string is no longer dangerous, merely
undisciplined; this makes the discipline uniform without reorganising for its own sake.

---

## How this composes with the other roots

- **Root A** classifies what may *cross a door*; root C classifies what may *reach a generated
  file*. Different surfaces, same idea, and they share the `Mark` vocabulary — so C's new markers
  must be added to A's enum, not invented beside it. **If A lands first, C's new types satisfy its
  allowlist on arrival, which is the guard working.**
- **Root E** says a `TypeId` must name a *declared* type. Root C says it must be *shaped* safely
  for emission. Both are needed and neither implies the other: `alignment.bam` is declared and
  safe; `evil}\nprintln 'x'` is neither; a plausible-looking undeclared id is shaped safely and
  still wrong.
- **Root B** reports when an overlay replaces an `entry_channel` (A24). Root C does not forbid
  that replacement — it stays unbounded Groovy by design. The two are complementary: B makes it
  visible, C makes it the only unbounded field.

---

## Verification

Root I applies. Each probe added, watched failing, reverted.

| probe | expected |
|---|---|
| `nf_process` containing a newline | refused **at contract load**, naming the field |
| `nf_process` containing `}` or a space | refused at load |
| `nf_include` with a `..` segment, or absolute | refused at load |
| `Param.name` / port name with a newline | refused at load |
| a vocabulary file whose stem contains a newline | refused at load |
| `reason` containing a newline, set on a `DecisionRecord` | refused at construction (`Line`) |
| a bundle hand-edited to carry a multi-line `reason`, run through `mendel upgrade` | refused on read; **and if the type is bypassed, `_render_comment` still produces a valid comment** |
| `GateFailure.tool_message` containing newlines | **still accepted** — regression guard for the split |
| an `entry_channel` of arbitrary Groovy | **still emitted verbatim** — the designed exception |
| `ext_args` containing a quote | still escaped by `_render_literal` |
| the shipped registry | **byte-identical `main.nf` and `nextflow.config`** |

The last two rows are the ones that catch over-correction. A fix that makes the spine's own
output move, or that breaks `entry_channel`, has gone too far.

---

## Blast radius

- `comeni_core/marks.py` — new markers, validators, the `Text`/`Line` split.
- `comeni_core/contract.py` — field types on `ModuleContract`, `Param`, `InputPort`,
  `OutputPort`, `Provenance`.
- `comeni_core/vocabulary.py` — validate type ids on load; `entry_channels` values become
  `GroovyExpression`.
- `comeni_core/ir.py`, `decision.py`, `egress.py`, `goal.py` — `reason` → `Line`; `type_id`
  fields.
- `mendel_compiler/emit.py` — `_render_comment`, config renderers.
- Tests: golden files must not move; `tests/test_egress.py` free-text count must not change.

The registry itself is unchanged — every shipped contract already uses valid identifiers, which
is why the byte-identical row above is a real check rather than a formality.

---

## What this spec does not cover

- **Whether a contract with absent module source should be emitted at all.** Recorded as
  considered and rejected here; if it is revisited it belongs with conformance, not with C.
- **`Param.default: Any` and `NfInput.literal: Any`** in `contract.py` — reviewer 2 flagged these
  as unverified hypotheses. They reach `_render_literal`, so they are contained for emission; as
  *types* they belong to root A's argument and are listed there as not-examined.
- **Root G.** A contract file that can be read two ways is a different problem from a contract
  field that can be rendered two ways.
