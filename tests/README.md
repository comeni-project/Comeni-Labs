# Tests

## The three homes — this directory is one of them

Tests live in three places, and **most of them are not here**. Look in all three before
concluding something is untested.

| Where | What it holds |
|---|---|
| **`packages/<name>/tests/`** | **The bulk of the suite** — one directory per package, beside the code it exercises. `comeni-core`, `mendel-resolver`, `mendel-compiler`, `mendel-ai`, `mendel-forge`, `mendel-api`, `wiener-core`, `wiener-api`, `dag-core`, `comeni-vendor` |
| **`frontend/src/`** | `Component.test.tsx` beside `Component.tsx`, the Vitest convention |
| **`tests/`** (here) | Only what belongs to **no single package**: a pipeline built end to end, a scan over the whole repository, an invariant held across a boundary |

`pyproject.toml` sets `testpaths = ["tests", "packages"]`, so `uv run pytest` collects the
first and third together; the frontend runs under `npm test` in `frontend/`.

**No count is written down here**, for the reason `CLAUDE.md` gives: a number in prose goes
stale while everything around it stays true. Derive it:

```bash
find packages/*/tests tests -name 'test_*.py' | cut -d/ -f1-2 | sort | uniq -c | sort -rn
```

**A test belongs in its package unless it cannot.** Ask what would have to be true for it to
move there: if the answer is "nothing — it only imports one package", move it. What is left
here either builds a real pipeline through the resolver *and* the compiler, reads files the
repository owns, or holds a rule that would be unenforced if any one package could drop it.

## Where a test goes inside `tests/`

| Directory | What it holds | The question it answers |
|---|---|---|
| `guards/` | purity, purity-runtime, egress, construction, the clock scan, the live-model scan, the forge write boundary | **is an invariant still held?** |
| `registry/` | declared identity and loading, layer stacking, `lint`, the submodule check, vocabularies, the rule corpus, module specs, conformance | **does declared data load, and does it agree with the modules?** |
| `artifact/` | `pipeline.yml` round-trips, totality, the lockfile, `upgrade`, `publish`, AI provenance | **does the artifact say what happened, and can it be read back?** |
| `emit/` | the emitted Nextflow — runnability, channels, fan-in and fan-out, joins, samplesheets, scopes, and the counts matrix | **does what comes out run, and is it right?** |
| `diagnostics/` | code ownership and the code registry | **is every code declared once and emitted through `coded()`?** |
| `repo/` | `ARCHITECTURE.md`'s paths, the changelog splitter, compose, the Dockerfile, packaging, the release workflow, action pins, the generated stub | **do the repository's own files still describe the repository?** |
| `regressions/` | one test per audit finding, named for it — `test_a9_…`, `test_a125_…` | **is A9 still closed?** |

Two supporting directories carry no tests: `support/` holds helpers (`paths.py` for the
repository root, `walk.py` for annotation walking, `audit.py` for the regression fixtures), and
`fixtures/` and `golden/` hold data.

`guards/` is named in `make guards` and in `CLAUDE.md`'s invariants; `emit/test_counts.py` is
what `make verify` adds beyond `make check`. Moving a file out of either is a change to a
documented command, not a tidy-up.

## Two rules that are not obvious

**Ask `support.paths` for the repository root.** Every file used to spell it
`Path(__file__).parent.parent`, which is a claim about how deep the file sits — true while the
suite was flat, false the moment anything moved. Write `from support.paths import ROOT`
instead. `REGISTRY`, `FIXTURES`, `GOLDEN`, `EXAMPLES` and `PACKAGES` are there too.

**A loop is not an assertion.** A test whose only assertions sit inside `for x in <something
derived>` passes when the collection is empty, and says nothing. Assert the collection is
non-empty first, with a message that says so:

```python
assert rows, "nothing at all is open — this test is measuring nothing"
for row in rows:
    ...
```

Three tests in this repository were found asserting over an empty loop, and one of them was
the standing check for a documented rule. `tests/guards/test_no_clock.py` carries the pattern
as a separate named test where the collection is a file scan.

## When to add a directory

Rarely. Seven is already close to the number at which a reader has to guess, and the cost of a
wrong guess is a test written twice. Add one only when **all** of these hold:

1. **Three or more files want it.** Two files are a pair, not a category — put them in the
   closest existing directory and leave a line here saying why.
2. **You can name the question it answers** in the third column of that table above, in one
   sentence, without the word "and". If the sentence needs an "and", the directory is two
   directories or it is one of the existing ones.
3. **No existing directory's question already covers it.** `registry/` is about declared data,
   not about the registry package; `emit/` is about output, not about the compiler. The
   directories are named for subjects, not for the code under test — that is what lets a test
   crossing three packages have one obvious home.

Prefer a new **file** in an existing directory. A directory of fifteen well-named files is
easier to read than five directories of three, and the file name is where the subject belongs.

If a file grows past roughly a thousand lines, split the *file* by subject and keep the
directory: that is what `regressions/` is — one 2,389-line file that became seven, with the
test names unchanged so every `aNN` finding is still greppable by its number.
