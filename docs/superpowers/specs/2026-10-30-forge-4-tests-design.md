# Forge MVP 4 — tool tests, run as Wiener runs (#365)

Status: design, awaiting the operator's approval. Parent: #360. Builds on forging (#364).

**Operator's decisions (2026-10-30):** Mendel submits forge tests to Wiener itself, through one
narrow interface, rather than the browser carrying them; the pages are built from the issue,
because board 4 could not be read, and are compared with it later.

## 1. What this adds

A sixth piece, **Tests**, drafted by the AI from nf-core's own `main.nf.test` and approved like
any other. Once the draft layer is assembled, the person chooses **Run its tests**. The forge
builds a small pipeline from the contract, submits it to Wiener and reads the result.

**Green** means the run succeeded and every declared output exists in its declared format
(operator, MVP design). It proves our wiring and parameters run; it does not prove the analysis
is correct, and a page must not say otherwise.

## 2. The boundary with Wiener

This narrows `execution-boundary.md` §9's rejection of a Mendel→Wiener API, for one purpose. That
rejection gave two reasons: Wiener did not exist, and a hosted instance would gain what a
self-hosted one lacks. Neither applies now. The builder's Run button is unchanged: **the browser
stays the courier for anything a laboratory runs**, and non-receipt of patient data stays
structural.

```python
class TestRunner(Protocol):
    def submit(self, bundle: bytes, name: str, params: dict) -> str: ...   # the run id
    def state(self, run_id: str) -> str: ...
    def results(self, run_id: str) -> list[str]: ...                       # published paths
```

- The interface is in `mendel-forge`; `WienerRunner` is in `mendel-api`, over HTTP. A merged
  service later replaces this one class. Tests use a fake that records calls.
- **Only the forge's test job holds one.** A guard fails if anything else in `mendel-api` imports
  it, so this cannot grow into a second way to run a laboratory's pipeline.
- What crosses: the emitted test pipeline, and URLs of public `nf-core/test-datasets` files.
- Settings: `MENDEL_WIENER_URL` and `MENDEL_WIENER_TOKEN` (Wiener's bearer token, never logged,
  shown or sent to a model). Unset, tests show as unavailable and say why; forging still works up
  to assembly.

## 3. A test

An item `tests:test:<name>`, written to `tools/<id>/tests/<name>.yml` in the draft layer:

```yaml
declares: test
contract: nf-core/quast@5.3.0
name: sarscov2-ref
data_commit: <test-datasets commit>
inputs:
  consensus: [genomics/sarscov2/illumina/fasta/contigs.fasta]
  fasta: [genomics/sarscov2/genome/genome.fasta.gz]
setup: []            # registry tools run first, each output feeding a port
params: {}           # only names the contract declares
expect:
  - {port: tsv, pattern: "*.tsv"}
```

- **Inputs are paths inside `test-datasets`, never URLs.** A model cannot name an arbitrary host
  for Nextflow to download from. The path has a grammar; the engine builds the URL.
- **`data_commit` is the engine's, not the AI's:** read at sync with `git ls-remote` on the
  `modules` branch and stamped at assembly, because a dataset that moves is one a result cannot be
  compared against.
- `expect` patterns come from the module's `meta.yml`, already parsed, and every produced port
  must be covered or carry a stated reason.
- `setup` steps name registry tools (design answer 7), or a pending draft's. Ready-made inputs
  are preferred.

`check_items` refuses an unknown port, parameter or setup tool, as it does for the other pieces.
`tests` depends on `contract` and `parameters`. A tool may have several tests; one is required.

## 4. Building and running

- **`build_test_pipeline(test, stack)`** makes the IR directly: one node per setup step and one
  for the tool, edges between them, direct entry parameters. It then calls `Pipeline.of`, `emit`
  and `emit_config`. **It does not go through routing:** the test is of this tool, and the rules
  must not choose another.
- **The flow:** `assembled → testing → tested`, and back to `assembled` on a failure. Any command
  demotes to `reviewing`, as now. A tested adaptation stays visible as pending vocabulary.
- **`forge_test_run`** records the test, the digest of the draft layer, the Wiener run id and the
  outcome. **Green counts only for the digest it ran against.**
- **Polling is a worker cron, every 30 seconds**, over open rows, not a job that sleeps, so a
  restart loses nothing and an idle stack does no work. A run with no answer for an hour fails
  with a reason.

## 5. The pages

The Tests chip becomes a real piece. The assembled panel gains **Run its tests**, replaced while
running by each test's state, then its outcome, what was missing, and a link to the run in Wiener.
A failure is shown, not hidden; the person fixes it through the chat or by hand and assembles
again. Wording says a green test shows the tool runs, not that its results are correct. Tested
at 1440 and 390 in a browser once the stack can run.

## 6. The registry

- A `ToolTest` shape in `comeni-core`, read by the layer loader so a malformed test refuses to
  load; `mendel lint` learns `tests/`; the tool page lists them.
- The registry repository's `ENGINE_REF` moves to a commit that knows this. It lands in a writable
  checkout of `comeni-registry` with MVP 5, before the first forge pull request.

## 7. Not in this MVP

- **Tests for the ten existing tools.** The issue asks for them. Writing them needs nf-test files
  and each needs a real run to mean anything, so they follow once the machine can take real runs.
  **MVP 4 is not finished until they exist.**
- **A real Wiener run.** Built and tested against the fake; the first real run is walked with
  #412. A live run may change `WienerRunner` or the format check.
- Comparing outputs against nf-core's snapshots: the operator's definition of green is existence
  and format.

## 8. Costs and risks

- A second caller of Wiener's API: its routes become a contract with a server client, not only
  the browser.
- `mendel-worker` gains Wiener's token, and that token permits running code. It stays in the
  worker's environment only, not the API's.
- A model-drafted test spec is data the engine turns into a pipeline. Everything in §3 that
  reaches Nextflow is validated, and the emitter's literal rendering is the second wall.
- A pattern check proves a name, not a format's contents. That is the definition agreed, and the
  page says what was checked.
