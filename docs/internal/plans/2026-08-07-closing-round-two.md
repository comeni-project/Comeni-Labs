# Plan 1.9 — closing round two

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement
> this plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax.
> Do **not** farm tasks out with `subagent-driven-development` — subagents are for review and
> design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Close A17–A35 by fixing the nine root design problems behind them, rather than the
eighteen findings in front of them.

**Architecture:** Nine parts, A–I, one per root. Each part is a spec in
[`../specs/`](../specs/) that carries the design, the argument and the verification table; this
plan carries the steps. **Read the part's spec before starting it** — the plan deliberately does
not repeat the reasoning, and several decisions in it were made against evidence that is recorded
only there.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Jinja2, PyYAML. No new dependencies.

---

## Global Constraints

- **Root I is in force from Task 1.** Every guard this plan adds or touches is **reverted and
  watched failing** before its task is called done, and the observed failure message is pasted
  into the task. A guard whose message would not lead a reader to the defect is a finding, not a
  pass. See [`../specs/2026-08-07-root-i-every-guard-is-watched-failing.md`](../specs/2026-08-07-root-i-every-guard-is-watched-failing.md).
- **`make verify`, not `make check`,** at the end of every part. `make check` deselects
  `tests/test_counts.py`, which is the only test exercising the v1 criterion — that is A14's own
  fourth instance.
- **Byte-identical emission is a hard requirement.** The shipped registry must produce identical
  `main.nf` and `nextflow.config` after every part except where a part's spec says otherwise.
  Golden files move only with an explicit, argued commit.
- **The pure packages stay pure.** `comeni-core`, `mendel-resolver`, `mendel-compiler` import no
  web framework, HTTP client or LLM library. `tests/test_purity.py` and
  `tests/test_purity_runtime.py` must stay green.
- Ruff line length 100. `uv run ruff check` and `uv run pytest` pass before every commit.
- Parts run in order **A, B, C, D, E, F, G, H**. Verified topologically: `A→C`, `C→D`, `C→E`,
  `E→H`, `A→B`. Part I has no position; it is the rule above.
- **Expect to correct this plan.** Every plan in this repository has needed correction during
  execution — six steps in the measurements plan, five in 1.5, six in 1.6, two in 1.8. Correct it
  in place, with the reason, as those did.

---

## File structure

```
packages/comeni-core/src/comeni_core/
  __init__.py       re-exports FreeText, ParamLiteral, ShadowRecord — all three deleted   A, B
  marks.py          Mark enum; NfIdentifier, NfPath, Line, GroovyExpression, EdgeRef   A, C, E
  layered.py        NEW — Layer, Kind, Policy, Stacked, Displacement, stack()          B
  yaml_strict.py    NEW — one strict loader                                            G
  registry.py       Registry.load becomes a Kind                                       B
  vocabulary.py     Vocabulary.load becomes a Kind; add_states                         B
  measurement.py    MeasurementRegistry.load becomes a Kind                            B
  decision.py       DecisionKind; three decision types; three *Asked types             E, H
  egress.py         Emitted/EmittedFile; AmbiguityRequest projection                   D, H
  ir.py             shadowed -> displaced; reason -> Line                              B, C
  contract.py       nf_process/nf_include/name/type_id get types                       C
  digest.py         entry_hash() extracted                                             F
packages/mendel-resolver/src/mendel_resolver/
  layers.py         builds Layer values; asserts file coverage                         B
  rules.py          RuleTable.load becomes a Kind; producer_for returns a Pin          B
  router.py         RouteStep.from_layer required; _choose destructures a Pin          B
  resolve.py        takes a vocabulary; validates type ids                             E
  diff.py           edges and tier                                                     D
packages/mendel-compiler/src/mendel_compiler/
  emit.py           _render_comment; config renderers                                  C
  cli.py            OVERLAY block; publish records Emitted; upgrade compares           B, D
tests/
  test_egress.py    positive leaf rule; Any predicate; new roots                       A, H
  test_purity.py    ctypes                                                             A17
  test_construction.py  alias resolution                                               E
  test_audit_regressions.py  one test per finding, A17-A35                             all
docs/internal/audits/guard-ledger.md   NEW — append-only revert ledger                 I
```

---

# Part A — the egress boundary declares what may cross

Spec: [`root-a-egress-allowlist.md`](../specs/2026-08-07-root-a-egress-allowlist.md).
Closes A19, A20, A30 and the open marker set.

### Task A1: `Mark` — one closed marker vocabulary

**Files:** Modify `packages/comeni-core/src/comeni_core/marks.py`; test
`tests/test_audit_regressions.py`.

**Interfaces:** Produces `Mark(StrEnum)` with 15 members and all 15 aliases rewritten as
`Annotated[str, Mark.<X>]`. Consumed by every later part.

- [x] **Step 1: Write the failing test.** In `tests/test_audit_regressions.py`:

```python
def test_a20_marker_metadata_is_a_closed_vocabulary():
    """An invented marker must not read as a declared identifier."""
    import typing
    from comeni_core.marks import ContractId, Mark

    assert all(isinstance(m, Mark) for m in ContractId.__metadata__)
    invented = typing.Annotated[str, "clinical-notes"]
    assert not any(isinstance(m, Mark) for m in invented.__metadata__)
```

- [x] **Step 2: Run to verify it fails.** `uv run pytest tests/test_audit_regressions.py -k a20_marker -x`
      → `ImportError: cannot import name 'Mark'`.
- [x] **Step 3: Add the enum**, 15 members, exactly the strings currently used as metadata plus
      `FREE_TEXT = "free-text"` and `PARAM_LITERAL = "param-literal"`. Docstring: why an enum
      rather than strings — `isinstance(meta, Mark)` is a question with an answer.
- [x] **Step 4: Rewrite all 15 aliases** to `Annotated[str, Mark.<X>]`. `FreeText` and
      `ParamLiteral` classes are deleted; `Text = Annotated[str, Mark.FREE_TEXT]`,
      `ParamValue`'s string arm becomes `Annotated[str, Mark.PARAM_LITERAL]`.
- [x] **Step 5: Fix the re-exports.** `comeni_core/__init__.py` imports and lists `FreeText`
      and `ParamLiteral` in `__all__` (lines 34, 60, 76). Replace both with `Mark`. Found by
      the plan's own self-review, not by execution — an `__init__` that re-exports a deleted
      name is an `ImportError` at the top of the next task.
- [x] **Step 6: Fix `tests/test_egress.py`'s marker references.** `_mentions(annotation,
      marks.FreeText)` becomes an `isinstance(meta, Mark) and meta is Mark.FREE_TEXT` test.
      `FREE_TEXT_FIELDS` keeps its four entries and its count must not change. Four sites:
      `test_egress.py:149` plus three in docstrings at `:159`, `:162`, `:172`.
- [x] **Step 7: Run the suite.** `uv run pytest tests/test_egress.py -v` → 8 passed;
      `uv run python -c "import comeni_core.profile"` still imports.
- [x] **Step 8: Commit** `refactor(core): marker metadata is a closed vocabulary — A20`

### Task A2: the positive leaf rule

**Files:** Modify `tests/test_egress.py`.

**Interfaces:** Consumes `Mark` (A1). Produces
`test_every_payload_field_is_a_declared_shape`.

- [x] **Step 1: Write the rule.** A `_permitted(annotation) -> list[str]` walker returning
      offending descriptions. Permitted: `int`, `float`, `bool`, `NoneType`; any
      `enum.Enum` subclass; any `BaseModel` in `_payload_types()`; `str` **only** when some
      metadata element `isinstance(meta, Mark)`; `list[X]`/`frozenset[X]` with `X` permitted;
      every arm of a union permitted. `Annotated[X, ...]` unwraps to `X` and non-`Mark` metadata
      (an `AfterValidator`) is allowed alongside.
- [x] **Step 2: Run it against the tree as it stands.** Expected **PASS** — the table is a
      transcription of the measured graph (22 models, `list`/`frozenset` only, 8 terminal kinds).
      **If it fails, stop: that is a finding, not a reason to widen the table.**
- [x] **Step 3: Give `Any` its own predicate** and point
      `test_no_payload_carries_an_untyped_container` at it:

```python
def _mentions_any(annotation: object) -> bool:
    if annotation is typing.Any:
        return True
    return any(_mentions_any(arg) for arg in typing.get_args(annotation))
```

- [x] **Step 4: Watch all nine probes fail.** One at a time, added to a real payload, run,
      reverted. Paste each observed message into this task.

| probe | on | must fail |
|---|---|---|
| `leak: object` | `Lockfile` | positive rule |
| `leak: Path \| None` | `PublishBundle` | positive rule |
| `leak: Any` | `PublishBundle` | positive rule **and** the repaired `Any` rule |
| `leak: dict[str, Any]` | `PublishBundle` | both |
| `leak: tuple[str, str]` | `Lockfile` | positive rule |
| `leak: bytes` | `Lockfile` | positive rule and binary rule |
| `leak: Mapping[MeasurementId, ParamValue]` | `Lockfile` | positive rule and mapping rule |
| `leak: str` | `Lockfile` | positive rule and bare-str rule |
| `leak: Annotated[str, "invented"]` | `Lockfile` | **positive rule only — passes today** |

- [x] **Step 5: `git status` clean**, `uv run pytest tests/test_egress.py -v` → 9 passed.
- [x] **Step 6: Commit** `test(egress): a payload field is a declared shape — A19, A20, A30`

### Task A3: A17 — `ctypes`

**Files:** Modify `tests/test_purity.py`, `tests/test_purity_runtime.py`, `CLAUDE.md`.

A17 is unclustered (see the root-causes document: the purity banlist cannot become an allowlist),
but it is a two-line fix and belongs with the other guard work.

- [x] **Step 1: Reproduce.** Add reviewer 1's `_telemetry()` to `emit.py` — `ctypes.CDLL`,
      `libc.socket`/`connect`/`send` to `127.0.0.1` — with a listener. Confirm
      `uv run pytest tests/test_purity.py tests/test_purity_runtime.py` → **3 passed** while
      bytes arrive.
- [x] **Step 2:** Add `"ctypes"` to `BANNED_PREFIXES`.
- [x] **Step 3:** Add `"ctypes.dlopen"`, `"ctypes.dlsym"`, `"ctypes.call_function"`,
      `"ctypes.cdata"` to `WATCHED`.
- [x] **Step 4: Re-run.** Both guards must now fail, naming the file.
- [x] **Step 5: Delete the telemetry code.** `git status` clean.
- [x] **Step 6: `CLAUDE.md` invariant 1** gains FFI: the union of the two guards does not cover a
      libc call obtained through `ctypes`, and now does.
- [x] **Step 7: Commit** `test(purity): ctypes is a route the union did not cover — A17`

- [x] **Part A gate:** `make verify` — check, slow, guards, drift. Paste the four numbers.

---

# Part B — a layer is one thing, and it stacks one way

Spec: [`root-b-a-layer-is-one-thing.md`](../specs/2026-08-07-root-b-a-layer-is-one-thing.md).
Closes A22, A23, A24, A25, A26, A35. **The largest part.**

### Task B1: `layered.py` — the mechanism, with no callers

**Files:** Create `packages/comeni-core/src/comeni_core/layered.py`; test
`packages/comeni-core/tests/test_layered.py`.

**Interfaces:** Produces `Layer(path, name, index)`, `DeclaredKind(StrEnum)`, `Policy(StrEnum)`,
`Kind`, `Stacked(entries, origin, displaced)`, `Displacement`, `stack(layers, kind)`.

- [x] **Step 1: Write failing tests** against a synthetic kind with no dependency on the
      registry: two layers, one shared key, one unique key each. Assert `entries` has the
      higher layer's value, `origin` maps each key to a layer **index**, and `displaced` holds
      one record naming both layers.
- [x] **Step 2: Run to verify it fails** — `ModuleNotFoundError: comeni_core.layered`.
- [x] **Step 3: Implement.** Recursion via `rglob`, `*.yml` **and** `*.yaml`, missing
      subdirectory tolerated, entries sorted for determinism, and a `claimed: set[Path]` on
      `Stacked` recording which files were read.
- [x] **Step 4: Test the collision case** — two layers whose `name` is identical but whose
      `index` differs. Both displacement records must survive. This is A25 and it must fail
      before step 3 is complete.
- [x] **Step 5: Test `Policy.DELETE_GROUP`** — a `group` key differing from the storage key,
      with displaced members removed. This is contract shadowing, tested before any contract
      uses it.
- [x] **Step 6:** `uv run pytest packages/comeni-core/tests/test_layered.py -v`.
- [x] **Step 7: Commit** `feat(core): a layer is a value and stacking is one mechanism`

### Task B2: measurements move to `stack()`

**Files:** Modify `measurement.py`, `layers.py`; test `tests/test_audit_regressions.py`.

- [x] **Step 1: Write the failing A23 test** — base + overlay measurement with a different
      `meta_values` translation; assert a `Displacement` is produced naming both layers.
- [x] **Step 2: Run to verify it fails** — no displacement is recorded today.
- [x] **Step 3:** `MeasurementRegistry.load` becomes `Kind(MEASUREMENTS, parse, key=stem,
      policy=REPLACE)` with `add_values` as `Policy.MERGE`.
- [x] **Step 4: Re-run.** Also assert the shipped single-layer registry produces **no**
      displacement.
- [x] **Step 5: Commit** `fix(core): a measurement overlay says so — A23`

### Task B3: vocabularies move to `stack()`, and `add_states` lands

**Files:** Modify `vocabulary.py`, `layers.py`; test `tests/test_audit_regressions.py`.

- [x] **Step 1: Write two failing tests** — A24 (an overlay replacing `entry_channel` is
      reported) and A35 (an overlay declaring `states:` replaces and **is reported**; one
      declaring `add_states:` extends and base states survive).
- [x] **Step 2: Run to verify they fail.** A35 currently surfaces as
      `UnknownStateError: 'trimmed' is not a declared state` from an unrelated contract — paste
      that, it is the misdirection the fix removes.
- [x] **Step 3:** `Vocabulary.load` becomes a `Kind`; `add_states` is `Policy.MERGE`; the
      per-field conditional replacement is removed so one policy governs the whole entry.
- [x] **Step 4: Re-run.** Shipped registry unchanged.
- [x] **Step 5: Commit** `fix(core): a vocabulary overlay says so, and add_states extends — A24, A35`

### Task B4: contracts move to `stack()`; `ShadowRecord` is deleted

**Files:** Modify `registry.py`, `ir.py`, `layers.py`, `cli.py`, `lockfile.py`.

- [x] **Step 1: Write the failing test** — `PipelineIR.displaced` holds a `Displacement` for a
      shadowed contract, with `displaced_keys` naming the full ids removed.
- [x] **Step 2: Run to verify it fails** — `PipelineIR` has `shadowed`, not `displaced`.
- [x] **Step 3:** `Registry.load` becomes `Kind(CONTRACTS, parse=ModuleContract.load,
      key=id, group=module_key, policy=DELETE_GROUP)`. `Registry.layer_of` maps to **index**.
- [x] **Step 4:** `PipelineIR.shadowed` → `displaced: list[Displacement]`; delete
      `ShadowRecord`; update `cli.py`'s `SHADOW` line into the `OVERLAY` block. **Five consumers
      beyond `registry.py`**, found by self-review: `comeni_core/__init__.py:43,88` (import and
      `__all__`), `ir.py:24,180`, and prose references in `layer.py:9`, `ir.py:77`,
      `test_ir_provenance.py:66`, `test_audit_regressions.py:148,334`. The prose references are
      history and stay; the imports must go.
- [x] **Step 5: Revert `Lockfile.drift_against`'s layer comparison** and confirm its guard fails.
      It was inert once already (`8dbde51`) and this part changes the identity it reads.
- [x] **Step 6:** `uv run pytest tests/test_lockfile.py tests/test_publish.py -v`.
- [x] **Step 7: Commit** `refactor(core): contracts stack through the one mechanism — A25`

### Task B5: rules move to `stack()`, and a pin carries its provenance — A22

**Files:** Modify `rules.py`, `router.py`, `resolve.py`; test `tests/test_audit_regressions.py`.

**Interfaces:** Produces `Pin(contract_id, from_layer, displaced_layer, decision, row)`.
`RouteStep.from_layer` loses its default.

- [x] **Step 1: Write the failing A22 test** — an overlay with a **`producer_of:`** rule block
      (not `param:` — that is the bug in the A15 fixture). Assert `selection.from_layer` names
      the layer whose *rule* decided, and `overlay_reroutes()` names it.
- [x] **Step 2: Run to verify it fails.** Expected today: `from_layer: registry`,
      `displaced_layer: None`, `overlay_reroutes() == []` — the artifact asserting the opposite
      of what happened. Paste it.
- [x] **Step 3:** `RuleTable.producer_for` returns a `Pin`.
- [x] **Step 4:** `RouteStep.from_layer: LayerName` — **no default**. Fix every construction
      site; the type is what forces the read.
- [x] **Step 5:** `router._choose` destructures the `Pin` and prefers rule provenance over the
      contract-level answer when a rule decided.
- [x] **Step 6: Re-run**, plus the A15 `param:` test, which must still pass.
- [x] **Step 7: Commit** `fix(resolver): a rule-pinned reroute says which layer decided — A22`

### Task B6: every file in a layer is claimed — A26

**Files:** Modify `layers.py`; test `tests/test_audit_regressions.py`.

- [x] **Step 1: Write three failing tests** — a `.yaml` contract loads; a vocabulary nested one
      directory deep loads; an unrecognised `.yml` under a layer subdirectory **raises naming
      the file**.
- [x] **Step 2: Run to verify they fail.** The `.yaml` case today routes on the base layer with
      exit 0 — paste that.
- [x] **Step 3:** `layers.load` unions every `Stacked.claimed` and raises on the residue.
- [x] **Step 4: Re-run**; shipped registry unaffected.
- [x] **Step 5: Commit** `fix(resolver): a file in a layer that nothing reads is an error — A26`

- [x] **Part B gate:** `make verify`. **Emission must be byte-identical** for the shipped
      single-layer registry — this is the part most likely to move it.
      **Green, 2026-08-07:** check 392, slow 2 (the counts matrix, including the
      strandedness assertion A23's mechanism touches), guards 13, drift skipped. Golden
      files unmoved.

> **Corrections made while executing Part B**, in the spirit of the global constraint.
>
> - **Every loader takes layer roots**, not `<layer>/contracts` or `<layer>/measurements`.
>   The plan said "`MeasurementRegistry.load` becomes a `Kind`" without saying what it is
>   handed; `stack()` reads `layer.path / kind.which.value`, so a slice-taking loader cannot
>   use it. `names=` disappears from `Registry.load` and `RuleTable.load` for the same
>   reason — the fact the caller was forwarding is now on the `Layer`. ~40 call sites, all
>   in tests, all mechanical.
> - **Each container carries its own `displaced`**, and `resolve()` reads
>   `measurements.displaced + registry.displaced`. Passing them in would be the guard in a
>   caller the next caller forgets — the same argument the plan makes for `RouteStep`.
>   `Vocabulary`'s join in Part E, when `resolve()` takes one; recorded in `resolve.py`.
> - **`value_for` returns a `Pin` too**, not only `producer_for`. Same forgetting risk,
>   and A15 was found at exactly that site.
> - **A35 needed a message, not only a record.** Reporting the displacement does not help
>   if the build dies first with `UnknownStateError` naming a base contract. `layers.load`
>   joins the two: `UnknownStateError` carries `type_id` and `state`, and the loader names
>   the layer that removed the state.
> - **B6's residue check covers the whole layer**, not only the four subdirectories —
>   everything under those is claimed by construction, so the check would have been inert.
>   A misspelled `contract/` is the case that matters.
> - **Two dead conditions found by reverting**: `origin[key] != layer.index` can never be
>   false, and `stack()`'s duplicate-key message named "an earlier file" when the duplicate
>   is usually in the same file.

---

# Part C — every string the emitter writes has a declared kind

Spec: [`root-c-nothing-is-interpolated.md`](../specs/2026-08-07-root-c-nothing-is-interpolated.md).
Closes A27, A34.

### Task C1: the four new marks and their validators

**Files:** Modify `marks.py`; test `packages/comeni-core/tests/test_marks.py`.

**Interfaces:** Produces `NfIdentifier`, `NfPath`, `GroovyExpression`, `Line`; `Text` unchanged.
`Mark` gains `NF_IDENTIFIER`, `NF_PATH`, `GROOVY_EXPRESSION`.

- [x] **Step 1: Write failing tests** — `NfIdentifier` accepts `STAR_ALIGN`, rejects
      `"A }\nprintln 'x'"`, a space and an empty string. `NfPath` accepts
      `modules/nf-core/star/align/main`, rejects a leading `/`, a `..` segment and a newline.
      `Line` rejects `"a\nb"`; **`Text` still accepts it.**
- [x] **Step 2: Run to verify they fail.**
- [x] **Step 3: Implement.** `Line = Annotated[str, Mark.FREE_TEXT, AfterValidator(_single_line)]`
      — **the same `Mark.FREE_TEXT`**, so part A's `FREE_TEXT_FIELDS` count does not change.
- [x] **Step 4: Run** `uv run pytest packages/comeni-core/tests/test_marks.py tests/test_egress.py -v`.
- [x] **Step 5: Commit** `feat(core): a string that reaches an artifact declares its kind`

### Task C2: apply the kinds

**Files:** Modify `contract.py`, `vocabulary.py`, `ir.py`, `decision.py`, `egress.py`, `goal.py`.

- [x] **Step 1: Write the failing A34 test** — a contract with a newline in `nf_process` is
      **refused at load**, naming the field.
- [x] **Step 2: Run to verify it fails.** Today it loads and injects; paste the emitted
      `include { LAB_SORT }` / `println …` / `include { … }` block.
- [x] **Step 3: Retype** per the spec's table: `nf_process`→`NfIdentifier`,
      `nf_include`→`NfPath`, `id`→`ContractId`, `container`→`ContainerRef | None`, every
      `name`→`NfIdentifier`, every `type_id`→`TypeId`, `entry_channels` values→`GroovyExpression`,
      `reason`→`Line`. **`GateFailure.tool_message` stays `Text`.**
- [x] **Step 4:** Validate vocabulary type ids (filename stems) on load.
- [x] **Step 5: Run** the whole suite; the shipped registry must load unchanged.
- [x] **Step 6: Commit** `fix(core): an identifier is validated, not interpolated — A34`

### Task C3: the emitter renders by class, both surfaces

**Files:** Modify `emit.py`; test `tests/test_audit_regressions.py`.

- [x] **Step 1: Write two failing tests** — a `reason` that reaches the emitter with a newline
      produces a comment that is still a comment; `withName:` in `nextflow.config` cannot be
      broken out of.
- [x] **Step 2: Run to verify they fail.** Paste the `process { … println … }` config block.
- [x] **Step 3:** Add `_render_comment()`; route every `emit_config` interpolation through a
      renderer rather than an f-string.
- [x] **Step 4: Confirm the exceptions still work** — `entry_channel` emits arbitrary Groovy
      verbatim, `ext_args` is still escaped by `_render_literal`.
- [x] **Step 5: Golden check** — `main.nf` and `nextflow.config` byte-identical for the shipped
      registry.
- [x] **Step 6: Commit** `fix(compiler): prose and identifiers are rendered, not interpolated — A27`

- [x] **Part C gate:** `make verify`. **Green, 2026-08-07:** check 425, slow 2, guards 13,
      drift skipped. Golden files unmoved, so the shipped registry's identifiers were all
      valid — which is what made that row a check rather than a formality.

> **Corrections made while executing Part C.**
>
> - **No `re`.** It is not on `comeni-core`'s purity allowlist, and the spec's regexes would
>   have needed it. `str.isidentifier()` plus `str.isascii()` is the same rule; the control
>   character test is a comprehension. Widening the allowlist for a character class is the
>   wrong trade — `test_purity.py` caught this on the first run.
> - **`isascii()` is a narrowing, not a correction.** Groovy follows Java and *does* allow
>   unicode identifiers. Reverting it failed no test, which is how an unjustified narrowing
>   looks exactly like an untested one. Both fixed: two unicode cases in `test_marks.py`, and
>   the reason written down — two process names that render identically and are not equal is
>   a bad property for a reviewer's reading to have.
> - **`TypeId` gained a shape validator**, which the spec's table implied ("itself validated
>   identifier-safe") without saying what the rule is: letters, digits, dot, underscore,
>   hyphen, starting with a letter. `profile.yml` is a shipped type id and stays legal.

---

# Part D — the verdict comes from the artifact

Spec: [`root-d-the-verdict-comes-from-the-artifact.md`](../specs/2026-08-07-root-d-the-verdict-comes-from-the-artifact.md).
Closes A28.

### Task D1: the bundle records what it emitted

**Files:** Modify `egress.py`, `cli.py`; test `tests/test_publish.py`.

**Interfaces:** Produces `EmittedFile(name: NfPath, digest: Digest)`,
`Emitted(files: list[EmittedFile])`, `PublishBundle.emitted: Emitted | None`.

- [x] **Step 1: Write the failing test** — a published bundle's `emitted.files` names `main.nf`
      and `nextflow.config`, sorted, with `sha256:` digests; publishing without a gate still
      records them.
- [x] **Step 2: Run to verify it fails.**
- [x] **Step 3: Implement**, filling it in `publish` **after** the gate, so the digest is of the
      files that passed.
- [x] **Step 4: Run `tests/test_egress.py`** — a new payload field must satisfy part A's leaf
      rule. Update `test_the_bundle_carries_all_four_parts`'s exact key set deliberately, as
      `gate` did.
- [x] **Step 5: Commit** `feat(core): a bundle records the artifact it produced`

### Task D2: upgrade compares, and reports what it cannot explain

**Files:** Modify `cli.py`, `diff.py`; test `tests/test_upgrade.py`.

- [x] **Step 1: Write four failing tests** — unchanged registry reports byte-identical; a
      hand-edited `reason` reports **differs** (today: "no changes"); an edge rewire is named by
      `diff_ir`; a digest difference with an empty `diff_ir` prints the **unexplained** message
      naming both causes.
- [x] **Step 2: Run to verify they fail.** Paste the current
      `no changes: this pipeline re-resolves identically` beside a `diff` showing `main.nf` moved.
- [x] **Step 3:** Compare digests for the verdict; extend `diff_ir` to edges (keyed
      `(to_node, to_port)`) and tier. Do **not** add profile, shadowed or unverified.
- [x] **Step 4: Test the `emitted: None` case** — a bundle predating the field must say so, not
      claim identity.
- [x] **Step 5: Test the deleted-contract case** — upgrade after removing a contract reports
      drift and a verdict, **no `KeyError`**. This is why the digest is recorded rather than
      re-emitted.
- [x] **Step 6: Commit** `fix(compiler): the upgrade verdict comes from the artifact — A28`

- [x] **Part D gate:** `make verify`. **Green, 2026-08-07:** check 429, slow 2, guards 13.

> **Corrections made while executing Part D.**
>
> - **The "hand-edited `reason`" probe does not reproduce.** Editing the bundle's own IR
>   changes neither the emitted files nor the recorded digests, so the artifact matches and
>   the verdict is right to say so. The real blind spot is a *registry* field the diff does
>   not compare: `ext_args` reaches `nextflow.config` and nothing in `diff_ir` looks at it.
>   That is the probe now, and it exercises the unexplained message honestly rather than by
>   forging a digest.
> - **The deleted-contract probe is the two-layer case.** Deleting a contract the rule table
>   names makes the *rules* invalid, and deleting the only producer of a type makes the goal
>   unroutable — both are refusals, not verdicts. Publishing against two layers and upgrading
>   against one removes a locked contract while leaving the pipeline routable, which is the
>   case the spec was reaching for.

---

# Part E — a declared identifier names something that exists

Spec: [`root-e-a-declared-id-names-something.md`](../specs/2026-08-07-root-e-a-declared-id-names-something.md).
Closes A29, A18, A16.

### Task E1: `resolve()` validates type ids — A29

**Files:** Modify `resolve.py` and every call site; test `tests/test_audit_regressions.py`.

- [ ] **Step 1: Write the failing test** — a goal with
      `type_id: "PT-4471023 Jane Doe, /data/…"` is refused by `resolve()`; the same through
      `required_states`; the same through a bundle via `mendel upgrade`.
- [ ] **Step 2: Run to verify it fails.** Paste the `grep` showing it in
      `pipeline.bundle.json`.
- [ ] **Step 3:** `resolve()` gains a **required** `vocabulary` parameter — required for A2's
      reason — and validates `have`, `want` and `required_states`.
- [ ] **Step 4: Update every call site.** Count them; **do not trust a number written here** —
      Plan 1.8 Task 4 predicted eight and found twelve plus a README, and a loose grep during
      this plan's self-review returned 46 across code, tests and docs. Establish the real figure
      with a narrow grep before starting, and record it in this step.
- [ ] **Step 5: Confirm `examples/rnaseq-goal.yml` still resolves**, emission byte-identical.
- [ ] **Step 6: Commit** `fix(resolver): a goal's types must be declared — A29`

### Task E2: a decision declares its kind — A16

**Files:** Modify `decision.py`, `ir.py`, `resolve.py`, `router.py`, `replay.py`, `marks.py`.

**Interfaces:** Produces `DecisionKind`, `EdgeRef`, `ParamDecision`, `ProducerDecision`,
`SourceDecision`, `DecisionRecord` as a discriminated union.

- [ ] **Step 1: Write failing tests** — `ProducerDecision(chosen="not-a-contract")` refused;
      `SourceDecision(chosen="run.cram")` refused; **`SourceDecision(chosen="dual.bam")`
      accepted**; a published bundle round-trips through the union.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the three types over a shared base, with `EdgeRef` built from
      `NfIdentifier` (part C).
- [ ] **Step 4: Construct the right kind** at all three ambiguity sites.
- [ ] **Step 5: Narrow `HumanParamValue`** to `ParamDecision.human_override` alone; the other
      two kinds now have real domains.
- [ ] **Step 6: `replay.py` round-trips the union**; `uv run pytest -k replay -v`.
- [ ] **Step 7: Commit** `refactor(core): a decision declares its kind — A16`

### Task E3: the construction guard stops matching spellings — A18

**Files:** Modify `tests/test_construction.py`.

- [ ] **Step 1: Write the failing test** — `from … import DataProfile as _DP;
      _DP.model_construct(...)` in a pure package is flagged.
- [ ] **Step 2: Run to verify it fails** — today: 1 passed.
- [ ] **Step 3:** Reuse `test_purity.py`'s `_imported_names`; flag `model_construct`,
      `model_validate`, `model_validate_json` on a binding resolving to `DataProfile`.
- [ ] **Step 4: Record in the docstring** that A2's re-check inside `resolve()` is the real
      enforcement and this scan is belt and braces — otherwise the next reader treats a
      spelling-matcher as the guarantee, which is how A18 happened.
- [ ] **Step 5: Commit** `test(construction): resolve aliases and alternate constructors — A18`

- [ ] **Part E gate:** `make verify`.

---

# Part F — a guard calls its subject

Spec: [`root-f-a-guard-calls-its-subject.md`](../specs/2026-08-07-root-f-a-guard-calls-its-subject.md).
Closes A21.

### Task F1: extract `entry_hash` and rewrite the forgery test

**Files:** Modify `digest.py`, `packages/comeni-core/tests/test_digest.py`.

- [ ] **Step 1: Revert `_hex(name.encode())` → `name`** and run
      `uv run pytest packages/comeni-core/tests/test_digest.py -v`. Expected **12 passed** —
      paste it. That is the finding.
- [ ] **Step 2: Extract `entry_hash(name, content_digest) -> str`**, public, documenting that a
      test must construct forgeries through it.
- [ ] **Step 3: Rewrite the test** to build its forged filename from `entry_hash`.
- [ ] **Step 4: With the fix still reverted, re-run.** The test must now **fail**.
- [ ] **Step 5: Restore the fix**; digest of the shipped registry unchanged.
- [ ] **Step 6: Ask A21's symmetric question** — revert `_FILE` domain separation and run the
      suite. If nothing fails, that is a **new finding**; record it as A36 rather than fixing it
      here.
- [ ] **Step 7: Commit** `test(digest): the forgery test calls the code it guards — A21`

### Task F2: the sweep

**Files:** Modify `docs/internal/audits/guard-ledger.md`.

- [ ] **Step 1:** For each of `test_lockfile.py`, `test_registry_drift.py`,
      `test_generated_types.py`, `test_conformance.py` and the remaining `test_digest.py` tests,
      answer one question: does the test **call** the code under test to build its fixture, or
      **restate** what that code does?
- [ ] **Step 2:** Record each answer in the ledger. Restating is a finding, numbered A37+.
- [ ] **Step 3: Commit** `docs: the guard ledger, and what re-implements its subject`

- [ ] **Part F gate:** `make verify`.

---

# Part G — a file reads one way

Spec: [`root-g-a-file-reads-one-way.md`](../specs/2026-08-07-root-g-a-file-reads-one-way.md).
Closes A31.

### Task G1: the strict loader

**Files:** Create `packages/comeni-core/src/comeni_core/yaml_strict.py`; modify the 7 call sites.

- [ ] **Step 1: Write the failing test** — a contract with a repeated `priority:` is refused,
      and the message names **the file, the key and both line numbers**.
- [ ] **Step 2: Run to verify it fails.** Paste `loaded priority = 999`.
- [ ] **Step 3: Implement** a `SafeLoader` subclass overriding `construct_mapping`.
- [ ] **Step 4: Move all 7 call sites** — `vocabulary.py`, `contract.py`, `measurement.py`,
      `layer.py`, `rules.py`, `modulespec.py`, `cli.py` (the goal file).
- [ ] **Step 5: Run against everything the project owns** — the shipped `registry/`, all of
      `examples/`, and **every vendored `meta.yml`**. A vendored file that trips it is a finding
      about that module, recorded, **not exempted**.
- [ ] **Step 6: Commit** `fix(core): a declared file cannot be read two ways — A31`

### Task G2: measure the anchor hypothesis

**Files:** `docs/internal/audits/2026-08-07-round-two-audit.md`.

- [ ] **Step 1:** Construct a contract using a YAML anchor and alias; load it. Record what
      happens.
- [ ] **Step 2:** Construct a billion-laughs expansion; load it with a timeout. Record what
      happens.
- [ ] **Step 3:** **Only now** decide whether `_StrictLoader` refuses anchors. If it should,
      that is a new task; if not, record why. Recording an untested hypothesis as a fix is what
      this plan exists to stop.
- [ ] **Step 4: Commit** `docs: anchors and expansion, measured`

- [ ] **Part G gate:** `make verify`.

---

# Part H — the seam is a door

Spec: [`root-h-the-seam-is-a-door.md`](../specs/2026-08-07-root-h-the-seam-is-a-door.md).
Closes A32, A33. **Depends on Part E** for `DecisionKind` and `EdgeRef`.

### Task H1: `Ambiguity` becomes three declared types

**Files:** Modify `decision.py`, `ports.py`, `router.py`, `resolve.py`, `egress.py`,
`tests/test_egress.py`.

**Interfaces:** Produces `ParamAsked`, `ProducerAsked`, `SourceAsked`; `Resolution` gains
`extra="forbid"` and `resolved_by: ResolverId`.

- [ ] **Step 1: Write failing tests** — `Ambiguity(..., extra=1)` refused; a `context=` keyword
      fails because the field is gone; `Resolution(resolved_by=<unmarked str>)` refused.
- [ ] **Step 2: Run to verify they fail** — today `Ambiguity` has no `model_config` at all.
- [ ] **Step 3: Implement** the three types, moving `context`'s three uses (`type_id`,
      `required`, `states`, `tier_hint`) to declared fields per kind.
- [ ] **Step 4: Add `Ambiguity` and `Resolution` to the egress guard's roots**; they must pass
      part A's leaf rule.
- [ ] **Step 5: Assert the projection is total** — a test that every `*Asked` field maps to an
      `AmbiguityRequest` field, so a future field cannot silently fail to cross.
- [ ] **Step 6:** `FlagOnlyResolver` and `ReplayResolver` still satisfy the protocol.
- [ ] **Step 7: Commit** `refactor(core): the seam a model sits behind is a declared type — A32`

### Task H2: A33's four smaller items

**Files:** Modify `router.py`, `resolve.py`, `cli.py`, `CLAUDE.md`.

- [ ] **Step 1:** `router._choose`'s tier-4 reason states what happened rather than always
      `"chosen by id order"`.
- [ ] **Step 2:** Document at the site why `_resolve_param` trusts a non-candidate answer while
      the other two sites do not.
- [ ] **Step 3:** Add `ValueError` to `cli.main`'s except-list so a symlinked layer and A35's
      `UnknownStateError` read as `mendel:` lines rather than tracebacks.
- [ ] **Step 4:** Correct `CLAUDE.md` invariant 14 — it says two free-text fields; there are
      four, and the guard is the honest one.
- [ ] **Step 5: Commit** `fix: four smaller items at the AI seam — A33`

- [ ] **Part H gate:** `make verify`.

---

# Part I — the ledger

Spec: [`root-i-every-guard-is-watched-failing.md`](../specs/2026-08-07-root-i-every-guard-is-watched-failing.md).
Closes A14 — **and only when the ledger is complete, which this plan does not achieve alone.**

### Task I1: start the ledger, in Part A

**Files:** Create `docs/internal/audits/guard-ledger.md`.

- [ ] **Step 1:** One row per guard: file, test, what was reverted, what happened, message
      quality, date. Append-only.
- [ ] **Step 2:** Seed it with round two's 22 recorded reverts.
- [ ] **Step 3: Commit** `docs: the guard ledger — A14's closure condition`

### Task I2: the residue

- [ ] **Step 1:** After Parts A–H, list every guard in `tests/` with no ledger row.
- [ ] **Step 2:** Revert each, watch, record. Most will already be covered because A–H rewrite
      them.
- [ ] **Step 3:** **Re-revert every guard a part rewrote**, after the rewrite. A21 exists
      because a *fix* disarmed a guard.
- [ ] **Step 4: Commit** `docs: the ledger is complete — A14 closed`

---

## Verification

```bash
make verify                       # after every part, not make check
uv run pytest tests/test_audit_regressions.py -v    # one test per finding, A17-A35
uv run python tools/check_registry_drift.py ../comeni-registry
```

**Done when:** A17–A35 are ✅ with the commit that closed each, `tests/test_audit_regressions.py`
holds a test per finding **that was watched failing**, the guard ledger has a row per guard in
`tests/`, and `CLAUDE.md` makes no claim this plan did not enforce.

**Not done when this plan merges, if the ledger is incomplete.** A14 closes on the ledger, not on
the parts. Say so rather than marking it closed to make the arithmetic work — that was the call
made in Plan 1.8 and it was right.

---

## Round three

Audit again after this plan, by the brief in
[`../audits/2026-08-07-round-two-brief.md`](../audits/2026-08-07-round-two-brief.md), starting at
**A36** or wherever Part F and G's measurements have taken the numbering. The sharpest defect has
been in the freshest code in all three audits; there is no reason to expect this plan to be the
exception, and five of round two's findings were in code written to close round one.
