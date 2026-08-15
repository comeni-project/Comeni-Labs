# One source for a diagnostic code — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` — task by task, in a
> worktree. Steps use `- [ ]` for tracking.

**Goal:** every emission of a diagnostic code goes through one function that checks it against
the registry, and both directions — declared-but-never-raised, raised-but-never-declared — are
tests that can fail.

**Architecture:** Four tasks. `coded()` first so there is something to convert to; the
conversion second, per package, largest file first so the shape is settled early; the
bidirectional guard third, because it cannot pass until the conversion is done; documentation
last.

**Spec:** [`notes/specs/2026-08-16-one-source-for-a-diagnostic.md`](../specs/2026-08-16-one-source-for-a-diagnostic.md)

## Global Constraints

- **Work in a worktree.** This plan runs in `.worktrees/diagnostic-factory`.
- **No message text changes.** This moves where a code is checked, not what it says. The one
  intended output change is `MD0202`'s format (spec §5) — everything else must be byte-identical.
- **`docs/reference/diagnostics.md` must not move.** It is the canary: if it changes, something
  other than an emission site changed.
- **`make verify`** closes Tasks 2 and 3 — both touch `comeni-core`.
- **Every guard watched failing**, with a ledger row.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `comeni_core/diagnostics.py` | `coded()` | 1 |
| `packages/comeni-core/tests/test_diagnostics_registry.py` | `coded()`'s own tests | 1 |
| ~12 source files across three packages | every emission through `coded()` | 2 |
| `tests/test_diagnostics_ownership.py` | both directions; `UNLOCATABLE` deleted | 3 |
| `docs/reference/diagnostics.md` | **unchanged** — the canary | all |
| `CLAUDE.md`, `docs/guides/contributing.md` | how to add a code | 4 |

---

## Task 1: `coded()` — **done**

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.py`
- Modify: `packages/comeni-core/tests/test_diagnostics_registry.py`

**Interfaces:**
- Produces: `comeni_core.diagnostics.coded(code: str, message: str) -> str`, returning
  `f"{code}: {message}"` and raising `UnknownDiagnosticError` for an undeclared code.

- [x] **Step 1: Write the failing tests**

```python
def test_coded_prefixes_the_message_with_the_code():
    assert coded("MD0001", "a thing went wrong") == "MD0001: a thing went wrong"


def test_coded_refuses_an_undeclared_code():
    """The whole point. A string literal cannot be wrong about this any more."""
    with pytest.raises(UnknownDiagnosticError) as caught:
        coded("MD9999", "a thing went wrong")
    assert "MD9999" in str(caught.value)


def test_coded_refuses_a_near_miss():
    """`MD00001` is the realistic typo — a digit too many, and it reads right."""
    with pytest.raises(UnknownDiagnosticError):
        coded("MD00001", "a thing went wrong")


def test_coded_leaves_the_message_alone():
    """No wrapping, no rstrip, no reflow. A message that changes shape is a message whose
    tests start asserting the formatter instead of the text."""
    message = "line one\n  line two, indented\n"
    assert coded("MD0001", message) == f"MD0001: {message}"
```

- [x] **Step 2: Run and watch them fail**

Run: `uv run pytest packages/comeni-core/tests/test_diagnostics_registry.py -k coded -v`
Expected: FAIL, `cannot import name 'coded'`.

- [x] **Step 3: Implement it**

In `diagnostics.py`, beside `spec_for` and `explain`, which already do this lookup:

```python
def coded(code: str, message: str) -> str:
    """A message with its diagnostic code on the front, checked against the registry.

    **This is the one place a code becomes text.** Before it, seventy-eight emissions were
    string literals — `f"MD0001: {where} is not valid YAML"` — with nothing tying the code to
    `diagnostics.yml`. A typo shipped, a `raise` outliving its registry entry shipped, and both
    printed to a user while failing `mendel explain` and never appearing in the generated page.

    **A string builder rather than an exception factory**, because twelve exception types carry
    codes — `ValueError` at sixty-five, `RuleValidationError` at nineteen — and because several
    emissions are not raises at all: the CLI prints `mendel: MD0210: …` and `MD0202` is a report
    line. One function serves every site, changes no exception class, and leaves `raise` visible
    where control flow is decided.

    Checked at call time, which is the error path — weaker than import time, and not the whole
    answer. `tests/test_diagnostics_ownership.py` scans the literals, which is the half that
    runs before anything fails.
    """
    if code not in REGISTRY:
        raise UnknownDiagnosticError(
            f"{code} is not a declared diagnostic. Declare it in "
            f"comeni_core/diagnostics.yml, or fix the code.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}: {message}"
```

- [x] **Step 4: Run, watch pass, then watch the guard fail**

Remove the `if code not in REGISTRY` block; `test_coded_refuses_an_undeclared_code` and
`test_coded_refuses_a_near_miss` must both fail. Restore. Ledger row.

- [x] **Step 5: Export it**

`comeni_core/__init__.py` re-exports the package's public surface; add `coded` beside `explain`
and `spec_for` if they are listed there. If they are not, do not add it — the resolver and
compiler import from `comeni_core.diagnostics` directly.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: coded() — one place a diagnostic code becomes text"
```

---

## Task 2: every emission goes through it — **done**

> **Corrections, 2026-08-16.** Three mechanical failures, all producing syntactically plausible
> output, all caught by Step 2's "read the diff before converting the other sixteen":
>
> 1. A regex cannot do this — the messages are implicit multi-line concatenations, so the closing
>    paren belongs after the last literal. The AST knows the extent.
> 2. `ast` column offsets are UTF-8 **bytes** and these files are full of em dashes; slicing by
>    character duplicated the tail of every long message.
> 3. A `Constant` inside a `JoinedStr` matches the same test as the `JoinedStr`, so seventeen
>    messages got one replacement nested inside another.
>
> **The plan converted per file and this ran per package**, which was a deliberate trade after
> the hardest file (17 sites, multi-line) converted cleanly — three suite runs rather than
> seventeen. The corrections above were all found in that first file, so the trade held.
>
> `marks.py` takes **function-local imports**: `diagnostics.py` imports `Line` and `Text` from
> it, which the plan did not anticipate and that file's own docstring warns about.

**Files:** ~12, across three packages. Largest first, so the shape is settled before it is
repeated: `mendel_resolver/rules/validate.py` (17), `comeni_core/artifact/pipeline.py` (12),
`mendel_compiler/cli/artifact_verbs.py` (7), `comeni_core/declared/contract.py` (6),
`mendel_resolver/rules/format.py` (5), `comeni_core/spell/marks.py` (5), then the rest.

- [x] **Step 1: Record the canary before touching anything**

```bash
sha256sum docs/reference/diagnostics.md
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/before --gate lint
sha256sum /tmp/before/pipeline.yml
```

Both must be unchanged at the end. The generated page must not move at all — nothing here
changes what a code *says* — and a built pipeline must not move either, since no successful build
emits a diagnostic.

- [x] **Step 2: Convert one file and read the diff**

Start with `mendel_resolver/rules/validate.py`. Each site:

```python
-        raise RuleValidationError(f"MD0311: {path}: {name} does not cover {missing}")
+        raise RuleValidationError(coded("MD0311", f"{path}: {name} does not cover {missing}"))
```

**Read the diff before converting the other eleven.** The mechanical risk is a message that had
no space after the colon, or one where the code was mid-string; both change the output, and this
plan's constraint is that output does not change.

- [x] **Step 3: Run the suite after that one file**

Run: `uv run pytest -q -m "not slow"`
Expected: PASS. Several tests assert message text; they are the check that the conversion is
faithful.

- [x] **Step 4: Convert the remaining files, running the suite after each**

Per file, not per package: a failure after eleven files is eleven files to bisect.

- [x] **Step 5: The CLI's `mendel: ` prefix**

`artifact_verbs.py` writes `f"mendel: MD0210: {source}/modules is absent…"`. The prefix stays
outside:

```python
f"mendel: {coded('MD0210', f'{source}/modules is absent…')}"
```

- [x] **Step 6: `MD0202`, the one intended output change**

Currently `f"  MD0202  {line}"` — two spaces either side, aligned as a report. It becomes
`coded("MD0202", line)`, so `MD0202: {line}`. **A test asserts that report's shape**; find it,
update it, and say in the commit message that the format moved and why. Spec §5 predicted this.

- [x] **Step 7: Check the canary**

```bash
sha256sum docs/reference/diagnostics.md    # must equal Step 1
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/after --gate lint
diff /tmp/before/pipeline.yml /tmp/after/pipeline.yml    # must be empty
```

- [x] **Step 8: Confirm nothing was missed**

```bash
grep -rnE '["'"'"'][^"'"'"']*MD[0-9]{4}:' --include='*.py' packages/*/src | grep -v "coded(" | grep -v "code="
```

Expected: **no output**. Any line here is an emission that still writes its own code.

- [x] **Step 9: `make verify`, commit**

---

## Task 3: both directions, and `UNLOCATABLE` goes — **done**

**Files:** `tests/test_diagnostics_ownership.py`

- [x] **Step 1: Rewrite `_raising_packages` against the two real shapes**

With the conversion done there are exactly two: `coded("MD0001"` and `code="MD0100"`. The
three-pattern guess and its `UNLOCATABLE` exemption both go.

```python
EMISSION = re.compile(r"""(?:coded\(|code=)["'](MD\d{4})["']""")


def _emitted() -> dict[str, set[str]]:
    """Every code emitted anywhere, to the packages that emit it."""
    found: dict[str, set[str]] = {}
    for package, text in SOURCES:
        for match in EMISSION.finditer(text):
            found.setdefault(match.group(1), set()).add(package)
    return found
```

- [x] **Step 2: Write the two new tests**

```python
def test_every_emitted_code_is_declared():
    """Belt to `coded()`'s braces: that check runs on the error path, this one runs always."""
    undeclared = sorted(set(_emitted()) - set(REGISTRY))
    assert undeclared == [], f"emitted but not in diagnostics.yml: {undeclared}"


def test_every_declared_code_is_emitted():
    """The operator's decision, 2026-08-16. A code nothing raises is a promise in a document
    that no code keeps.

    A reserved *band* stays legal — `MD0400`–`MD0499` is a comment in `diagnostics.yml`, not an
    entry. Reserving a *code* does not, which is the change.
    """
    unemitted = sorted(set(REGISTRY) - set(_emitted()))
    assert unemitted == [], f"declared but never emitted: {unemitted}"
```

- [x] **Step 3: Delete `UNLOCATABLE` and the test that pinned it**

Both exist only because three emission shapes had to be matched by pattern. With one shape there
is nothing to exempt. Say so in the commit rather than deleting silently.

- [x] **Step 4: Run, watch pass**

Expected: PASS, with `test_every_locatable_code_is_owned_by_the_package_that_raises_it` still
green — the ownership check now reads the same `_emitted()` map.

- [x] **Step 5: Watch all three fail**

Add `coded("MD9998", "x")` to a source file → `test_every_emitted_code_is_declared` fails. Add an
entry to `diagnostics.yml` that nothing emits → `test_every_declared_code_is_emitted` fails.
Change one `emitted_by` → the ownership test fails. Three ledger rows.

- [x] **Step 6: `make verify`, commit**

---

## Task 4: how to add a code, written down — **done**

- [x] **Step 1: `docs/guides/contributing.md` gains a short section**

Four steps: declare it in `diagnostics.yml` with `emitted_by` naming the package that will raise
it; emit it through `coded()`; run `make docs`; and know that declaring without emitting fails a
test, because a code nothing raises is a promise nothing keeps.

- [x] **Step 2: `CLAUDE.md`'s diagnostics line**

It currently says the page is generated and CI checks it. Add that a code is *emitted* through
`coded()` and that both directions are tested. One or two lines; no counts.

- [x] **Step 3: Journal**

What the conversion found, whether the canary held, and the `MD0202` format change.

- [x] **Step 4: Final gate, one PR**

```bash
uv run ruff check . && make verify && make links
```

## Self-review

- **Every spec section has a task.** §3 → Task 1–2; §4 → Task 3; §5's `MD0202` note → Task 2
  Step 6; §6's exclusions respected; §7 → Task 2 Step 7 and Task 3.
- **The canary is the load-bearing check** and it is recorded *before* the first edit rather than
  compared at the end from memory — which is the mistake issue #46 made when a layer digest moved
  under a change that was supposed to be pure relocation.
- **Task 2 converts file by file with the suite in between**, because a mechanical edit across
  twelve files is exactly the change whose failure is cheapest to bisect and most tempting to
  batch.
