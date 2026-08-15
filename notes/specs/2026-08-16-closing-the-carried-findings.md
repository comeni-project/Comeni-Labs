# Closing the carried findings — #48, #49, A130, A36

**Written 2026-08-16 against the tree at `b023d2c`.** Four items, closed before Plan 2 by the
operator's decision. A14 is explicitly **not** in scope: it is open-ended revert-and-watch work,
not a fix.

Two of the four are small and two are design. They land in one branch because three of them touch
the same question from different sides — *what does the artifact say about who decided a thing,
and can a reader believe it*.

## 1. #48 — a tier-4 setting's reason goes stale the moment it is answered

**What happens.** Answering a tier-4 question means writing `human_override` and
`override_reason` into `decisions:` and setting the setting's `value:`. The setting's own
`why.reason` goes on reading *"no rule covered 'seq_platform'; selected the first of 1 candidates
without judgement — please review"* until the next `upgrade` propagates the override. `emit`
accepts it at exit 0.

**Why `MD0223` is blind to it.** `stale_reasons()` skips any setting whose `why.for_value` is
`None`, on the stated grounds that *"a file written before 1.14 has no such field, and absence is
not disagreement"*. A tier-4 value nothing resolved *also* has `for_value: null`. The one case
where a human is most likely to be editing a value is the one case the check cannot see.

**The fix, and why it is narrow.** Fire when all three hold: `for_value` is `None`, the setting's
tier is 4, and the decision for that key carries a `human_override`. Pre-1.14 files stay exempt
without a special case — they are `version: 1`, and `predates_schema()` already suppresses the
whole family for them. The third condition is what makes it a real check rather than a nag: an
*unanswered* tier-4 setting is supposed to say "please review", and must not be flagged for it.

**The message must say what to write**, not merely that something is wrong: the reason belongs in
`override_reason`, and the setting's `why.reason` should say the override answered it.

## 2. #49 — the loading stage refuses with a Pydantic traceback

**`MD0000`–`MD0099` is reserved for "loading declared registry data" and is empty.** Every other
stage refuses with a code, a subject and a fix. Loading refuses with `ValidationError`, which
names a Python class and a field path — not a file, and not what to write instead.

**Six codes, chosen from the failures the loaders can actually produce**, not from imagination:

| code | says |
|---|---|
| `MD0001` | a declared file is not valid YAML |
| `MD0002` | a declared file is in the wrong kind's directory |
| `MD0003` | a declared file is missing a required field, or carries an undeclared one |
| `MD0004` | a layer has no `registry.yml`, or its manifest disagrees with what it holds |
| `MD0005` | a vocabulary state is used but never declared |
| `MD0006` | a role is named by a rule or a contract and filled by nothing in any loaded layer |

**`stack()` is where most of this belongs**, because invariant 11 says every kind loads through
it — one place rather than five. `MD0005` and `MD0006` are cross-kind and belong in
`layers.load()`, which is the function that already exists to make the load *order* a fact rather
than a convention.

**Each must name the file and the layer.** The whole complaint is that a Pydantic error names a
model; a code that named only a model would be the same defect wearing a number.

**What this does not do:** it does not replace Pydantic validation. It wraps the failure at the
boundary where the file's path is still known, which is the information the traceback loses.

## 3. A130 — human, model, or neither

**The finding, in its sharpest form** (design audit, table row): *the artifact cannot state that
no model was consulted; `resolved_by` and `confidence` are the resolver's claims about itself.*

The operator's question was what best allows distinguishing **human, model and none**. It takes
two fields, because the per-value answer and the "none" answer need different kinds of evidence.

### 3.1 `ValueSource.MODEL` — the per-value answer

`ValueSource` already answers *who settled this*: `resolver` (the deterministic ladder), `goal`
(the user, before resolution), `human` (a person, after it), `measured` (a tool that named
itself). `model` is a genuinely distinct fifth answer and needs no parallel vocabulary.

Nothing writes it until Plan 2. It is declared now so that a model adapter has somewhere truthful
to write, rather than the enum arriving mid-Plan-2 alongside the first thing that needs it.

### 3.2 `Pipeline.ai` — what could have been consulted

A per-value `source: resolver` is *the resolver's claim about itself*. Round three recorded this
explicitly: `Resolution.source` can be set untruthfully by any resolver, including a future model
adapter. So `model` appearing is informative; `model` **not** appearing proves nothing.

What proves it is a fact about the *build* rather than a self-report — which of the three declared
runtime AI points had an adapter configured:

```yaml
ai:
  available: []   # of the three declared runtime AI points, which had an adapter
  used: []        # which actually answered
```

Both empty means **no model could have been consulted**, because nothing was wired to one. That
is a positive statement a reader can act on, and today it is always true.

### 3.3 The guard, and the half that cannot be guarded

**Checkable:** if `ai.available` is empty, no value and no decision may claim model authorship. A
new code in the pipeline-file band — **`MD0225`** — refuses that combination on any load.

**Not checkable, and written down beside the field rather than left implied:** a model-backed
build whose adapter writes `source: resolver` is indistinguishable from a deterministic one. The
field's honesty is the same standing as `confidence` and `reason` — declared vocabulary, not
proof. A130 is closed in the direction that can be proven and the other direction is documented
as a limit, because a field that implies more than it delivers is worse than no field.

**Schema version goes to 4.** `ai:` is a new required section with a default, and a v3 file
loading without it must not silently read as "no model" when it means "written before the
question was asked". Absence and emptiness are different, exactly as `for_value` taught in #48.

## 4. A36 — a domain separator that separates nothing

`digest.py` prefixes every file's content hash with `_FILE = b"file\x00"`. Setting it to `b""`
and running the suite passes. Its sibling `_LINK` went with the symlink branch A9 removed, so
there is one entry kind and a separator between one thing and nothing.

The audit gave three options and said changing the tag is *"free today and expensive after the
first lockfile a stranger holds"*.

**That cost has arrived.** `comeni-registry` is published and tagged `v0.2.0`, and a layer digest
is what a pipeline pins. Deleting `_FILE` would move every layer digest in every existing
`pipeline.yml`. So option 1 is no longer free.

**Option 3: give it a test that can fail.** Hash a directory two ways — once normally, once with
a synthetic second entry kind — and assert they differ. It makes the tag's claim checkable, it
moves no digest, and it is the only option that turns "this line cannot be wrong" into "this line
is tested". A line that cannot be wrong reads exactly like a line that is untested, which is A36's
own sentence and A14's thesis.

## 5. What lands, and what does not

**Lands:** `MD0001`–`MD0006`, `MD0225`, the widened `MD0223`, `ValueSource.MODEL`, `Pipeline.ai`,
schema version 4, and a test that can fail for `_FILE`.

**Does not:** A14, by the operator's decision. No `ProfilePolicy` — the protection profiles still
have no implementation, and building one for `ai:` alone would be inventing the consumer. No
signature or attestation over `ai:`; it is a declared statement, and §3.3 says so.

## 6. Success criterion

A malformed contract refuses with a code naming its file. A tier-4 setting answered by hand and
left with a stale reason refuses with `MD0223`. `pipeline.yml` states that no model was consulted,
and a hand-edited file claiming otherwise refuses with `MD0225`. Reverting `_FILE` to `b""` fails
a test. `make verify` green, and `pipeline.yml`'s `steps:` block byte-identical to today's apart
from the new `ai:` section.
