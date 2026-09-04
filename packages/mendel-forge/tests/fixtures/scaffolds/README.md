# Golden scaffolds

What the forge produces for one nf-core tool and one PEGiS tool, frozen. A change to any part of
the deterministic half — the derivation, the hole addressing, the module skeleton, the JSON
writer — shows up here as a reviewable diff instead of as a behaviour nobody looked at.

**They cover what the forge *authored*, not what it copied.** `deterministic` holds every file
the forge composed; `source_paths` holds only the *names* of the files it copied verbatim.
Embedding a copy of the vendored `main.nf` would mean a registry bump churns a golden that is not
about the registry, and the copying itself is already checked by
`test_an_nf_core_source_is_copied_unchanged_and_gets_no_generated_module`.

| fixture | the case it carries |
|---|---|
| `nfcore_fastqc.json` | a source that ships Nextflow: a contract skeleton, semantic hole ids from real channel names, and **no generated module** — nf-core wrote the process, so nothing downstream may author one |
| `pegi3s_clustalw.json` | a source that ships a container and prose: a module skeleton whose input, output and script are all marked open (`MF0011`, `MF0005`), a process name invented as a placeholder while the hole stays open, and a container settled from a **digest** rather than a tag |

The two exist for the difference between them. A golden that only covered nf-core would not
notice the PEGiS path breaking, and the PEGiS path is the one where the forge is authoring rather
than transcribing — which is where a wrong answer is both likeliest and least visible.

Regenerate after reading the diff:

    uv run pytest packages/mendel-forge/tests/test_scaffold_goldens.py --regenerate

`--regenerate` is a flag rather than an environment variable: it appears in `pytest --help`, it
cannot be left set in a shell and quietly rewrite a golden on the next run, and a CI lane that
never passes it cannot regenerate by accident.
