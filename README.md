# Comeni Labs

Deterministic bioinformatics pipeline construction.

A researcher describes an analysis; **Mendel** resolves it into a Nextflow pipeline where every
decision traces to a constraint, a convention, a measurement, or an explicitly flagged judgement
call.

> **Same goal in → same pipeline out, and nothing was guessed silently.**

That claim is the whole point. A chat window will produce a plausible-looking `nf-core` pipeline
in minutes and give you no basis for judging whether its tool choices, parameters or data
assumptions are defensible. Mendel produces the same pipeline every time and tells you which
parts it was unsure about.

---

## Intended purpose

> Mendel constructs and documents analysis pipelines. It is not a diagnostic device and produces
> no diagnostic result. Pipelines must be validated by the laboratory before clinical use.

This sentence is load-bearing rather than boilerplate, and it also appears as a header comment in
every pipeline Mendel emits. Under IVDR, device status follows the intended purpose its
manufacturer states: a laboratory using Mendel to build a pipeline it then validates is the
manufacturer of its own in-house device, and we are a tool — the same relationship BWA, GATK and
Nextflow already have with the diagnostic pipelines they appear in.

We claim no compliance with IVDR, CLIA, CAP or ISO 15189, and no software can — those attach to a
laboratory's processes. What Mendel supplies is the documentation substrate those processes
require.

**Mendel does not receive patient data.** Not "anonymises" — genetic data are not reliably
anonymisable, and pseudonymised data remains personal data under GDPR Article 9. A `Goal` holds
type identifiers, states and declared measurements: a shape, not data. There is no field for a
filename, a path or a sample identifier, and a test asserts there is nowhere to put one.

---

## Status

**Plans 1 and 2 are complete.** A typed goal becomes a runnable RNA-seq pipeline with no AI
involved anywhere. 165 tests, and `-stub-run` executes the whole DAG green against real `nf-core`
modules.

Built:

- `comeni-core` — contracts, closed type vocabularies, declared measurements, the pipeline IR,
  the layered registry
- `mendel-resolver` — the four-tier ladder, backward-chaining router, validated tier-3 decision
  tables, module pinning, ports that accept alternatives
- `mendel-compiler` — IR to Nextflow DSL2, validation gates, `mendel build` and `mendel profile`

[`ARCHITECTURE.md`](ARCHITECTURE.md) describes how those fit together, written against the types
that exist rather than the ones a plan predicted.

Not built yet, and named so nothing here reads as more finished than it is: the AI adapters and
the contract forge (Plan 2), the FastAPI surface and React dashboard (Plan 3), and pipeline
publication and lockfiles (Plan 1.7).

---

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/), Python 3.12+, and — for the `stub` gate — Nextflow
and Docker.

```bash
uv sync
uv run pytest -v
uv run mendel build --goal examples/rnaseq-goal.yml --out build/
```

That writes `build/main.nf`, `build/nextflow.config` and `build/pipeline.ir.json`, and prints
what needs a human:

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

To execute the whole graph with dummy outputs — about a minute, and several minutes the first
time while containers pull:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

Rules reason about *measured* properties of the data, so there is a verb for measuring them.
`mendel profile` emits a pipeline that measures what this registry knows how to measure, plus a
`profile.yml` recording which module produces each value — with `value: null`, because the
pipeline has been emitted and not run:

```bash
uv run mendel profile --have fastq.reads --out profile-build/
```

```
profiling for: read_length
  NOT MEASURED  n_samples, paired, strandedness — declared, but no contract in this registry produces them
```

The laboratory runs that pipeline, fills the values in, and the same file goes back into a goal's
`profile:` block. Mendel never sees the data.

A laboratory's own contracts, rules, types and measurements stack over the public ones. A
registry layer is a directory holding `contracts/`, `rules/`, `vocabularies/` and
`measurements/`; later layers win:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry/ --registry ./lab-registry --out build/
```

---

## The four tiers

Every module choice and every parameter exits at exactly one tier and carries it forever.

| Tier | Fires when | Review | UI |
|---|---|---|---|
| 1 structural | no choice exists — the inputs force it | none | silent |
| 2 convention | a documented default exists | none | green |
| 3 data-profiled | a declared rule matched measured data | advisory | **yellow** |
| 4 ambiguous | no rule matched | required | **red** |

Tier 3 is yellow rather than silent on purpose. A rule match is only as good as the rule *and*
the measurement behind it: if the profiler misreads strandedness, the rule fires correctly on
wrong input and produces a confidently wrong pipeline. Yellow means *the machinery worked, check
the premise* — exactly the failure a biologist can catch and the software cannot.

Tier 4 is always flagged, even at high confidence. That is the honesty mechanism, and the
difference from a chat window.

---

## How it works

Five stages, each a pure function:

```
Goal (YAML) → RoutePlan → PipelineIR → main.nf + nextflow.config → GateResult
```

The router chains **backwards** from what you want. To reach `counts.matrix` it finds a producer,
discovers that producer needs a coordinate-sorted BAM, finds a producer for *that*, and so on
until the goal's inputs satisfy the requirement. A tie between candidates is ambiguity, not a coin
flip — it demotes to tier 4 and asks a human.

The semantic layer is what makes this possible. `nf-core`'s `meta.yml` declares outputs as
`type: file` with a filename pattern, so a sorted BAM and an unsorted one are indistinguishable
and "sorted" exists only in an English sentence. Mendel's contracts add the missing part: closed
state vocabularies a router can actually prove a connection against.

---

## Distribution

Open source and self-hostable. **Self-hosted is not a degraded tier** — same registry, same
resolver, byte-identical output. Tiers 1 to 3 need no model at all, so a Mendel with no provider
configured still ingests a goal, routes it, resolves it and emits Nextflow; tier 4 flags instead
of guessing, which is behaviour the product promises anyway.

The public registry lives in its own repository under CC-BY-4.0. What ships here under
`examples/` is hand-written test data, not a registry.

---

## Licences

- **Code:** Apache-2.0 — see [`LICENSE`](LICENSE)
- **Registry data** (`contracts/`, `rules/`, `vocabularies/`): CC-BY-4.0 — see
  [`LICENSE-DATA`](LICENSE-DATA). Contracts and rules cite papers; attribution is the currency of
  the field.
- **Vendored `nf-core` modules** under `vendor/` retain their own licences and notices.

---

## Documentation

[**`docs/`**](docs/) is the index. In short:

| You want | Read |
|---|---|
| to build your first pipeline | [`docs/guides/getting-started.md`](docs/guides/getting-started.md) |
| to teach Mendel a tool it does not know | [`docs/guides/writing-a-contract.md`](docs/guides/writing-a-contract.md) |
| a choice to depend on your data | [`docs/guides/writing-a-rule.md`](docs/guides/writing-a-rule.md) |
| to look up a field or a flag | [`docs/reference/`](docs/reference/) |
| to know why it works this way | [`docs/concepts/`](docs/concepts/) |
| to change the code | [`ARCHITECTURE.md`](ARCHITECTURE.md), then [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| the design records and what was rejected | [`docs/design/`](docs/design/) |

## The audit

[`docs/internal/audits/2026-08-03-plan-1-audit.md`](docs/internal/audits/2026-08-03-plan-1-audit.md)
is linked deliberately. Three guards claimed to enforce the properties this project sells, and an
independent reviewer broke all three on first attempt — each the same way, by checking the surface
it was written against and stopping at the first boundary. One fell to four lines:

```python
import urllib.request, socket, http.client
importlib.import_module("httpx").post(...)
__import__("openai").OpenAI()
```

All four defects are closed and the guards are the shape they are because of it. Keeping the
record public is cheaper than the alternative.

## Contributing

Registry data — a contract, a rule, a measurement — is the most valuable contribution and needs
no Python. See [`CONTRIBUTING.md`](CONTRIBUTING.md), and
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), which applies everywhere in this project.

Security and privacy reports go through [`SECURITY.md`](SECURITY.md) rather than a public issue.
A hole in the egress boundary, or a way to get patient data into a `Goal`, is a security issue.
