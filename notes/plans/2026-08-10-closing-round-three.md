# Plan 1.11 — Closing Round Three Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement
> this plan task-by-task, sequentially, in the worktree `.worktrees/plan-1.11`. **Do NOT use
> `subagent-driven-development`** — CLAUDE.md § *How to start implementing* overrides the
> writing-plans default: drive this plan yourself. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the seventeen round-three audit findings (A38–A54), four of them critical, so the
fix-then-re-audit loop's exit criterion — no critical finding survives — is met.

**Architecture:** Two defect shapes. *A guard checks a string's shape, not its content* — fixed by
giving the marked types (`TestDataRef`, `NfTemplate`) real content grammars and by wiring the two
dead emission routes. *A fact is computed and never carried to where it is read* — fixed by making
`publish` certify without re-resolving, carrying four-kind displacements to the artifact, and
collapsing the tier-4 answer to one writable field. Pure packages only; no new dependency, no
network.

**Tech Stack:** Python 3.12, Pydantic v2, `uv` workspace, pytest, Jinja2 (emitter templates),
Nextflow 25.10.4 (gate target). Design authority: `notes/specs/2026-08-10-closing-round-three.md`.

## Global Constraints

- **`make verify`, never `make check` alone, gates every task.** Every task touches `emit.py`,
  `cli.py`, `pipeline.py`, `resolve.py` or `router.py`; `make check` deselects `test_counts.py`,
  the only tests that run a real tool. (`make verify` needs Docker, ~2 min.)
- **Every refusal added or restored earns a guard-ledger row, reverted and watched.** Append to
  `notes/audits/guard-ledger.md`: break the code, run the guard, paste what you saw, restore.
  A refusal with no failing revert is the inert guard A14 names.
- **Reproduce before fixing.** Each task's first step runs the audit's own reproduction and watches
  it misbehave; the fix is done when the same reproduction refuses or behaves.
- **Byte-identical emission is a hard requirement (invariant 10).** Anything serialising a set sorts
  on output; any new emitter branch is checked against a two-item input, not a one-item one.
- **A marked string reaching Groovy is refused when malformed, never silently escaped** — except
  where the value legitimately lands in a shell command line, where it is escaped by `_render_literal`
  exactly as today. Refusing names the author's mistake; rewriting hides it.
- **Line length 100** (`ruff check`). **No `ruff format` sweeps** — 28 files are hand-wrapped.
- **Diagnostic codes are data.** A new code (`MD0208`) is added to
  `packages/comeni-core/src/comeni_core/diagnostics.yml`; `make docs` regenerates
  `docs/reference/cli.md` and CI checks it is current.

**Test-writing note.** End-to-end CLI tests through `tests/test_pipeline_file.py`'s helpers are the
right design here, because the audit's core lesson is that only a test running a real emit/build
catches these bugs. Those helpers: `_build(tmp_path, name="p") -> out`,
`_emit(out, capsys, path=None) -> (code, stderr)`, `_load(out) -> Pipeline`,
`_answer(out, name, value)`. `GOAL` and `ROOT` are module constants. Unit-level validator tests go
in `packages/comeni-core/tests/test_routes.py` / `test_marks.py` where a `Param`/`NfTemplate` is
constructed directly.

---

## Task 1: A44 — escape `test_data`, and validate `TestDataRef`

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_render_test_data`, ~line 173)
- Modify: `packages/comeni-core/src/comeni_core/marks.py` (`TestDataRef`, ~line 410; add validator)
- Test: `tests/test_pipeline_file.py` (add), `packages/comeni-core/tests/test_marks.py` (add)
- Ledger: `notes/audits/guard-ledger.md`

**Interfaces:**
- Consumes: `_render_literal(value) -> str` (already single-quotes and escapes Groovy).
- Produces: `TestDataRef` gains an `AfterValidator`; `_render_test_data` emits escaped values.

- [ ] **Step 1: Write the failing test (end-to-end injection)**

```python
# tests/test_pipeline_file.py
def test_test_data_is_escaped_not_executed(tmp_path, capsys):
    out = _build(tmp_path)
    p = out / "pipeline.yml"
    payload = 'x"; throw new RuntimeException("PWNED"); def z="'
    text = p.read_text().replace(
        "reference/genes.gtf", "reference/genes.gtf\n#poison", 1
    )  # anchor exists; real edit below targets the test_data list item
    # Edit the annotation.gtf test_data entry to the payload:
    import yaml
    doc = yaml.safe_load(p.read_text())
    for ch in doc["channels"]:
        if ch["type_id"] == "annotation.gtf":
            ch["test_data"] = [payload]
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    config = (out / "nextflow.config").read_text()
    # The payload must be a single-quoted, escaped literal — never a bare statement.
    assert 'throw new RuntimeException' not in config or "'x\\\"" in config
    assert "params.gtf = 'x" in config  # single-quoted, escaped
```

- [ ] **Step 2: Run it, watch it fail** — `uv run pytest tests/test_pipeline_file.py::test_test_data_is_escaped_not_executed -v`. Expected: FAIL — config contains the raw double-quoted payload `params.gtf = "x"; throw ...`.

- [ ] **Step 3: Escape at the emitter.** In `emit.py`, `_render_test_data` currently wraps in raw double quotes. Route each lab-supplied value through `_render_literal` (single-quoted, escaped). Note the stub-data path uses generated `${projectDir}/...` literals elsewhere and is not this function — leave it. New body:

```python
def _render_test_data(value: list[str]) -> str:
    if len(value) == 1:
        return _render_literal(value[0])
    return "[" + ", ".join(_render_literal(item) for item in value) + "]"
```

- [ ] **Step 4: Add the content validator.** In `marks.py`, give `TestDataRef` an `AfterValidator` enforcing the shape its docstring already promises — a URL, no shell/Groovy metacharacters, no path separators beyond a URL's:

```python
def _test_data_ref(value: str) -> str:
    # A public example pinned to a commit — its docstring's promise, enforced. Reject the
    # metacharacters that make A44 an injection: quotes, $, backtick, semicolon, newline.
    if not re.match(r"^https?://[\w./~%+:@-]+$", value):
        raise ValueError(
            "MD0210: test_data must be an http(s) URL pinned to a commit, not "
            f"{value!r} — it is emitted into the generated config and a lab path or a "
            "shell metacharacter there is both a broken reference and an injection."
        )
    return value

TestDataRef = Annotated[str, Mark.TEST_DATA_REF, AfterValidator(_test_data_ref)]
```
(Reuse `MD0210` only if it is the closest existing "absent/invalid emitted reference" code; otherwise allocate the next free `MD02xx` and add it to `diagnostics.yml`. Check `mendel explain MD0210` first.)

- [ ] **Step 5: Unit test the validator** in `test_marks.py`:

```python
import pytest
from pydantic import TypeAdapter
from comeni_core.marks import TestDataRef

def test_test_data_ref_rejects_a_groovy_payload():
    ta = TypeAdapter(TestDataRef)
    with pytest.raises(ValueError):
        ta.validate_python('x"; throw new RuntimeException("x"); def z="')

def test_test_data_ref_accepts_a_pinned_url():
    ta = TypeAdapter(TestDataRef)
    url = "https://raw.githubusercontent.com/nf-core/test-datasets/72a702d/reference/genes.gtf"
    assert ta.validate_python(url) == url
```

- [ ] **Step 6: `make verify`** — green. Then the guard-ledger row: revert Step 3's escaping, confirm `test_test_data_is_escaped_not_executed` fails, restore. Append the row.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix(compiler): test_data is escaped and validated — A44

A config GString is code; test_data reached it double-quoted and unescaped, so a
hand-edited or overlay-supplied value executed at \`nextflow config\` time. Now escaped
through _render_literal and validated to a pinned URL. Guard-ledger row added.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: A45 — give `NfTemplate` a real grammar

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/marks.py` (`_nf_template`, ~line 311)
- Test: `packages/comeni-core/tests/test_marks.py`, `tests/test_pipeline_file.py`
- Ledger: `notes/audits/guard-ledger.md`

**Interfaces:**
- Produces: `_nf_template` rejects any `${…}` body that is not a dotted `meta`/`task` identifier, and rejects bare `"` and backtick.

- [ ] **Step 1: Failing unit test** in `test_marks.py`:

```python
from pydantic import TypeAdapter
from comeni_core.marks import NfTemplate

def test_nf_template_rejects_arbitrary_groovy_interpolation():
    ta = TypeAdapter(NfTemplate)
    for bad in [
        '-Q {value}; touch /tmp/x #',
        '-Q {value}"${new File("/tmp/x").text="y"}"',
        "-Q {value}`id`",
    ]:
        with pytest.raises(ValueError):
            ta.validate_python(bad)

def test_nf_template_allows_value_and_meta_and_task():
    ta = TypeAdapter(NfTemplate)
    ok = "--outSAMattrRGline 'ID:${meta.id}' 'SM:${meta.id}' 'PL:{value}'"
    assert ta.validate_python(ok) == ok
```

- [ ] **Step 2: Run, watch fail** — the first payload with `; touch` and the `${new File...}` both pass today (`_nf_template` only rejects newlines).

- [ ] **Step 3: Implement the grammar** in `marks.py`. Keep the newline refusal; add: no bare double-quote or backtick; every `${…}` body must match `(meta|task)\.[A-Za-z_][A-Za-z0-9_]*`:

```python
_ALLOWED_INTERP = re.compile(r"^\$\{(meta|task)\.[A-Za-z_][A-Za-z0-9_]*\}$")

def _nf_template(value: str) -> str:
    if "\n" in value:
        raise ValueError("MD0204: a template is one line — it composes into an argument string")
    if '"' in value or "`" in value:
        raise ValueError(
            "MD0204: a template may not contain a double quote or a backtick — it is emitted "
            "into a Groovy string, and both start a new expression there. Use single quotes "
            "for literal text, {value} for the resolved value, or ${meta.x}/${task.x}."
        )
    for interp in re.findall(r"\$\{[^}]*\}", value):
        if not _ALLOWED_INTERP.match(interp):
            raise ValueError(
                f"MD0204: {interp} is not an allowed interpolation. A template may reference "
                "only ${meta.<id>} or ${task.<id>}; anything else is arbitrary Groovy reaching "
                "the generated config."
            )
    return value
```

- [ ] **Step 4: Run, watch pass. Confirm the shipped STAR template still validates** — `test_nf_template_allows_value_and_meta_and_task` and the existing `test_routes.py` STAR cases.

- [ ] **Step 5: `make verify`.** Guard-ledger row: revert the `${…}` allowlist loop, confirm `test_nf_template_rejects_arbitrary_groovy_interpolation` fails, restore.

- [ ] **Step 6: Commit** — `fix(core): NfTemplate has a grammar, not just a newline check — A45`.

---

## Task 3: A38 — implement the `meta` and `directive` emission routes

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_process_scope`, `_entry_channels`/meta assembly, `_ext_scope`)
- Test: `tests/test_pipeline_file.py`, `packages/mendel-compiler/tests/test_emit.py`
- Ledger: `notes/audits/guard-ledger.md`

**Interfaces:**
- Consumes: `Setting.via` (`Via.EXT|META|DIRECTIVE`), `Setting.value`, `Step.settings`, `Channel.meta`.
- Produces: directive settings emit `withName: <PROCESS> { <name> = <rendered> }`; meta settings merge into the consuming step's channel meta map. A new guard `test_every_via_member_emits_or_is_refused`.

- [ ] **Step 1: Two failing end-to-end tests.** Use an overlay contract adding a directive and a meta setting to a spine module, then assert the emitted files contain them. Simplest: add params to a copy of `registry/contracts/nf-core/subread-featurecounts.yml` under a tmp overlay, build with `--registry registry/ --registry <overlay>`, assert.

```python
# tests/test_pipeline_file.py
def _overlay_with(tmp_path, extra_params: str) -> pathlib.Path:
    ov = tmp_path / "ov"
    (ov / "contracts" / "nf-core").mkdir(parents=True)
    (ov / "registry.yml").write_text("name: lab\n")
    src = (ROOT / "registry/contracts/nf-core/subread-featurecounts.yml").read_text()
    src = src.replace("params:", "params:\n" + extra_params, 1)
    (ov / "contracts/nf-core/subread-featurecounts.yml").write_text(src)
    return ov

def test_via_directive_reaches_nextflow_config(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: cpus, default: 7, via: directive}\n")
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    assert "cpus = 7" in (out / "nextflow.config").read_text()

def test_via_meta_reaches_the_channel_meta_map(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: strand, default: forward, via: meta}\n")
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    assert "strand: 'forward'" in (out / "main.nf").read_text()
```

- [ ] **Step 2: Run, watch both fail** — the values are recorded in `pipeline.yml` but absent from the emitted files.

- [ ] **Step 3: Implement directive emission.** In `_process_scope` (or a new `_directive_scope` it calls), for each step collect `Via.DIRECTIVE` settings and emit inside the step's `withName` block: `<name> = <_render_literal(value)>`. Directives share the `withName: <PROCESS> { ... }` block with `ext.*`; group by process so one block carries both. Keep the block name-sorted and `sorted(set(...))` for byte-identical output.

- [ ] **Step 4: Implement meta emission.** Meta settings attach to the step that consumes them, not to an entry channel. Locate where the step's input channel meta map is built for emission (the `_with_meta`/`_render_meta` path used for measurements). Add each `Via.META` setting as a `key: value` entry alongside the measured facts, so it renders `meta + [strand: 'forward', ...]`. Render values with `_render_literal`. Sort keys.

- [ ] **Step 5: Add the completeness guard** in `test_emit.py` — every `Via` member is either emitted or refused, so a future added route cannot ship dead:

```python
def test_every_via_member_emits_or_is_refused():
    from comeni_core.routes import Via
    handled = {Via.EXT, Via.META, Via.DIRECTIVE}  # update when Via changes
    assert set(Via) == handled, "a Via member exists that emit.py neither emits nor refuses"
```

- [ ] **Step 6: `make verify`** — including that the golden `tests/golden/spine/` files did NOT move (the spine uses only `via: ext`, so its output is unchanged). If they moved, a route leaked into the default path — investigate before regenerating.

- [ ] **Step 7: Guard-ledger rows** — revert directive emission (watch `test_via_directive_reaches_nextflow_config` fail), revert meta emission (watch its test fail), revert the completeness guard's `handled` set to `{Via.EXT}` (watch it fail). Three rows.

- [ ] **Step 8: Commit** — `feat(compiler): via: meta and via: directive emit — A38, closing issue #10 one level down`.

---

## Task 4: A40 — `MD0208`, two writers for one destination

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (add `MD0208`)
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`Step` validator, and the meta-assembly site)
- Test: `tests/test_pipeline_file.py`, `packages/comeni-core/tests/test_pipeline_totality.py`
- Ledger, docs: `guard-ledger.md`, regenerate `docs/reference/cli.md`

**Interfaces:**
- Consumes: `Step.settings`, and the meta map assembled in Task 3.
- Produces: `MD0208` refusal when two settings target one `ext` key, one directive name, or one meta key; or when a `via: meta` setting and a `Measurement.meta_key` collide.

- [ ] **Step 1: Add `MD0208` to `diagnostics.yml`.** Copy the shape of a neighbouring entry (`emitted_by: core`, `concern: pipeline-file`, `fires_on: [build, emit, upgrade]`, `refuses: true`), with `says`/`fix`/`explanation` describing two-writers-one-destination.

- [ ] **Step 2: Failing test** — two settings on one `ext` key concatenate today (A40's reproduction):

```python
def test_two_settings_on_one_destination_are_refused(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: a, default: x, via: ext, key: prefix}\n"
                                 "  - {name: b, default: y, via: ext, key: prefix}\n")
    out = tmp_path / "b"
    code = main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)])
    assert code == 2  # MD0208, not a silent concatenation
```

- [ ] **Step 3: Run, watch fail** — exit 0 today, both concatenated into one `ext.prefix`.

- [ ] **Step 4: Implement the refusal.** In `Step`'s model validator (beside `_no_duplicate_setting`, which catches duplicate *names*), group settings by *destination* — `(via, key)` for ext, `(via, name)` for directive, `(via, name)` for meta — and refuse when two settings share one destination. For the meta-vs-measurement collision, add the check where Task 3 assembles the meta map (a setting key equal to a `Measurement.meta_key` on the same channel). Raise `MD0208` with both writers named.

- [ ] **Step 5: Run, watch pass.** Regenerate docs: `make docs`, confirm `MD0208` now in `cli.md`.

- [ ] **Step 6: `make verify`.** Guard-ledger row: revert the destination-grouping refusal, watch `test_two_settings_on_one_destination_are_refused` fail, restore.

- [ ] **Step 7: Commit** — `feat(core): MD0208 refuses two writers for one destination — A40`.

---

## Task 5: A39 — a non-templated `ext` key is rendered once

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_ext_scope`, ~line 240 vs 265)
- Test: `tests/test_pipeline_file.py`

- [ ] **Step 1: Failing test** — a single `via: ext, key: prefix` setting emits doubled quotes today:

```python
def test_a_non_templated_ext_key_is_quoted_once(tmp_path):
    ov = _overlay_with(tmp_path, "  - {name: tag, default: alpha, via: ext, key: prefix}\n")
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    cfg = (out / "nextflow.config").read_text()
    assert "ext.prefix = 'alpha'" in cfg          # once
    assert "ext.prefix = '\\'alpha\\''" not in cfg # not doubled
```

- [ ] **Step 2: Run, watch fail** — today it emits `ext.prefix = '\'alpha\''`.

- [ ] **Step 3: Fix the double render.** In `_ext_scope`, the non-templated branch appends `_render_literal(setting.value)` to the fragment list, and the join then `_render_literal`s the joined string again. Append the **raw** value and let the single join-time `_render_literal` quote it, exactly as the templated branch does. Confirm the templated branch is unaffected (it inserts raw fragments).

- [ ] **Step 4: Run, watch pass.** `make verify` — including golden files unchanged (spine has no `prefix` setting).

- [ ] **Step 5: Commit** — `fix(compiler): a non-templated ext key is quoted once, not twice — A39`.

---

## Task 6: A46 — one writable answer for a tier-4 question

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`Pipeline._readable_and_unambiguous` or a new reconcile validator)
- Modify: `packages/mendel-resolver/src/mendel_resolver/replay.py` if the reconcile lives at load
- Test: `tests/test_pipeline_file.py`
- Ledger: `guard-ledger.md`

**Interfaces:**
- Consumes: `settings[].value`, `decisions[].human_override`, the decision key ↔ setting mapping.
- Produces: on load, `settings[].value` differing from the recorded decision becomes the `human_override`; a `human_override` contradicting `settings[].value` is refused (`MD02xx`). `emit` and `upgrade` then read one consistent answer.

- [ ] **Step 1: Failing test** — the two homes disagree and produce two pipelines (A46's reproduction):

```python
def test_emit_and_upgrade_agree_on_a_tier_four_answer(tmp_path, capsys):
    out = _build(tmp_path)
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"
    for d in doc["decisions"]:
        if d["key"].endswith("seq_platform"):
            d["human_override"] = "illumina"     # contradicts settings[].value
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD02" in err           # the contradiction is refused, not resolved two ways
```

- [ ] **Step 2: Run, watch fail** — today `emit` silently emits `nanopore` and `upgrade` `illumina`.

- [ ] **Step 3: Implement reconcile-or-refuse.** On `Pipeline` load, for each tier-4 setting with a matching decision: if `settings[].value` is set and the decision has no `human_override`, set `human_override = value, source = HUMAN` (the documented "editing this file answers the question"); if both are set and differ, raise `MD02xx` naming both. `decisions[].human_override` is no longer independently authoritative — `settings[].value` is the writable field, per the spec. Allocate the code in `diagnostics.yml`.

- [ ] **Step 4: Run, watch the contradiction refuse. Add the positive case** — editing only `settings[].value` answers the question and both verbs agree:

```python
def test_editing_the_value_answers_for_both_verbs(tmp_path, capsys):
    out = _build(tmp_path)
    _answer(out, "seq_platform", "nanopore")     # sets settings[].value
    code, err = _emit(out, capsys)
    assert "PL:nanopore" in (out/"nextflow.config").read_text()
    nxt = tmp_path / "next"
    assert main(["upgrade", str(out/"pipeline.yml"), "--registry", str(ROOT/"registry"),
                 "--out", str(nxt), "--root", str(ROOT)]) == 0
    assert "PL:nanopore" in (nxt/"nextflow.config").read_text()
```

- [ ] **Step 5: `make verify`.** Guard-ledger row: revert the contradiction refusal, watch `test_emit_and_upgrade_agree_on_a_tier_four_answer` fail, restore.

- [ ] **Step 6: Commit** — `fix(core): a tier-4 answer has one writable home, and a contradiction is refused — A46`.

---

## Task 7: A52 — a duplicate decision key is refused

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`Pipeline` validator, beside step-id check)
- Test: `tests/test_pipeline_file.py`
- Ledger: `guard-ledger.md`

- [ ] **Step 1: Failing test** — a second decision record for one key discards the override today:

```python
def test_a_duplicate_decision_key_is_refused(tmp_path, capsys):
    out = _build(tmp_path)
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text())
    dec = [d for d in doc["decisions"] if d["key"].endswith("seq_platform")][0]
    dup = dict(dec); dup["human_override"] = "illumina"
    doc["decisions"].append(dup)
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD02" in err
```

- [ ] **Step 2: Run, watch fail** — today `setdefault` keeps the first, drops `illumina`, exit 0.

- [ ] **Step 3: Refuse the duplicate.** Add a `Pipeline` model validator (beside the duplicate-step-id `MD0212` check) collecting `decisions[].key` and refusing repeats. Allocate a code or reuse the duplicate-key band; the `ReplayResolver` docstring already argues a duplicate is corruption.

- [ ] **Step 4: Run, watch pass.** `make verify`. Guard-ledger row: revert, watch fail, restore.

- [ ] **Step 5: Commit** — `fix(core): a duplicate decision key is corruption, and is refused — A52`.

---

## Task 8: A47 — `emit` carries the gate verdict

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (`stamp` call, ~line 395)
- Test: `tests/test_pipeline_file.py`

- [ ] **Step 1: Failing test:**

```python
def test_emit_preserves_the_gate_verdict(tmp_path, capsys):
    out = _build(tmp_path)
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text()); doc["gate"] = "lint"
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    _emit(out, capsys)
    assert yaml.safe_load((out/"pipeline.yml").read_text())["gate"] == "lint"
```

- [ ] **Step 2: Run, watch fail** — `gate` becomes `null` after emit.

- [ ] **Step 3: Fix.** The `emit` path calls `pipeline_file.stamp(out, pipeline)` with `gate` defaulting to `None`. Pass `gate=pipeline.gate` so an emit that changed nothing carries the verdict. (Confirm `pipeline.gate` is the loaded value; it is a `Gate | None` field.)

- [ ] **Step 4: Run, watch pass.** `make verify`.

- [ ] **Step 5: Commit** — `fix(compiler): emit carries the gate verdict rather than erasing it — A47`.

---

## Task 9: A48 — a missing `goal:` is refused

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`Pipeline.goal` field, ~line 291)
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (upgrade path, zero-step guard)
- Test: `tests/test_pipeline_file.py`
- Ledger: `guard-ledger.md`

- [ ] **Step 1: Failing test:**

```python
def test_a_pipeline_with_no_goal_is_refused(tmp_path, capsys):
    out = _build(tmp_path)
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text()); doc.pop("goal")
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2   # not a silent empty pipeline
```

- [ ] **Step 2: Run, watch fail** — loads with a default empty `Goal`; `upgrade` empties to `steps: []` at exit 0.

- [ ] **Step 3: Make `goal` required.** Change `Pipeline.goal` from `Field(default_factory=Goal)` to a required field. Fix any construction site that relied on the default (`Pipeline.of` already takes `goal` keyword-only, per Task 6 of Plan 1.10). As defence in depth, in the upgrade path refuse when re-resolution yields zero steps from a non-empty previous.

- [ ] **Step 4: Run, watch pass.** `make verify` — watch for construction sites in tests that omitted `goal`; fix them to pass a real `Goal`. Guard-ledger row: revert `goal` to `default_factory=Goal`, watch the test fail, restore.

- [ ] **Step 5: Commit** — `fix(core): a pipeline.yml with no goal is refused, not upgraded to empty — A48`.

---

## Task 10: A49 — a refused `emit` leaves nothing behind

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (emit write sequence, ~line 393-395)
- Test: `tests/test_pipeline_file.py`

- [ ] **Step 1: Failing test** — a rename plus a bad value rewrites `main.nf` then dies before `nextflow.config`, and the retry blames the user:

```python
def test_a_refused_emit_writes_nothing(tmp_path, capsys):
    out = _build(tmp_path)
    before = (out/"main.nf").read_text()
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text())
    for s in doc["steps"]:
        if s["id"] == "trimgalore": s["process"] = "TRIMGALORE2"
        for setting in s.get("settings", []):
            if setting["name"] == "min_mqs": setting["value"] = "0 bad"  # fails MD0201 in config
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2
    assert (out/"main.nf").read_text() == before   # untouched on refusal
```

- [ ] **Step 2: Run, watch fail** — `main.nf` is rewritten though the emit refused.

- [ ] **Step 3: Make emit atomic.** Render both files in memory first (`emit(pipeline)`, `emit_config(pipeline)` — the second is where `MD0201` raises), and only then write both and stamp. A raise during rendering leaves the directory as it was, the posture `upgrade` already takes (`cli.py:222`).

- [ ] **Step 4: Run, watch pass.** `make verify`.

- [ ] **Step 5: Commit** — `fix(compiler): a refused emit leaves the directory untouched — A49`.

---

## Task 11: A50 — `publish` certifies without re-resolving

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (split `publish` off the shared upgrade path)
- Test: `tests/test_publish.py`
- Ledger: `guard-ledger.md`

**Interfaces:**
- Produces: `publish` loads the artifact, refuses a divergent directory (`MD0213`/`MD0214`, already present), runs the gate on the on-disk files, stamps the verdict — and does **not** build a `ReplayResolver`, re-resolve, or write in place. No `--registry` needed.

- [ ] **Step 1: Failing test** — publish against a different registry stack currently moves the pipeline and erases an override:

```python
def test_publish_certifies_what_is_on_disk_without_re_resolving(tmp_path):
    # build against base; install an overlay that would reroute; publish must NOT reroute.
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--out", str(out), "--root", str(ROOT)]) == 0
    before = (out / "pipeline.yml").read_text()
    # Overlay that reroutes the aligner: copy the hisat2 contract with priority bumped so it
    # wins over star. (A re-resolving publish would swap star->hisat2; a certifying one won't.)
    ov = tmp_path / "ov"; (ov / "contracts" / "nf-core").mkdir(parents=True)
    (ov / "registry.yml").write_text("name: lab\n")
    import re as _re
    h = (ROOT / "registry/contracts/nf-core/hisat2-align.yml").read_text()
    (ov / "contracts/nf-core/hisat2-align.yml").write_text(
        _re.sub(r"priority:\s*\d+", "priority: 99", h))
    code = main(["publish", str(out/"pipeline.yml"), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--gate", "lint"])
    after = (out / "pipeline.yml").read_text()
    import yaml
    assert yaml.safe_load(after)["gate"] == "lint"        # verdict stamped
    # everything else identical — the aligner did not change, the override survived:
    b, a = yaml.safe_load(before), yaml.safe_load(after)
    assert b["steps"] == a["steps"] and b["decisions"] == a["decisions"]
```

- [ ] **Step 2: Run, watch fail** — today `steps`/`decisions` change (aligner rerouted, override dropped).

- [ ] **Step 3: Split `publish` from the upgrade path.** Give `publish` its own branch: load the artifact, run `_refuse_a_divergent_directory` (keeps `MD0213`/`MD0214`), run the gate on the emitted files already on disk, `stamp(source.parent, pipeline, gate=<verdict>)`. Remove its use of `ReplayResolver`/re-resolution and its `args.out = source.parent` write of re-emitted files. It certifies; it does not produce. (`upgrade` keeps the shared re-resolution path and its `_report_upgrade` — untouched.)

- [ ] **Step 4: Run, watch pass. Add a second test** — a legitimate edit-then-publish still works via emit: edit the goal's profile, `emit`, then `publish`, and the published pipeline is the emitted one.

- [ ] **Step 5: `make verify`.** Guard-ledger row: revert the split so `publish` re-resolves again, watch `test_publish_certifies_what_is_on_disk_without_re_resolving` fail, restore.

- [ ] **Step 6: Commit** — `fix(compiler): publish certifies the on-disk artifact without re-resolving — A50`.

---

## Task 12: A51 — displacements of all four kinds reach the artifact

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (~line 70, `displaced=`) and/or `cli.py` (set `ir.displaced` from `loaded.displaced`)
- Test: `tests/test_audit_regressions.py` or `tests/test_pipeline_file.py`
- Ledger: `guard-ledger.md`

**Interfaces:**
- Consumes: `layers.load(...).displaced` — one list, all four `DeclaredKind`s.
- Produces: `PipelineIR.displaced` / `pipeline.yml`'s `registry.displaced` carries all four kinds; the `OVERLAY` block prints a vocabulary/rules displacement.

- [ ] **Step 1: Failing, parametrised over kind** — a vocabulary overlay reroutes silently today:

```python
def test_a_vocabulary_displacement_reaches_the_artifact(tmp_path):
    ov = tmp_path / "ov"; (ov/"vocabularies").mkdir(parents=True)
    (ov/"registry.yml").write_text("name: lab-vocab\n")
    (ov/"vocabularies/annotation.gtf.yml").write_text(
        'states: []\nentry_channel: "Channel.fromPath(params.lab_gtf, checkIfExists: true)'
        '.map { g -> [ [id: g.baseName], g ] }"\n')
    out = tmp_path / "b"
    assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)]) == 0
    import yaml
    displaced = yaml.safe_load((out/"pipeline.yml").read_text())["registry"]["displaced"]
    assert any(d["kind"] == "vocabularies" for d in displaced)
```

- [ ] **Step 2: Run, watch fail** — `displaced` is `[]` though `layers.load(...).displaced` records it.

- [ ] **Step 3: Carry the whole list.** Replace the two-kind re-derivation at `resolve.py:70` (`displaced=[*measurements.displaced, *registry.displaced]`) with the loader's own `loaded.displaced` (all four kinds), threaded in from `cli.py`. Confirm the `OVERLAY` block renderer handles a `vocabularies`/`rules` kind (it prints from `PipelineIR.displaced`).

- [ ] **Step 4: Add the same test for a rules overlay** (a `rules/*.yml` displacing a base decision block) → `kind == "rules"`.

- [ ] **Step 5: `make verify`.** Guard-ledger row: revert to the two-kind list, watch `test_a_vocabulary_displacement_reaches_the_artifact` fail, restore. (This is A51's inert-guard finding closed — the A23 fix was untested.)

- [ ] **Step 6: Commit** — `fix(resolver): all four displacement kinds reach the artifact — A51`.

---

## Task 13: A53 — `upgrade --out` refuses another pipeline's directory

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (the `--out` identity guard, ~line 187)
- Test: `tests/test_upgrade.py`
- Ledger: `guard-ledger.md`

- [ ] **Step 1: Failing test** — upgrading A into B's directory destroys B:

```python
def test_upgrade_refuses_to_overwrite_another_pipeline(tmp_path):
    a, b = tmp_path/"A", tmp_path/"B"
    for d in (a, b):
        assert main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                     "--out", str(d), "--root", str(ROOT)]) == 0
    code = main(["upgrade", str(a/"pipeline.yml"), "--registry", str(ROOT/"registry"),
                 "--out", str(b), "--root", str(ROOT)])
    assert code == 2   # B holds a different pipeline.yml — refused absent --force
```

- [ ] **Step 2: Run, watch fail** — exit 0, B overwritten.

- [ ] **Step 3: Broaden the guard.** Beyond `out.resolve() == source.parent.resolve()`, refuse when `out` already contains a `pipeline.yml` whose content digest differs from the one being upgraded, unless `--force`. Add the `--force` flag to the `upgrade` subparser. Keep the existing self-overwrite refusal.

- [ ] **Step 4: Add relative/symlink coverage for the existing self-guard** — a relative `--out` and a symlinked `--out` to the source both refuse (watches the `.resolve()` A53 flagged as inert):

```python
def test_upgrade_self_guard_sees_a_relative_out(tmp_path, monkeypatch):
    out = tmp_path/"p"
    assert main(["build","--goal",str(GOAL),"--registry",str(ROOT/"registry"),
                 "--out",str(out),"--root",str(ROOT)]) == 0
    monkeypatch.chdir(tmp_path)
    assert main(["upgrade", str(out/"pipeline.yml"), "--registry", str(ROOT/"registry"),
                 "--out", "p", "--root", str(ROOT)]) == 2
```

- [ ] **Step 5: `make verify`.** Guard-ledger rows: revert `.resolve()` → `==` (watch the relative-out test fail), and revert the different-digest refusal (watch the overwrite test fail). Two rows.

- [ ] **Step 6: Commit** — `fix(compiler): upgrade --out refuses another pipeline's directory — A53`.

---

## Task 14: A54 — `source: HUMAN` is not assertable through the port

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (a `Pipeline` validator) and/or `ir.py`/`resolve.py`
- Test: `tests/test_pipeline_file.py`, `packages/mendel-resolver/tests/test_replay.py`
- Ledger: `guard-ledger.md`

**Interfaces:**
- Produces: every `why.source: human` in a `Pipeline` must have a matching non-null `decisions[].human_override`; a pipeline claiming `HUMAN` without one is refused.

- [ ] **Step 1: Failing test** — a `why.source: human` with no matching override loads today:

```python
def test_human_source_requires_a_matching_override(tmp_path, capsys):
    out = _build(tmp_path)
    import yaml
    doc = yaml.safe_load((out/"pipeline.yml").read_text())
    for s in doc["steps"]:
        for setting in s.get("settings", []):
            if setting["name"] == "seq_platform":
                setting["value"] = "nanopore"; setting["why"]["source"] = "human"
    # deliberately leave decisions[].human_override null
    (out/"pipeline.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    code, err = _emit(out, capsys)
    assert code == 2 and "MD02" in err
```

- [ ] **Step 2: Run, watch fail** — loads cleanly, `needs_review()` drops the item though no human answered.

- [ ] **Step 3: Add the cross-check.** A `Pipeline` validator: for every setting whose `why.source is HUMAN`, require a `decisions[]` entry for its key with a non-null `human_override`. Refuse otherwise. This composes with Task 6's reconcile — a genuine edit sets both, so the honest case passes. Allocate the code.

- [ ] **Step 4: Run, watch pass.** `make verify`. Guard-ledger row: revert the cross-check, watch the test fail, restore.

- [ ] **Step 5: Commit** — `fix(core): source HUMAN requires a matching human_override — A54`.

---

## Task 15: A41 — emit `MD0200`, and blame the right file

**Files:**
- Modify: contract loading (`packages/comeni-core/src/comeni_core/contract.py` or where `ModuleContract` is validated) to catch missing `via`
- Modify: the CLI error surface that prints "this goal is not valid"
- Test: `tests/test_pipeline_file.py` / `packages/comeni-core/tests/test_routes.py`
- Ledger: `guard-ledger.md`

- [ ] **Step 1: Failing test** — a contract missing `via:` yields a raw Pydantic error blamed on the goal:

```python
def test_a_contract_missing_via_emits_MD0200_and_blames_the_contract(tmp_path, capsys):
    ov = _overlay_with(tmp_path, "  - {name: x, default: 1}\n")  # no via:
    out = tmp_path / "b"
    code = main(["build", "--goal", str(GOAL), "--registry", str(ROOT/"registry"),
                 "--registry", str(ov), "--out", str(out), "--root", str(ROOT)])
    err = capsys.readouterr().err
    assert code == 2 and "MD0200" in err and "goal is not valid" not in err
```

- [ ] **Step 2: Run, watch fail** — today `err` is a Pydantic `Field required` under "this goal is not valid".

- [ ] **Step 3: Catch and re-raise.** Where contract YAML is validated into `Param`, catch the missing-`via` `ValidationError` and raise `MD0200`'s declared message naming the contract and the param. Fix the CLI wrapper so a contract-loading failure prints "contract <id> is not valid", not "this goal is not valid". Keep the goal-side message for genuine goal errors.

- [ ] **Step 4: Run, watch pass.** `make verify` — confirm `mendel explain MD0200` still resolves. Guard-ledger row: revert the catch, watch the test fail, restore.

- [ ] **Step 5: Commit** — `fix(core): a missing via emits MD0200 and names the contract — A41`.

---

## Task 16: A42 — tests for the six untested refusals and two emission properties

**Files:**
- Test: `tests/test_pipeline_file.py`, `packages/mendel-compiler/tests/test_emit.py`
- Ledger: `notes/audits/guard-ledger.md` (six rows)

No production code changes — this task adds the missing guards A42 named, each reverted and watched. (Some may already be covered by earlier tasks' tests; skip a row only after confirming the property's revert is watched by a committed test, and note which task covers it.)

- [ ] **Step 1: `MD0215`** — a `StepInput` naming both `source` and `channel`, and neither, each refused (unit test on `StepInput`).
- [ ] **Step 2: `MD0201` at emit** — a setting value outside the substitutable class is refused during `emit` (end-to-end, not just the `substitutable()` unit).
- [ ] **Step 3: `MD0204` one-line** — a multi-line template is refused (may be folded into Task 2's tests; confirm).
- [ ] **Step 4: the two-settings `ext.args` name-sort** — the property the emitter's own docstring predicted no test could see. Two `key: args` settings on one step emit in name-sorted order; reversing the sort changes the output:

```python
def test_two_ext_args_settings_emit_name_sorted(tmp_path):
    ov = _overlay_with(tmp_path,
        "  - {name: zulu, default: 1, via: ext, key: args, template: --zulu {value}}\n"
        "  - {name: alpha, default: 2, via: ext, key: args, template: --alpha {value}}\n")
    out = tmp_path / "b"
    assert main(["build","--goal",str(GOAL),"--registry",str(ROOT/"registry"),
                 "--registry",str(ov),"--out",str(out),"--root",str(ROOT)]) == 0
    line = [l for l in (out/"nextflow.config").read_text().splitlines()
            if "SUBREAD_FEATURECOUNTS" in l and "args" in l][0]
    assert line.index("--alpha") < line.index("--zulu")  # name-sorted, not declaration order
```
(If Task 4's `MD0208` refuses two settings on one destination, note that two `key: args` settings compose rather than collide — confirm the destination grouping treats `args` fragments as composing, not colliding, and this test builds. If they are made to collide, this property moves to a unit test on `_ext_scope` with a hand-built `Step`.)

- [ ] **Step 5: the process-scope `sorted(set(...))` dedup** — a contract used by two steps emits its block once.
- [ ] **Step 6: Six guard-ledger rows**, each reverted and watched. `make verify`.
- [ ] **Step 7: Commit** — `test: the six untested round-three refusals now have watched guards — A42`.

---

## Task 17: A43 — documentation matches the code

**Files:**
- Modify: `CLAUDE.md`, `CHANGELOG.md`, `notes/README.md`, `docs/design/clinical-data-protection.md`, `docs/reference/pipeline-schema.md`, and issue #18's text
- Test: none (docs); `make docs` for the generated table

- [ ] **Step 1: Counts** — everywhere "24 codes" / "sixteen new diagnostics" / "fourteen diagnostics" appears, correct to the real count (25 before this plan; more after `MD0208` and any codes tasks 6/7/14 allocated — recount from `diagnostics.yml`). The `MD0200`–`MD0216` range is contiguous once `MD0208` exists (Task 4).
- [ ] **Step 2: Door 4 payload** — `clinical-data-protection.md`'s four-doors table says `PublishBundle`; change to `Pipeline`. Remove or correct the named-but-absent `test_publish_bundle_is_typed`.
- [ ] **Step 3: `CallArg.empty_width`** — add it to `docs/reference/pipeline-schema.md`, the field-by-field reference that skips it.
- [ ] **Step 4: Issue #18 numbers** — update "41 raise sites, 32 bare ValueError" to the current count (`grep -rn "raise " packages/*/src` — was 79/47 at audit time; recount, since this plan added raises).
- [ ] **Step 5: `make docs`** to regenerate `cli.md`; confirm `make check`'s docs-freshness lane is green.
- [ ] **Step 6: Commit** — `docs: round-three documentation matches the code — A43`.

---

## Closing the plan

- [ ] **Update `notes/README.md`** order table: Plan 1.11 complete, round four next.
- [ ] **Journal entry** `notes/journal/2026-08-<dd>.md`: what shipped, what each task corrected in this plan (every prior plan needed corrections — record them inline), and that a round-four audit is still owed because the loop exits on *no critical surviving*, not on an empty audit.
- [ ] **Final `make verify`** green, `ruff check` clean, `make static` green.
- [ ] **Confirm A14's ledger** gained a watched row for every refusal this plan added or restored.

## Self-review notes (for the executor)

- **Codes to allocate** as you go, in `diagnostics.yml`: `MD0208` (Task 4), and one each for the
  reconcile-contradiction (Task 6), duplicate decision key (Task 7), and `source: HUMAN` cross-check
  (Task 14) unless an existing band fits. Do not hard-code a number in a test before allocating it;
  assert on the `MD02` prefix, then tighten to the exact code once chosen.
- **Golden files** (`tests/golden/spine/`) must not move in tasks 3, 4, 5 — the shipped spine uses
  only `via: ext` with single settings, so its output is unchanged. A moved golden file in those
  tasks means a route leaked into the default path.
- **Task ordering matters at two seams:** Task 4 (`MD0208`) must land after Task 3 (which makes the
  meta collision reachable); Task 6 (reconcile) before Task 14 (which composes with it). The rest are
  independent and may be reordered if a blocker appears.
