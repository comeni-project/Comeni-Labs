# Closing the carried findings — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` — task by task, in a
> worktree, driven by you rather than farmed to subagents (`CLAUDE.md`, *How to start
> implementing*). Steps use `- [ ]` for tracking.

**Goal:** close #48, #49, A130 and A36, so nothing carried is open when Plan 2 starts.

**Architecture:** Four independent items in dependency order. A36 first because it is small and
touches the digest, which everything else must not move. Then `MD0000`–`MD0009` at the loading
boundary. Then `ai:` and `ValueSource.MODEL`, which bump the artifact to `version: 4`. Then #48,
which is a three-condition widening of an existing check and is easiest to reason about once the
schema is settled.

**Tech Stack:** Python 3.12, pydantic v2, pytest, ruff.

**Spec:** [`notes/specs/2026-08-16-closing-the-carried-findings.md`](../specs/2026-08-16-closing-the-carried-findings.md)

## Global Constraints

- **Work in a worktree.** This plan runs in `.worktrees/close-the-issues`.
- **`make verify`, not `make check`**, closes Tasks 2, 3 and 4: all three touch files on
  `CLAUDE.md`'s named list (`comeni_core/artifact/pipeline.py`, and the resolver's load path).
- **No layer digest may move.** A36 is about `_FILE`, and the one thing that must not happen is
  changing it. Task 1 Step 1 records the digest and every task re-checks it.
- **Every guard is watched failing** and gets a ledger row. A14's condition.
- **A14 itself is out of scope**, by the operator's decision on 2026-08-16.
- **New codes are `MD0001`–`MD0009` and `MD0225`.** `MD0000` stays unallocated: the band's own
  comment reserves it and a code that is all zeroes reads like a placeholder.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `packages/comeni-core/tests/test_digest.py` | `_FILE`'s claim becomes checkable | 1 |
| `comeni_core/diagnostics.yml` | ten new entries | 2, 3 |
| `comeni_core/declared/layered.py` | `MD0001`, `MD0002`, `MD0006` | 2 |
| `comeni_core/declared/vocabulary.py` | `MD0007`, `MD0008`, `MD0009` | 2 |
| `mendel_resolver/layers.py` | `MD0003`, `MD0004`, `MD0005` | 2 |
| `tests/test_loading_diagnostics.py` | one test per code, each watched | 2 |
| `comeni_core/plan/tiers.py` | `ValueSource.MODEL` | 3 |
| `comeni_core/artifact/pipeline.py` | `AiProvenance`, `Pipeline.ai`, `MD0225`, `SCHEMA_VERSION = 4` | 3 |
| `mendel_compiler/pipeline_file.py` | `stale_reasons` widened | 4 |
| `docs/reference/pipeline-schema.md` | `ai:`, and version 4 | 3 |

---

## Task 1: `_FILE`'s claim becomes checkable — A36 — **done**

**Files:**
- Modify: `packages/comeni-core/tests/test_digest.py`

**Interfaces:**
- Produces: nothing importable. This task adds a test and changes no behaviour, which is the
  point — the digest must not move.

- [x] **Step 1: Record the layer digest, for every later task to check against**

```bash
uv run python -c "
from pathlib import Path
from comeni_core.artifact.digest import digest_of_directory
print(digest_of_directory(Path('registry')))
"
```

Expected: `sha256:6209f7e115fea05dbead941feb9ef6c85022e4fc77084766c83942199dc07040`.

Write it down. If any task moves it, that task is wrong: a layer digest is what a published
`pipeline.yml` pins, and `comeni-registry` is tagged `v0.2.0`.

- [x] **Step 2: Write the test that can fail**

The audit's option 3. `_FILE` claims to keep a second entry kind from hashing alike; there is
currently one kind, so the claim is untested. Invent the second kind *in the test*:

```python
def test_the_file_tag_separates_entry_kinds(tmp_path):
    """`_FILE` is a domain separator, and A36 is that nothing could observe it working.

    Setting it to `b""` and running the whole suite passed — 436 tests — because there is
    exactly one entry kind and a separator between one thing and nothing separates nothing.
    Its sibling `_LINK` went with the symlink branch A9 removed.

    **Deleting it was the audit's option 1 and is no longer free.** `comeni-registry` is
    published and tagged, and a layer digest is what a `pipeline.yml` pins — dropping the tag
    would move every layer digest in every existing artifact. So the tag stays and its claim
    is made checkable instead, which is the only option that turns "this line cannot be
    wrong" into "this line is tested".

    The second entry kind is invented here rather than in the code, because inventing one in
    the code to test the separator would be building a feature to justify a byte.
    """
    from comeni_core.artifact import digest as module

    payload = b"alpha"
    as_file = module.content_hash(payload)
    as_other_kind = hashlib.sha256(b"link\x00" + payload).hexdigest()
    assert as_file != as_other_kind, (
        "`_FILE` does not separate entry kinds: a second kind hashing the same bytes "
        "collides with a file, which is what the tag exists to prevent"
    )

    # And the separator is what makes the difference — not the bytes.
    assert module._FILE != b"", "the tag is empty, so it separates nothing (A36)"
    assert as_file == hashlib.sha256(module._FILE + payload).hexdigest()
```

- [x] **Step 3: Watch it fail**

Set `_FILE = b""` in `digest.py`, run `uv run pytest packages/comeni-core/tests/test_digest.py -v`.

Expected: **FAIL** on the third assertion, and on the second with *"the tag is empty, so it
separates nothing"*. Restore `_FILE`.

This is the assertion A36 says did not exist: the whole suite passed with `_FILE = b""`.

- [x] **Step 4: Confirm the digest did not move**

Re-run Step 1's command. Expected: the same digest.

- [x] **Step 5: Ledger and commit**

Add the revert to `notes/audits/guard-ledger.md`, with the note that option 1 (deletion) was
priced out by publication rather than rejected on principle.

```bash
git add -A
git commit -m "test: _FILE's domain separation is checkable now (A36)"
```

---

## Task 2: `MD0001`–`MD0009` — the loading stage refuses with a code — **done**

> **Correction, 2026-08-16.** Two of the nine tests were green on their first run, before any code
> existed. `pytest` names `tmp_path` after the test that asked for it, so a refusal quoting the
> layer path contains the literal string `MD0004`, and `assert "MD0004" in message` passed against
> a message with no code in it. A68's shape. `_refusal()` scrubs the path now, and the plan's
> Step 2 should have said so — asserting a code against a string that contains the test's own name
> is a trap this plan walked into while writing tests *for* legibility.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Modify: `comeni_core/declared/layered.py`, `comeni_core/declared/vocabulary.py`,
  `mendel_resolver/layers.py`
- Create: `tests/test_loading_diagnostics.py`

**Interfaces:**
- Consumes: `DiagnosticSpec` and `REGISTRY` from `comeni_core.diagnostics`, which validate a code
  against the registry at construction — so an undeclared code cannot be raised.
- Produces: nine codes. Later tasks do not depend on them.

- [x] **Step 1: Add a `loading` concern and the nine entries**

`diagnostics.yml` entries take `emitted_by`, `concern`, `says`, `fires_on`, `refuses`, `fix`.
Add `loading` to `HEADINGS` in `tools/generate_diagnostics_doc.py`, **first**, since it is the
first thing that happens to a build:

```python
HEADINGS: dict[str, str] = {
    "loading": "Loading declared registry data",
    "conformance": "A contract disagrees with its module",
    ...
}
```

The generator raises if a concern has no heading, so forgetting this fails rather than renders
nothing.

- [x] **Step 2: Write one failing test per code**

`tests/test_loading_diagnostics.py`. Each builds the smallest layer that produces the failure and
asserts the code and the **file name** appear:

```python
def test_MD0001_a_file_that_is_not_yaml(tmp_path):
    layer = _layer(tmp_path)
    (layer / "contracts" / "broken.yml").write_text("id: [unclosed\n")
    with pytest.raises(ValueError) as caught:
        layers.load(layer)
    assert "MD0001" in str(caught.value)
    assert "broken.yml" in str(caught.value), "a code that names only a model is the same defect"
```

Nine of these. The `assert "<name>.yml" in ...` is not decoration: issue #49's whole complaint is
that a Pydantic error names a class and a field path rather than a file.

- [x] **Step 3: Run them and watch every one fail**

Run: `uv run pytest tests/test_loading_diagnostics.py -v`
Expected: **9 failed** — six raise uncoded `ValueError`s, and `MD0001`/`MD0002` raise
`ValidationError` or `yaml.YAMLError` with no file name at all.

- [x] **Step 4: Wrap `kind.parse` for `MD0001` and `MD0002`**

In `stack()`, the per-file parse is `for entry in kind.parse(path)` and `path` is in scope — which
is the whole reason this belongs here rather than in each kind:

```python
        for path in _files(directory):
            claimed.add(path)
            try:
                parsed = list(kind.parse(path))
            except yaml.YAMLError as error:
                raise ValueError(
                    f"MD0001: {path.relative_to(layer.path)} in layer {layer.path} is not "
                    f"valid YAML.\n  {error}"
                ) from error
            except ValidationError as error:
                raise ValueError(
                    f"MD0002: {path.relative_to(layer.path)} in layer {layer.path} is not a "
                    f"valid {kind.which.value[:-1]}.\n"
                    + "\n".join(
                        f"  {'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}"
                        for e in error.errors()
                    )
                ) from error
            for entry in parsed:
```

`list(...)` before the loop, deliberately: `kind.parse` returns an `Iterable`, and a generator
would raise inside the body where `path` is still in scope but the `try` is not.

- [x] **Step 5: Give the seven existing refusals their codes**

Prefix each message. No logic changes:

| file:line | code |
|---|---|
| `layered.py` — "is declared twice/in … and in" | `MD0006` |
| `vocabulary.py` — "`add_states` … cannot carry … as well" | `MD0007` |
| `vocabulary.py` — "`add_states` for …, which no layer declares" | `MD0008` |
| `vocabulary.py` — `UnknownStateError` | `MD0009` |
| `layers.py` — "contains a symlink at" | `MD0004` |
| `layers.py` — "holds no registry data" | `MD0005` |
| `layers.py` — `_every_file_is_claimed`, "which nothing reads" | `MD0003` |

- [x] **Step 6: Run and watch all nine pass**

Run: `uv run pytest tests/test_loading_diagnostics.py -v`
Expected: **9 passed.**

- [x] **Step 7: Watch each code fail on its own subject**

For each of the nine, remove the code from the message it was added to and confirm exactly that
test fails. Nine reverts, nine ledger rows. This is the step that takes the longest and is the
reason the task exists as its own task.

- [x] **Step 8: Regenerate the docs and check the digest**

```bash
make docs && make links
uv run python -c "
from pathlib import Path
from comeni_core.artifact.digest import digest_of_directory
print(digest_of_directory(Path('registry')))
"
```

Expected: `docs/reference/diagnostics.md` gains a *Loading declared registry data* section
**first**, and the digest is unchanged from Task 1 Step 1.

- [x] **Step 9: `make verify`, then commit**

```bash
git add -A
git commit -m "feat: loading declared data refuses with a code (#49)"
```

---

## Task 3: `ai:` and `ValueSource.MODEL` — A130 — **done**

**Files:**
- Modify: `comeni_core/plan/tiers.py`, `comeni_core/artifact/pipeline.py`,
  `comeni_core/diagnostics.yml`, `docs/reference/pipeline-schema.md`
- Create: `tests/test_ai_provenance.py`

**Interfaces:**
- Produces: `ValueSource.MODEL`; `AiProvenance(available: list[AiPoint], used: list[AiPoint])`;
  `Pipeline.ai: AiProvenance`; `SCHEMA_VERSION = 4`; `MD0225`.

- [x] **Step 1: Write the failing tests**

`tests/test_ai_provenance.py`:

```python
def test_a_build_states_that_no_model_was_consulted():
    """A130 — the artifact could not say this, and absence is not a statement.

    `source: resolver` on every value is the resolver's claim about itself; round three
    recorded that a resolver can set it untruthfully. What a reader can rely on is a fact
    about the *build*: nothing was wired to a model, so nothing could have been consulted.
    """
    pipeline = _build()
    assert pipeline.ai.available == []
    assert pipeline.ai.used == []


def test_MD0225_a_value_cannot_claim_a_model_that_was_not_available(tmp_path):
    """The checkable half of A130. The other half is not checkable and is documented."""
    raw = yaml.safe_load(_built_pipeline_text())
    raw["steps"][0]["why"]["source"] = "model"
    with pytest.raises(ValidationError) as caught:
        Pipeline.model_validate(raw)
    assert "MD0225" in str(caught.value)


def test_a_version_3_file_is_not_read_as_no_model_consulted():
    """Absence and emptiness differ — the lesson `for_value` taught in #48.

    A v3 file was written before the question existed. It must not load as a positive
    statement that no model was consulted, because nobody made that statement.
    """
    raw = yaml.safe_load(_built_pipeline_text())
    raw["version"] = 3
    del raw["ai"]
    pipeline = Pipeline.model_validate(raw)
    assert pipeline.ai.available is None, "a v3 file states nothing about models"
```

Note the third: `available` is `list | None`, not `list`. `None` is *"this file predates the
question"*; `[]` is *"nothing was wired"*. Collapsing them is exactly the defect #48 is about,
one field over.

- [x] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_ai_provenance.py -v`
Expected: FAIL — `Pipeline` has no `ai`.

- [x] **Step 3: Add `ValueSource.MODEL`**

In `comeni_core/plan/tiers.py`, beside `HUMAN` and `MEASURED`:

```python
    MODEL = "model"
    """A model answered an ambiguity the deterministic ladder could not settle.

    Distinct from `HUMAN` for the reason `HUMAN` is distinct from `GOAL`: who settled it is
    what a reviewer needs, and the three answers oblige different amounts of trust.

    **Nothing writes this until Plan 2**, and it is declared now rather than then so a model
    adapter has somewhere truthful to write on the day it exists — rather than the enum
    arriving alongside the first thing that needs it, which is when a shortcut gets taken.

    **It is a claim, not a proof.** A resolver sets its own `source`, and an adapter that
    writes `resolver` here is indistinguishable from the deterministic ladder. Same standing
    as `confidence` and `reason`. What *is* provable is the negative, and that lives on
    `Pipeline.ai` — see `AiProvenance`.
    """
```

- [x] **Step 4: Add `AiProvenance` and `Pipeline.ai`**

```python
class AiPoint(StrEnum):
    """The three declared runtime AI points. Invariant 3 says there are exactly these."""

    PROMPT = "prompt"
    """Prompt → goal extraction. The user corrects the result before anything runs."""
    TIER_4 = "tier-4"
    """Resolution of an ambiguity the ladder could not settle. Always flagged."""
    REPAIR = "repair"
    """Compiler repair, bounded to three attempts."""


class AiProvenance(BaseModel):
    """What could have been consulted for this build, and what was.

    **`available` is the field that makes "no model" mean something.** `used` is derivable
    from the decisions; `available` is a fact about how the build was configured, and it is
    the one a reader cannot get any other way. Both empty is a positive statement: nothing
    was wired to a model, so nothing could have been consulted.

    **`None` is not `[]`.** `None` means the file predates the question — a `version: 3`
    artifact, written when nothing asked. `[]` means somebody looked and there was nothing.
    Reading the first as the second would be inventing a statement nobody made, which is
    `MD0223`'s lesson one field over.

    **The limit, stated here rather than implied.** This proves the negative and not the
    positive: a build with an adapter configured *will* say so, but a model-backed build
    whose adapter writes `source: resolver` on every value is indistinguishable from a
    deterministic one. A130 closes in the direction that can be checked. The other direction
    needs the adapter to be honest, and no field can make it so.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: list[AiPoint] | None = None
    used: list[AiPoint] | None = None
```

On `Pipeline`, beside `registry`:

```python
    ai: AiProvenance = Field(default_factory=AiProvenance)
    """Which of the three declared AI points were reachable, and which answered. A130."""
```

- [x] **Step 5: `MD0225` on the model validator**

In `_readable_and_unambiguous`, after the `MD0212` block:

```python
        if self.ai.available == []:
            claimed = sorted(
                f"{step.id}.{setting.name}"
                for step in self.steps
                for setting in step.settings
                if setting.why.source is ValueSource.MODEL
            )
            if claimed:
                raise ValueError(
                    f"MD0225: {', '.join(claimed)} claim a model settled them, and this "
                    "build records that no AI point was available. One of the two is "
                    "false. `ai.available: []` means nothing was wired to a model."
                )
```

`== []` and not falsy: `None` must not trigger it, because a v3 file makes no claim either way.

- [x] **Step 6: `SCHEMA_VERSION = 4`, and set `ai` where the build writes it**

`Pipeline.of` records `available=[]` — through Plan 1 nothing is wired — and `used=[]`. A comment
must say the empty list is a measurement rather than a placeholder, or the next reader will
"fix" it to a default.

- [x] **Step 7: Run, watch pass, then watch each guard fail**

Three reverts: drop the `MD0225` block; change `available: list | None = None` to `= []`
(which makes the v3 test fail, since absence becomes a statement); change `== []` to `not
self.ai.available` (which makes the v3 file refuse). Three ledger rows.

- [x] **Step 8: Document `ai:` in the schema reference**

`docs/reference/pipeline-schema.md` gains an `ai:` section and its version bumps to 4. It must
carry §3.3's limitation in the reader-facing words, not only in the docstring — the schema page
is what a stranger opens.

- [x] **Step 9: `make verify`, digest check, commit**

```bash
git add -A
git commit -m "feat: the artifact can state that no model was consulted (A130)"
```

---

## Task 4: `MD0223` sees an answered tier-4 setting — #48 — **done**

> **Correction, 2026-08-16.** Two existing tests refused after the fix and the plan did not
> predict either. Both were completing their own premise rather than absorbing a regression:
> `test_human_source_with_a_matching_override_is_accepted` claimed *"the value, the `human`
> source and the decision's override all agree — the record proves it"* while leaving
> `why.reason` reading *"no rule covered … please review"*, and `_with_override` in
> `test_upgrade.py` claimed to answer *"the way a reviewer would"* and answered half. Issue #48
> was written as a docstring in this repository a plan and a half before anyone filed it.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/pipeline_file.py`
- Modify: `tests/test_pipeline_file.py`

**Interfaces:**
- Consumes: `Pipeline` at `version: 4` from Task 3.
- Produces: a widened `stale_reasons(pipeline) -> list[str]`. Signature unchanged.

- [x] **Step 1: Write the failing test**

```python
def test_MD0223_sees_a_tier_four_setting_answered_by_hand(tmp_path):
    """#48 — the one case a human is most likely to be editing was the one case it missed.

    `stale_reasons` skipped every setting whose `for_value` is `None`, because a pre-1.14
    file has no such field and "absence is not disagreement". A tier-4 value nothing
    resolved *also* has `for_value: null`.
    """
    pipeline = _answered_tier_four()  # human_override set, value set, why.reason untouched
    stale = stale_reasons(pipeline)
    assert any("seq_platform" in line for line in stale)
    assert any("override_reason" in line for line in stale), "say what to write, not just that it is wrong"


def test_an_unanswered_tier_four_setting_is_not_flagged():
    """`please review` is what an *open* question is supposed to say. Flagging it would make
    the check a nag, and a nag is a check people stop reading."""
    assert stale_reasons(_built()) == []
```

- [x] **Step 2: Run and watch the first fail, the second pass**

Run: `uv run pytest tests/test_pipeline_file.py -k MD0223 -v`
Expected: the first FAILS, the second PASSES. The second passing *now* is what proves the
widening does not simply flag everything.

- [x] **Step 3: Widen the check**

```python
    answered = {
        decision.key
        for decision in pipeline.decisions
        if decision.human_override is not None
    }
    return [
        ...
        for step in pipeline.steps
        for setting in step.settings
        if (
            setting.why.for_value is not None and setting.why.for_value != setting.value
        ) or (
            # #48 — a tier-4 value nothing resolved has `for_value: None`, which is
            # indistinguishable from a pre-1.14 field by shape alone. Three conditions,
            # because only all three together mean "a human answered this and left the
            # resolver's reason standing": no recorded value, tier 4, and an override.
            setting.why.for_value is None
            and setting.why.tier is Tier.AMBIGUOUS
            and f"{step.id}.{setting.name}" in answered
        )
    ]
```

- [x] **Step 4: Run and watch both pass**

- [x] **Step 5: Watch the widening fail on its subject**

Drop the third condition (`in answered`) and confirm
`test_an_unanswered_tier_four_setting_is_not_flagged` fails — that is the condition that keeps it
from being a nag. Then drop the whole second clause and confirm the first test fails. Two ledger
rows.

- [x] **Step 6: Reproduce the original report end to end**

The issue was found by hand in `docs/guides/driving-mendel.md` §6. Redo it:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/i48 --gate lint
# set human_override + override_reason in decisions:, and value: on the setting
uv run mendel emit /tmp/i48/pipeline.yml --out /tmp/i48
```

Expected: `MD0223` now fires and names `override_reason`. **Then update §6 of the guide**, which
currently documents the defect as a rough edge — it says the reason "stays stale until the next
`upgrade`", and that will no longer be true.

- [x] **Step 7: `make verify`, digest check, commit**

```bash
git add -A
git commit -m "fix: MD0223 sees a tier-4 setting answered by hand (#48)"
```

---

## Task 5: closing out — **done**

- [x] **Step 1: Journal entry**

`notes/journal/2026-08-16-evening.md` gains a third section. What it must carry: the layer digest
unmoved through all four tasks; what each revert found; and whether anything here should have been
caught earlier.

- [x] **Step 2: `CLAUDE.md`'s two stale claims**

Found while surveying, and unrelated to these four — fix them here rather than leaving them:

- *"Fifteen round-four findings are carried as issues"* naming `#26` and `#32` as must-reads. All
  thirteen (#24–#36) closed on 2026-08-15, and the table three lines below says so, so the file
  contradicts itself.
- The issue table has no rows for **#43, #46, #49**.

- [x] **Step 3: Final gate**

Run: `uv run ruff check . && make verify && make links`

- [x] **Step 4: One PR, closing #48 and #49**

A36 and A130 have no issues; the PR body records them, and `CLAUDE.md`'s *What is open* section
loses both.

## Self-review

Checked against the spec, 2026-08-16:

- **Every spec section has a task.** §1 → Task 4; §2 → Task 2; §3 → Task 3; §4 → Task 1; §5's
  exclusions are respected — no `ProfilePolicy`, no attestation, A14 untouched.
- **One thing the spec did not settle, decided here:** `AiProvenance.available` is
  `list | None`, not `list`. The spec said absence and emptiness differ and did not say how; a
  nullable list is how, and Task 3 Step 1's third test is what holds it.
- **Task order is not arbitrary.** A36 first because it is the one task that must move no digest
  and the others must not either — establishing the digest as a checked constant before anything
  else changes is cheaper than diagnosing a moved digest three tasks later, which is the mistake
  issue #46 made.
- **`MD0000` is deliberately unallocated.** A code of all zeroes reads as a placeholder, and the
  band's own comment already reserves the range rather than the number.
