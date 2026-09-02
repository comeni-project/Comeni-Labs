# One source for a diagnostic code

**Written 2026-08-16 against the tree at `0b5ae99`.** The operator's question was whether
`diagnostics.md` is generated and whether a code has one source of truth that moves when the code
moves. The document half was already true. The emission half was not.

## 1. What is already right

`comeni_core/diagnostics.yml` is the only place a code is declared. `REGISTRY` loads it at
import; `tools/generate_diagnostics_doc.py` renders **the whole of**
`docs/reference/diagnostics.md` from it, header included, and `make docs --check` runs on every
pull request and again nightly. The page carries `<!-- generated … do not edit -->` and refuses a
hand-edited heading. Nothing about the *document* needs changing.

Two consumers already validate against the registry: `Diagnostic.code` has a field validator, and
`mendel explain` refuses an unknown code. `Diagnostic`'s docstring states the principle this spec
extends:

> *"The alternative was a test asserting every emittable code has an explanation, and a test can
> only find codes on paths it executes. This makes an undeclared code unrepresentable —
> invariant 7's shape, a closed vocabulary, applied to diagnostics."*

## 2. What is wrong

**Twelve of ninety emission sites are validated. The other seventy-eight are string literals.**

```python
raise ValueError(f"MD0001: {where} in layer {layer.path} is not valid YAML.\n  {error}")
```

That is a string. Nothing connects `MD0001` to the registry. So a typo ships, a `raise` outliving
its registry entry ships, and a code invented at the call site ships — each of them printing to a
user, each failing `mendel explain`, and none of them appearing in the generated page.

All sixty codes currently in source do exist in the registry. **It is correct by vigilance, not
by construction**, which is the state this repository does not otherwise accept.

**The nightly proved the cost of the same defect class on the same day.** Two spellings of one
assertion — a shell glob for `*.featureCounts.txt` and a pytest test accepting `.txt` or `.tsv` —
drifted, and the wrong one ran first and skipped the right one, red every night for five days
with nobody notified. A second spelling of one truth is the defect; diagnostics have seventy-eight
of them.

## 3. The shape: one function, every emission through it

```python
def coded(code: str, message: str) -> str:
    """`"MD0001: …"`, with the code checked against the registry."""
```

Call sites become:

```python
raise ValueError(coded("MD0001", f"{where} in layer {layer.path} is not valid YAML.\n  {error}"))
print(coded("MD0202", line), file=sys.stderr)
```

**Why a string builder rather than an exception factory.** Twelve distinct exception types carry
codes today — `ValueError` at sixty-five, `RuleValidationError` at nineteen, and ten others. A
factory returning an exception would have to take the type as an argument, which reads worse than
the `raise` it replaces, and it would not serve the emissions that are *not* raises at all: the
CLI prints `f"mendel: MD0210: …"`, and `MD0202` is a report line. One function that builds the
string serves every site, changes no exception class, and keeps `raise ValueError` visible where
control flow is decided.

**Validation is at call time, which is the error path.** That is weaker than import time and it is
not the whole answer — §4 is. What it buys is that a bad code cannot reach a user: the emission
raises `UnknownDiagnosticError` instead, loudly, naming the code and the known set.

## 4. Every declared code is raised, and every raised code is declared

Once every emission goes through `coded()` or `Diagnostic(code=)`, both directions are **derivable
from two patterns** rather than from a regex over prose:

| direction | check |
|---|---|
| a code in the source must be declared | scan for `coded("…")` and `code="…"`; every literal must be in `REGISTRY` |
| a declared code must be emitted somewhere | the same scan; every `REGISTRY` key must appear |

The second is the operator's decision of 2026-08-16, and it is **satisfiable today**: all sixty
codes belong to `core`, `compiler` or `resolver`, and none is declared for the forge or the API,
which do not exist. A reserved *band* stays legal — `MD0400`–`MD0499` is a comment, not an entry.
Reserving a *code* stops being legal, and that is the point: a code nothing raises is a promise
in a document that no code keeps.

**This replaces `UNLOCATABLE`.** That list exists only because three emission shapes had to be
matched by pattern; with one shape there is nothing to exempt, and `MD0202` — its sole entry —
becomes locatable by going through `coded()` like everything else.

## 5. What this costs, stated plainly

**Seventy-eight call sites across three packages**, concentrated in twelve files — `validate.py`
(17), `pipeline.py` (12), `artifact_verbs.py` (7). Mechanical, and the messages themselves do not
change.

**One output format does change.** `MD0202` is currently printed as `f"  MD0202  {line}"` — two
spaces, aligned as a report rather than a refusal. Through `coded()` it becomes `MD0202: {line}`.
That is a visible change to `upgrade`'s output and is called out here rather than discovered in a
diff.

**A pure package gains a runtime lookup on the error path.** `coded()` is a dict membership test
in `comeni-core`, which every other package already imports. No new dependency, nothing reaching
the network, invariant 1 untouched.

## 6. What is not in scope

- **No change to the generated document**, which already works.
- **No change to `Diagnostic`**, whose validator is the pattern being extended, not replaced.
- **No new codes**, and no renumbering. A code is never renumbered once published.
- **No exception hierarchy.** Making every coded refusal a `DiagnosticError` subclass is a
  larger design about how callers catch things, and it is not what was asked.

## 7. Success criterion

Every emission of a code goes through `coded()` or `Diagnostic(code=)`. A typo'd code raises at
the emission rather than printing. A code declared and never emitted fails a test, and so does a
code emitted and never declared. `UNLOCATABLE` is gone. `docs/reference/diagnostics.md` is
byte-identical, because none of this changes what a code *says*.
