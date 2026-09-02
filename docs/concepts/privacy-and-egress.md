# Privacy and the egress boundary

Clinical laboratories are a target user rather than a later market, so this is a design
constraint rather than a policy page.

Two claims, both enforced by tests.

## 1. Mendel does not receive patient data

Not "anonymises". Not "de-identifies". **Does not receive.**

A `Goal` holds type identifiers, states and declared measurements — a *shape*. "Paired,
150bp, reverse-stranded, twelve samples" is true of thousands of studies and identifies
nobody. There is no field for a filename, a path or a sample identifier, and
`extra="forbid"` on every model means an unrecognised key is a loud error rather than a
quietly carried payload.

Sample identity enters at run time, in your environment, through the `params.input`
placeholder the emitted pipeline declares. It never reaches Mendel's process.

### Why not "anonymised"

Genetic data are not reliably anonymisable, and pseudonymised data remains personal data
under GDPR Article 9. Claiming anonymisation would be both wrong and weaker. Minimisation
by non-receipt is the accurate claim and the stronger one: there is no data to protect
because none arrived.

### Why scrubbing was rejected

Safe Harbor requires all 18 identifier classes to be gone. NLP de-identification leaves
false negatives, and — worse — it fails *silently*, producing text that looks clean.
Pattern matching survives only inverted, in the `guarded` profile, where a suspicious
payload halts the send and asks a human rather than quietly editing it.

### Where the guard lives

`packages/mendel-resolver/tests/test_rules.py` and `tests/test_end_to_end.py`.

When measurements became declared data, the model stopped being able to refuse an
undeclared key — so the guard **moved rather than weakened**:
`MeasurementRegistry.profile()` is the only validating constructor,
`tests/test_construction.py` enforces that nothing else builds a profile, and
`mendel build` re-routes every goal's profile through it. Delete that one call and
`profile: {sample_name: SILVA_biopsy_01}` builds cleanly — which is how the guard was
verified.

## 2. Data leaves through four doors and no others

| Door | Payload | Carries |
|---|---|---|
| goal extraction | `PromptRequest` | your prompt — the single taint source |
| tier-4 resolution | `AmbiguityRequest` | node id, subject, candidates, states |
| compiler repair | `RepairRequest` | the IR and typed failure facts |
| publication | `Pipeline` | the pipeline file: steps, settings, decisions, provenance |

Every payload is a declared type. No payload may carry `Any`, a mapping, or a plain `str`.
**Seven fields across the entire surface may hold free text**, and they are named literally in
`tests/test_egress.py`: the prompt, a gate's tool message, and five `reason` fields carrying
the prose that explains a choice.

That number has only ever gone up by *refactor* — splitting a decision record into three
kinds, and swapping the publication payload — never by a new kind of string crossing. The
literal list is what makes somebody check which of the two it was.

Publication carries the artifact itself. `pipeline.yml` is what a person reads before
publishing, so the thing reviewed and the thing sent are one document rather than two that can
disagree.

Widening that boundary means editing a file whose contents say *these are all the ways data
leaves this building* — which is the moment a person should be thinking, and the test is
what makes them.

Publication is the door with no undo. A leaked prompt in a model call is an incident; a
leaked prompt in a signed public registry is in every clone's history permanently.

### Why no mapping

`dict[MeasurementId, MeasurementValue]` passes every other rule — the key is an annotated
newtype, so the bare-`str` check does not fire — and is still unsafe, because nothing
checks the key was ever *declared*. A payload carrying `{"patient_id": "4471023"}` would
type-check perfectly. Payloads carry lists of declared records instead. Subtlety is what
failed the last time.

## The three protection profiles

Three ladders exist in this project and must never be conflated: the four **resolution
tiers**, the three **visibility tiers** (private / published / curated), and these three
**protection profiles**.

| | `open` | `guarded` (default) | `sealed` |
|---|---|---|---|
| prompt door | sends | shows the payload, waits | closed — typed goals only |
| `GateFailure.tool_message` | included | `None` | `None` |
| repair | proposes and applies | proposes and applies | proposes only |
| tier 4 | flags | flags | **blocks the build** |
| attribution | optional | when available | required |
| reference pinning | tags | tags | digests required |

`guarded` is the default because the unconfigured install is the one most likely to exist.

**Never configurable, at any level:** the four doors, typed payloads, a record per
crossing, tier 4 always flagged, typed-only publish bundles, and no patient data received.

Profiles arrive with the AI adapters. Today there is no AI path at all, so every build is
already the strictest lane.

## Telemetry

Opt-in and off by default — and structural rather than promised. `comeni-core`,
`mendel-resolver` and `mendel-compiler` are under a **closed import allowlist** enforced by
`tests/test_purity.py`, covering the standard library (where the transports actually live)
and the dynamic import forms. They cannot open a socket, so telemetry can only live in the
API package.

An earlier version of that guard was defeated with four lines:

```python
import urllib.request, socket, http.client
importlib.import_module("httpx").post(...)
__import__("openai").OpenAI()
```

All of it passed, because the banned list held only third-party names and the walk looked
only at import statements. Both are fixed.

## We are a tool; the laboratory is the manufacturer

We claim no compliance with IVDR, CLIA, CAP or ISO 15189 — those attach to a laboratory's
processes, and no software can carry them for you. Mendel supplies the documentation
substrate those processes require.

"Curated" in this project means reference material a laboratory validates, never a
validated test. Distributing a validated test across legal entities would forfeit the IVDR
Article 5(5) in-house exemption.

## Reporting a hole

If you find a way through the boundary, see [`SECURITY.md`](../../.github/SECURITY.md). A test that
demonstrates it is the most useful possible report.

Full rationale: [`docs/design/clinical-data-protection.md`](../design/clinical-data-protection.md).
