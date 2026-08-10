# Round three — the audit

**Scope:** `main` at `b0a4550`, the first audit of Plan 1.10's surface. Run by the method in
[`2026-08-07-round-two-brief.md`](2026-08-07-round-two-brief.md) — *revert and watch, not read* —
and narrowed by the operator on 2026-08-10 to **clean code and documentation-against-behaviour**.

Findings keep their numbers permanently. Round three starts at **A38**.

Every finding below was reproduced by execution. Commands are given so each can be re-run.

| # | Finding | Severity |
|---|---|---|
| A38 | `via: meta` and `via: directive` are declared, validated, recorded — and never emitted | **critical** |
| A39 | a non-templated `ext` key is rendered twice, so its value carries literal quote characters | important |
| A40 | `MD0208` was specified and never implemented; two writers for one destination concatenate | important |
| A41 | `MD0200` is published but unemittable, and its real failure is reported as a bad *goal* | important |
| A42 | five live refusals and properties have no test at all — deleting them is invisible | important |
| A43 | six documentation claims disagree with the code, including door 4's payload type | minor |
| A44 | `test_data` reaches `nextflow.config` unescaped — config-parse-time code execution | **critical** |
| A45 | `NfTemplate` validates only newlines — the string around `{value}` injects shell and Groovy | important |
| A46 | a tier-4 answer has two homes; `emit` and `upgrade` read different ones and disagree | **critical** |
| A47 | `mendel emit` silently erases a recorded gate verdict | important |
| A48 | a `pipeline.yml` with no `goal:` loads, and `upgrade` writes an empty pipeline at exit 0 | important |
| A49 | a refused `emit` half-regenerates the directory, then diagnoses its own damage as a hand edit | important |
| A50 | `mendel publish` is a silent in-place `upgrade` with every brake removed | **critical** |
| A51 | rules and vocabulary displacements are recorded at load and dropped before the artifact | important |
| A52 | a duplicate decision key silently discards a human override (`setdefault`, first wins) | important |
| A53 | `upgrade --out` protects only the source directory — it destroys any *other* pipeline's | important |
| A54 | a resolver may claim `source: HUMAN` and empty `needs_review()` — the red flag suppressed | minor→important |

**A38, A40 and two of A42's rows were independently reproduced** by two cold reviewers with no
knowledge of this document — the corroboration the independent-review method exists to produce.
A44–A49 are new, from those same two reviews; A50–A54 are from a third, on the replay /
`upgrade` / `publish` / layer-stacking subsystem. Every one was **re-verified first-hand in this
worktree before entry**, per the brief's rule; the reproductions below are mine, not the
reviewers'.

---

## A38 — two of the three emission routes carry nothing. **Critical.**

`routes.py` declares three emission sites. `contract.py` validates all three. `pipeline.py`
records all three into `pipeline.yml` with full provenance. **`emit.py` implements one.**

```python
# emit.py:227, inside _ext_scope — the only place a setting is read
for setting in sorted(step.settings, key=lambda s: s.name):
    if setting.via is not Via.EXT:
        continue          # META and DIRECTIVE leave here and are never seen again
```

`grep -rn "Via\." packages/*/src` returns six sites. Not one of them emits `META` or `DIRECTIVE`.

### Reproduction

Add two params to `registry/contracts/nf-core/star-align.yml`:

```yaml
  - name: cpus
    via: directive
    default: 7
  - name: strandedness_probe
    via: meta
    default: probe_value
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/probe
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

Exit 0, no diagnostic. `pipeline.yml` records both values with a `why:` and a tier:

```yaml
  - name: cpus
    value: 7
    via: directive
  - name: strandedness_probe
    value: probe_value
    via: meta
```

Neither string appears in `main.nf` or `nextflow.config`. The emitted process scope is:

```groovy
process {
    withName: STAR_ALIGN { ext.args = '--readFilesCommand zcat' }
    withName: SUBREAD_FEATURECOUNTS { ext.args = '-Q 0' }
}
```

No `cpus = 7`. No meta entry.

### Why this is critical

This is **issue #10 reopened one level down**, and issue #10 is recorded as closed by this plan.
The gotcha in `CLAUDE.md` states the rule this breaks:

> A resolved value reaching no tool is *deadness*, and no amount of forge output fixes it.

`CLAUDE.md` currently claims the opposite is now structural:

> Every setting declares the **route** that carries it to the tool, so a resolved value that
> reaches nothing is refused rather than emitted (issue #10).

A route is declared. Two of the three routes carry nothing, and nothing refuses. `MD0216` — the
one guard in this area — refuses a value whose *name* no contract declares; it does not ask
whether the declared route is implemented. `Param._route_is_complete` proves a route is
*well-formed*, never that it is *connected*.

`cpus` is the sharp case: a laboratory routing `cpus` to a directive gets a pipeline that
silently runs at Nextflow's default while `pipeline.yml` states, with a tier and a citation,
that cpus was resolved to 7.

### Why no test caught it

Every `Via.DIRECTIVE` test is in `packages/comeni-core/tests/test_routes.py`, and every one
tests the **`Param` validator** — that a directive param constructs, or refuses. Not one tests
that a directive param *emits*. `Via.META` has no test at all. The registry declares `via: ext`
three times and the other two routes zero times, so the shipped spine cannot see it.

This is A14's *"asserts over an empty loop"* with the loop one layer out: the declaration is
guarded thoroughly, the behaviour behind it not at all.

### Fix, in the order the repo would take it

1. A refusal is the cheap half and should land first: at `Pipeline.of`, refuse a `Setting`
   whose `via` the emitter does not implement. That converts a silent no-op into a diagnostic
   in the reserved band and cannot regress.
2. Implementing `META` and `DIRECTIVE` is the real fix. `_with_meta` and `_render_meta` already
   exist for measurements, and `withName` blocks already exist for `ext`, so both have a
   destination — this is wiring, not new machinery.
3. Whichever lands, the test must be an **emission** test, not a validator test.

---

## A39 — a non-templated `ext` key is rendered twice. **Important.**

`_ext_scope` calls `_render_literal` on each fragment *and* on the joined result.

```python
# emit.py:240 — per fragment
fragments.setdefault(setting.key.value, []).append(_render_literal(setting.value))
...
# emit.py:265 — and again on the join
f"    withName: {step.process} {{ ext.{key} = {_render_literal(joined)} }}"
```

`_render_literal` single-quotes and escapes. Applied twice, the quotes become part of the value.

### Reproduction

One param, nothing else:

```yaml
  - name: sample_tag
    via: ext
    key: prefix
    default: alpha
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/probe3
$ grep prefix /tmp/probe3/nextflow.config
    withName: STAR_ALIGN { ext.prefix = '\'alpha\'' }
```

In Groovy that is the string `'alpha'` **including the quote characters**, so every output file
this process names would carry them.

The templated keys escape this because a template fragment is inserted raw
(`setting.template.replace("{value}", rendered)`) and `step.ext_args` likewise. Only the
non-templated branch double-renders — and `prefix` is the only non-templated `ExtKey`, which is
exactly the key no contract in the registry uses and no test emits.

`grep -rn "prefix" packages/mendel-compiler/tests/test_emit.py tests/test_pipeline_file.py`
returns nothing.

**Fix:** append the raw value at line 240 and let the single `_render_literal` at the join do
the quoting — which is what the templated branch already does.

---

## A40 — `MD0208` was specified, planned, and never implemented. **Important.**

The spec assigns it a job:

> **`MD0208`** exists because `via: meta` and a `Measurement.meta_key` write to the same map.
> […] Two writers for one destination is a refusal, not a precedence rule nobody remembers.

The plan lists the step: *"Refuse two writers for one destination with `MD0208`."*

It is in neither `diagnostics.yml` nor any source file. `MD0208` is the **only gap** in
`MD0200`–`MD0216`, and three documents describe that range as contiguous (A43).

### Reproduction

Two params, different names, same destination:

```yaml
  - name: sample_tag
    via: ext
    key: prefix
    default: alpha
  - name: run_label
    via: ext
    key: prefix
    default: beta
```

```
$ grep prefix /tmp/probe2/nextflow.config
    withName: STAR_ALIGN { ext.prefix = '\'beta\' \'alpha\'' }
```

Silently concatenated, in name-sorted order (`run_label` before `sample_tag`), with A39's
double-quoting on top. `MD0212` does not catch it: that refuses two settings sharing a *name*,
and these have different names and the same *destination*, which is the distinction `MD0208`
was written to make.

The `via: meta` collision the spec actually names — a setting and a `Measurement.meta_key` both
claiming `single_end` — is currently unreachable only because A38 means no `via: meta` setting
reaches the meta map at all. **Fixing A38 without fixing A40 opens it.** These two should be
fixed together.

---

## A41 — `MD0200` is published but cannot fire, and its real failure blames the goal. **Important.**

`MD0200` is declared in `comeni_core/diagnostics.yml`, `refuses: True`, `fires_on: [build, emit,
upgrade]`, and it is published in the generated public table at `docs/reference/cli.md`. Its
`says` is *"a setting declares no `via:`, so nothing would carry its value"*, with a fix line.

No code emits it. `via` has no default, so the failure is Pydantic's, and the test that covers
the case says so in its own docstring — `test_routes.py:20`: *"MD0200. `via` has no default, so
this is a missing-field error."*

### Reproduction

Remove `via: ext` from `star-align.yml`'s `seq_platform`:

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/p200
mendel: this goal is not valid —
1 validation error for ModuleContract
params.0.via
  Field required [type=missing, input_value={'name': 'seq_platform', ...}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
```

Two defects in four lines:

- **The code the docs promise never appears.** A user who reads the published table and runs
  `mendel explain MD0200` gets a fix for a diagnostic nothing can produce.
- **"this goal is not valid" is the wrong noun.** The goal is fine; a *contract* is malformed.
  The message sends a reader to the file they did not write and cannot fix.

This is issue #18's territory — the half-declared error surface — and it is the concrete case
for it. **The issue's own numbers are stale:** it records *41 raise sites, 32 bare `ValueError`*.
Today the pure packages hold **79 raise sites, 47 of them bare `ValueError`**. Plan 1.10 nearly
doubled the surface while adding the diagnostics that were meant to shrink it.

```
$ grep -rn "raise " packages/*/src --include="*.py" | wc -l          # 79
$ grep -rn "raise ValueError" packages/*/src --include="*.py" | wc -l # 47
```

---

## A42 — five live refusals and properties have no test at all. **Important.**

A14's closure condition is that every guard has a recorded revert. These are the inverse case
and belong in the same ledger: the **code refuses correctly**, and **no test would notice its
deletion**. Each row below was produced by removing the condition and running the full fast
suite.

| Property | Site | Full fast suite after removal |
|---|---|---|
| `MD0215` — an input names exactly one of `source`/`channel` | `pipeline.py:176` | 542 passed |
| `MD0201` — a value outside the substitutable class is refused | `emit.py:242` | 542 passed |
| `MD0204` — a template is one line | `marks.py:327` | 542 passed |
| `ext.args` fragments are **name-sorted** | `emit.py:226` | 542 passed |
| the process scope is `sorted(set(blocks))` | `emit.py:279` | 542 passed |

All five refusals are **live** — driving them by hand raises correctly:

```
>>> Param(name="x", via=Via.EXT, key=ExtKey.ARGS, template="--a {value}\n--b")
ValueError: MD0204: a template is one line …
>>> StepInput(port="reads", source="a.b", channel="fastq.reads")
ValueError: MD0215: input reads must name exactly one of `source` or `channel`
```

So this is not A14's *inert guard*. It is the case one step earlier: **a refusal with no guard
over it.** The distinction matters for the fix — the code is right, the tests are absent.

The last two rows are the sharpest, because the code **predicts its own blind spot** and no one
acted on the prediction:

> `emit.py:212` — "With one setting that sort is unobservable, which is exactly why a test
> carrying one cannot see a sort bug — and byte-identical emission depends on it."

That docstring is correct, and there is still no test with two settings on one step. Reversing
the sort changes nothing observable in the whole suite. Invariant 10 — *same `Goal` →
byte-identical `.nf`* — rests on an ordering the tests cannot see.

### Watched failing, and correctly

Recorded so the negative result is legible too. These were reverted and **caught**, naming the
right thing: `MD0216`, `MD0212` (both the duplicate-setting and duplicate-step-id halves),
`MD0207`, `MD0211`, `MD0204` (both `contract.py` halves), `MD0205` (both halves), `MD0209`, and
`_render_literal`'s Groovy escaping.

**One correction to my own probe.** My first `MD0207` probe changed the message text from
`MD0207:` to `MD0207x:` and stayed green; I recorded it as inert before checking. It is not —
removing the condition outright is caught by
`test_pipeline_file.py::test_a_newer_version_is_refused`. The probe was invalid because that
test asserts `"MD0207" in err`, and `MD0207x` contains that substring. Worth one line rather
than a finding: **substring assertions on diagnostic codes do not pin the code.**

---

## A43 — documentation that disagrees with the code. **Minor, and one of them is not.**

The generated surface is honest. `tools/generate_diagnostics_doc.py --check` passes, and
`docs/reference/cli.md` correctly omits `MD0208`. **Every drift below is in hand-written prose**,
which is the same shape as A33 — the literal list is right and the sentence about it is wrong.

| Where | Claim | Reality |
|---|---|---|
| `CLAUDE.md:444`, `CHANGELOG.md:40`, journal 2026-08-09-evening | "24 codes: `MD0100`–`MD0108`, `MD0200`–`MD0216`" | **25** codes; the second range is not contiguous — `MD0208` does not exist |
| `docs/internal/README.md:129` | "sixteen new diagnostics (`MD0108`, `MD0202`–`MD0203`, `MD0206`–`MD0216`)" | that list is 14 entries and 13 real codes |
| `docs/internal/README.md:105` | "fourteen diagnostics arrive" | contradicts line 129 in the same file |
| **`docs/design/clinical-data-protection.md:141`** | the four-doors table gives door 4's payload as **`PublishBundle`** | door 4 carries `Pipeline`; `PublishBundle` no longer exists |
| `docs/design/clinical-data-protection.md:385` | names the guard `test_publish_bundle_is_typed` | no test of that name exists |
| `docs/reference/pipeline-schema.md` | field-by-field reference for `pipeline.yml` | `CallArg.empty_width` is never mentioned — the third of the three shapes `CallArg` documents itself as mirroring |
| issue #18 | "41 raise sites, 32 bare `ValueError`" | 79 and 47 |

**The clinical doc is the one that is not minor.** It is public, it is the reference `CLAUDE.md`
points at for *"the egress boundary"*, and its doors table is written in the present tense. A
clinical reader auditing what leaves the building against that table would be auditing a type
that was deleted. The property still holds — `tests/test_egress.py` guards it through `DOORS` —
so this is a documentation defect and not an egress defect, but it is the door with no undo and
the wrong noun is on the page.

`CallArg.empty_width` is the reverse of a harmless omission: `NfInput.empty` is the field the
gotchas single out (*"a 2-tuple in a 3-tuple slot dies on Path value cannot be null"*), it is
present in every real `pipeline.yml`, and the one page that promises to explain the file
field-by-field skips it.

---

## Second tranche — code injection and the tier-4 round trip

Found by two independent cold reviewers dispatched over the same range with no knowledge of the
first tranche, and re-verified here. The first tranche was the *narrowed* scope — clean code and
docs. This tranche is what an adversarial pass at the invariants turned up, and it is more
serious: two critical code-execution or determinism defects that the narrowed scope would not
have reached.

The unifying shape is the one this repo names in its own gotchas — **a guard that checks the
*shape* of a string and not its *content*** — arriving on the surface Plan 1.10 widened by
making `pipeline.yml` hand-editable and registry-authored strings flow verbatim into generated
Groovy.

### A44 — `test_data` reaches `nextflow.config` unescaped, and executes at config-parse time. **Critical.**

`_render_test_data` (`emit.py:173`) wraps each value in **double** quotes with no escaping:

```python
def _render_test_data(value: list[str]) -> str:
    if len(value) == 1:
        return f'"{value[0]}"'
    return "[" + ", ".join(f'"{item}"' for item in value) + "]"
```

A double-quoted Groovy string is a GString, and `params.gtf = "…"` is a statement, not data.
`TestDataRef` (`marks.py:410`) is `Annotated[str, Mark.TEST_DATA_REF]` — **marked, never
validated**. Its own docstring promises "a URL pinned to a commit, never a laboratory's own
path", and nothing enforces it.

### Reproduction — the documented hand-edit workflow

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/rce
# in /tmp/rce/pipeline.yml, replace the genes.gtf test_data line with:
#   - 'x"; new File("/tmp/PWNED").text = "rce"; def z="'
$ uv run mendel emit /tmp/rce/pipeline.yml --out /tmp/rce
MD0213: … Regenerating.
$ grep params.gtf /tmp/rce/nextflow.config
        params.gtf = "x"; new File("/tmp/PWNED").text = "rce"; def z=""
$ cd /tmp/rce && nextflow config -profile test .
nextflow config exit: 0
$ cat /tmp/PWNED
rce                       # executed by `nextflow config` alone — no pipeline run
```

**Reachable through the registry with no hand-edit at all.** `test_data` is declared in the
vocabulary, and vocabularies stack. A single overlay layer replacing `annotation.gtf.yml`'s
`test_data` with the same payload produces an identical `params.gtf` and executes on
`nextflow config`. A lab installing an untrusted `--registry` overlay is enough; the payload
never touches the goal, so no goal-door blocklist sees it.

### Why the guards do not catch it

The egress guard (`test_egress.py`) verifies a leaf **carries a Mark**, never its content — so
this same payload also crosses **door 4 (publication)** unremarked, because `test_data` rides on
`Channel` inside the `Pipeline` (`pipeline.py:240`). `substitutable()`/`NfTemplate` guard the
`ext.args` route, a different code path. `_render_literal`, which *does* single-quote and escape,
is used for `ext` values and pointedly **not** for test-profile params.

### Fix

Render `test_data` through `_render_literal` (single-quoted, escaped) rather than raw
double-quote wrapping, and give `TestDataRef` an `AfterValidator` enforcing the
URL-pinned-to-commit shape its docstring already promises. The generated stub-data params on the
same path deliberately need `${projectDir}`, so the escaping must be scoped to the lab-derived
`test_data` values, not the stub literals beside them.

---

### A45 — `NfTemplate` validates only newlines, so the string around `{value}` is an injection point. **Important.**

`_nf_template` (`marks.py:311`) rejects a newline and nothing else. The spec's §5 argument is
that the resolved `{value}` is *validated, not escaped, because it lands in a shell command
line* — and the template text around it lands in the **same** place, checked for nothing.

**Shell path** — any metacharacter, straight into `ext.args`:

```
# template: -Q {value}; touch /tmp/OWNED #
$ uv run mendel emit /tmp/tpl/pipeline.yml --out /tmp/tpl
$ grep SUBREAD_FEATURECOUNTS /tmp/tpl/nextflow.config
    withName: SUBREAD_FEATURECOUNTS { ext.args = '-Q 0; touch /tmp/OWNED' }
```

**Groovy path** — a `${…}` fragment routes into a closure GString (`emit.py:261`) with no
escaping, so it is arbitrary Groovy at task runtime:

```
# template: -Q {value}"${new File("/tmp/PWNED_TPL").text='x'}"
$ grep SUBREAD_FEATURECOUNTS /tmp/tpl/nextflow.config
    withName: SUBREAD_FEATURECOUNTS { ext.args = { "-Q 0"${new File("/tmp/PWNED_TPL").text='x'}"" } }
```

`TypeAdapter(NfTemplate).validate_python(...)` accepts both verbatim. The template is
contract/registry-authored, so an unverified contract or a malicious overlay carries it; no
conformance check covers an unverified contract's template. This is lower than A44 only because
`ext.args` is deferred to task run rather than executed at config parse — I confirmed acceptance
and emission into the executable closure, not a landed proof file from a full stub job, so the
runtime-execution step is standard GString-in-closure behaviour rather than something I ran.

Independent of any attacker, the same hole breaks a *legitimate* template: `--rg "PL:{value}"`
produces malformed config on the closure path. **Fix:** give `NfTemplate` a real grammar — forbid
bare `"` and backtick, allow `{value}` and a small allowlist of `${meta.<id>}` / `${task.<id>}`,
reject any other `${…}` body.

---

### A46 — a tier-4 answer has two homes, and `emit` and `upgrade` read different ones. **Critical.**

`docs/reference/pipeline-schema.md` tells the user, verbatim:

> **Answering a tier-4 question is editing this file.** Set the `value`, run `mendel emit`, and
> the answer reaches the tool.

That is `settings[].value`, and `emit` reads it (`_settings` → `node.params`, `pipeline.py:410`).
But `upgrade` replays from `decisions[].human_override` (`replay.py`), which the schema doc never
mentions. The two are independent fields in one file, and **nothing checks that they agree**.

### Reproduction — set them to different values

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/c2
# settings[seq_platform].value: nanopore     decisions[…].human_override: illumina
$ uv run mendel emit /tmp/c2/pipeline.yml --out /tmp/c2
$ grep -o 'PL:[a-z]*' /tmp/c2/nextflow.config
PL:nanopore
$ uv run mendel upgrade /tmp/c2/pipeline.yml --out /tmp/c2next --root .
  ANSWERED star_align.seq_platform = 'illumina'
$ grep -o 'PL:[a-z]*' /tmp/c2next/nextflow.config
PL:illumina
```

One file, one question, two answers, two pipelines, no diagnostic. This is the product claim —
*"Same goal in → same pipeline out"* — failing on **the plan's headline deliverable**, issue #10,
inside the single artifact whose entire purpose was to end the four-file split where evidence and
pipeline could diverge. `test_answering_a_tier_four_question_in_the_file_reaches_the_tool`
(`test_pipeline_file.py:70`) edits `settings[].value` and only ever calls `emit`, so the
round-trip through `upgrade` is uncovered.

**Fix:** make `settings[].value` the single writable answer; on load, a `value` that differs from
what the recorded decision would produce *becomes* the `human_override` (source `HUMAN`), and a
`human_override` contradicting `settings[].value` is a refusal in the `MD02xx` band. One of the
two fields must stop being independently writable.

---

### A47 — `mendel emit` silently erases a gate verdict. **Important.**

`cli.py:395` calls `pipeline_file.stamp(out, pipeline)` with `gate` defaulting to `None`
(`pipeline_file.py:94`), so `stamp` does `model_copy(update={"gate": None})`.

```
$ uv run mendel publish /tmp/i2/pipeline.yml --gate lint
$ grep '^gate:' /tmp/i2/pipeline.yml
gate: lint
$ uv run mendel emit /tmp/i2/pipeline.yml --out /tmp/i2      # file not stale, bytes identical
$ grep '^gate:' /tmp/i2/pipeline.yml
gate: null
```

The spec makes `gate:` load-bearing — *"the evidence and the pipeline are one document"* — and the
documented archive workflow is `pipeline.yml` + regenerate-later. Regenerating drops the
certification. **Fix:** `stamp(out, pipeline, gate=pipeline.gate)`.

---

### A48 — a `pipeline.yml` with no `goal:` loads, and `upgrade` empties it at exit 0. **Important.**

`Pipeline.goal` carries `Field(default_factory=Goal)` (`pipeline.py:291`). Task 6's correction #4
made `goal` keyword-only with no default *on `Pipeline.of()`* for exactly this reason — but the
**model field** kept its default, and the load path uses the model, and the load path is the one
hand-editing exercises.

```
# delete the goal: block from /tmp/i3/pipeline.yml
$ uv run mendel emit /tmp/i3/pipeline.yml --out /tmp/i3          # exit 0
$ uv run mendel upgrade /tmp/i3/pipeline.yml --out /tmp/i3next --root .
  CHANGED   trimgalore … -> (removed)  (tier 1) no longer routed
  … all five steps removed …
0 modules, 0 requiring review
$ grep '^steps:' /tmp/i3next/pipeline.yml
steps: []
```

Dropping a section is the likeliest hand-edit mistake there is, and it produces an empty pipeline
with no error. **Fix:** make `Pipeline.goal` required, and refuse in the upgrade path when
re-resolution yields zero steps from a non-empty previous.

---

### A49 — a refused `emit` half-regenerates, then blames the user for the damage. **Important.**

`emit` writes `main.nf` (`cli.py:393`), then `nextflow.config` (394) — and `MD0201` fires *inside*
`emit_config`. So an edit that renames a process (valid → `main.nf` rewritten) and carries one
non-substitutable value (fails in `emit_config`) leaves `main.nf` rewritten and `nextflow.config`
stale, with no rollback:

```
# process: TRIMGALORE -> TRIMGALORE2   AND   min_mqs value: 0 -> '0 bad'
$ uv run mendel emit /tmp/i6b/pipeline.yml --out /tmp/i6b
MD0213: … Regenerating.
mendel: MD0201: subread_featurecounts.min_mqs is '0 bad', which is outside the substitutable class…
$ # main.nf was rewritten anyway. Fix the value and retry:
$ uv run mendel emit /tmp/i6b/pipeline.yml --out /tmp/i6b
mendel: MD0214: main.nf changed since it was generated, and re-emitting would overwrite that.
  Make the change in pipeline.yml and run this again — that is the file the pipeline is built from.
  To discard it instead, delete main.nf and run this again.
```

The user did make the change in `pipeline.yml`. `MD0214` blames them for a modification **Mendel
itself made** on the failed run, and the only exit is to delete `main.nf`. This is the same
A4-class posture (`cli.py:222`) that `upgrade` already applies and `emit` does not. **Fix:** render
both files in memory, then write both — a refusal must leave nothing behind.

---

### Second-tranche minor

- **`_ParamView` is dead code** (`emit.py:14`, with its `NamedTuple` import) — no reference
  anywhere but its definition. Twelve lines below it, `_render_comment` was deleted with a comment
  on why dead defensive code is worse than none; this survived the same edit.
- **`mendel emit` prints nothing on success**, though it rewrites two files and re-stamps a third.
- **`upgrade --dry-run` prints only non-empty categories**, where the spec's example and
  `cli.md` show five headings — silence reads as an error rather than as zero drift.

---

## Third tranche — the replay / upgrade / publish boundary

Found by a third cold reviewer scoped to `replay.py`, `diff.py`, `resolve.py`, `layers.py`, the
`upgrade`/`publish` verbs and their tests, and re-verified here. The unifying shape is distinct
from the second tranche's and worth stating: **a fact is correctly computed and then not carried
to where it is read.** `resolver.orphaned` is computed on publish and discarded; `Layers.displaced`
is computed for four kinds and read for two; a second decision record is parsed and dropped. Each
has a correct producer, a correct consumer *elsewhere*, and no wire between them — and each test
that should have caught it asserts on the producer and stops.

### A50 — `mendel publish` is a silent in-place `upgrade` with every brake removed. **Critical.**

`publish` and `upgrade` share one code path (`cli.py:169`): both load the previous `pipeline.yml`,
build a `ReplayResolver(previous.decisions)`, **re-resolve against the currently-installed
registry stack**, re-emit, and re-write. Two differences, both fatal for the door with no undo:

1. `cli.py:186` sets `args.out = source.parent` for publish — it writes **in place**, over the
   artifact a person just read. The "never in place" refusal at line 187 is in the `elif`, which
   publish never reaches.
2. `cli.py:230` gates the entire safety report — `DRIFT`, `CHANGED`, `STALE`, `ORPHANED`, and the
   `MD0203` refusal that *halts* an upgrade — on `command == "upgrade"`. On publish,
   `resolver.orphaned` and `resolver.stale_overrides` are computed inside `_report_upgrade`, which
   is never called.

### Reproduction — publish against an installed overlay that reroutes the aligner

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/pub
# record a human override: human_override: illumina on star_align.seq_platform, then emit
$ grep -o 'star/align@[0-9.]*' /tmp/pub/pipeline.yml | head -1     # star/align@1.11.0
$ uv run mendel publish /tmp/pub/pipeline.yml --registry registry/ --registry /tmp/overlay --gate lint
  … gate lint: PASS  (exit 0)
$ grep -o 'hisat2/align@[0-9.]*\|star/align@[0-9.]*' /tmp/pub/pipeline.yml | head -1   # hisat2/align@2.2.2
$ grep 'human_override:' /tmp/pub/pipeline.yml                     # human_override: null
$ grep '^gate:' /tmp/pub/pipeline.yml                              # gate: lint
```

The aligner changed `star → hisat2`, the lab director's answer is **gone**, a passing gate is
stamped, and the input artifact is overwritten in place — exit 0. `publish` certified a pipeline
nobody read. Its docstring (`cli.py:326`) claims "a person can read what they are about to
publish"; publish rewrites it first.

### Why the suite did not catch it

All eleven tests in `test_publish.py` call `main(["publish", …])` with **no `--registry`**, so they
certify against the exact registry that built the pipeline — re-resolution is a fixed point and the
missing report has nothing to report. The shape none has: **build against registry A, publish
against registry B.** `test_upgrade.py` has exactly that shape for `upgrade` (the `MD0203` orphan
refusal) and it is never re-run for `publish`.

### Fix

Drop `and args.command == "upgrade"` at line 230 so `_report_upgrade` runs for both — the reviewer
applied that one-line change and the fast suite went **541 passed, 1 failed**, the single failure a
capsys-buffer bleed in an unrelated test, meaning *nothing pins the current behaviour*. Beyond that,
`publish` should **refuse** when re-resolution moves the pipeline (certifying something the operator
did not read) rather than only reporting it, and should not write in place.

---

### A51 — displacements are recorded at load and dropped before the artifact. **Important.**

`layers.load()` assembles `Layers.displaced` from all four kinds (`layers.py:104`) — its docstring:
*"one field rather than four conventions."* **That field has no reader.** `resolve.py:70` rebuilds
its own list from **two** kinds:

```python
displaced=[*measurements.displaced, *registry.displaced],
```

`vocabulary.displaced` and the rule table's displacements never join it, though the comment two
lines up says they do. So an overlay that displaces a vocabulary type or a rule reroutes the
pipeline with **no `OVERLAY` line and an empty `displaced:` in `pipeline.yml`** — the exact
"installed overlay reroutes a pipeline silently" that invariant 11 forbids.

### Reproduction

```
# /tmp/ov2/vocabularies/annotation.gtf.yml replaces the entry channel:
#   entry_channel: "Channel.fromPath(params.lab_gtf_override, …)"
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --registry /tmp/ov2 --out /tmp/vocab
5 modules, 1 requiring review         # no OVERLAY line
$ grep lab_gtf_override /tmp/vocab/main.nf        # the reroute happened
    ch_annotation_gtf = Channel.fromPath(params.lab_gtf_override, …)
$ grep -A3 '^registry:' /tmp/vocab/pipeline.yml | grep displaced
  displaced: []                       # and it is not recorded
$ python -c "from mendel_resolver import layers; print(layers.load(['registry','/tmp/ov2']).displaced)"
[Displacement(kind=VOCABULARIES, key='annotation.gtf', winning_layer='lab-vocab', …)]   # load knew
```

**And the wired half is itself unguarded.** Reverting `*measurements.displaced` out of
`resolve.py:70` — undoing the A23 fix — leaves the fast suite at **542 passed**. `test_audit_regressions.py`
A23/A24 assert on `layers.load(...).displaced` and stop; they never check the record reaches
`PipelineIR.displaced` or the artifact. Only A25 (contracts) does.

**Fix:** pass `loaded.displaced` into `resolve()` (or set `ir.displaced` from it in `cli.py`) rather
than re-deriving from two kinds, so "one mechanism" is enforced by there being one source, and add
one artifact-level test per `DeclaredKind`.

---

### A52 — a duplicate decision key silently discards a human override. **Important.**

`ReplayResolver.__init__` uses `setdefault`, so the first record for a key wins. Its own comment
calls two records for one key "a corrupt bundle" whose arbitrary resolution "would be the coin flip
invariant 8 forbids" — then picks one silently. Nothing refuses a duplicate: `Pipeline` checks
duplicate *step* ids (MD0212) but not decision keys, and `yaml_strict` refuses repeated *mapping*
keys, not repeated *list* entries.

### Reproduction — append a second record, the natural shape when a tool appends rather than edits

```
# decisions: two entries for star_align.seq_platform; the second carries human_override: illumina
$ uv run mendel emit /tmp/dup/pipeline.yml --out /tmp/dup
$ uv run mendel upgrade /tmp/dup/pipeline.yml --registry registry/ --out /tmp/dupnext
1 decisions replayed, 0 newly asked
  REVIEW  star_align.seq_platform
$ grep human_override /tmp/dupnext/pipeline.yml
  human_override: null              # illumina erased; the same file edited in place answers correctly
```

`test_replay.py::test_replay_is_deterministic_over_duplicate_keys` feeds exactly this input but both
records are resolver choices — **neither carries a `human_override`** — so it asserts determinism and
is blind to the only case where "first wins" costs anything. A fixture that agrees with itself, the
brief's own named shape.

**Fix:** refuse a duplicate decision key at load, beside MD0212 — the docstring already argues it is
corruption. At minimum, add the dropped record to `stale_overrides` so it is reported.

---

### A53 — `upgrade --out` protects the source directory and no other pipeline. **Important.**

The guard compares `args.out.resolve() == source.parent.resolve()` — an identity check against one
directory, not a check that the target is safe. Upgrading into a *different* pipeline's directory
destroys it.

### Reproduction

```
$ uv run mendel build … --out /tmp/A                                  # star aligner
$ uv run mendel build … --registry registry/ --registry /tmp/ov --out /tmp/B   # hisat2 aligner
$ uv run mendel upgrade /tmp/A/pipeline.yml --registry registry/ --out /tmp/B
1 decisions replayed, 0 newly asked                                   # exit 0, no warning
$ grep -o 'star/align@[0-9.]*\|hisat2/align@[0-9.]*' /tmp/B/pipeline.yml | head -1
star/align@1.11.0                                                     # B's hisat2 pipeline destroyed
```

**The working half is also inert.** Reverting `.resolve()` to plain `==` leaves the fast suite at
**542 passed** — `test_upgrade_refuses_to_write_into_the_directory_it_read` passes the identical
string, so `==` satisfies it and any *other spelling* of the same path (relative, `..`, symlink)
bypasses the guard undetected.

**Fix:** refuse `--out` when the target already holds a `pipeline.yml` that is not the one being
read (absent `--force`); and add relative/`..`/symlink cases to the existing test, since `.resolve()`
is correct and deserves a guard that watches it.

---

### A54 — a resolver may claim `source: HUMAN` and empty `needs_review()`. **Minor today, Important the day `mendel-ai` ships.**

`ir.py:35` drops a required-review value from `needs_review()` exactly when
`source is ValueSource.HUMAN`. `source` is declared vocabulary set by the resolver, not proof, so a
resolver — including a future model adapter behind the declared `AmbiguityResolver` port — can return
`source=HUMAN` for a value no human saw, and the CLI's `REVIEW` list and `N requiring review` count
both drop it. Invariant 6's *letter* survives (tier stays 4, a record is written); its *spirit* — the
red thing a person must look at — does not.

No protection-profile bypass exists **today**, only because `sealed`'s "tier 4 blocks the build" is
unimplemented (issue #2). When it lands it will key on `tier`, not `source`, so it would still block —
but that safety is currently luck, not design, and worth pinning. The artifact is also internally
inconsistent — `why.source: human` with a matching `decisions[].human_override: null` — and nothing
checks the two agree. **Fix:** make `HUMAN` non-assertable through the port (derive it from
`record.human_override`, the only evidence a human touched anything), or add a `Pipeline` validator
requiring every `why.source: human` to have a matching non-null `human_override`.

---

## Clean — attacked and held

Named, because without this section a reader cannot tell what was examined from what was skipped.

- **The documented headline flow is honest.** All seven commands in `CLAUDE.md`'s block run
  clean: `explain`, `build`, `emit`, `upgrade --dry-run`, `upgrade --out`, `profile`, and
  `generate_types.py --check`.
- **The issue #10 demo in the journal reproduces exactly as written.** Editing `value: null` to
  `nanopore` in `pipeline.yml` and re-emitting fires `MD0213` and puts `PL:nanopore` into
  `ext.args`. The `via: ext` route works end to end.
- **`mendel emit` really needs no registry.** Run from `/tmp` against an absolute path, with no
  `--registry`, it regenerates correctly.
- **Invariant 14's "seven fields" matches the guard's literal list**, entry for entry. The
  sentence that has drifted three times is currently accurate.
- **The generated diagnostics table is current**, and the check that keeps it so works.
- **Every diagnostic code that any source file emits is mentioned somewhere in the tests** —
  though see A42, since mention is not assertion, and my first measure of this counted comments.
- **`make check` is green at 542 passed, 3 deselected**, matching the journal's number exactly.
- **`MD0207`, `MD0211`, `MD0212`, `MD0205`, `MD0209`, `MD0216`** and `_render_literal`'s escaping
  were each reverted and each failed, naming the right thing.

### From the adversarial reviews — genuinely attacked, held

Recorded because these are the strongest parts of the surface and a reader needs to know they
were pushed on, not skipped. Each was tried by a cold reviewer and confirmed here.

- **Determinism under `PYTHONHASHSEED`.** The spine was built under seeds `0, 1, 7, 12345, 99991`
  and `diff -r` is byte-identical across all. A model-graph scan found every `frozenset` payload
  field carries a sorting `field_serializer` except `TypeDeclaration.states` — and that one is
  benign, folded into `Vocabulary.types` which does sort, and never itself digested. Invariant 10
  holds against hash-seed variation. (It does **not** hold against A46, which is a different
  mechanism — two fields, not one ordering.)
- **Digest forgery and directory hashing.** `digest_of_directory` domain-separates with `_FILE`,
  hashes both filename and content to fixed-width hex (the A21 fix), and refuses symlinks (A9). No
  collision or symlink bypass found.
- **`emitted.from_digest` divergence.** Editing `pipeline.yml` and re-emitting fires `MD0213`;
  editing a generated `main.nf` and re-emitting fires `MD0214`; `content_digest` excludes
  `emitted`, so it round-trips. No silent divergence found. (A47 is a *different* defect — the
  verdict is destroyed rather than the digest desynchronised.)
- **The egress allowlist itself.** `Pipeline` is `frozen=True, extra="forbid"`; `_leaf_problems`
  is a real allowlist over the whole payload graph and rejected a synthetic bare-`str` field on
  probe. The boundary enforces *shape declaration* correctly — A44's payload crosses it only
  because a declared, marked type validates its *content* nowhere, which is a gap in the marked
  types, not a hole in the allowlist.
- **Invariant 15 through the goal door.** `HumanParamValue` / `_reject_path_shaped` still rejects
  `/data/patients/…` and sequencing-suffix values on `ParamOverride.value` and `human_override`.
  Held. `test_data` evades it only because it is registry-authored, not goal-authored — see A44.
- **`NfIdentifier`, `EdgeRef`, `NfPath`, `_render_literal` escaping** each rejected the
  metacharacter payloads tried against them. The injection surface is exactly the two
  *marked-but-not-content-validated* types, `TestDataRef` (A44) and `NfTemplate` (A45), and not
  these.

### From the replay/upgrade review — genuinely attacked, held

- **`upgrade --dry-run` writes nothing.** Verified by hashing the tree before and after — identical —
  and a *refusing* dry run (MD0203) created no output directory either. The return is before
  `args.out.mkdir`.
- **Symlink attacks on `upgrade --out`, both directions** (out→source, and source reached via a
  symlink) are refused. The guard *body* is right; only its test is missing — see A53.
- **The parameter-override fix is properly guarded.** Reverting the `[None]` special case in
  `_still_applies` fails five named replay tests; that regression cannot silently return. And the
  `[None]`-domain class was swept across all three `Ambiguity` kinds — only `ParamAsked` has a
  degenerate domain and it is the one handled; `ProducerAsked`/`SourceAsked` build candidate lists
  only at length ≥ 2, so the membership check is live for them.
- **The layer digest covers the bytes the registry loads.** `digest_of_directory` hashes every file
  under the layer (no extension filter), name and content, `_FILE`-separated — a strict superset of
  what the loader reads. `drift_against`'s layer comparison reports a reorder, an addition, and a
  same-name-different-digest layer. No change got past it.
- **The gate is honest about *what it ran*.** No way found to stamp a verdict the freshly-emitted
  files had not earned; `emit` correctly clears the verdict (which is A47 — cleared when it should be
  carried, a different defect). A50's problem is not the gate lying but *which* pipeline it gated.

## Not audited

`test_purity.py`, `test_purity_runtime.py` and the registry-stacking passes (invariant 11's four
kinds) were out of the narrowed scope and are untouched by this round. The round-two brief's
passes 1, 2 and 4 are therefore still open for round three, as is the `Resolution.source`
truthfulness question that Plan 1.10 raised and deliberately left.

`upgrade --out` resolving to the input directory — named in the 2026-08-09 journal as worth
attacking — was **not** reached.
