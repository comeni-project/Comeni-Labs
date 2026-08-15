# Plan 1.12 — closing round four

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` and drive it
> task by task, sequentially, in this session. **Do not use `subagent-driven-development`** —
> `CLAUDE.md` reserves subagents for review and design. Steps use checkbox (`- [ ]`) syntax.

**Goal:** close round four's four critical findings and the two that go live the day Plan 2
wires a model — A55, A57, A58, A59, A56, A70 — so the MVP can be built on a surface whose
known code-execution and guard-bypass routes are shut.

**Architecture:** six independent fixes, each landing as its own commit with its own watched
guard. Four are guards being repaired in `tests/` (A57, A58, A59, and the watched half of
A56); two are refusals added to product code (A55 in `comeni-core` + `mendel-compiler`, A70 in
`mendel-compiler`). Two new diagnostics, `MD0221` and `MD0222`. Nothing here needs a new
dependency, and nothing here touches `mendel-ai`, which does not exist yet.

**Tech stack:** Python 3.12, pydantic v2, pytest, ruff, Jinja2, Nextflow 25.10.4 (Task 1's
verification only), `uv` for everything.

## This is the last audit-driven plan — decided 2026-08-13

The operator's decision: **1.12 is the final pass, then Plan 2 and the MVP.** That overrides
the loop's stated exit criterion, which is *no critical finding surviving a fresh audit*
(`notes/README.md`, "Why that order"). Recorded rather than quietly dropped, because
three plans deferred Plan 2 on the strength of that criterion.

What this means concretely, and Task 7 writes it into the docs:

- **A14 does not close.** It is not being closed; it is being *carried*, with round four's
  measurement of it (~34 of ~183 guards have a watched revert — A69) standing as the honest
  number. No document may claim the loop exited.
- **Fifteen findings are carried, not fixed** — A60–A69 and A71–A75. Task 7 files them as
  GitHub issues so a finding named only in an audit file is not a finding lost.
- **The two Plan-2 blockers are in scope precisely because they stop being latent when a model
  is wired to the resolver port** (A56) and because publish is the door with no undo (A70).
  Fixing them after Plan 2 means fixing them with a model already in the loop, which is the
  argument that ordered Plan 1.8 before Plan 2.

## Global constraints

Copied verbatim from `CLAUDE.md` and from what round three learned the hard way. Every task's
requirements implicitly include this section.

- **`re` is banned in `comeni-core` and `mendel-resolver`.** The purity allowlist
  (`CLOSED_PACKAGES`, `tests/test_purity.py:30`) does not carry it. Plan 1.11 Tasks 1 and 2
  were both written with `re` and both had to be rewritten with spelled-out `frozenset`s and
  hand-rolled scanners. **Character classes are data here, not regex.** Task 1 obeys this.
- **`make verify`, not `make check`, is what verifies this plan.** Five of the six tasks touch
  a file on the named list — `emit.py`, `resolve.py`, `mendel_compiler/cli.py`,
  `comeni_core/pipeline.py`. `make check` deselects `tests/test_counts.py`, the only tests that
  run a tool. Budget ~2 minutes per verification.
- **Every guard this plan writes or repairs needs a row in
  `notes/audits/guard-ledger.md`** — reverted, watched failing, restored, recorded.
  That is A14's condition, and it is the reason `MD0216` shipped inert in Plan 1.10. Green is
  not evidence. Each task below has the revert as an explicit step; do not fold it into the
  implementation step.
- **Work in a worktree, with absolute paths.** Plan 1.11 lost half a verification run to a
  `cd` that silently returned the shell to the main checkout; a `542` vs `591` collected-test
  count was the tell. Use `git -C <worktree>` or absolute paths for every command.
- **`ruff check` at line length 100. Never run `ruff format`** — 28 files are hand-wrapped and
  a formatting sweep belongs in its own commit.
- **A code is never renumbered.** `MD0221` and `MD0222` are the next free codes; the highest
  allocated today is `MD0220`. `docs/reference/cli.md`'s table is generated from
  `packages/comeni-core/src/comeni_core/diagnostics.yml` — run `make docs` after adding either,
  and CI checks it.
- **Import modules, not symbols, where tests monkeypatch.**

## Task order, and why

1. **Task 1 — A55**, first because it is arbitrary code execution reachable through a file the
   product tells people to share, on a public repo.
2. **Task 2 — A58** and **Task 3 — A59**, next and adjacent because they *compose*:
   `yaml.unsafe_load` inside `layers.load` reaches the network during the stage the runtime
   hook does not watch. Neither fix alone closes the composition; Task 3's coverage assertion is
   what keeps the watched region from narrowing again.
3. **Task 4 — A57**, the third critical: the egress guard reasons about annotations, and
   pydantic has two other ways into the JSON.
4. **Task 5 — A56** and **Task 6 — A70**, the Plan-2 blockers.
5. **Task 7 — docs, issues, and the record.**

---

### Task 1: A55 — a resolved value may not execute as Groovy

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py:107-117` (`Setting`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py:263-299` (`_ext_scope`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (add `MD0221`)
- Test: `tests/test_pipeline_file.py`, `packages/mendel-compiler/tests/test_emit.py`
- Docs: `docs/reference/cli.md` (generated — run `make docs`)

**Interfaces:**
- Consumes: `comeni_core.marks.substitutable(value: object) -> bool` — already imported by
  `emit.py`; `comeni_core.routes.Via`, `comeni_core.routes.ExtKey`.
- Produces: nothing new for later tasks. `Setting` gains a `@model_validator(mode="after")`
  named `_a_raw_ext_value_cannot_be_groovy`; `_ext_scope` gains a local `templated: set[str]`.

**The defect, exactly.** `_ext_scope` has two branches. The templated one (`emit.py:277`) calls
`substitutable()` and raises `MD0201` on `${…}`. The non-templated one (`emit.py:265`, added by
A39) appends `str(setting.value)` raw. At the join (`emit.py:296`), any fragment containing
`${` is emitted as a Groovy **closure** — `ext.<key> = { "…" }` — whose body Nextflow evaluates
per task. `key: prefix` is a *legal non-templated shape by design* (MD0204 refuses a template on
it), so no tampering is required: editing the field `pipeline.yml`'s own header tells a human to
edit is enough. Reproduced end to end in the audit — `id` ran on the host, outside any
container, in the `docker` group, invisible in the task log.

**Why two layers of fix.** The validator on `Setting` refuses a hostile `pipeline.yml` at *load*,
which is what protects `mendel emit` and `mendel publish` on a file someone handed you. The
change in `_ext_scope` makes the closure branch structurally unreachable from a raw value, so the
emitter is not relying on a validator somewhere else having run. **Both, not either** — A70 in
this same round is what one layer of "something else checks it" looks like when the something
else short-circuits.

**Not a concern:** every `via: ext` param in `registry/` today is templated
(`star-align.yml:16`, `subread-featurecounts.yml:19`, `hisat2-align.yml:14`), so the raw branch
has no legitimate producer in the shipped spine and this refusal changes no existing build. Do
not take that on faith — Step 8 is `make verify`.

- [ ] **Step 1: Write the failing load-time test**

In `tests/test_pipeline_file.py`:

```python
def test_a_raw_ext_value_cannot_smuggle_groovy():
    """A55. `key: prefix` takes no template (MD0204), so its value rides the raw branch of
    `_ext_scope` — and a `${…}` there becomes a closure Nextflow evaluates per task. The
    value is the field pipeline.yml's header tells a human to edit, and the file is meant
    to be shared, so this is refused at load rather than at emit."""
    with pytest.raises(ValidationError) as caught:
        Setting(
            name="seq_platform",
            value="${['sh','-c','id'].execute().text}",
            via=Via.EXT,
            key=ExtKey.PREFIX,
            template=None,
            why=Why(tier=4, settled_by="human", layer=0, reason="probe"),
        )
    assert "MD0221" in str(caught.value)


def test_an_ordinary_raw_ext_value_still_loads():
    """The refusal is the substitutable class, not a ban on the raw route: A39 added that
    branch for a reason and `prefix` values are ordinary identifiers."""
    setting = Setting(
        name="seq_platform",
        value="illumina",
        via=Via.EXT,
        key=ExtKey.PREFIX,
        template=None,
        why=Why(tier=4, settled_by="human", layer=0, reason="probe"),
    )
    assert setting.value == "illumina"
```

Add `Setting`, `Via`, `ExtKey`, `Why` and `ValidationError` to that file's imports if absent.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest tests/test_pipeline_file.py -k smuggle_groovy -v
```

Expected: FAIL — `DID NOT RAISE ValidationError`. That is the finding, reproduced as a test.

- [ ] **Step 3: Add the validator**

In `packages/comeni-core/src/comeni_core/pipeline.py`, inside `Setting`, after the fields:

```python
    @model_validator(mode="after")
    def _a_raw_ext_value_cannot_be_groovy(self) -> "Setting":
        """`MD0221`. A55: a value on the untemplated `ext` route is appended raw, and the
        emitter turns any fragment mentioning `${` into a Groovy closure evaluated per task.

        The templated route has always been checked here (`MD0201`); this is the same class,
        on the branch that had none. It is at *load* on purpose: `pipeline.yml` is shareable
        and publishable, so the refusal has to happen before `emit` reads the file, not
        inside it.
        """
        if self.via is Via.EXT and self.template is None and not substitutable(self.value):
            raise ValueError(
                f"MD0221: {self.name} routes {self.value!r} to `ext.{self.key}` with no "
                "template, so it is emitted verbatim into Nextflow config. Use letters, "
                "digits and _ . : + - only, or a number, or true/false — "
                "`mendel explain MD0221`."
            )
        return self
```

Import `substitutable` from `.marks` and `model_validator` from `pydantic` if not already
imported in that module.

- [ ] **Step 4: Run the load-time tests**

```bash
uv run pytest tests/test_pipeline_file.py -k "smuggle_groovy or ordinary_raw_ext" -v
```

Expected: 2 passed.

- [ ] **Step 5: Write the failing emitter test**

The validator is one layer. This is the other — that the closure branch cannot be reached from a
raw value even if a `Setting` arrives by some path that skipped validation (`model_construct`
does exactly that, and A62 is the open finding that it can). In
`packages/mendel-compiler/tests/test_emit.py`:

```python
def test_the_closure_branch_is_unreachable_from_a_raw_value():
    """A55, defence in depth. `model_construct` skips validators — A62 — so the emitter must
    not depend on Task 1's validator having run. A raw value mentioning `${` is refused
    here, while a *contract's* templated fragment still legitimately produces a closure."""
    step = _step_with(
        Setting.model_construct(
            name="seq_platform",
            value="${['sh','-c','id'].execute().text}",
            via=Via.EXT,
            key=ExtKey.PREFIX,
            template=None,
            why=_why(),
        )
    )
    with pytest.raises(ValueError, match="MD0221"):
        _ext_scope(step)


def test_a_templated_fragment_still_emits_a_closure():
    """The read-group line STAR needs is `--outSAMattrRGline 'ID:${meta.id}' …` — a closure
    is correct there, and Task 1 must not break it."""
    step = _step_with(
        Setting(
            name="seq_platform",
            value="illumina",
            via=Via.EXT,
            key=ExtKey.ARGS,
            template="--outSAMattrRGline 'ID:${meta.id}' 'PL:{value}'",
            why=_why(),
        )
    )
    assert 'ext.args = { "' in "\n".join(_ext_scope(step))
```

Use the file's existing helpers for building a `Step` and a `Why`; if it has none under these
names, write `_step_with` and `_why` as module-level helpers in that test file rather than
inlining a `Step(...)` twice.

- [ ] **Step 6: Run it and watch it fail**

```bash
uv run pytest packages/mendel-compiler/tests/test_emit.py -k closure_branch -v
```

Expected: FAIL — no exception raised, because the raw branch appends and the join makes a
closure.

- [ ] **Step 7: Make the closure branch structurally unreachable**

In `_ext_scope`, record which keys got a *validated template* fragment, and refuse a raw value
that would reach the closure join. Replace the raw branch (`emit.py:263-273`) with:

```python
        if setting.template is None:
            # A39: append the raw value; the single `_render_literal` at the join quotes it,
            # exactly as the templated branch inserts raw fragments. Rendering here as well
            # double-quoted it — `alpha` became `'\'alpha\''`, quotes and all. Bool lowercased
            # to match the templated branch, so `true` stays `true` rather than `True`.
            #
            # A55: and it is checked, which it was not. The join below turns any fragment
            # mentioning `${` into a closure Nextflow evaluates per task, so an unchecked
            # raw value here is arbitrary Groovy on the pipeline host. `Setting` refuses this
            # at load (MD0221); this is the second layer, because `model_construct` skips
            # validators and the emitter must not assume the file was validated.
            if not substitutable(setting.value):
                raise ValueError(
                    f"MD0221: {step.id}.{setting.name} is {setting.value!r} on an "
                    f"untemplated `ext.{setting.key.value}` route, so it would be emitted "
                    "verbatim into Nextflow config. Use letters, digits and _ . : + - only, "
                    "or a number, or true/false — `mendel explain MD0221`."
                )
            raw = (
                str(setting.value).lower()
                if isinstance(setting.value, bool)
                else str(setting.value)
            )
            fragments.setdefault(setting.key.value, []).append(raw)
            continue
```

`substitutable` is already imported by `emit.py` for the templated branch; confirm rather than
re-import.

- [ ] **Step 8: Run the emitter tests, then the full verification**

```bash
uv run pytest packages/mendel-compiler/tests/test_emit.py -v
make verify
```

Expected: emit tests pass; `make verify` green — 591 fast + 3 slow + 20 guards, `ruff` clean.
**`make check` alone does not verify this task**: `emit.py` is on the named list and
`tests/test_counts.py` is the only test that runs featureCounts.

- [ ] **Step 9: Add the diagnostic and regenerate the docs table**

Append to `packages/comeni-core/src/comeni_core/diagnostics.yml`:

```yaml
MD0221:
  emitted_by: core
  concern: pipeline-file
  says: "an untemplated `via: ext` value is outside the substitutable class"
  fires_on: [build, emit, upgrade, publish]
  refuses: true
  fix: |
    Use letters, digits and `_ . : + -` only, or a number, or `true`/`false`. If your value
    legitimately needs a space or a slash, that is a case we assumed did not exist — please
    report it.
  explanation: |
    A setting with `via: ext` and no `template:` is written into `nextflow.config` verbatim,
    inside the `ext.<key>` assignment. Nextflow emits a fragment mentioning `${…}` as a
    **closure**, evaluated once per task on the machine running the pipeline — so a value
    containing `${…}` is not data, it is code, and it runs outside any container.

    `pipeline.yml` is meant to be shared, published and edited: `settings[].value` is the
    field the file's own header points a human at, and `key: prefix` takes no template by
    design (`MD0204` refuses one). So the shape needs no tampering to arrive — which is why
    this is refused when the file loads, before `emit` ever reads it, rather than at
    emission.

    This is the same class `MD0201` has always enforced on the *templated* route. Audit A55
    found the untemplated branch had none.
```

Then:

```bash
make docs
uv run pytest tests/test_diagnostics_registry.py -v
```

- [ ] **Step 10: Revert the guard, watch it fail, restore, record**

A14's condition, and the reason `MD0216` shipped inert.

```bash
# 1. comment out the `if ... not substitutable` block in `Setting._a_raw_ext_value_cannot_be_groovy`
uv run pytest tests/test_pipeline_file.py -k smuggle_groovy -v      # MUST fail
# 2. restore it, then comment out the `if not substitutable` in `_ext_scope`
uv run pytest packages/mendel-compiler/tests/test_emit.py -k closure_branch -v   # MUST fail
# 3. restore both
uv run pytest tests/test_pipeline_file.py packages/mendel-compiler/tests/test_emit.py -q
```

Append a row to `notes/audits/guard-ledger.md` under a new `## Round four fixes (Plan
1.12)` section, naming both probes, both failure messages, and the date.

- [ ] **Step 11: Commit**

```bash
git add packages/comeni-core/src/comeni_core/pipeline.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml \
        packages/mendel-compiler/src/mendel_compiler/emit.py \
        tests/test_pipeline_file.py packages/mendel-compiler/tests/test_emit.py \
        docs/reference/cli.md notes/audits/guard-ledger.md
git commit -m "fix: a resolved value cannot execute as Groovy on the host (A55, MD0221)

The untemplated `via: ext` branch appended `settings[].value` raw, and the join
emits any fragment mentioning `\${` as a closure Nextflow evaluates per task. No
tampering was needed: `key: prefix` takes no template by design (MD0204), and
`pipeline.yml` is a shareable artifact whose header tells a human to edit that
field. Refused at load *and* at emit, because `model_construct` skips validators.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: A58 — the purity scan closes yaml's loader surface

**Files:**
- Modify: `tests/test_purity.py:100-135` (the `ast.Attribute` pass) and its constants block
- Test: `tests/test_purity.py` itself — this task's deliverable *is* a guard

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: two module-level constants later tasks may read —
  `BANNED_ATTRIBUTES: dict[str, frozenset[str]]` and `ATTRIBUTE_EXEMPT: frozenset[str]`.

**The defect, exactly.** `CLOSED_PACKAGES` is an allowlist over *module names*. `yaml` is on it,
and PyYAML's non-safe loaders are arbitrary code execution — `!!python/object/apply:` instantiates
any importable callable. `yaml.unsafe_load` is a single-link attribute on an allowlisted module,
so the existing `ast.Attribute` rule does not fire: that rule triggers only when `node.attr in
sys.stdlib_module_names`, and `unsafe_load` is not a module name. No banned prefix, no
`__import__`, no `exec`. The audit reproduced `os.system` from a pure-package file importing only
`yaml`, with `test_purity.py` green.

**The general lesson, worth writing into the code:** a closed allowlist holds only if each
allowlisted module's own *surface* is closed. This task closes `yaml`'s. It does not claim to
have closed pydantic's — say *raises the cost*, never *proves*, exactly as invariant 1 does.

**The one legitimate caller.** `packages/comeni-core/src/comeni_core/yaml_strict.py:55` is
`yaml.load(..., Loader=_StrictLoader)` and is the only file in the pure packages that names a
loader at all. It is a **one-file exemption by path**, which is the shape `tests/test_construction.py`
already uses.

- [ ] **Step 1: Write the failing test**

In `tests/test_purity.py`:

```python
def test_a_pure_package_cannot_name_an_unsafe_yaml_loader(tmp_path):
    """A58. `yaml` is on the allowlist and `yaml.unsafe_load` is an RCE primitive:
    `!!python/object/apply:` instantiates any importable callable. It is a single-link
    attribute on an allowlisted module, so the `stdlib_module_names` rule never fires —
    a whole axis the scan did not consider, not the documented two-link gap."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        "import yaml\n"
        "def go():\n"
        "    return yaml.unsafe_load('!!python/object/apply:os.system\\nargs: [id]\\n')\n"
    )
    assert _problems(probe, allowed=CLOSED_PACKAGES["comeni-core"]), (
        "yaml.unsafe_load reached os.system with the scan green"
    )


def test_the_strict_loader_is_the_one_exemption():
    """`yaml_strict.py` names `yaml.load` and a `Loader=`, on purpose — it is the single
    place a loader may be spelled, which is what makes the ban costless everywhere else."""
    assert _problems(
        ROOT / "packages/comeni-core/src/comeni_core/yaml_strict.py",
        allowed=CLOSED_PACKAGES["comeni-core"],
    ) == []
```

Match `_problems`' real name and signature in that file — it is the helper the scan already
uses per file; if it takes `(path, allowed)` in a different order, follow the file.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest tests/test_purity.py -k unsafe_yaml_loader -v
```

Expected: FAIL — the assertion finds no problems, because the scan does not model this.

- [ ] **Step 3: Add the capability ban**

Add beside `CLOSED_PACKAGES` in `tests/test_purity.py`:

```python
BANNED_ATTRIBUTES = {
    # A58. An allowlist over module *names* says nothing about what a listed module can do.
    # PyYAML's non-safe loaders are arbitrary code execution — `!!python/object/apply:`
    # instantiates any importable callable — and `yaml.unsafe_load` is a single-link
    # attribute on an allowlisted module, so no rule above sees it.
    #
    # This closes `yaml`'s surface. It does not close pydantic's, and this file does not
    # claim to: cost-raising, not a proof, exactly as invariant 1 says.
    "yaml": frozenset(
        {"load", "unsafe_load", "full_load", "Loader", "UnsafeLoader", "FullLoader",
         "load_all", "unsafe_load_all", "full_load_all"}
    ),
}

ATTRIBUTE_EXEMPT = frozenset(
    {
        # The single place a loader may be named. Every other file in the pure packages
        # reads YAML through it, which is what makes the ban above cost nothing.
        "packages/comeni-core/src/comeni_core/yaml_strict.py",
    }
)
```

Then extend the `ast.Attribute` branch (`tests/test_purity.py:117`), keeping the existing
`stdlib_module_names` check intact and adding the capability check beside it:

```python
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            dotted = f"{node.value.id}.{node.attr}"
            if (
                node.value.id in bound
                and node.attr in sys.stdlib_module_names
                and dotted not in DOTTED_ALLOWED
            ):
                found.append(
                    f"{where} reaches `{dotted}` — that is the `{node.attr}` module as an "
                    "attribute of an imported one, which no import statement declares"
                )
            banned = BANNED_ATTRIBUTES.get(bound.get(node.value.id, node.value.id), frozenset())
            if node.attr in banned and relative not in ATTRIBUTE_EXEMPT:
                found.append(
                    f"{where} reaches `{dotted}` — an allowlisted module's unsafe surface. "
                    "Read YAML through `comeni_core.yaml_strict`, which is the one file that "
                    "may name a loader"
                )
            continue
```

`bound` maps a local name to the module it was bound from, so `import yaml as y` is caught by
the same rule; `relative` is this file's repo-relative path — use whatever the surrounding
function already computes for `where`, deriving it if `where` carries extra decoration.

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_purity.py -v
```

Expected: all pass, including `test_the_strict_loader_is_the_one_exemption` and the existing
`test_pure_packages_import_nothing_impure`.

- [ ] **Step 5: Revert, watch, restore, record**

```bash
# drop `"unsafe_load"` from BANNED_ATTRIBUTES["yaml"]
uv run pytest tests/test_purity.py -k unsafe_yaml_loader -v     # MUST fail
# restore; then remove the ATTRIBUTE_EXEMPT check from the condition
uv run pytest tests/test_purity.py -k strict_loader -v          # MUST fail
# restore both
uv run pytest tests/test_purity.py -q
```

Record both probes in the guard ledger.

- [ ] **Step 6: Commit**

```bash
git add tests/test_purity.py notes/audits/guard-ledger.md
git commit -m "test: the purity scan closes yaml's loader surface (A58)

CLOSED_PACKAGES is an allowlist over module names, and yaml.unsafe_load is an RCE
primitive on it — a single-link attribute whose name is not a module name, so the
stdlib_module_names rule never fired. A1 reproduced through a route A1's fix does
not cover. yaml_strict.py is the one-file exemption.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: A59 — the runtime hook watches the whole build

**Files:**
- Modify: `tests/test_purity_runtime.py:95-135`
- Test: same file — the deliverable is the guard

**Interfaces:**
- Consumes: Task 2's closed yaml surface (the two findings compose; this is the other half).
- Produces: a module-level `PURE_ROOTS: tuple[Path, ...]` and a `_covered_files(...)` helper the
  coverage assertion uses.

**The defect, exactly.** `test_a_real_build_opens_no_socket_and_spawns_no_process` calls
`layers.load(...)` and `Goal.model_validate(...)` at lines 112–113, **before** `state["armed"] =
True` at line 115. Everything that parses declared data — `comeni_core/layered.py`,
`yaml_strict.py`, `mendel_resolver/layers.py` — runs unwatched, and that is precisely the stage
that ingests stranger-authored registry YAML. The audit opened a real socket inside `layers.load`
and the guard reported `2 passed`.

**Why the coverage assertion matters more than the move.** Moving the arm line is two minutes of
work and silently reversible — the next person who needs a fixture loaded before arming will move
it back, and nothing will say so. Recording *which pure files executed under the hook* and failing
when that set shrinks is what makes the region non-narrowable. This is the same reasoning as A69:
measure the thing, not its proxy.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_purity_runtime.py`:

```python
def test_the_loading_stage_is_watched():
    """A59. The hook armed after `layers.load`, so the stage that parses stranger-authored
    registry YAML ran unwatched — and composed with A58 that is a network call the union of
    both guards cannot see. Asserts the *coverage*, not the absence: a build must execute
    the loading modules under the hook."""
    executed = _files_executed_under_the_hook()
    for required in ("layered.py", "yaml_strict.py", "layers.py"):
        assert any(name.endswith(required) for name in executed), (
            f"{required} did not execute under the audit hook — the watched region has "
            "narrowed, and the stage that reads stranger files is the one it dropped"
        )
```

And a helper that runs the build with the hook armed from the first line, recording the pure
files whose frames appear:

```python
def _files_executed_under_the_hook() -> set[str]:
    """Every file inside a pure package that ran a watched event's frame while armed.

    Uses the `import` audit event as the coverage signal rather than instrumenting each
    module: it fires per module executed, needs no cooperation from the code under test,
    and is already one of the events this file knows how to attribute to a frame.
    """
```

Write its body from the existing `_offending_frames()` machinery in that file — collect frames
rather than only the first, and return the set of file names.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest tests/test_purity_runtime.py -k loading_stage_is_watched -v
```

Expected: FAIL — `layered.py` and `yaml_strict.py` are absent, because they ran before arming.

- [ ] **Step 3: Move the arm above the loading stage**

In `test_a_real_build_opens_no_socket_and_spawns_no_process`, move `state["armed"] = True` from
line 115 to immediately after `sys.addaudithook(hook)`, so `layers.load` and
`Goal.model_validate` run inside the watched region:

```python
    sys.addaudithook(hook)
    # A59: armed *before* the loading stage, not after. `layers.load` and `yaml_strict` parse
    # stranger-authored registry YAML — the one stage in this build that reads a file somebody
    # else wrote — and they ran outside the watched region until round four opened a real
    # socket inside `layers.load` and this test reported `2 passed`.
    state["armed"] = True
    try:
        loaded = layers.load(ROOT / "registry")
        goal = Goal.model_validate(
            yaml.safe_load((ROOT / "examples/rnaseq-goal.yml").read_text())
        )
        ir = resolve(
            goal,
            loaded.registry,
            loaded.rules,
            loaded.measurements,
            vocabulary=loaded.vocabulary,
        )
        emit(_pipe(ir, loaded))
    finally:
        state["armed"] = False
```

Note the `yaml.safe_load` on the goal file is the *test's* own call, not a pure package's, and
`_offending_frames()` already attributes by frame — so it does not fire. If it does, that is a
finding about `_offending_frames`, not a reason to move the arm back down: record it.

- [ ] **Step 4: Run both tests**

```bash
uv run pytest tests/test_purity_runtime.py -v
```

Expected: 3 passed. If the socket/process assertion now fires on a real call from a pure
package, **stop and treat it as a finding** — that is a genuine violation the guard could not
previously see, and it is exactly what this task was for.

- [ ] **Step 5: Revert, watch, restore, record**

```bash
# move `state["armed"] = True` back below `layers.load`
uv run pytest tests/test_purity_runtime.py -k loading_stage_is_watched -v   # MUST fail
# restore, then add a probe socket inside comeni_core/layered.py just before its return:
#   __import__('socket').socket().close()   # PROBE — remove
uv run pytest tests/test_purity_runtime.py -v                               # MUST fail
# remove the probe
git diff --stat        # MUST be empty for packages/ — confirm the probe is gone
uv run pytest tests/test_purity_runtime.py -q
```

The `git diff --stat` check is not ceremony: round four found a reviewer's `telemetry.py` probe
left behind as an untracked file in a worktree. Check `git status` too.

- [ ] **Step 6: Commit**

```bash
git add tests/test_purity_runtime.py notes/audits/guard-ledger.md
git commit -m "test: the runtime hook watches the loading stage too (A59)

The hook armed after layers.load, so every module that parses stranger-authored
registry YAML ran unwatched — a real socket opened inside layers.load and the
guard said 2 passed. Composed with A58 that defeated the union of both purity
guards. The coverage assertion is the half that keeps the region from narrowing
again; moving the arm line alone is silently reversible.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: A57 — the egress guard checks what is serialised

**Files:**
- Modify: `tests/test_egress.py` — every rule that filters on `model_fields`
  (lines 173, 251, 295, 318, 336, 349, 372, 436)
- Test: same file

**Interfaces:**
- Consumes: nothing from Tasks 1–3.
- Produces: `_serialised_fields(payload: type[BaseModel]) -> dict[str, object]` — name →
  annotation, covering declared *and* computed fields. Later rules call it instead of
  `payload.model_fields`.

**The defect, exactly.** Every rule filters `if name in payload.model_fields`. Pydantic has two
other ways to put a key in the JSON that crosses a door, and neither touches `model_fields`: a
`@computed_field` (which lands in `model_computed_fields`) and a `@model_serializer` (which
replaces the dump wholesale). The allowlist that was inverted from a blocklist so that "an
unnamed shape is silence" could not recur is **still a blocklist with respect to where a value
comes from**. The audit put a patient path and a variant into `PromptRequest`'s JSON both ways,
with `15 passed`.

**Two fixes, because the two routes are different shapes.** A computed field has a return
annotation, so it can go through the existing leaf check. A `@model_serializer` has no
per-key annotation at all — there is nothing to check, so the rule is that a payload **may not
define one**. That asymmetry is the finding's actual content and belongs in a comment.

- [ ] **Step 1: Write the failing tests**

In `tests/test_egress.py`:

```python
def test_a_computed_field_cannot_cross_a_door_unchecked():
    """A57. `@computed_field` puts a key in the JSON and lands in `model_computed_fields`,
    which no rule in this file consulted — so the leaf allowlist, inverted from a blocklist
    precisely so an unnamed shape could not be silence, was still a blocklist about where a
    value comes from."""

    class Sneaky(PromptRequest):
        @computed_field
        @property
        def context(self) -> str:
            return "/data/patients/PT-4471023/notes"

    problems = [
        problem
        for name, annotation in _serialised_fields(Sneaky).items()
        for problem in _leaf_problems(annotation, f"Sneaky.{name}", set())
    ]
    assert problems, "a computed `str` crossed the door with no Mark and no complaint"


def test_no_payload_replaces_its_own_dump():
    """A57, the other half. A `@model_serializer` replaces the dump wholesale — there is no
    per-key annotation left to check, so the only enforceable rule is that a payload may not
    define one. Asserted over the real payloads, not a probe."""
    for payload in _payload_types():
        assert "__pydantic_serializer_functions__" not in vars(payload) and not any(
            getattr(getattr(payload, attr, None), "__pydantic_serializer__", None)
            for attr in vars(payload)
        ), f"{payload.__name__} defines a @model_serializer — the dump is no longer checkable"
```

For the second test, use whatever attribute pydantic v2 actually exposes in the installed
version — check with `uv run python -c "import pydantic; print(pydantic.VERSION)"` and inspect a
throwaway model that has a `@model_serializer`. **Do not guess the attribute name**: write the
probe, read the real `vars()`, then write the assertion against what is there. A simpler
equivalent that needs no internals, and is preferred if it holds: for each payload, a
default-constructible instance satisfies
`set(instance.model_dump().keys()) <= set(payload.model_fields) | set(payload.model_computed_fields)`.

- [ ] **Step 2: Run them and watch them fail**

```bash
uv run pytest tests/test_egress.py -k "computed_field or replaces_its_own_dump" -v
```

Expected: the computed-field test fails on `_serialised_fields` not existing (that is the
correct first failure); write the helper, then it must fail on `problems == []`.

- [ ] **Step 3: Add the helper and route every rule through it**

```python
def _serialised_fields(payload: type[BaseModel]) -> dict[str, object]:
    """Name → annotation for everything that reaches the JSON, not everything declared.

    A57: `model_fields` is what a payload *declares*; a `@computed_field` lands in
    `model_computed_fields` and crosses the door all the same. Every rule below asks this
    rather than `model_fields`, because the question a door guard has to answer is what is
    serialised — not what was annotated.
    """
    fields: dict[str, object] = {
        name: field.annotation for name, field in payload.model_fields.items()
    }
    fields.update(
        {name: info.return_type for name, info in payload.model_computed_fields.items()}
    )
    return fields
```

Then replace each `if name in payload.model_fields` filter with iteration over
`_serialised_fields(payload)`. There are eight sites; the mechanical shape is

```python
    for name, annotation in _serialised_fields(payload).items():
        ...
```

replacing the current `for name, annotation in payload.__annotations__.items(): if name in
payload.model_fields:` pairs. Do them one at a time and run the file after each — this is the
guard, and a rule that silently stops iterating is the failure mode being fixed.

- [ ] **Step 4: Run the whole guard**

```bash
uv run pytest tests/test_egress.py -v
```

Expected: all pass, and the count is at least the 15 it was before plus the 2 added.

- [ ] **Step 5: Revert, watch, restore, record**

```bash
# make `_serialised_fields` return only `model_fields`
uv run pytest tests/test_egress.py -k computed_field -v      # MUST fail
# restore
uv run pytest tests/test_egress.py -q
```

Then the sharper probe, which is the one that matters: add the audit's actual
`@computed_field` returning a patient path to the **real** `PromptRequest` in
`packages/comeni-core/src/comeni_core/egress.py`, run the whole file, watch it fail, and remove
it. Confirm with `git diff` that it is gone. Record both.

- [ ] **Step 6: Fix the stale comment the audit noticed**

`tests/test_egress.py` carries an internal comment "Exactly two fields may carry it" above a set
of seven — the same drift family as invariant 14. Change it to state the count is the literal set
below and that the set is the honest record, not the sentence.

- [ ] **Step 7: Commit**

```bash
git add tests/test_egress.py notes/audits/guard-ledger.md
git commit -m "test: the egress guard checks what is serialised, not what is annotated (A57)

Every rule filtered on model_fields. A @computed_field lands in
model_computed_fields and a @model_serializer replaces the dump wholesale, and
neither touches model_fields — so a patient path crossed door 1 with 15 passed.
The allowlist was still a blocklist with respect to where a value comes from.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: A56 — `HUMAN` is evidence, not a claim a resolver can make

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py:294-325`
- Test: `packages/mendel-resolver/tests/test_resolve.py`, `packages/mendel-resolver/tests/test_replay.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–4.
- Produces: no new names. `_resolve_param` stops deriving `human_override` from
  `resolution.source`; the replay path passes the recorded override explicitly.

**The defect, exactly.** `decision.py` already concedes a resolver could set `source`
untruthfully — "the same standing as `confidence` and `reason`". That is not the finding. The
finding is that `source: HUMAN` is **not** like those two: it clears the tier-4 review
(`needs_review()` drops the item into `overrides()`), and A54's fix (`resolve.py:308`) now
*writes* `human_override = resolution.chosen` whenever the resolver claims `HUMAN` — the very
evidence `MD0220` demands. So `MD0220` constrains only hand-edited files; against a resolver it
is satisfied automatically by a value the resolver invented. **Invariant 6 is what this
defeats** — "tier 4 is always flagged, even at high model confidence … the difference from a
chat window."

The comment at `resolve.py:305` asserts "Only `ReplayResolver` returns `HUMAN`". A54 turned
that unenforced assumption into a load-bearing one. Latent today because `FlagOnlyResolver`
never sets `HUMAN`; **live the day Plan 2 wires a model to that port**, which is the next plan.

**The fix is to make the assumption enforced rather than to document it harder.** A `HUMAN`
source must come from a replayed record, and `_resolve_param` must not synthesise the evidence
from the claim.

- [ ] **Step 1: Write the failing test**

In `packages/mendel-resolver/tests/test_resolve.py`:

```python
def test_a_resolver_cannot_certify_itself_as_human():
    """A56. `source: HUMAN` clears the tier-4 review, and A54's fix wrote the
    `human_override` MD0220 checks straight from the resolver's own claim — so a model
    could clear its own red flag and forge the evidence. Invariant 6 is what that defeats:
    tier 4 is always flagged, even at high model confidence."""

    class LyingResolver:
        def resolve(self, request):
            return Resolution(
                chosen="nefarious",
                reason="trust me",
                confidence=0.99,
                resolved_by="totally-a-model",
                source=ValueSource.HUMAN,
            )

    ir = resolve(_goal(), _registry(), _rules(), _measurements(),
                 vocabulary=_vocabulary(), resolver=LyingResolver())

    assert ir.needs_review(), "the tier-4 flag was cleared by the resolver's own claim"
    assert ir.overrides() == [], "a resolver's guess was recorded as a human override"
    decision = _param_decision(ir, "seq_platform")
    assert decision.human_override is None, "the evidence MD0220 checks was forged"
```

Use the fixtures the file already has for `_goal()`, `_registry()` and friends; follow
`conftest.py` rather than inventing them. Match `resolve()`'s real keyword for the resolver port.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-resolver/tests/test_resolve.py -k certify_itself_as_human -v
```

Expected: FAIL on the first assertion — `needs_review()` is empty, the flag is gone.

- [ ] **Step 3: Stop deriving evidence from the claim**

In `resolve.py`, replace the `human_override=` argument (lines 305–313) with:

```python
            # A54 recorded the override here so the artifact is self-consistent; A56 is that
            # deriving it from `resolution.source` let the resolver *manufacture* the evidence.
            # `source: HUMAN` clears the tier-4 review, so unlike `confidence` and `reason` it
            # is not a claim a resolver may make about itself — invariant 6 is the thing that
            # would break, and Plan 2 wires a model to exactly this port.
            #
            # A replayed record is the only origin: it carries the override that a person
            # actually wrote, and `replay` passes it explicitly rather than signalling it
            # through a field the resolver also controls.
            human_override=replayed_override,
```

and compute `replayed_override` above the `decisions.append(...)`, from the recorded decision
being replayed rather than from `resolution`. Read `mendel_resolver/replay.py` for the shape it
already hands `_resolve_param`; if the recorded decision is not currently in scope at this call
site, **thread it as an explicit parameter** — that is the point of the fix, and a resolver-side
signal is what is being removed.

Then make the `ValueSource.HUMAN` on the returned `ResolvedValue` conditional on the same
`replayed_override` rather than on `resolution.source`.

- [ ] **Step 4: Run the resolver and replay tests**

```bash
uv run pytest packages/mendel-resolver/tests/test_resolve.py \
              packages/mendel-resolver/tests/test_replay.py -v
uv run pytest tests/test_upgrade.py tests/test_pipeline_file.py -v
```

Expected: all pass. `upgrade`'s replay is the path that legitimately produces `HUMAN`, and
`MD0218`/`MD0220` are the two diagnostics that read the pair — if any of those fail, the fix has
cut the honest path as well as the dishonest one, and the override is not being threaded.

- [ ] **Step 5: Revert, watch, restore, record**

```bash
# restore `human_override=(resolution.chosen if resolution.source is ValueSource.HUMAN else None)`
uv run pytest packages/mendel-resolver/tests/test_resolve.py -k certify_itself_as_human -v  # MUST fail
# restore the fix
uv run pytest packages/mendel-resolver/tests/test_resolve.py -q
```

- [ ] **Step 6: Verify and commit**

```bash
make verify
git add packages/mendel-resolver/src/mendel_resolver/resolve.py \
        packages/mendel-resolver/tests/test_resolve.py \
        notes/audits/guard-ledger.md
git commit -m "fix: a resolver cannot certify its own answer as human (A56)

A54's fix wrote human_override straight from resolution.source, so a resolver
claiming HUMAN cleared its own tier-4 review and forged the evidence MD0220
checks. Unlike confidence and reason, source: HUMAN is not a claim a resolver may
make about itself — invariant 6 is what it defeats, and Plan 2 wires a model to
this exact port. HUMAN now comes only from a replayed record.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: A70 — publish refuses what it cannot certify

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py:493-515`
  (`_refuse_a_divergent_directory`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (add `MD0222`)
- Test: `tests/test_publish.py`
- Docs: `docs/reference/cli.md` (generated — `make docs`)

**Interfaces:**
- Consumes: nothing from Tasks 1–5.
- Produces: no new names. `_refuse_a_divergent_directory` gains an early refusal branch.

**The defect, exactly.** Publish's whole integrity claim is `_refuse_a_divergent_directory`: the
gate runs on the files *this* `pipeline.yml` describes. It calls `pipeline_file.hand_edited`
(`MD0214`) and `is_stale` (`MD0213`), and **both short-circuit to a no-op when
`pipeline.emitted is None`** (`pipeline_file.py:129`, `:146`). That is a supported, documented
state — archived or hand-authored files have no `emitted:` block. So publish runs the gate on
whatever `main.nf` is on disk and stamps the verdict. The audit published an RNA-seq
`pipeline.yml` whose recorded `main.nf` digest was an *unrelated workflow's*, at exit 0.

**Why the fix goes on the verb and not in `pipeline_file`.** `hand_edited` and `is_stale`
returning "nothing to compare" is *correct* — there is genuinely no evidence. The bug is that a
**certifying** verb treats no-evidence as no-problem. `emit` must keep working on an
`emitted: None` file: it is the cure, and it regenerates the files and stamps the record, after
which `MD0213`/`MD0214` mean something again.

**In scope and confirmed by the audit:** the build-time conformance relocation from A50 *holds* —
`build`, `upgrade` and `profile` all run `conformance.check` unconditionally before emitting. A70
is a separate hole, about `main.nf` ↔ `pipeline.yml` correspondence, not contract ↔ module
conformance. Do not re-open A50.

- [ ] **Step 1: Write the failing test**

In `tests/test_publish.py`:

```python
def test_publish_refuses_a_pipeline_with_no_emitted_record(tmp_path):
    """A70. `hand_edited` and `is_stale` both no-op when `emitted is None` — a supported
    state for archived and hand-authored files — so publish's only tie between `main.nf` and
    `pipeline.yml` goes silent and it certifies whatever is on disk. The door with no undo."""
    directory = _built_spine(tmp_path)               # a real build, gate preview
    source = directory / "pipeline.yml"
    _strip_the_emitted_block(source)
    (directory / "main.nf").write_text("workflow { }\n")   # an unrelated, valid workflow

    code = cli.main(["publish", str(source), "--gate", "preview"])

    assert code != 0, "publish certified a main.nf with nothing tying it to pipeline.yml"
    assert "MD0222" in _stderr()
```

Write `_strip_the_emitted_block` as a small helper that loads the YAML, deletes the `emitted`
key and writes it back — not a string edit, because the digest of the file is what the next
assertion would otherwise depend on. Use the file's existing capsys/stderr convention rather
than the `_stderr()` placeholder above.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest tests/test_publish.py -k no_emitted_record -v
```

Expected: FAIL — `code == 0`. That is the audit's reproduction, as a test.

- [ ] **Step 3: Refuse on the certifying verb**

At the top of `_refuse_a_divergent_directory`, before the `hand_edited` call:

```python
    if previous.emitted is None:
        # A70. `hand_edited` and `is_stale` both return "nothing to compare" here, and that
        # is right — there is no evidence. What is wrong is a *certifying* verb reading
        # no-evidence as no-problem: publish would gate whatever `main.nf` is on disk and
        # stamp the verdict onto an artifact that then permanently claims it emitted that
        # file. Nothing ties the two together, and publish is the door with no undo.
        #
        # `emit` is deliberately not on this path: it is the cure. It regenerates the files
        # from this `pipeline.yml` and stamps `emitted:`, after which MD0213 and MD0214 are
        # meaningful again.
        print(
            f"mendel: MD0222: {source} records no `emitted:` block, so nothing ties the "
            f"files in {directory} to it and `{verb}` cannot certify them. Run "
            f"`mendel emit {source} --out {directory}` first — `mendel explain MD0222`.",
            file=sys.stderr,
        )
        return 2
```

Confirm `2` is this CLI's refusal code by reading the neighbouring `MD0214` branch, and match it.

- [ ] **Step 4: Run the publish and upgrade tests**

```bash
uv run pytest tests/test_publish.py tests/test_upgrade.py tests/test_pipeline_file.py -v
```

Expected: all pass. `upgrade` shares `_refuse_a_divergent_directory` and is *also* a verb that
treats the generated files as evidence, so it is correct for it to refuse too — if an existing
`upgrade` test breaks on an `emitted: None` fixture, read it: either the fixture is unrealistic,
or `upgrade` has a legitimate no-evidence path and the refusal belongs on `publish` alone.
Decide it explicitly and write the reason into the code comment.

- [ ] **Step 5: Add the diagnostic**

```yaml
MD0222:
  emitted_by: compiler
  concern: pipeline-file
  says: "this pipeline records no `emitted:` block, so its directory cannot be certified"
  fires_on: [publish, upgrade]
  refuses: true
  fix: |
    Run `mendel emit <pipeline.yml> --out <directory>` first. That regenerates the files from
    this pipeline and records their digests, after which the directory describes itself.
  explanation: |
    `publish` stamps a gate verdict onto `pipeline.yml`, and the verdict is a claim about the
    files beside it. The only thing tying those files to the pipeline is the `emitted:` block
    — the digests recorded when they were generated. `MD0213` and `MD0214` compare against it.

    A pipeline with no `emitted:` block is a supported state: an archived pipeline, or one
    written by hand. But it means there is no evidence, and the two checks above have nothing
    to compare — so before this code existed, publish read "nothing to compare" as "nothing
    wrong" and certified whatever `main.nf` happened to be in the directory, recording that
    file's digest as the one this pipeline emitted.

    `emit` does not refuse: it is the cure, and it legitimately regenerates from a pipeline
    with no record. Audit A70.
```

```bash
make docs && uv run pytest tests/test_diagnostics_registry.py -v
```

- [ ] **Step 6: Revert, watch, restore, record**

```bash
# comment out the `if previous.emitted is None` block
uv run pytest tests/test_publish.py -k no_emitted_record -v      # MUST fail
# restore
uv run pytest tests/test_publish.py -q
```

- [ ] **Step 7: Verify and commit**

```bash
make verify
git add packages/mendel-compiler/src/mendel_compiler/cli.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml \
        tests/test_publish.py docs/reference/cli.md notes/audits/guard-ledger.md
git commit -m "fix: publish refuses a directory it cannot certify (A70, MD0222)

hand_edited and is_stale both no-op when emitted is None — a supported state for
archived files — so publish's only tie between main.nf and pipeline.yml went
silent and it gated whatever was on disk, recording an unrelated workflow's digest
as this pipeline's. No-evidence is not no-problem on a certifying verb. emit stays
unchanged: it is the cure.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: the record — docs, carried findings, and the changed exit criterion

**Files:**
- Modify: `CLAUDE.md` (the stale counts A71/A72 name, and the plan status)
- Modify: `notes/README.md` (the plan table and "Why that order")
- Create: `notes/journal/2026-08-13.md`
- Modify: `notes/audits/guard-ledger.md` (the round-four-fixes section header, if Task 1
  did not create it)

**Interfaces:** none — this task produces no code.

This is not paperwork. Fifteen findings are being carried rather than fixed, the loop's exit
criterion is being overridden, and A14 stays open — and a repository whose documents claim
otherwise is the exact drift `notes/audits/` exists to catch.

- [ ] **Step 1: File the fifteen carried findings as issues**

One issue per finding, titled `A<n>: <the audit's own one-line summary>`, body quoting the
audit's section verbatim and linking
`notes/audits/2026-08-11-round-four-audit.md`. Label them `audit` and
`round-four`.

```bash
gh issue create --title "A60: the dynamic-importer check matches a spelling" \
  --label audit --body "$(...)"
```

The fifteen: **A60, A61, A62, A63, A64, A65, A66, A67, A68, A69** (guards and totality) and
**A71, A72, A73, A74, A75** (docs and the error surface). A71/A72 are fixed in Step 2 instead —
file the other thirteen and note in the journal that two were fixed rather than filed.

A73 is worth its own note in the issue body: **issue #18's own GitHub body understates the error
surface by ~50 sites** — it says 41/32, and it is 91/56. `CLAUDE.md` is right. Update issue #18's
body while you are there, because a fix plan scoped from the tracker inherits a 55%-too-small
estimate.

- [ ] **Step 2: Fix the two stale counts in `CLAUDE.md` (A71/A72)**

The guard-ledger line says "it names the eleven files that still have none" — it is **zero** now,
since `test_pipeline_totality.py` gained rows in round four. And A69's finding is that A14's
progress was being reported at file granularity (46/47, which reads as nearly done) when its
condition is per *guard* (~34 of ~183). Replace the sentence with the per-guard number and say
which measure it is, because the file-level residue being exhausted is what made the wrong
measure look like success.

- [ ] **Step 3: Record the changed exit criterion**

In `notes/README.md`, under "Why that order", add a dated subsection stating: the
fix-then-re-audit loop's exit criterion was *no critical finding surviving a fresh audit*; on
**2026-08-13 the operator decided Plan 1.12 is the last audit-driven plan**, and Plan 2 follows
it regardless of what a round five would find. State the argument against — round four found four
criticals, three of them in the guards, and the reason those guards keep falling is that nobody
had attacked the new surface; 1.12's own surface gets no such pass. Then state the counter: the
v1 criterion's one unmet clause is the plain-language prompt, four plans have now deferred it,
and an audit loop with no exit is a way of never shipping. **Record both. Do not soften either.**

Update the plan table: row 11 becomes `2026-08-13-closing-round-four.md` — Plan 1.12, and row 12
(Plan 2) becomes **Next**.

- [ ] **Step 4: Write the journal entry**

`notes/journal/2026-08-13.md`, following the shape of `2026-08-10-evening.md`: what
1.12 closed, what each task corrected in this plan (there will be corrections — every plan in
this repository has needed them), the thirteen carried findings and their issue numbers, that
A14 stays open and is now measured per guard, and that **Plan 2 is next**.

- [ ] **Step 5: Verify the whole repository one more time**

```bash
make verify
make static
uv run python tools/generate_types.py --check
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: Plan 1.12 closes round four's criticals; thirteen findings carried

A55, A56, A57, A58, A59 and A70 are fixed. A60-A69 and A73-A75 are filed as
issues rather than fixed, and the loop's exit criterion — no critical finding
surviving — is overridden by decision on 2026-08-13: 1.12 is the last
audit-driven plan and Plan 2 is next. A14 stays open, now measured per guard
(~34 of ~183) rather than per file, which is A69.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** Six findings in scope, six tasks: A55 → Task 1, A58 → Task 2, A59 → Task 3,
A57 → Task 4, A56 → Task 5, A70 → Task 6. Task 7 carries the fifteen out of scope. Every audit
"fix direction" is implemented: A55's "validate at load, closure reachable only from a validated
template" (Steps 3 and 7); A57's "iterate `model_computed_fields`, assert no `@model_serializer`"
(Steps 1 and 3); A58's "ban the loader attribute names, one-file exemption" (Step 3); A59's "arm
above `layers.load`, assert coverage" (Steps 3 and 1); A56's "`HUMAN` reachable only through
replay" (Step 3); A70's "refuse when `previous.emitted is None`, leave `emit` unchanged" (Step 3).

**Two places the plan deliberately does not hand over finished code**, flagged rather than
hidden: Task 4 Step 1's `@model_serializer` detection depends on pydantic internals that must be
read from the installed version rather than guessed, and Task 5 Step 3's `replayed_override`
needs `replay.py`'s actual call shape. Both say so explicitly and say what to read. Guessing a
pydantic internal in a plan is how Plan 1.11's `re` problem happened.

**Type consistency.** `substitutable(value: object) -> bool` from `comeni_core.marks` in Tasks 1
(both sites). `Via.EXT`, `ExtKey.PREFIX`/`ExtKey.ARGS` from `comeni_core.routes`. `ValueSource.HUMAN`
from the decision module, in Task 5 only. `_serialised_fields` defined once in Task 4 and used by
its eight rewritten rules. `_refuse_a_divergent_directory(source, previous, verb)` keeps its
signature in Task 6. `MD0221` (Task 1) and `MD0222` (Task 6) are the only new codes and neither
collides with the `MD0220` high-water mark.
