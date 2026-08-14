# Plan 1.13 — closing the design audit's correctness findings

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task, driven yourself, sequentially. Subagents are for review and design only —
> that is the operator's instruction in `CLAUDE.md`, not a suggestion. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Fix the five design-audit findings that produce wrong output or block Plan 2, without
changing the `pipeline.yml` schema version.

**Architecture:** Five independent repairs across three packages. Each makes something the design
*guessed* into something a contract or a caller must *declare*, and each is guarded by a test that
was watched failing. No new dependency, no network, no AI. The `pipeline.yml` `version:` stays `1`
— every schema addition is deferred to Plan 1.14 so that this plan can ship without invalidating
an archived pipeline.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, Nextflow 25.10.4, pytest, `uv`.

**Spec:** [`docs/internal/audits/2026-08-14-design-audit.md`](../audits/2026-08-14-design-audit.md)
— roots 4, 6, 5 and 7. The four stream reports beside it carry each finding's full demonstration,
and `.audit-artifacts/` holds the probe layers that reproduce them.

## Global Constraints

- **Python floor is 3.12.12 exactly**; CI runs 3.12 and 3.13.
- **`comeni-core`, `mendel-resolver` and `mendel-compiler` do not reach the network.** No new
  import in those three packages may be a transport, `ctypes`, `subprocess`, or a dynamic import
  form. `tests/test_purity.py` and `tests/test_purity_runtime.py` enforce it.
- **Line length 100.** `uv run ruff check .` must be clean. `ruff format` is *not* a gate — do not
  run a formatting sweep.
- **`make check` is not verification for this plan.** Every task here touches at least one of
  `resolve.py`, `router.py`, `rules.py`, `mendel_compiler/cli.py`, `mendel_compiler/emit.py` or
  `comeni_core/pipeline.py`. **Run `make verify`** at every task's verification step — it is
  `check` + `tests/test_counts.py` + the guards + registry drift, and takes about two minutes.
- **A code is never renumbered.** New diagnostics take the next free number in their band:
  `MD0300`–`MD0399` is routing and resolution and is **empty today**; `MD0223` is the next free
  pipeline-file code. Every new code needs an entry in
  `packages/comeni-core/src/comeni_core/diagnostics.yml` and `make docs` regenerated, which CI
  checks.
- **`pipeline.yml` `version:` stays `1` for the whole of this plan.** If a task appears to need a
  schema field, it belongs in Plan 1.14 — stop and say so rather than bumping.
- **Byte-identical emission is a hard requirement.** Anything that serialises a set needs a
  `field_serializer` that sorts, as `IREdge.states` has.
- **Read process names and containers out of `vendor/modules/**/main.nf`, never out of this plan.**

---

## Task 1: A92 — a channel join must be declared, not guessed

**The defect.** `emit._argument()` joins two ports sharing one channel with `.combine()`, a
Cartesian product. Two samples in gives four processes, half of them pairing one sample's data
with another's, exit 0, no warning. The shipped spine is accidentally safe because its second port
is a single reference file (`N × 1 = N`). `--gate test` cannot see this class at all: the nf-core
RNA-seq test dataset has one sample, so `1 × 1 = 1`.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/routes.py` — add the `Join` enum
- Modify: `packages/comeni-core/src/comeni_core/contract.py:176-224` — `NfInput.join`
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py:161-174` — `CallArg.join`
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` — carry `join` at materialisation
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py:97-109` — `_argument`
- Modify: `registry/contracts/nf-core/subread-featurecounts.yml` — declare `join: broadcast`
- Test: `tests/test_runnable.py` (declaration is required), `tests/test_join.py` (new, the run)

**Interfaces:**
- Consumes: `NfInput.ports: list[str]`, `CallArg.ports: list[PortName]`, `emit._port_expression`.
- Produces: `comeni_core.routes.Join` (`BROADCAST` / `BY_SAMPLE`), `NfInput.join: Join | None`,
  `CallArg.join: Join | None`. Task 2 and later do not depend on these.

- [ ] **Step 1: Write the failing test for the declaration requirement**

Add to `tests/test_runnable.py`:

```python
def test_two_ports_in_one_channel_must_declare_a_join():
    """A cross product where a per-sample join belongs is a wrong result from a green run.

    Audit A92: two samples in, four processes out, half of them pairing sample 1's data with
    sample 2's. Nextflow reports success. `--gate test` cannot catch it because the nf-core
    test dataset has one sample.
    """
    with pytest.raises(ValidationError, match="two or more ports"):
        NfInput(ports=["bam", "annotation"])


def test_one_port_needs_no_join():
    assert NfInput(ports=["bam"]).join is None
```

`NfInput` and `ValidationError` are already imported in that file; add
`from comeni_core.contract import NfInput` if the import is not present.

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_runnable.py -k join -v`
Expected: FAIL — `DID NOT RAISE` on the first test, `AttributeError: 'NfInput' object has no
attribute 'join'` on the second.

- [ ] **Step 3: Add the `Join` enum**

In `packages/comeni-core/src/comeni_core/routes.py`, beside `Via`:

```python
class Join(StrEnum):
    """How two channels filling one process input are matched.

    Closed for the same reason `Via` is: each member needs its own line in the emitter.

    There is no default, and that is the finding. `emit` combined unconditionally, which is
    correct only while the second channel carries one reference file for every sample —
    true of the shipped spine and false of BAM + BAI, tumour + matched normal, or reads plus
    a per-sample adapter file. Audit A92.
    """

    BROADCAST = "broadcast"
    """`.combine()` — the second channel is one thing every sample is paired against."""
    BY_SAMPLE = "by_sample"
    """`.join()` — both channels are per-sample and match on the meta map's first element."""
```

- [ ] **Step 4: Require it on `NfInput`**

In `packages/comeni-core/src/comeni_core/contract.py`, add the field after `ports` and a
validator after `empty`:

```python
    join: Join | None = None
    """How this entry's ports are matched when there is more than one. Audit A92."""

    @model_validator(mode="after")
    def _join_declared_when_it_matters(self) -> "NfInput":
        if len(self.ports) > 1 and self.join is None:
            raise ValueError(
                f"nf_inputs entry with two or more ports ({', '.join(self.ports)}) must "
                f"declare `join:` — `broadcast` if the later ports are one reference for "
                f"every sample, `by_sample` if they are per-sample and must match. There is "
                f"no safe default: guessing `broadcast` cross-products two per-sample "
                f"channels and Nextflow reports success."
            )
        return self
```

Import `Join` from `.routes` and `model_validator` from `pydantic` at the top of the file if
either is absent.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_runnable.py -k join -v`
Expected: PASS, 2 passed.

- [ ] **Step 6: Declare the join on the one shipped contract that needs it**

`registry/contracts/nf-core/subread-featurecounts.yml` — the annotation is one GTF for every
sample, so this is `broadcast` and saying so is the point:

```yaml
# The GTF is one annotation for every sample, so a cross product is what is wanted here and
# `broadcast` says so out loud. Audit A92: this was the emitter's unconditional default, which
# is correct here and silently wrong for any second per-sample port.
nf_inputs: [{ports: [bam, annotation], join: broadcast}]
```

Read the file first — the existing `nf_inputs` line is the one to edit, not a new one to add.

- [ ] **Step 7: Verify the registry still loads and the spine still builds**

Run: `uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/j --gate lint`
Expected: `5 modules, 1 requiring review`, `gate lint: PASS`, and
`SUBREAD_FEATURECOUNTS(SAMTOOLS_SORT.out.bam.combine(ch_annotation_gtf.map { it[1] }))`
unchanged in `/tmp/j/main.nf`.

- [ ] **Step 8: Commit the declaration half**

```bash
git add packages/comeni-core/src/comeni_core/routes.py \
        packages/comeni-core/src/comeni_core/contract.py \
        registry/contracts/nf-core/subread-featurecounts.yml tests/test_runnable.py
git commit -m "feat(core): a multi-port nf_input must declare its join (A92)"
```

- [ ] **Step 9: Write the failing test for the emitted Groovy**

Create `tests/test_join.py`:

```python
"""A92 — two ports in one channel are matched by a declared rule, not by a guess.

The audit built `PAIRUP`, gave it two per-sample channels, and got four processes for two
samples with two of them pairing one sample's data with another's. Nextflow exited 0. This
file is the guard for that, and the run at the bottom is the half that would have caught it.
"""

import pathlib
import subprocess

import pytest
from comeni_core.pipeline import CallArg
from comeni_core.routes import Join
from mendel_compiler.emit import _argument


def test_by_sample_emits_join(spine_pipeline):
    step = spine_pipeline.steps[-1]
    arg = CallArg(ports=["bam", "annotation"], join=Join.BY_SAMPLE)
    rendered = _argument(spine_pipeline, step, arg)
    assert ".join(" in rendered
    assert ".combine(" not in rendered


def test_broadcast_emits_combine(spine_pipeline):
    step = spine_pipeline.steps[-1]
    arg = CallArg(ports=["bam", "annotation"], join=Join.BROADCAST)
    rendered = _argument(spine_pipeline, step, arg)
    assert ".combine(" in rendered
```

`spine_pipeline` is a fixture returning a built `Pipeline`; add it to `tests/conftest.py` if it
does not exist, reading `build/pipeline.yml` from a `mendel build` in a `tmp_path`. Copy the
construction from `tests/test_pipeline_file.py`, which already builds and parses one back.

- [ ] **Step 10: Run it to make sure it fails**

Run: `uv run pytest tests/test_join.py -v`
Expected: FAIL — `TypeError: CallArg() got an unexpected keyword argument 'join'`.

- [ ] **Step 11: Carry `join` onto `CallArg` and through materialisation**

In `packages/comeni-core/src/comeni_core/pipeline.py`, `CallArg`:

```python
    join: Join | None = None
    """How `ports` are matched. Mirrors `NfInput.join`; see audit A92."""
```

Find where `CallArg` is built from `NfInput` during materialisation (search for `empty_width=`)
and add `join=entry.join` beside it. The artifact must carry the fact, because `mendel emit` runs
with no registry and cannot ask the contract.

- [ ] **Step 12: Emit the declared join**

Replace the tail of `emit._argument` (`emit.py:105-109`):

```python
    # Several semantic ports share one channel — featurecounts wants
    # tuple(meta, bams, annotation). The contract says how they are matched: `.combine()`
    # broadcasts one reference across every sample, `.join()` pairs per-sample channels on
    # the meta map. Guessing `combine` cross-produced two per-sample channels and Nextflow
    # called it success. Audit A92.
    head, *rest = expressions
    if arg.join is Join.BY_SAMPLE:
        joined = "".join(f".join({expr})" for expr in rest)
    else:
        joined = "".join(f".combine({expr}.map {{ it[1] }})" for expr in rest)
    return f"{head}{joined}"
```

Import `Join` from `comeni_core.routes` at the top of `emit.py`.

- [ ] **Step 13: Run the tests to verify they pass**

Run: `uv run pytest tests/test_join.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 14: Write the run that proves it — the two-sample fixture**

Append to `tests/test_join.py`. This is the test the v1 criterion cannot provide, and it needs no
Docker: a local-executor process with no container.

```python
MODULE = """process PAIRUP {
    input:
    tuple val(meta), path(a), path(b)

    output:
    path "*.paired.txt", emit: paired

    script:
    \"\"\"
    echo "A=${a} B=${b}" > ${a.baseName}__${b.baseName}.paired.txt
    \"\"\"
}
"""

WORKFLOW = """nextflow.enable.dsl = 2
include {{ PAIRUP }} from './pairup.nf'
workflow {{
    ch_a = Channel.fromPath(params.a).map {{ f -> [ [id: f.baseName.split('\\\\.')[0]], f ] }}
    ch_b = Channel.fromPath(params.b).map {{ f -> [ [id: f.baseName.split('\\\\.')[0]], f ] }}
    PAIRUP({expression})
}}
"""


@pytest.mark.slow
@pytest.mark.parametrize(
    "expression,expected",
    [("ch_a.join(ch_b)", 2), ("ch_a.combine(ch_b.map { it[1] })", 4)],
)
def test_two_samples_join_pairwise_and_combine_cross_products(tmp_path, expression, expected):
    """Two samples in. `join` gives two analyses; `combine` gives four, and two are wrong.

    The `combine` half is not a bug being asserted — it is the evidence that the two branches
    differ, so a future change collapsing them back into one fails here instead of in a
    laboratory. Audit A92.
    """
    for name in ("s1.a", "s1.b", "s2.a", "s2.b"):
        (tmp_path / f"{name}.tsv").write_text(f"{name}\n")
    (tmp_path / "pairup.nf").write_text(MODULE)
    (tmp_path / "main.nf").write_text(WORKFLOW.format(expression=expression))

    subprocess.run(
        ["nextflow", "run", "main.nf",
         "--a", str(tmp_path / "*.a.tsv"), "--b", str(tmp_path / "*.b.tsv")],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    produced = sorted(p.name for p in tmp_path.glob("work/*/*/*.paired.txt"))
    assert len(produced) == expected
    if expected == 2:
        assert produced == ["s1.a__s1.b.paired.txt", "s2.a__s2.b.paired.txt"]
    else:
        assert "s1.a__s2.b.paired.txt" in produced
```

- [ ] **Step 15: Run it and read the output**

Run: `uv run pytest tests/test_join.py -m slow -v`
Expected: PASS, 2 passed. If the `join` branch produces 4, the emitter is still combining; if it
produces 2 but with the wrong names, the meta key derivation in the fixture is wrong, not the
emitter.

- [ ] **Step 16: Watch the guard fail, and record it**

Revert Step 12's `if arg.join is Join.BY_SAMPLE:` branch so both cases combine, run
`uv run pytest tests/test_join.py -m slow -v`, and confirm it fails with `assert 4 == 2`. Restore
the branch. Then append a row to `docs/internal/audits/guard-ledger.md` naming the guard, what
was reverted, and the message seen — this is A14's closure condition and the ledger is the only
thing that counts it.

- [ ] **Step 17: Verify and commit**

Run: `make verify`
Expected: exit 0.

```bash
git add packages/comeni-core/src/comeni_core/pipeline.py \
        packages/mendel-compiler/src/mendel_compiler/emit.py \
        tests/test_join.py tests/conftest.py docs/internal/audits/guard-ledger.md
git commit -m "fix(compiler): emit a declared join instead of an unconditional cross product (A92)"
```

---

## Task 2: A125 — a tie is answered from the candidates that tied

**The defect.** `_choose` ranks candidates by `(surplus, -priority, id)`, uses the ranking to
*detect* a tie, then hands the resolver **every** candidate sorted alphabetically. `FlagOnlyResolver`
returns `candidates[0]`. Reproduced: adding one `minimap2` contract at `priority: 10` — tying STAR,
also 10 — made the build select **HISAT2** at `priority: 0`, the contract the registry ranked last
and which was not part of the tie. The artifact then reports that nothing distinguishes three
contracts that `priority` distinguishes deliberately.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py:316-321` and the `chosen=` line
- Test: `tests/test_registry_layer.py`

**Interfaces:**
- Consumes: `_choose`'s local `rank()` and `ordered`, unchanged.
- Produces: no new symbol. `ProducerAsked.candidates` narrows from all candidates to the tied ones.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_registry_layer.py`:

```python
def test_a_tie_offers_only_the_candidates_that_tied(tmp_path, spine_registry):
    """Adding a contract must not install one that lost. Audit A125.

    Three producers of `alignment.bam`: STAR and MINIMAP2 at priority 10, HISAT2 at 0. The tie
    is between the first two. Handing the resolver all three sorted by id makes `hisat2` win on
    the letter h.
    """
    plan = route_goal(goal_wanting("alignment.bam"), spine_registry_with_minimap2(tmp_path))
    asked = [d for d in plan.decisions if d.subject == "producer:alignment.bam"]
    assert len(asked) == 1
    assert asked[0].candidates == [
        "nf-core/minimap2/align@2.28.0",
        "nf-core/star/align@1.11.0",
    ]
    assert "hisat2" not in asked[0].chosen
```

**Hand-write the fixture inline** — do not reach for `.audit-artifacts/`, which is untracked and
may be pruned. A layer is a directory, so build the smallest one that ties:

```python
MINIMAP2 = """id: nf-core/minimap2/align@2.28.0
nf_process: MINIMAP2_ALIGN
priority: 10          # deliberately equal to STAR's, which is what makes this a tie
consumes: [{type_id: fastq.reads}]
produces: [{name: bam, type_id: alignment.bam}]
"""


def _tying_layer(tmp_path: pathlib.Path) -> pathlib.Path:
    """One contract at STAR's priority, so `alignment.bam` has a genuine two-way tie.

    Inline rather than a committed fixture: the finding is about *ranking*, so the only thing
    that must be true of this contract is its priority, and a reader should not have to open a
    second file to see that. Audit A125.
    """
    layer = tmp_path / "tie-layer"
    (layer / "contracts" / "nf-core").mkdir(parents=True)
    (layer / "contracts" / "nf-core" / "minimap2-align.yml").write_text(MINIMAP2)
    (layer / "registry.yml").write_text("name: tie-layer\nversion: 0\n")
    return layer
```

Read a shipped contract before writing `MINIMAP2` — the fields above are the ones the finding
needs, not necessarily every field `ModuleContract` requires, and a contract that fails to load
will look like the test failing for the right reason when it is failing for the wrong one. Pass
the layer through `mendel_resolver.layers.load()`, which takes **layer roots**, never a
`contracts/` directory.

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_registry_layer.py -k tied -v`
Expected: FAIL — `candidates` holds all three ids and `chosen` is the HISAT2 contract.

- [ ] **Step 3: Offer only the tied candidates**

In `router.py`, replace the `ambiguity = ProducerAsked(...)` construction and the `chosen =` line
that follows it:

```python
    # Only the candidates that actually tied. `ordered` is every candidate ranked by
    # (surplus, -priority, id); handing all of them to a resolver that takes `candidates[0]`
    # let a contract the registry ranked *last* win on alphabetical order, and the artifact
    # then said "nothing distinguishes" three contracts that priority distinguishes
    # deliberately. Audit A125.
    tied = [contract for contract in ordered if rank(contract)[:2] == best[:2]]
    ambiguity = ProducerAsked(
        node_id=_node_id(tied[0]),
        subject=f"producer:{type_id}",
        candidates=sorted(contract.id for contract in tied),
        states=sorted(states),
    )
    resolution = resolver.resolve(ambiguity)
    chosen = next((c for c in tied if c.id == resolution.chosen), tied[0])
```

Leave the existing comment block below `resolution` — it records A8 and is still true.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_registry_layer.py -k tied -v`
Expected: PASS.

- [ ] **Step 5: Verify nothing else moved**

Run: `make verify`
Expected: exit 0. The shipped spine has one producer per type, so no golden file should change.
**If a golden `.nf` moved, stop** — that means a build was resolving a tie whose membership just
changed, which is a finding rather than a rebase.

- [ ] **Step 6: Watch the guard fail, and record it**

Revert Step 3's `tied` filter to `ordered`, confirm the test fails, restore it, and append the
row to `docs/internal/audits/guard-ledger.md`.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/router.py \
        tests/test_registry_layer.py docs/internal/audits/guard-ledger.md
git commit -m "fix(resolver): a producer tie offers only the candidates that tied (A125)"
```

---

## Task 3: A126 — a producer decision is keyed on what is decided

**The defect.** `Ambiguity.key()` is `f"{node_id}.{subject}"`, and `ProducerAsked.node_id` is the
*winning* candidate's process name. Install one more contract and the key changes, so a curator's
recorded override is reported `ORPHANED — your edit no longer applies to anything` while the
identical question is asked one line above under the new name. Reproduced: a decision recorded as
`minimap2_align.producer:alignment.bam` whose `chosen` is a HISAT2 contract — the key names a
module that is not in the pipeline.

**This task changes the recorded key format**, so it must also keep archived pipelines replayable.
That compatibility step is not optional: without it, every existing `pipeline.yml` reports its
producer override orphaned on the first `upgrade`.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/decision.py:70-72` — `ProducerAsked.key()`
- Modify: `packages/mendel-resolver/src/mendel_resolver/replay.py` — accept the legacy key
- Test: `tests/test_upgrade.py`

**Interfaces:**
- Consumes: `Ambiguity.key()`, `ProducerDecision.key`.
- Produces: `ProducerAsked.key()` returns `subject` alone — `producer:alignment.bam`, not
  `star_align.producer:alignment.bam`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_upgrade.py`:

```python
def test_a_producer_override_survives_a_new_contract(tmp_path):
    """A recorded human answer must not be orphaned by installing an unrelated contract.

    Audit A126: the decision key was the winning candidate's node id, so adding a contract
    renamed the question. `upgrade` reported ORPHANED and asked the same question again under
    the new name, having replayed nothing.
    """
    built = build_spine(tmp_path / "base")
    override_producer(built, "producer:alignment.bam", "nf-core/star/align@1.11.0")

    result = upgrade(built, registries=[REGISTRY, minimap2_layer(tmp_path)])

    assert result.orphaned == []
    assert result.replayed == 1


def test_a_producer_decision_key_names_the_question_not_the_winner(tmp_path):
    pipeline = build_spine(tmp_path / "keys")
    keys = [d.key for d in pipeline.decisions if d.subject.startswith("producer:")]
    assert all("." not in key.split(":")[0] for key in keys), keys
```

Reuse this file's existing `build_spine`/`upgrade` helpers rather than writing new ones; read the
top of the file first.

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_upgrade.py -k producer -v`
Expected: FAIL — `orphaned` holds one entry and `replayed` is 0.

- [ ] **Step 3: Key a producer question on the question**

In `packages/comeni-core/src/comeni_core/decision.py`, on `ProducerAsked`:

```python
    def key(self) -> str:
        """What is being decided, never who won it.

        `Ambiguity.key()` is `node_id.subject`, and a producer question's `node_id` is the
        winning candidate's process name — so installing one more contract renamed the
        question, and `upgrade` reported a curator's recorded override as ORPHANED while
        asking the identical question one line above under the new name. `subject` is already
        `producer:<type_id>`, which identifies the question uniquely within a pipeline
        because a contract appears at most once (A97). Audit A126.
        """
        return self.subject
```

`ParamAsked` and `SourceAsked` keep the inherited `node_id.subject` — a parameter question is
genuinely per-step, and two steps may ask about the same parameter name.

- [ ] **Step 4: Accept the legacy key when replaying**

In `replay.py`, where a recorded decision is looked up by key, match the new key *or* the
pre-1.13 form:

```python
def _matches(record_key: str, asked: Ambiguity) -> bool:
    """A pre-1.13 producer key carried the winning module's node id in front. A72-era
    artifacts are still valid files and must still replay; A126 is what made the prefix
    meaningless, not what made those files unreadable.
    """
    if record_key == asked.key():
        return True
    return asked.key().startswith("producer:") and record_key.endswith(f".{asked.key()}")
```

Route the existing lookup through `_matches`. Read the surrounding function first — the lookup is
a dict access today and becomes a scan, which is fine at these sizes and must not change
ordering.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_upgrade.py -k producer -v`
Expected: PASS, 2 passed.

- [ ] **Step 6: Verify against a pipeline built before this change**

Run:
```bash
git stash && uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ \
  --out /tmp/legacy --gate lint && git stash pop
uv run mendel upgrade /tmp/legacy/pipeline.yml --registry registry/ --dry-run
```
Expected: no `ORPHANED` line. This is the compatibility claim tested against a file this code did
not write, which is the only way it means anything.

- [ ] **Step 7: Verify, watch the guard fail, record it, and commit**

Run: `make verify` — expected exit 0. Then revert Step 3's `key()` override, confirm
`test_a_producer_override_survives_a_new_contract` fails, restore it, and append the ledger row.

```bash
git add packages/comeni-core/src/comeni_core/decision.py \
        packages/mendel-resolver/src/mendel_resolver/replay.py \
        tests/test_upgrade.py docs/internal/audits/guard-ledger.md
git commit -m "fix(core): key a producer decision on the question, not the winner (A126)"
```

---

## Task 4: A118 — a computed `then` is refused at load

**The defect.** `DecisionRow.then` is a `ParamValue` and reaches the resolver verbatim. Nothing
validates it against the parameter it decides. `then: "read_length-1"` loads, resolves at **tier
3**, cites Dobin et al. 2013, is absent from the review list, and reaches
`nextflow.config` as `ext.args2 = '--sjdbOverhang read_length-1'`. STAR receives the literal
string. The only thing that ever refuses this is `MD0201`, a *shell-injection character class*
that permits `-`, and it covers one of three routes — `via: directive` is unchecked.

`rule-tables-and-port-logic.md` §13.2 says this case "cannot be written". It can; it is not
refused. Correct §13.2 as part of this task.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py:272+` — `_validate`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` — `MD0300`
- Modify: `docs/design/rule-tables-and-port-logic.md` §13.2 — the correction
- Test: `tests/test_audit_regressions.py`

**Interfaces:**
- Consumes: `Decision.decides`, `DecisionRow.then`, `_validate(decision, path, registry,
  vocabulary, measurements)`.
- Produces: `MD0300`, refused at load.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_audit_regressions.py`:

```python
COMPUTED = """version: 1
decisions:
  - decides: {param: sjdb_overhang}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {}, then: "read_length-1"}
"""


def test_a_computed_then_is_refused_at_load(tmp_path):
    """A118. It loaded, resolved at tier 3, carried a real citation, and was not flagged.

    The spaced spelling `read_length - 1` was refused — by MD0201, a shell-injection character
    class that happens to exclude spaces. Removing them was enough to reach the tool.
    """
    layer = rule_layer(tmp_path, COMPUTED)
    with pytest.raises(DiagnosticError) as caught:
        load(layer_roots=[REGISTRY, layer])
    assert caught.value.code == "MD0300"
    assert "read_length-1" in str(caught.value)


def test_a_literal_then_still_loads(tmp_path):
    layer = rule_layer(tmp_path, COMPUTED.replace('"read_length-1"', "149"))
    assert load(layer_roots=[REGISTRY, layer]) is not None
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_audit_regressions.py -k computed -v`
Expected: FAIL — `DID NOT RAISE`.

- [ ] **Step 3: Refuse a `then` that names a measurement**

In `rules.py`'s `_validate`, inside the `{param: X}` branch, add:

```python
    for row in decision.rows:
        if not isinstance(row.then, str):
            continue
        named = [m for m in measurements.ids() if m in row.then]
        if named and row.then not in measurements.states_of(decision.param or ""):
            raise DiagnosticError(
                code="MD0300",
                where=f"{path}:{decision.key()}",
                summary=f"`then: {row.then}` reads as an expression, not a value",
                detail=(
                    f"    it names the measurement(s) {', '.join(named)}, and `then` is "
                    f"emitted verbatim — the tool would receive the string `{row.then}`."
                ),
                fix=(
                    "write one row per range with a literal `then`, or add the computed form "
                    "to the rule format deliberately — see issue #39"
                ),
            )
```

`measurements.ids()` is the declared measurement vocabulary; if the accessor has a different name,
read `MeasurementRegistry` and use the real one rather than adding a method. **This is a
containment check, not an expression parser** — the point is that any `then` mentioning a
measurement is refused loudly rather than emitted quietly.

- [ ] **Step 4: Register the diagnostic**

Add to `packages/comeni-core/src/comeni_core/diagnostics.yml`, opening the routing band:

```yaml
MD0300:
  emitted_by: resolver
  concern: rules
  says: "a rule's `then` reads as an expression, and `then` is emitted verbatim"
  fires_on: [build, upgrade]
  refuses: true
  fix: |
    `then` is a value, not a formula. `then: "read_length-1"` was resolved at tier 3, cited,
    left out of the review list, and reached the tool as the literal string `read_length-1`.
    Write one row per range with a literal `then`. If the rule genuinely needs arithmetic,
    that is issue #39 and a format change, not a value.
```

Then run `make docs` to regenerate the table in `docs/reference/cli.md`; CI checks it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit_regressions.py -k then -v`
Expected: PASS, 2 passed.

- [ ] **Step 6: Correct §13.2**

In `docs/design/rule-tables-and-port-logic.md` §13.2, replace the claim that the computed rule
"cannot be written" with what the audit measured:

```markdown
**Corrected 2026-08-14 by the design audit (A118).** This said the computed rule "cannot be
written". It can be written; it was **not refused**. `then: "read_length-1"` loaded, resolved at
tier 3, carried a real citation, stayed out of the review list, and reached `nextflow.config` as
`--sjdbOverhang read_length-1`. The only thing that ever caught it was `MD0201`, a
shell-injection character class, and only on the spaced spelling. `MD0300` now refuses it at
load. The expressive limit is real and unchanged; what was wrong was calling it a limit rather
than a hole.
```

- [ ] **Step 7: Verify, watch the guard fail, record it, and commit**

Run: `make verify` — expected exit 0. Revert Step 3's `raise`, confirm the test fails, restore,
append the ledger row.

```bash
git add packages/mendel-resolver/src/mendel_resolver/rules.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/cli.md \
        docs/design/rule-tables-and-port-logic.md tests/test_audit_regressions.py \
        docs/internal/audits/guard-ledger.md
git commit -m "feat(resolver): MD0300 refuses a computed rule value (A118)"
```

---

## Task 5: A129 — door 2 carries all three tier-4 question kinds

**The defect.** `AmbiguityRequest` is documented as "the union of what the three `*Asked` types
carry", and `tests/test_egress.py` asserts that union — **by comparing field names**. Two of the
three kinds fail validation on their *values*:

```
ParamAsked  candidates=[None]                REFUSED: Input should be a valid string
SourceAsked candidates=['star_align.bam']    REFUSED: not a contract id
ProducerAsked                                OK
```

Door 2 is exactly what Plan 2 Task 5 opens, so today only producer questions can be asked of a
model. This is the same family as [#32 (A68)](https://github.com/comeni-project/Comeni-Labs/issues/32)
through a different guard.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/egress.py:91-112` — `AmbiguityRequest.candidates`
- Modify: `tests/test_egress.py` — the union assertion tests values, not names
- Test: `tests/test_egress.py`

**Interfaces:**
- Consumes: `ParamAsked`, `SourceAsked`, `ProducerAsked` from `comeni_core.decision`.
- Produces: `AmbiguityRequest.candidates: list[CandidateRef]` where `CandidateRef` admits a
  contract id, an `EdgeRef`, or `None`. Plan 2 Task 5's `AmbiguityResolver` sees this type.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_egress.py`:

```python
@pytest.mark.parametrize("ambiguity", [
    ParamAsked(node_id="star_align", subject="seq_platform", candidates=[None]),
    SourceAsked(node_id="samtools_sort", subject="reads", candidates=["star_align.bam"]),
    ProducerAsked(node_id="star_align", subject="producer:alignment.bam",
                  candidates=["nf-core/star/align@1.11.0"]),
])
def test_every_tier_four_question_can_cross_door_two(ambiguity):
    """A129. The door is documented as the union of the three; it accepted one.

    `test_every_payload_field_is_a_declared_shape` compared field *names*, so a door whose
    `candidates` could not hold two of the three kinds' values read as complete. Plan 2 Task 5
    opens this door.
    """
    AmbiguityRequest(**ambiguity.model_dump())
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_egress.py -k door_two -v`
Expected: FAIL on two of three params — `Input should be a valid string`, and
`'star_align.bam' is not a contract id`.

- [ ] **Step 3: Widen `candidates` to the union of what the three carry**

In `egress.py`:

```python
CandidateRef = ContractId | EdgeRef | None
"""What a tier-4 question can offer. **A closed union, not a widening.**

Three shapes because there are three question kinds: a producer question offers contract ids,
a source question offers `<node>.<port>` edge references, and a parameter question offers
`[None]` — the honest spelling of "no default was ever written", which is A83's finding and
not this one's to fix. `None` stays in the union until a `ParamAsked` can carry real options.
Every member is a declared alias; none is a bare `str`. Audit A129.
"""


class AmbiguityRequest(EgressPayload):
    ...
    candidates: list[CandidateRef] = []
```

`EdgeRef` already exists in `comeni_core.pipeline`; import it rather than declaring a second
alias. **Do not add `str`** — a bare `str` bypasses the marker in one line and a prompt fits in
it perfectly, which is invariant 14's whole argument.

- [ ] **Step 4: Make the union assertion test values, not names**

In `tests/test_egress.py`, find the test asserting `AmbiguityRequest` is the union of the three
`*Asked` types and extend it to construct one of each rather than compare `model_fields`:

```python
def test_door_two_is_the_union_by_construction_not_by_field_name():
    """A129: comparing field names let a door that refuses two of three kinds read as green."""
    for ambiguity in (PARAM_ASKED, SOURCE_ASKED, PRODUCER_ASKED):
        AmbiguityRequest(**ambiguity.model_dump())
```

Leave the field-name assertion in place beside it — it catches a *new* field with nowhere to
land, which is the quiet half of A32 and still worth having.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_egress.py -v`
Expected: PASS, whole file.

- [ ] **Step 6: Verify the guards specifically**

Run:
```bash
uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
  tests/test_egress.py tests/test_construction.py
```
Expected: exit 0. Widening a door is the change most likely to weaken the egress guard, so this
runs on its own before `make verify`.

- [ ] **Step 7: Watch it fail, record it, verify and commit**

Narrow `CandidateRef` back to `ContractId`, confirm the new test fails on two of three, restore,
and append the ledger row. Then `make verify` — expected exit 0.

```bash
git add packages/comeni-core/src/comeni_core/egress.py tests/test_egress.py \
        docs/internal/audits/guard-ledger.md
git commit -m "fix(core): door 2 carries all three tier-4 question kinds (A129)"
```

---

## Finishing

- [ ] **Run the full gate one more time**

Run: `make verify && uv run pytest -m slow`
Expected: exit 0 on both. `make verify` excludes the new two-sample join test, which is `slow`.

- [ ] **Update `CLAUDE.md`'s open-issues table**

A92, A118, A125, A126 and A129 are closed by this plan. Issue #1 (routing ties) is *narrowed*, not
closed — A125 fixes which candidates are offered, not whether a human is asked. Say so rather than
ticking it.

- [ ] **Write the journal entry**

`docs/internal/journal/YYYY-MM-DD.md`, append-only, carrying what shipped, what was corrected
mid-flight, and what is next — which is Plan 1.14.

- [ ] **Open the pull request**

Merge commit, not squash: this repository keeps per-task history so that each commit's correction
survives.

---

## Self-review notes, recorded because the plan is a claim about code

Three things in this plan are predictions about code I read but did not run, and each is the
shape that has been wrong before in this repository:

1. **`measurements.ids()` (Task 4, Step 3) may not exist under that name.** Read
   `MeasurementRegistry` and use the real accessor. Do not add a method to make the plan right.
2. **The `spine_pipeline` fixture (Task 1, Step 9) may not exist in `tests/conftest.py`.**
   `tests/test_pipeline_file.py` builds and re-parses a `Pipeline` already; lift that rather than
   writing a second builder.
3. **`replay.py`'s lookup (Task 3, Step 4) is described as a dict access.** If it is already a
   scan, `_matches` slots in directly; if the key is used as a dict key elsewhere — in `upgrade`'s
   reporting, for instance — that call site needs the same treatment and this task grows a step.

**Expect to correct this plan while executing it.** That instruction is in `CLAUDE.md` because the
measurements plan predicted four things that did not exist, all written in good faith against
types that had not been built yet.
