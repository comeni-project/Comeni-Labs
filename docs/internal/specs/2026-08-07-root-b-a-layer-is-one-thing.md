# Root B — a layer is one thing, and it stacks one way

**Spec, 2026-08-07.** Closes A22, A23, A24, A25, A26, A35. Root B in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `bc2dbd1`.

---

## The problem

Invariant 11 talks about layers. **The code has no such thing.** `layers.load` hand-assembles
four loaders and passes `Path` around; a layer has no identity (a name recomputed by
`layer_name(path)` at three call sites), no position (implicit in list order, lost before
provenance is recorded), and no contents (each loader discovers its own slice, so nothing knows
what a layer holds as a whole).

What each loader independently decides — read from the source, not inferred:

| | contracts | rules | vocabularies | measurements |
|---|---|---|---|---|
| find files | `rglob("*.yml")` | `glob("*.yml")` | `glob("*.yml")` | `glob("*.yml")` |
| key an entry | parsed `id` field | `decides.key()` | filename stem | filename stem |
| missing directory | caller pre-filters | `if not exists: continue` | caller pre-filters | `if not exists` |
| what stacking means | shadow by module key, **delete** displaced | last-wins | last-wins per sub-key | last-wins, **or `add_values` extends** |
| records displacement | `ShadowRecord` | `displaced_layer` dict | **no** | **no** |
| knows its layer's name | yes | yes | **no** | **no** |

Six axes, four implementations, no two agreeing on all six. Every finding in this cluster is a
cell in that table:

- **A23, A24** — the two "no" columns. An overlay measurement flipped strandedness from `reverse`
  to `forward` in the emitted `meta` map, and an overlay vocabulary replaced `params.input` with
  hardcoded laboratory paths. Both silent.
- **A25** — identity is a name, and names collide. The lockfile's own docstring says this is a
  day-one collision.
- **A26** — row one. Three loaders are non-recursive and all four ignore `.yaml`, so an overlay
  contract renamed `.yaml` vanished and the build routed on the base layer, exit 0.
- **A35** *(new, found while writing this spec)* — "what stacking means" differs *within* the
  vocabulary loader. `types[type_id] = frozenset(...)` replaces unconditionally while
  `entry_channel` and `test_data` replace only when present. An overlay declaring
  `states: [phix_removed]` deleted `trimmed`, `deduplicated` and `subsampled`; the build then
  failed with `UnknownStateError: 'trimmed' is not a declared state` — an unhandled traceback,
  exit 1, naming the *base contract* rather than the overlay that removed the state. The
  loader's own docstring promises the opposite: *"A laboratory adding a state … needs types to
  stack the way contracts already do."*
- **A22** — the subtlest. `RuleTable` records `displaced_layer` correctly and `router._choose`
  never reads it, so a rule-pinned aligner reroute is unreported *and the IR asserts
  `from_layer: registry`* — the opposite of what happened. **Recording provenance is not enough
  if consulting it is optional.**

---

## The design

### 1. `Layer` becomes a value

```python
class Layer(BaseModel):
    """A layer as a value, not a path passed around."""
    path: Path
    name: LayerName   # from registry.yml, or the basename. For rendering only.
    index: int        # position in the stack, lowest first. This is identity.
```

**Identity is the index; the name is a label.** That closes A25 by construction: nothing can key
displacement on a name, because displacement is recorded against an index. `layer_name()` is
called once, when the stack is built, instead of at three call sites.

### 2. One `stack()`, parameterised only by what genuinely differs

```python
class DeclaredKind(StrEnum):
    CONTRACTS = "contracts"
    RULES = "rules"
    VOCABULARIES = "vocabularies"
    MEASUREMENTS = "measurements"


class Kind(Generic[K, T]):
    """How one sort of declared data is found, parsed, keyed and merged."""
    which: DeclaredKind
    parse: Callable[[Path], Iterable[T]]      # one file -> zero or more entries
    key: Callable[[T], K]                     # storage key
    group: Callable[[T], K]                   # displacement key; defaults to `key`
    policy: Policy                            # REPLACE | MERGE | DELETE_GROUP


def stack(layers: Sequence[Layer], kind: Kind[K, T]) -> Stacked[K, T]: ...
```

The mechanism owns everything the table showed diverging: recursion, `*.yml` **and** `*.yaml`, a
missing subdirectory, stack order, and recording what displaced what. A kind declares only its
parse, its keys and its policy.

```python
class Stacked(BaseModel, Generic[K, T]):
    entries: dict[K, T]
    origin: dict[K, int]                 # key -> the layer index that supplied it
    displaced: list[Displacement]
```

### 3. One `Displacement`, for all four kinds

```python
class Displacement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: DeclaredKind
    key: Subject
    winning_layer: LayerName
    displaced_layer: LayerName
    displaced_keys: list[ContractId] = []   # contracts only: full ids removed
```

Every field is a `StrEnum`, a marked string, or a list of marked strings — so it satisfies root
A's leaf allowlist and may cross a door. Written that way deliberately; the two specs must not
fight.

### 4. Provenance is carried, not consulted — the A22 fix

Recording is not the problem; *remembering to read* is. So the pin carries it:

```python
class Pin(BaseModel):
    contract_id: ContractId
    from_layer: LayerName
    displaced_layer: LayerName | None
    decision: Decision
    row: DecisionRow
```

`RuleTable.producer_for()` returns a `Pin` instead of a bare tuple, and **`RouteStep.from_layer`
loses its default**. A caller cannot construct a route step without saying where the selection
came from, so `router._choose` cannot repeat A22 — not because it is told to read the fact, but
because it cannot build the result without it.

This is Plan 1.8's own lesson, which nine of thirteen fixes already applied: a guard in a caller
is a guard the next caller forgets.

### 5. Displaced declarations reach the artifact

`PipelineIR.shadowed: list[ShadowRecord]` becomes
`PipelineIR.displaced: list[Displacement]`, covering all four kinds. `ShadowRecord` is deleted
rather than kept as a projection — an abstraction with one kind opted out decays back into four
loaders, and nothing is published yet, so the artifact shape is still free to move.

`mendel build` prints them in the existing `OVERLAY` block. Measurements and vocabularies finally
have somewhere to be reported: they have no `IRNode` to hang off, which is why A23 and A24 had
nowhere to go.

### 6. Merge policy becomes explicit and consistent — the A35 fix

Measurements already have an explicit extension (`add_values`). Vocabularies get the same shape:
**default is replace; `add_states` extends.** A lab adding a state writes `add_states`, and an
overlay declaring `states:` is understood to be replacing the set deliberately.

This makes one convention across kinds instead of two behaviours inside one loader. The
vocabulary docstring's promise is then either true or explicitly opted into.

### 7. Every file in a layer is claimed

`stack()` records which files it read. `layers.load` asserts, after all four kinds, that every
`*.yml`/`*.yaml` under a layer's four subdirectories was claimed by exactly one kind, and
**raises naming the file** otherwise. That is the load-bearing half of A26: an overlay that does
nothing must not look like an overlay that worked.

---

## Ordering between kinds stays explicit

`stack()` handles one kind. `layers.load` keeps orchestrating, in the order the dependencies
require: **measurements → vocabulary → contracts → rules.** Contracts parse against a
`Vocabulary`; rules validate against a `Registry`. The mechanism must not pretend the kinds are
independent, and the existing docstring in `layers.py` already says why loading them by hand
fails inside a contract rather than at the caller.

---

## Verification

Root I applies. Each guard added here is reverted and watched failing before its task is done.

| probe | expected |
|---|---|
| overlay measurement changing `strandedness` translation | reported as a `Displacement`; emitted `meta` still traceable (A23) |
| overlay vocabulary replacing `entry_channel` | reported (A24) |
| overlay rule pinning a producer | reported, and `selection.from_layer` names **the layer whose rule decided** (A22) |
| two layers with the same `LayerName` | both displacement records survive (A25) |
| a `.yaml` contract in an overlay | loaded, routes (A26) |
| a vocabulary file nested one directory deep | loaded (A26) |
| an unrecognised `.yml` under a layer subdirectory | **raises, naming the file** (A26) |
| overlay declaring `states:` without `add_states` | replaces, and the *displacement* is reported rather than surfacing as `UnknownStateError` from an unrelated file (A35) |
| overlay declaring `add_states:` | extends; base states survive (A35) |
| single-layer build | **no `Displacement` at all**, byte-identical emission |

The last row is the regression that matters most: a lab with no overlay must see no change
whatsoever, and `make verify` must stay green — including the counts matrix, since A23's
mechanism is exactly what `tests/test_counts.py` asserts.

---

## Blast radius

Larger than root A, and the largest in the plan.

- **New:** `comeni_core/layered.py` (`Layer`, `Kind`, `Policy`, `Stacked`, `Displacement`,
  `stack`).
- **Rewritten:** `Registry.load`, `Vocabulary.load`, `MeasurementRegistry.load`,
  `RuleTable.load` — each becomes a `Kind` plus a thin constructor.
- **Changed:** `mendel_resolver/layers.py` (builds `Layer` values, asserts file coverage),
  `router.py` (`RouteStep.from_layer` required; `_choose` destructures a `Pin`),
  `resolve.py`, `ir.py` (`shadowed` → `displaced`), `mendel_compiler/cli.py` (the `OVERLAY`
  block), `lockfile.py` (`drift_against` reads layers positionally).
- **Deleted:** `ShadowRecord`.
- **Docs:** invariant 11 names `ShadowRecord`; CLAUDE.md and `ARCHITECTURE.md` both need updating.

`Lockfile.drift_against` is where care is needed: it is the site of A21-shaped guard drift, and
its guard was inert once already (`8dbde51`). Revert it deliberately as part of this work.

---

## What this spec does not cover

- **Root G's YAML strictness.** `stack()` owns *which files* are read; whether a file can be read
  two ways (duplicate keys, A31) is root G. They meet in the same function and are still separate
  decisions.
- **Root C.** `entry_channel` remains unbounded Groovy emitted verbatim — deliberately, so a lab
  can bring its own type. A24 is closed by *reporting* its replacement, not by forbidding it.
- **Root E.** A displaced key is still a marked string, not a validated identifier.
