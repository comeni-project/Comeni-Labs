# Mendel's half of the execution boundary — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` and drive it
> yourself, task by task. **Do not use `subagent-driven-development`** — `CLAUDE.md` overrides
> the skill's own recommendation: subagents are for review and design only.
> **Tick each `- [ ]` as it completes**, not in a batch at the end. Where a step was carried out
> differently than written, tick it anyway and record the deviation in the execution record.

**Goal:** Emit executor profiles so one pipeline runs on local, Kubernetes and AWS unchanged,
and let a person gate a drawn pipeline from the builder and see the verdict.

**Architecture:** Two independent halves that meet at the gate. `emit_config` gains `local`,
`k8s` and `awsbatch` profiles and **keeps its one-parameter signature**, which is what stops a
deployment target reaching the artifact. The gate moves off the CLI and onto ARQ: the builder
posts a gate request against a kept draft, the worker emits, runs Nextflow and stamps
`Pipeline.gate`, and the browser polls a run row.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLAlchemy 2 + Alembic + Postgres, ARQ +
Redis, Nextflow 25.10, React 19 + TS + Vite, React Query.

**Spec:** [`../../docs/design/execution-boundary.md`](../../docs/design/execution-boundary.md).
Read it first; every task below argues from a numbered section of it.

---

## Global Constraints

Copied from the spec and from `CLAUDE.md`. Every task's requirements include these.

- **`emit_config(pipeline)` must never take a target as an argument** (§6). A per-target
  emission breaks invariants 10 and 13 at once and makes `Pipeline.emitted`'s digests depend on
  a deployment choice.
- **A gate and a run must not share a label** (§3). The test is *does it take a samplesheet*.
  Nothing added here may accept one — invariant 15.
- **What crosses the boundary is `pipeline.yml` plus the emitted files** (§4). Nothing added
  here sends a run request anywhere.
- **Byte-identical emission is a hard requirement** (invariant 10). Anything emitted must be
  sorted and deterministic.
- **`make verify`, not `make check`**, for any change under `mendel_compiler/emit.py`,
  `mendel_compiler/cli/` or `comeni_core/artifact/pipeline.py`. It is `check` + the counts
  matrix + the guards, ~2 minutes.
- **A new diagnostic code is declared in `comeni_core/diagnostics.yml` and emitted through
  `coded()`.** Never write a code into a string by hand. `make docs` regenerates the page and
  CI checks it.
- **Never hand-edit `frontend/src/api/`.** `make client` regenerates it from the served schema.
- **Run management is Wiener's and is out of scope.** This plan stops at the gate. If a step
  starts to need run history, retries or a samplesheet, stop and say so.

---

## What already exists, and what does not

Established by reading the code before writing this, because three plans in this repository
have been written against types that did not exist.

| Fact | Where |
|---|---|
| `run_gate(gate, workdir)` shells out to Nextflow, four gates, timeouts 60s–3600s | `mendel_compiler/gates.py:60` |
| `LINT` and `PREVIEW` need **no Docker**; `STUB` and `TEST` do | `gates.py:20-33` |
| `_publish_verb` is the exact flow a job needs: refuse divergence → materialise → gate → stamp | `cli/artifact_verbs.py:113` |
| `emit_config` emits `stub_data`, `test`, `docker`, `singularity` — **no executor block at all** | `emit.py:388` |
| `keep` writes `pipeline.yml` + `modules/` into `draft_root/<id>/`, but **not** `main.nf`/`nextflow.config` | `services/drafts.py` |
| The builder already has a **disabled** "Run pipeline" button titled *"Running a pipeline is Wiener's job"* | `Builder.tsx:220` |
| The worker exists and runs **one cron job**; **nothing enqueues anything** | `worker.py` |
| Three tables, and a guard asserting exactly those three | `models.py`, `tests/test_models.py:18` |

**Two defects found while researching this plan.** Both are steps below rather than warnings:

1. **`/app/drafts` is not a volume.** `MENDEL_DRAFT_ROOT: /app/drafts` is set on both `api` and
   `worker` in `docker-compose.yml` and **no volume backs it**, so `keep` writes into a
   container's ephemeral layer, the file is lost on restart, and the worker cannot see it at
   all. Gate-through-the-worker is impossible until this is fixed. Task 2.
2. **The runtime image has no Nextflow and no Java.** `run_gate` degrades honestly —
   `"nextflow not found on PATH"` — rather than crashing, so this is invisible today. Task 2.

---

## Task 1: Executor profiles, and the guard that keeps them out of the artifact

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py:388-428` (`emit_config`)
- Modify: `tests/golden/spine/nextflow.config`
- Test: `packages/mendel-compiler/tests/test_emit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `emit_config(pipeline: Pipeline) -> str`, signature **unchanged**. Adds three
  profiles named exactly `local`, `k8s`, `awsbatch`.

- [x] **Step 1: Write the failing signature guard**

This is the spec's §6 rule made executable. Add to `packages/mendel-compiler/tests/test_emit.py`:

```python
def test_emit_config_cannot_depend_on_a_deployment_target():
    """`docs/design/execution-boundary.md` §6.

    A pipeline emitted for AWS that differs from the same pipeline emitted for a laptop breaks
    invariant 10 (same goal → byte-identical `.nf`) and invariant 13 (self-hosted is not a
    degraded tier) at once, and makes `Pipeline.emitted`'s recorded digests depend on a
    deployment choice — so `mendel emit` could not reproduce the file it is handed.

    A one-parameter signature **cannot express** a per-target emission. That is why this guard
    is on the signature rather than on the output: it fails at the moment somebody reaches for
    the wrong design, not after they have wired it through.
    """
    import inspect

    from mendel_compiler.emit import emit_config

    params = list(inspect.signature(emit_config).parameters)
    assert params == ["pipeline"], (
        f"emit_config takes {params}. The executor reaches a run through a PROFILE and "
        "`-c site.config`, never through emission — docs/design/execution-boundary.md §6."
    )
```

- [x] **Step 2: Run it and watch it pass for the right reason**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py::test_emit_config_cannot_depend_on_a_deployment_target -v`
Expected: **PASS** — the signature is already correct.

Then **watch it fail**, which is the point (A14, and `make residue` counts it). Temporarily add
a second parameter:

```python
def emit_config(pipeline: Pipeline, target: str = "local") -> str:
```

Re-run. Expected: FAIL with `emit_config takes ['pipeline', 'target']`. **Revert the
parameter**, re-run, expect PASS, and append the revert to
`notes/audits/guard-ledger.md` with the message it printed.

- [x] **Step 3: Write the failing profile test**

```python
def test_the_config_offers_an_executor_for_every_target_the_mvp_names():
    """§7: local, Kubernetes and AWS, and Nextflow abstracts the difference.

    Every pipeline gets all three whether or not anyone selects one — exactly as every pipeline
    already gets `docker` and `singularity` blocks it may never use. That is what makes them a
    function of nothing.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    for name in ("local", "k8s", "awsbatch"):
        assert f"    {name} {{" in config, f"no `{name}` profile"
    assert "process.executor = 'awsbatch'" in config


def test_a_profile_that_needs_site_facts_says_so_in_the_file():
    """A `k8s` profile with no storage claim and an `awsbatch` profile with no queue cannot run
    on their own, and a reader must not have to discover that from a Nextflow stack trace.

    §5: the executor, the queue and `workDir` are site facts supplied at run time. The profile
    declares the intent; `-c site.config` completes it.
    """
    from mendel_compiler.emit import emit_config

    config = emit_config(_pipeline())
    assert "site.config" in config
```

- [x] **Step 4: Run both, verify they fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -k "executor or site_facts" -v`
Expected: FAIL — `no \`local\` profile`.

- [x] **Step 5: Emit the three profiles**

In `emit.py`, inside `emit_config`, immediately after the `singularity` block and before the
closing `"}"`:

```python
        # **Executors, and they are a function of nothing.**
        #
        # `docs/design/execution-boundary.md` §6: the executor must not enter `pipeline.yml`
        # or `main.nf`, because a pipeline that differed per deployment target would break
        # invariant 10 and invariant 13 at once. So every pipeline carries all three whether
        # or not anyone selects one — the same posture `docker` and `singularity` already
        # take. `emit_config` takes one parameter and a test holds it there.
        #
        # Nextflow does the actual work: same workflow, same modules, same containers, and
        # the backend is configuration. What Mendel cannot know is the site — a queue name, a
        # storage class, a role ARN, where `workDir` lives — so each profile names what it
        # still needs and Nextflow layers `-c site.config` over the top.
        "    local {",
        "        process.executor = 'local'",
        "    }",
        # **`k8s` is also the name of a Nextflow config SCOPE** — `k8s { namespace, ... }` —
        # and a profile called `k8s` that sets `k8s.*` inside itself reads like a recursion
        # and is not one. Kept anyway: `-profile k8s` is what somebody will type, and the
        # alternative is teaching a second word for one thing. The comment is the mitigation.
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
```

- [x] **Step 6: Run the two tests, verify they pass**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -k "executor or site_facts" -v`
Expected: PASS.

- [x] **Step 7: Update the golden file, by reading the diff rather than blessing it**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -k golden -v`
Expected: FAIL — the golden config no longer matches.

Regenerate and **read the diff before accepting it** (the Jinja gotcha in `CLAUDE.md` was caught
exactly this way):

```bash
uv run python -c "
from pathlib import Path
import sys; sys.path.insert(0, 'packages/mendel-compiler/tests')
from test_emit import _pipeline
from mendel_compiler.emit import emit_config
Path('tests/golden/spine/nextflow.config').write_text(emit_config(_pipeline()))
"
git diff tests/golden/spine/nextflow.config
```

Expected diff: **three added profile blocks and nothing else.** If any existing line moved,
stop — the change was not additive.

- [x] **Step 8: Find every other recorded digest that moved**

`cli/report.py:135` records `digest_of_bytes(emit_config(fresh).encode())`, so any committed
`pipeline.yml` carrying an `emitted:` block now disagrees with what would be emitted.

Run: `make verify`
Expected: some tests fail on emitted digests. For each, regenerate the fixture rather than
loosening the assertion — the digest moving is *correct*, and a test that stops checking it is
the drift the digest exists to catch.

**`notes/audits/fixtures/pipeline-v1/` is the exception: do not regenerate it.** It is an
archived v1 artifact that `tests/test_upgrade.py:572` and `tests/test_pipeline_file.py:75`
read precisely because it is old. `report.py` already handles a pipeline with no
`emitted` record by saying so.

- [x] **Step 9: Full verification**

Run: `make verify`
Expected: all green.

- [x] **Step 10: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/emit.py \
        packages/mendel-compiler/tests/test_emit.py \
        tests/golden/spine/nextflow.config notes/audits/guard-ledger.md
git commit -m "feat(compiler): one pipeline, three executors, and no target at emission"
```

---

## Task 2: A worker that can actually run a gate

**Files:**
- Modify: `Dockerfile` (runtime stage)
- Modify: `docker-compose.yml` (`api` and `worker` services)
- Modify: `docker-compose.prod.yml` if it repeats the draft root
- Test: `tests/test_compose.py` (the existing compose guard)

**Interfaces:**
- Consumes: nothing.
- Produces: a `worker` container with `nextflow` on `PATH` and a `drafts` volume shared with
  `api`, mounted at `/app/drafts`.

**Why this task exists:** two defects, both found by asking what a container does — the same
method that found phase 8's two.

- [x] **Step 1: Write the failing test for the shared draft root**

Add to `tests/test_compose.py`:

```python
def test_the_draft_root_is_a_volume_shared_by_the_api_and_the_worker(base):
    """`keep` writes an artifact and the worker gates it. Two containers, one directory.

    `MENDEL_DRAFT_ROOT` was set on both services with nothing backing it, so the API wrote
    into its own ephemeral layer: the file vanished on restart and the worker could not see it
    at all. A gate job would have run `nextflow` in a directory that does not exist and
    reported a Nextflow error, which is the worst kind of failure — a true message about the
    wrong thing.
    """
    services = base["services"]
    for name in ("api", "worker"):
        root = services[name]["environment"]["MENDEL_DRAFT_ROOT"]
        mounts = [v.split(":")[1] for v in services[name]["volumes"] if ":" in v]
        assert root in mounts, f"{name}: MENDEL_DRAFT_ROOT={root} is backed by no volume"
```

- [x] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_compose.py -k draft_root -v`
Expected: FAIL — `api: MENDEL_DRAFT_ROOT=/app/drafts is backed by no volume`.

- [x] **Step 3: Add the shared volume**

In `docker-compose.yml`, add to the `volumes:` list of **both** `api` and `worker`:

```yaml
      # **Shared, because two containers meet here.** `keep` (api) writes the artifact and the
      # gate job (worker) runs Nextflow in it. Set as an env var on both services with nothing
      # backing it until 2026-08-23, so the file lived in one container's ephemeral layer.
      - ./.run/drafts:/app/drafts
```

and create `.run/drafts/.gitkeep`. Check `.gitignore` already covers `/.run/`.

- [x] **Step 4: Run it, verify it passes**

Run: `uv run pytest tests/test_compose.py -v`
Expected: PASS. Also run
`uv run pytest packages/mendel-api/tests/test_build_service.py -k compose -v`, which is where
`test_every_configured_root_is_absolute_in_the_compose_file` actually lives — it caught
`MENDEL_DRAFT_ROOT` when 3E added it, and it is the guard most likely to have an opinion here.

- [x] **Step 5: Put Nextflow in the runtime image**

In `Dockerfile`, in the `runtime` stage, extend the existing `apt-get` layer:

```dockerfile
# `git` because accepting a drift is a commit — `mendel_forge.land` shells out to it.
# `default-jre-headless` and `nextflow` because a GATE is a `nextflow run` and the worker is
# where one belongs: `run_gate` blocks for up to 3600s and `mendel-api`'s worker docstring
# already named this job as the thing ARQ exists for.
#
# **LINT and PREVIEW only, in this image.** STUB and TEST pass `-profile ...,docker` and need a
# Docker daemon; giving this container one means mounting the host's socket, which is
# root-equivalent access to the host. That is a real decision and it is NOT taken here —
# docs/design/execution-boundary.md §8 leaves it to Wiener, which is the component that has to
# solve isolation anyway. `run_gate` already degrades honestly when a tool is absent.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl default-jre-headless \
 && curl -fsSL https://get.nextflow.io -o /usr/local/bin/nextflow \
 && chmod +x /usr/local/bin/nextflow \
 && rm -rf /var/lib/apt/lists/*

# **Created and chowned, because the worker does not run as root.** `docker-compose.yml` sets
# `user: "${DOCKER_UID:-1000}:${DOCKER_GID:-1000}"` and nothing in this file chowns `/app`, so
# a root-owned `NXF_HOME` is permission-denied on the first gate — and Nextflow writes there
# before it does anything else, because it downloads its plugins on first run. The failure
# would read as a Nextflow bug.
#
# That first run also needs the network. Legitimate — `mendel-api` is an impure package and
# invariant 1 constrains the other three — but an air-gapped installation must pre-seed this
# directory, and nothing else in the stack has that property.
ENV NXF_HOME=/app/.nextflow
RUN mkdir -p /app/.nextflow && chown -R 1000:1000 /app/.nextflow
```

**`1000:1000` is hardcoded and `DOCKER_UID` is not.** If `.env` overrides it, this breaks and
the message will be a permission error from Nextflow. Note it in the execution record if the
machine running this uses anything else.

- [x] **Step 6: Build and check it end to end**

```bash
docker compose build worker
docker compose run --rm worker nextflow -version
```
Expected: a version banner. If it reports a Java error the JRE line is wrong; if it reports a
permission error on `.nextflow`, the chown above did not take. **Fix either here rather than
discovering it inside a job**, where it arrives as a failed gate with a confusing message.

- [x] **Step 7: Commit**

```bash
git add Dockerfile docker-compose.yml tests/test_compose.py .run/drafts/.gitkeep
git commit -m "fix(compose): the draft root is one directory, and the worker has nextflow"
```

---

## Task 3: A row that remembers a gate

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`
- Modify: `packages/mendel-api/tests/test_models.py:18-30`
- Create: `packages/mendel-api/migrations/versions/<rev>_gate_run.py` (generated)

**Interfaces:**
- Produces: `GateRun` with `__tablename__ = "gate_run"` and columns
  `id: str(32)`, `draft_id: str(32)`, `who: str(200)`, `gate: str(16)`,
  `state: str(16)`, `output: Text`, `queued_at`, `finished_at | None`.
  `state` is one of `queued`, `running`, `passed`, `failed`.

- [x] **Step 1: Update the table guard first, and say why**

The fourth table must be a deliberate act, which is what `test_the_registry_is_not_in_the_database`
is for. Edit it:

```python
    assert tables == {"source_check", "queue_visit", "pipeline_draft", "gate_run"}, (
        f"unexpected: {tables}"
    )
```

and extend its docstring:

```python
    """...

    `gate_run` is the fourth table and is not that reversal either. A gate's verdict lives in
    the artifact — `Pipeline.gate`, stamped by `pipeline_file.stamp` — and this row holds what
    the artifact cannot: that somebody asked, when, and what Nextflow printed while failing.
    None of that is declared data and none of it is recoverable from disk.

    **It is not run history.** `docs/design/execution-boundary.md` §2 puts run management in
    Wiener; this table remembers gates, which are Mendel's own artifact checking itself.
    """
```

- [x] **Step 2: Run it, verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_models.py -v`
Expected: FAIL — `unexpected: {'source_check', 'queue_visit', 'pipeline_draft'}`.

- [x] **Step 3: Add the model**

Append to `models.py`:

```python
class GateRun(Base):
    """A gate somebody asked for, and what came back.

    **The fourth table.** The first one's docstring said a second would be a deliberate act,
    and each since has argued for itself. This one holds what the artifact cannot: `Pipeline.gate`
    records the strongest gate a pipeline *passed*, and says nothing about who asked, when, or
    what Nextflow printed on the way to failing. A person watching a 900s stub run needs all
    three, and none is recoverable from disk.

    **`output` is a tool's own text**, which is a free-text field with a real author — the same
    thing `GateFailure.tool_message` already is on the egress surface. It is stored and shown to
    the person who asked. It must never be folded into an egress payload without going through
    `tests/test_egress.py`, because `guarded` sets `tool_message` to `None` for a reason.

    **This is not run history** — `docs/design/execution-boundary.md` §2. A gate is Mendel's
    artifact checking itself on public data; a run is Wiener's, takes a samplesheet, and has no
    row here.
    """

    __tablename__ = "gate_run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(32), index=True)
    who: Mapped[str] = mapped_column(String(200))
    gate: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), index=True)
    """`queued` | `running` | `passed` | `failed`. A plain column rather than a native enum:
    adding a state to a Postgres enum is a migration, and `Gate` is already the closed
    vocabulary that matters here."""
    output: Mapped[str] = mapped_column(Text, default="")
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Add `Text` to the `sqlalchemy` import.

- [x] **Step 4: Run it, verify it passes**

Run: `uv run pytest packages/mendel-api/tests/test_models.py -v`
Expected: PASS.

- [x] **Step 5: Generate and read the migration**

```bash
cd packages/mendel-api && uv run alembic revision --autogenerate -m gate_run
```

There is no `make` target for autogeneration — `make migrate` only applies. Run it from
`packages/mendel-api`, which is where `alembic.ini` lives.

**Read the generated file.** `b6e3e0e31b73_pipeline_draft.py` is the shape to compare against.
Confirm it creates the table and both indexes and touches nothing else.

- [x] **Step 6: Apply it**

Run: `make migrate`
Expected: no error. Confirm with `docker compose exec postgres psql -U mendel -c '\d gate_run'`.

- [x] **Step 7: Commit**

```bash
git add packages/mendel-api/src/mendel_api/models.py \
        packages/mendel-api/tests/test_models.py \
        packages/mendel-api/migrations/versions/
git commit -m "feat(api): a row that remembers a gate, and why it is not run history"
```

---

## Task 4: The job

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/gates.py`
- Modify: `packages/mendel-api/src/mendel_api/worker.py`
- Test: `packages/mendel-api/tests/test_gate_service.py`

**Interfaces:**
- Consumes: `GateRun` (Task 3), `settings.draft_root`, `mendel_compiler.gates.run_gate`.
- Produces:
  - `gates.request(draft_id: str, gate: Gate, *, who: str) -> str` — writes a `queued` row,
    returns its id. Does **not** enqueue; the route does.
  - `gates.execute(run_id: str) -> None` — the whole gate, synchronously. Called by the worker.
  - `gates.read(run_id: str) -> GateView` — a Pydantic view for the route.
  - Seams `gates._load_run`, `gates._directory` mirroring `drafts._load` / `drafts._output_root`,
    so the rules can be tested without Postgres.

- [ ] **Step 1: Write the failing test for the rule worth defending in CI**

`packages/mendel-api/tests/test_gate_service.py`. The seams exist for the reason `drafts.py`
records: these tests need Postgres and CI has none, so the rules most worth defending are
tested with storage monkeypatched.

```python
"""What a gate does, with the storage stubbed out.

`services/drafts.py` records why the seams exist: CI has no Postgres, so a rule that could only
be checked on a developer machine is a rule nobody checks.
"""

import pytest
from comeni_core.artifact.gates import Gate

from mendel_api.services import gates


def test_a_gate_refuses_a_draft_that_was_never_kept(tmp_path):
    """A draft is a row; a gate runs on an artifact. `keep` is the boundary between them
    (`docs/design/execution-boundary.md` §4), so gating something never kept has no directory
    to run in — and Nextflow's error would blame the pipeline for a missing file rather than
    saying the pipeline was never written.

    **No monkeypatch.** `of` takes the directory as an argument and never calls `_directory`,
    so patching that seam here would change nothing and the test would pass for a reason
    unrelated to what it claims to check.
    """
    with pytest.raises(ValueError, match="MA0001"):
        gates.of(tmp_path / "never-kept", Gate.LINT)


def test_a_gate_reports_a_missing_nextflow_as_a_failed_gate_not_a_crash(tmp_path, monkeypatch):
    """`run_gate` already degrades honestly — `nextflow not found on PATH`. The service must
    carry that through as a FAILED result with that text, because an exception here would
    reach the person as a 500 with no message: the failure mode forge phase 2 shipped and
    spent an evening on."""
    from mendel_compiler.gates import GateResult

    directory = _kept(tmp_path)   # see below
    monkeypatch.setattr(
        gates,
        "_run",
        lambda gate, d: GateResult(gate=gate, passed=False, stderr="nextflow not found on PATH"),
    )
    result = gates.of(directory, Gate.LINT)
    assert result.passed is False
    assert "nextflow not found on PATH" in result.output


def _kept(tmp_path):
    """A real kept directory, because `of` loads and re-emits the artifact.

    Built by the same route the product uses rather than by hand-writing a `pipeline.yml`:
    a fixture that is not a real artifact tests a code path nothing takes. `tests/
    test_pipeline_file.py::_build` is the shape to copy — and **omit `--gate`**, because CI
    has no Nextflow (`CLAUDE.md`, Gotchas).
    """
    from mendel_compiler.cli import main

    out = tmp_path / "kept"
    # **No `--gate`.** CI installs neither Nextflow nor Docker, so any test passing one is
    # green locally and red in CI — `CLAUDE.md`, Gotchas. This is `tests/test_pipeline_file.py
    # ::_build` verbatim; it is the established way to get a real artifact into a tmp_path.
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out
```

`GOAL` and `ROOT` are module constants in `tests/test_pipeline_file.py`; copy those two lines
too rather than re-deriving the paths.

- [ ] **Step 2: Declare the diagnostic**

**`MA0001`, and it is the first `MA` code in the repository.** `diagnostics.yml`'s own header
says `MD` is "Mendel's deterministic core: the three packages that may not reach the network"
and that `MF`, `MA` and `MI` belong to the forge, the API and the AI adapters. This refusal is
raised in `mendel_api.services.gates`, so an `MD` code here would fail
`test_every_code_is_owned_by_the_package_that_emits_it`.

First add the band to the header comment, after the `MF0100-MF0199` line:

```
#   MA0001-MA0099  the API: gating a drawn pipeline
```

Then the entry. **`concern: gates`** — the twelve legal values are the keys of `HEADINGS` in
`tools/generate_diagnostics_doc.py`, and that generator *refuses* an unknown concern
(line 106). There is no `artifact` concern; `gates` renders as "Gates and emission".

```yaml
MA0001:
  emitted_by: api
  concern: gates
  says: "this draft has no artifact to gate — keep it first"
  fires_on: [gate]
  refuses: true
  fix: |
    Press *Keep* first, then gate. `POST /api/pipeline/drafts/{draft_id}/keep` is the same
    operation.
  explanation: |
    A gate runs Nextflow in a directory. A draft is a row in a database until `keep`
    validates it and writes `pipeline.yml` and the modules beside it, so a draft that was
    never kept has nothing to run. Reporting Nextflow's own "no such file" here would be a
    true message about the wrong thing.
```

The field names are `MD0100`'s exactly: `emitted_by`, `concern`, `says`, `fires_on`,
`refuses`, `fix`, `explanation`. **`fires_on` is `list[str]`** in `DiagnosticSpec` — checked,
not assumed — so `[gate]` needs no permission from anything.

Run `make docs` and confirm `docs/reference/diagnostics.md` regenerates, then
`uv run pytest tests/test_diagnostics_ownership.py -v` — it checks both directions and the
prefix scan.

- [ ] **Step 3: Run the tests, verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_gate_service.py -v`
Expected: FAIL — `No module named 'mendel_api.services.gates'`.

- [ ] **Step 4: Write the service**

`packages/mendel-api/src/mendel_api/services/gates.py`:

```python
"""Running a gate, and remembering that it ran.

**A gate is not a run.** `docs/design/execution-boundary.md` §3: a gate runs Mendel's own
artifact against data somebody else published, takes no samplesheet, and is bounded. A run
takes a laboratory's data and belongs to Wiener. Nothing in this module accepts a path from a
client — the directory is derived from an opaque draft id, exactly as `drafts._output_root`
derives its destination.

**The flow is `_publish_verb`'s, not a second one.** `cli/artifact_verbs.py` already emits,
materialises stub inputs, gates and stamps in that order, and every step of it earned itself
(A47, A49, A104). This re-uses the pieces rather than reordering them.
"""

import asyncio
import secrets
from datetime import UTC, datetime
from pathlib import Path

from comeni_core.artifact.gates import Gate
from comeni_core.diagnostics import coded
from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import GateResult, materialise_stub_data, run_gate
from pydantic import BaseModel

from mendel_api.db import session_scope
from mendel_api.models import GateRun
from mendel_api.settings import settings


class GateView(BaseModel):
    """What the browser polls. No path, no host detail — the same restraint the drafts
    routes take, for the same reason."""

    id: str
    gate: Gate
    state: str
    output: str
    queued_at: datetime
    finished_at: datetime | None


def _directory(draft_id: str) -> Path:
    """The destination seam. Server-chosen, never client-supplied — invariant 15."""
    return settings.draft_root / draft_id


def _run(gate: Gate, directory: Path) -> GateResult:
    """The subprocess seam, so a test can stub Nextflow without one installed."""
    return run_gate(gate, directory)


def request(draft_id: str, gate: Gate, *, who: str) -> str:
    """Record the ask. Enqueueing is the route's job — a service that reached Redis would
    make every test that touches a gate need one."""
    run_id = secrets.token_hex(16)
    with session_scope() as session:
        session.add(
            GateRun(
                id=run_id,
                draft_id=draft_id,
                who=who,
                gate=gate.value,
                state="queued",
                queued_at=datetime.now(UTC),
            )
        )
    return run_id


def of(directory: Path, gate: Gate) -> GateResult:
    """Emit, materialise, gate. The pure half — no database, so it is testable without one.

    Emission happens here rather than at `keep` because `keep` writes `pipeline.yml` and the
    modules and nothing else: the Nextflow is regenerated from the artifact, which is the
    property `mendel emit` sells.
    """
    target = directory / pipeline_file.FILENAME
    if not target.exists():
        # No f-string: ruff refuses one with no placeholder (F541), and `make check` runs it.
        raise ValueError(coded("MA0001", "there is no pipeline to gate. Keep the draft first."))
    pipeline = pipeline_file.load(target)
    (directory / "main.nf").write_text(emit(pipeline))
    (directory / "nextflow.config").write_text(emit_config(pipeline))
    if gate is Gate.STUB:
        materialise_stub_data(directory, entry_params(pipeline))
    return _run(gate, directory)


async def execute(run_id: str) -> None:
    """The worker's entry point. `run_gate` blocks for up to 3600s, so it goes to a thread —
    an ARQ worker is one event loop and a blocking subprocess in it stops every other job."""
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is None:
            return
        row.state = "running"
        draft_id, gate = row.draft_id, Gate(row.gate)

    try:
        directory = _directory(draft_id)
        result = await asyncio.to_thread(of, directory, gate)
        state, output = ("passed" if result.passed else "failed"), result.output
        # **Stamped on the failing path too, and that is not symmetry for its own sake.**
        # `of` regenerated `main.nf` and `nextflow.config` from the artifact, so leaving the
        # `emitted:` record untouched makes the directory diverge from its own `pipeline.yml`
        # — and the next `mendel emit` refuses with `MD0214`, blaming the person for a change
        # this gate made. `_publish_verb` stamps on both paths for exactly this reason, with
        # `gate=None` on failure: A4, never leave an artifact stamped with a gate it did not
        # pass.
        pipeline = pipeline_file.load(directory / pipeline_file.FILENAME)
        pipeline_file.stamp(directory, pipeline, gate=result.gate if result.passed else None)
    except ValueError as refusal:  # a coded refusal, e.g. MA0001
        state, output = "failed", str(refusal)

    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is not None:
            row.state, row.output = state, output
            row.finished_at = datetime.now(UTC)


def read(run_id: str) -> GateView:
    """Raises `KeyError` for an unknown run; the route maps it to 404."""
    with session_scope() as session:
        row = session.get(GateRun, run_id)
        if row is None:
            raise KeyError(run_id)
        return GateView(
            id=row.id, gate=Gate(row.gate), state=row.state, output=row.output,
            queued_at=row.queued_at, finished_at=row.finished_at,
        )
```

- [ ] **Step 5: Register the job with the worker**

In `worker.py`:

```python
from mendel_api.services import gates as gate_service


async def run_gate_job(ctx: dict, run_id: str) -> str:
    """Gate a kept draft. **Not a pipeline run** — `docs/design/execution-boundary.md` §3.

    This is the job this module's docstring was written for and never got: it named a stub
    gate at up to 900s as the thing that does not belong in a request, and then shipped with
    `check_sources` alone.
    """
    await gate_service.execute(run_id)
    return run_id
```

and extend `WorkerSettings.functions`:

```python
    functions = [check_sources, run_gate_job]
```

- [ ] **Step 6: Run the tests, verify they pass**

Run: `uv run pytest packages/mendel-api/tests/test_gate_service.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/gates.py \
        packages/mendel-api/src/mendel_api/worker.py \
        packages/mendel-api/tests/test_gate_service.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml \
        docs/reference/diagnostics.md
git commit -m "feat(api): gate a kept draft on the worker, where a 900s job belongs"
```

---

## Task 5: The two routes, and the first thing that enqueues

**Files:**
- Create: `packages/mendel-api/src/mendel_api/jobs.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/build.py`
- Test: `packages/mendel-api/tests/test_openapi.py`, `packages/mendel-api/tests/test_gate_routes.py`

**Interfaces:**
- Consumes: `gates.request`, `gates.read` (Task 4).
- Produces:
  - `POST /api/pipeline/drafts/{draft_id}/gate` → `GateView`, `operation_id="startGate"`,
    body `GateIn{gate: Gate}`.
  - `GET /api/pipeline/gates/{run_id}` → `GateView`, `operation_id="readGate"`.

  **`/api/pipeline/…`, not `/api/…`.** `routes/build.py:28` is
  `APIRouter(prefix="/pipeline", tags=["pipeline"])`, so every draft route already lives under
  it — verified by generating the document, not by reading the decorators. The router supplies
  the tag too, so **do not pass `tags=`**: a second value would invent an undeclared tag, and
  `test_every_operation_carries_a_tag` is satisfied by the router's.
  - `jobs.enqueue(name: str, *args) -> None`, an awaitable seam over ARQ.

**Nothing in this repository enqueues anything today** — the worker has run one cron job since
phase 8. This task builds that path.

- [ ] **Step 1: Write the failing route tests**

```python
def test_starting_a_gate_returns_a_queued_run_and_enqueues_exactly_once(client, monkeypatch):
    """The route writes a row and hands the work away. It must not run a gate itself: a stub
    gate is up to 900s cold, and `worker.py`'s docstring already says where that belongs.

    `jobs.enqueue` is patched rather than Redis, for the reason `services/drafts.py` records
    about its own seams — CI has neither Redis nor Postgres, and a rule only a developer
    machine can check is a rule nobody checks.
    """
    sent = []

    async def _capture(name, *args):
        sent.append((name, args))

    monkeypatch.setattr(jobs, "enqueue", _capture)
    monkeypatch.setattr(gate_service, "request", lambda draft_id, gate, who: "run-1")
    monkeypatch.setattr(
        gate_service,
        "read",
        lambda run_id: gate_service.GateView(
            id=run_id, gate=Gate.LINT, state="queued", output="",
            queued_at=datetime(2026, 8, 23, tzinfo=UTC), finished_at=None,
        ),
    )

    response = client.post("/api/pipeline/drafts/abc/gate", json={"gate": "lint"})

    assert response.status_code == 200
    assert response.json()["state"] == "queued"
    assert sent == [("run_gate_job", ("run-1",))], "the job was not queued exactly once"


def test_no_gate_route_accepts_a_path(client):
    """Invariant 15, and `tests/test_mount.py` already holds the general rule. This is the
    specific one: a gate names a DRAFT by opaque id, never a directory."""
    schema = client.get("/openapi.json").json()
    schema["paths"]["/api/pipeline/drafts/{draft_id}/gate"]["post"]["requestBody"]
    props = schema["components"]["schemas"]["GateIn"]["properties"]
    assert set(props) == {"gate"}, f"GateIn carries more than a gate: {set(props)}"
```

- [ ] **Step 2: Run them, verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_gate_routes.py -v`
Expected: FAIL — 404 on the route.

- [ ] **Step 3: Write the enqueue seam**

`packages/mendel-api/src/mendel_api/jobs.py`:

```python
"""Handing work to the worker.

**One seam, because a route that reached Redis directly would make every route test need
one.** `services/drafts.py` records the same argument for its storage seam.

The pool is created lazily and kept: ARQ's `create_pool` opens a connection, and doing that
per request is a connection per click.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from mendel_api.settings import settings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


async def enqueue(name: str, *args: object) -> None:
    """**Locked**, because two concurrent first requests would each see `None` and open a
    pool, and the loser is then never closed. Cheap: the lock is contended once per process."""
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await _pool.enqueue_job(name, *args)
```

- [ ] **Step 4: Write the routes**

In `routes/build.py`:

```python
class GateIn(BaseModel):
    """**A gate, and nothing else.** No path, no samplesheet, no output directory —
    `docs/design/execution-boundary.md` §3: the test for whether something is a *run* rather
    than a *gate* is whether it takes a samplesheet, and this cannot."""

    model_config = ConfigDict(extra="forbid")
    gate: Gate


@router.post(
    "/drafts/{draft_id}/gate",
    operation_id="startGate",
    summary="Gate a kept draft",
    responses=REFUSES,
)
async def start_gate(draft_id: str, body: GateIn) -> gate_service.GateView:
    """Queue a gate. Returns immediately with a `queued` run — a stub gate is up to 900s cold
    and nothing that long may sit in a request.

    **This is not *Run pipeline*.** A gate proves the artifact on public data; running a
    laboratory's data is Wiener's, and Mendel has no route for it by design.
    """
    # **`run_in_threadpool`, because this route had to become `async` to await the enqueue.**
    # Every other route here is a plain `def`, which FastAPI already runs in a threadpool; an
    # `async def` doing a synchronous Postgres session blocks the event loop for every other
    # request. Awaiting the two blocking calls explicitly is the smallest correct fix.
    run_id = await run_in_threadpool(
        gate_service.request, draft_id, body.gate, who=identity.default_author()
    )
    await jobs.enqueue("run_gate_job", run_id)
    return await run_in_threadpool(gate_service.read, run_id)


@router.get("/gates/{run_id}", operation_id="readGate", summary="How a gate is going")
def read_gate(run_id: str) -> gate_service.GateView:
    try:
        return gate_service.read(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such gate run: {run_id}") from None
```

- [ ] **Step 5: Run the tests, verify they pass**

Run: `uv run pytest packages/mendel-api/tests/ -v`
Expected: PASS. `test_openapi.py::test_every_operation_is_named_by_hand` holds an **exact
dict keyed by `(path, method)`**, so add both entries with the real paths:

```python
        ("/api/pipeline/drafts/{draft_id}/gate", "post"): "startGate",
        ("/api/pipeline/gates/{run_id}", "get"): "readGate",
```

New imports in `routes/build.py`: `from comeni_core.artifact.gates import Gate`,
`from fastapi.concurrency import run_in_threadpool`, `from mendel_api import jobs`,
`from mendel_api.services import gates as gate_service`.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-api/src/mendel_api/jobs.py \
        packages/mendel-api/src/mendel_api/routes/build.py \
        packages/mendel-api/tests/
git commit -m "feat(api): start a gate and poll it, and the first enqueue in the repository"
```

---

## Task 6: The Gate button, and the button it replaces

**Files:**
- Regenerate: `frontend/src/api/` via `make client`
- Create: `frontend/src/build/useGate.ts`, `frontend/src/build/Gate.tsx`, `Gate.test.tsx`
- Modify: `frontend/src/build/Builder.tsx:211-235` (the header) and `:462-484` (the rail tabs)

**Interfaces:**
- Consumes: `startGate`, `readGate`.
- Produces: `useGate(draftId)` → `{ start(gate), run, running }`.

- [ ] **Step 1: Regenerate the schema and widen the type seam**

Run: `make client`
Then: `git diff --stat frontend/src/api/`
Expected: `schema.d.ts` only.

**`make client` regenerates types, not a client.** The Makefile runs `openapi-typescript … -o
src/api/schema.d.ts` and nothing else; `frontend/src/api/client.ts` is a *hand-written* wrapper
exporting `get<T>(path: string)` and `post<T>(path, payload)`. So "never hand-edit
`frontend/src/api/`" means **`schema.d.ts`**, and the rest of that directory is ordinary code.

Add the two names to `frontend/src/api/types.ts`, which exists precisely because the generated
names are unstable (`DraftGraph` was `DraftGraph-Input` for one commit):

```ts
export type GateIn = S["GateIn"];
export type GateView = S["GateView"];
```

If either comes back as `GateView-Output`, that is the file's whole reason for existing — fix
it here and nowhere else.

- [ ] **Step 2: Write the failing test**

`frontend/src/build/Gate.test.tsx`:

```tsx
it("polls while a gate is running and stops when it lands", async () => {
  // The flicker lesson from 3E: the server seeds, the client owns. A gate is the opposite
  // case — the SERVER owns this state and the client may only watch it, so this is the one
  // place polling is right. It stops the moment the run is terminal.
});

it("says what a gate is not", () => {
  // dashboard.md's disabled control said "Running a pipeline is Wiener's job, and Wiener is
  // not built." That sentence is still true and must not be deleted along with the button —
  // execution-boundary.md §3 is exactly about these two not sharing a name.
  render(<Gate draftId="abc" />);
  expect(screen.getByTestId("gate-button")).toHaveTextContent(/gate/i);
  expect(screen.queryByText(/^Run pipeline$/)).toBeNull();
});
```

- [ ] **Step 3: Run them, verify they fail**

Run: `cd frontend && npx vitest run Gate` — Expected: FAIL, module not found.

- [ ] **Step 4: Write the hook**

`frontend/src/build/useGate.ts`, polling only while the run is live:

```ts
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get, post } from "../api/client";
import type { GateView } from "../api/types";

const LIVE = ["queued", "running"];

export function useGate(draftId: string | null) {
  const [runId, setRunId] = useState<string | null>(null);

  const run = useQuery({
    queryKey: ["gate", runId],
    // **A plain template string**: `client.ts` is a hand-written wrapper taking a path, not
    // openapi-fetch — there is no `{ params: { path } }` here. And the path carries the
    // router's `/pipeline` prefix, which `ROOT = "/api"` in that file completes.
    queryFn: () => get<GateView>(`/pipeline/gates/${runId}`),
    enabled: runId !== null,
    // **Two seconds, and only while it is live.** A gate is 60s to 3600s of server-owned
    // state, so polling is right here in a way it was wrong for the graph — the client
    // cannot know the answer and must ask. `false` the moment it lands: a terminal run
    // polled forever is exactly the spam this project asked not to ship.
    refetchInterval: (q) => (q.state.data && LIVE.includes(q.state.data.state) ? 2000 : false),
  });

  const start = useMutation({
    mutationFn: (gate: string) =>
      post<GateView>(`/pipeline/drafts/${draftId}/gate`, { gate }),
    onSuccess: (started) => setRunId(started.id),
  });

  return {
    run: run.data ?? null,
    start: (gate: string) => start.mutate(gate),
    // `queued` and `running` both count: the button must not offer a second gate while one
    // is in flight, and `start.isPending` alone goes false the moment the POST returns.
    running: start.isPending || (run.data ? LIVE.includes(run.data.state) : false),
  };
}
```

`post<T>(path, payload)` is `client.ts`'s other export; it raises `Refused` on a 422, so
`MA0001` reaches the panel as its own message rather than as "Request failed".

- [ ] **Step 5: Refuse to gate a draft that has moved since it was kept**

**A164, and it is the defect most likely to ship silently.** A gate runs on whatever `keep`
last wrote. Edit the graph, press *Gate*, and the verdict describes the **previous** artifact —
with a green tick beside a canvas that no longer matches it. That is A47's class exactly: a
stale file keeping its certification.

**Decision, taken because it cannot produce a false green:** *Gate* is **disabled while the
draft is dirty*, with the reason on the control. The rejected alternative is having *Gate*
keep first — it reads as more helpful and it silently changes what *Keep* means, including
`keep`'s refusal of an illegal graph, which would then surface as a failed gate.

`useGraph` already tracks `dirty` for the idle save, so this is a prop rather than new state.

```tsx
<Gate
  draftId={draftId}
  // `dirty` is the same flag the 5s idle save reads. A gate certifies what is ON DISK, and
  // an unsaved edit is not on disk — so this is not a UI nicety, it is the difference
  // between a verdict about your pipeline and a verdict about a previous one.
  blocked={graph.dirty ? "Keep your changes first — a gate certifies what was kept." : null}
/>
```

Write the test with it:

```tsx
it("will not gate a draft with unkept changes", () => {
  render(<Gate draftId="abc" blocked="Keep your changes first." />);
  expect(screen.getByTestId("gate-button")).toBeDisabled();
  expect(screen.getByText(/keep your changes first/i)).toBeTruthy();
});
```

- [ ] **Step 6: Replace the disabled Run button**

In `Builder.tsx`, replace the disabled `Run pipeline` button with the gate control, and keep
its sentence where a reader will still find it:

```tsx
{/* **A gate, not a run.** `docs/design/execution-boundary.md` §3: a gate proves this
    artifact on public test data and takes no samplesheet; running a laboratory's data is
    Wiener's job and Wiener is not built. The two must not share a label — a control called
    *Run* that sometimes gates is how invariant 15 stops being structural. */}
<Gate draftId={draftId} />
```

Add `gate` as a fourth rail tab after `compare`, showing state, elapsed time and — on failure —
`output` in a `<pre>` with `overflow-x: auto`.

- [ ] **Step 7: Run the frontend gate**

```bash
cd frontend && npx vitest run && npx tsc -b && npm run build
```
Expected: all pass. **`tsc -b`, not `tsc --noEmit`** — the latter checks nothing here, which is
the guard fixed in 3E and recorded in the ledger.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): gate a pipeline, and the button that is not a run"
```

---

## Task 7: Walk it

**Files:** none. This task produces a journal entry.

**Why it exists:** 3E was 76 steps of green tests, and the operator found nine defects in twenty
minutes of use. `CLAUDE.md` records the gap between *the plan is done* and *the thing works*,
and the only known way to close it is to use the thing.

- [ ] **Step 1: Bring the stack up**

Run: `make dev`. Confirm `docker compose ps` shows postgres, redis, api, worker, web.

- [ ] **Step 2: Draw, keep and gate**

In the browser: draw the RNA-seq spine, press *Keep*, then *Gate* at `lint`.
Expected: the tab shows `queued`, then `running`, then `passed` within a few seconds.

- [ ] **Step 3: Read the artifact by hand**

```bash
cat .run/drafts/<draft-id>/pipeline.yml | grep -A3 '^gate'
grep -A4 'awsbatch' .run/drafts/<draft-id>/nextflow.config
```
Expected: `gate: lint`, and the three executor profiles present in a file nobody hand-wrote.

- [ ] **Step 4: Make it fail on purpose**

Gate a draft that was never kept. Expected: `failed`, with `MA0001` readable in the panel —
not a 500, and not a Nextflow error about a missing file.

- [ ] **Step 5: Time it**

Record wall-clock for `lint` and `preview` end to end. The stated budget for a request is
500ms; a *gate* has no such budget, but the **route** does — `POST .../gate` must return in
well under 500ms because it only writes a row and enqueues.

- [ ] **Step 6: Write the journal entry**

`notes/journal/2026-08-2X-the-gate.md`: what worked, what did not, every deviation from this
plan, and what a fresh reader would get wrong. Add a row to `notes/README.md`.

- [ ] **Step 7: Full verification and commit**

Run: `make verify` and `make links`
Expected: green.

---

## Pre-execution audit — 2026-08-23, A158–A170

Run against the tree before a line was written, the way 3E's was. **Thirteen findings, three
critical**, and all thirteen are corrected above rather than listed as warnings — so the plan a
reader executes is the corrected one and this table is the record of what it used to say.

**Every critical came from the same root: the plan was written against what the code
*resembles* rather than what it *is*.** Route paths, a diagnostic prefix and a `concern` value
were each plausible, wrong, and checkable in one command.

| # | Severity | Finding |
|---|---|---|
| A158 | **critical** | `MD0230` is the wrong prefix. `diagnostics.yml`'s header reserves `MD` for "Mendel's deterministic core: the three packages that may not reach the network" and gives the API `MA`. An `MD` code raised in `mendel_api` fails `test_every_code_is_owned_by_the_package_that_emits_it`. It is now `MA0001` — **the first `MA` code**, so the band table gains a line |
| A159 | **critical** | `concern: artifact` does not exist. `tools/generate_diagnostics_doc.py:106` refuses any concern outside `HEADINGS`, whose twelve keys do not include it. Now `gates` — "Gates and emission". **This is the same error 3E hit during execution** and the plan reintroduced it |
| A160 | **critical** | Every route path in the plan was wrong. `routes/build.py:28` is `APIRouter(prefix="/pipeline")`, so drafts are at `/api/pipeline/drafts/{draft_id}`, not `/api/drafts/{draft_id}`. Found by generating the OpenAPI document rather than reading decorators. Affected the routes, the tests, the client calls and the diagnostic's own `fix:` prose |
| A161 | major | The frontend calls used openapi-fetch syntax. `frontend/src/api/client.ts` is a **hand-written** wrapper exporting `get<T>(path: string)`; there is no `{ params: { path } }`. Also corrects the plan's implication that `make client` generates a client — it generates `schema.d.ts` and nothing else |
| A162 | major | A failing gate never re-stamped. `gates.of` regenerates `main.nf` and `nextflow.config` every time, so skipping the stamp on failure leaves the directory diverging from its own `pipeline.yml` — and the next `mendel emit` refuses with `MD0214`, blaming the person for a change the gate made. `_publish_verb` stamps on both paths and its comment says why |
| A163 | major | Nextflow cannot write `NXF_HOME`. The worker runs as `user: 1000:1000`, the Dockerfile has no `USER` and no `chown`, and Nextflow downloads plugins into `NXF_HOME` on first run. The first gate would fail with what reads as a Nextflow bug |
| A164 | major | Gating gates whatever was last kept, silently. Edit the graph, press *Gate*, and a green tick appears beside a canvas the verdict does not describe — A47's class. **Decided**: *Gate* is disabled while the draft is dirty, because that cannot produce a false green. Having *Gate* keep first was rejected: it changes what *Keep* means, including its refusal of an illegal graph |
| A165 | minor | `async def start_gate` ran a synchronous Postgres session on the event loop. Every other route is a plain `def`, which FastAPI already threadpools; this one had to become `async` to await the enqueue. Now `run_in_threadpool` around both blocking calls |
| A166 | minor | `coded("MD0230", f"…")` had no placeholder. Verified against ruff: F541, and `make check` runs it |
| A167 | minor | `tags=["build"]` invented a second undeclared tag. The router already supplies `tags=["pipeline"]`, which satisfies `test_every_operation_carries_a_tag`. **Pre-existing and left alone: `pipeline` is not in `main.py`'s `TAGS`**, so it renders with no description — a one-line fix that is not this plan's job |
| A168 | minor | `test_every_operation_is_named_by_hand` holds an exact dict keyed by `(path, method)`, not a list. Both entries are now written out, with A160's paths |
| A169 | minor | `k8s` is also a Nextflow config *scope*, so a profile named `k8s` setting `k8s.*` reads like a recursion. **Kept**, because `-profile k8s` is what somebody will type; the emitted comment is the mitigation |
| A170 | minor | The generated names go through `frontend/src/api/types.ts`, which exists because FastAPI splits and namespaces model names unpredictably. `GateIn` and `GateView` are declared there, not imported from `schema` at six call sites |

### What the audit did not find, and the reason it might be wrong

**Nothing was checked by running it**, because none of it is built. The three criticals were all
*static* facts — a header comment, a dict of headings, a router prefix — and static facts are
what an audit before execution can reach. 3E's execution then found nine more, every one of them
behavioural.

**A162's fix is untested by anything in this plan.** No step reverts the stamp and watches
`MD0214` fire, so it is an argument rather than a guard. If Task 7's walk has spare minutes,
gate a draft, break it on purpose and re-emit.

### Second pass — A171–A174

**A157's lesson is that an audit's own repairs need auditing**: 3E's audit produced a fix that
was itself wrong. So the corrected plan was re-read, and the re-read found four more — three of
them *in the corrections*.

| # | Severity | Finding |
|---|---|---|
| A171 | major | The plan contained `...` elisions — an undefined `_Result` in a test, and a `useGate` hook that stopped before showing the start call. The skill that produced this plan calls that a plan failure, and A160 is why it matters here specifically: **the elided line was a path**, and every path in the first draft was wrong. Both are written out |
| A172 | major | `monkeypatch.setattr(gates, "_directory", …)` in the first gate test was **inert** — `of` takes the directory as an argument and never calls that seam. The test would have passed for a reason unrelated to what it patched, which is 3E's crossing-wires test failing upward |
| A173 | minor | The corrections hedged: *"if `fires_on: [gate]` is refused, the allowed values are a closed vocabulary"*. It is `list[str]` on `DiagnosticSpec`. **A hedge in a plan is a fact somebody declined to check**, and this plan's three criticals were all facts that took one command |
| A174 | minor | `jobs._pool` had no lock, so two concurrent first requests each open a pool and the loser leaks. Now double-checked under `asyncio.Lock` |

Three of these four were introduced by the first pass's own repairs. That ratio is the argument
for the second pass, and it is the same ratio 3E saw.

---

## Self-review

**Spec coverage.** §3 (two runs) → Tasks 5 and 6. §4 (what crosses) → Task 4, which emits from
the artifact and sends nothing. §5 (what the runner supplies) → Task 1's `site.config` comments.
§6 (executor out of the artifact) → Task 1, guarded on the signature. §7 (three targets) →
Task 1. §8 (Mendel stops at the gate) → the whole plan's scope, and Task 2's decision not to
mount a Docker socket.

**Not covered, deliberately.** §2's run level is Wiener and has no task here. STUB and TEST
gates cannot run in the container until the Docker-socket question is decided; Task 2 records
that rather than deciding it. `Gate.PREVIEW` needs `stub_data` params, which `materialise_stub_data`
supplies — but only `STUB` calls it today, so **if PREVIEW fails on a null parameter in Task 7,
that is the finding**, and the fix is one condition in `gates.of`.

**Type consistency.** `GateView` is the one shape crossing service → route → client.
`gates.request` / `gates.execute` / `gates.read` / `gates.of` are used with those exact names in
Tasks 4, 5 and 6. `run_gate_job` is the ARQ function name in both `worker.py` and the
`jobs.enqueue` call.

**Estimate.** Tasks 1–6 are roughly a day if nothing surprises. **Task 1 Step 8 is where it will
run long** — regenerating recorded digests has broken more tests than expected every time
emission changed. Per `CLAUDE.md`: if it goes past double, stop and say the new number rather
than pushing through.
