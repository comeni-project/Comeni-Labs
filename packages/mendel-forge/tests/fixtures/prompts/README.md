# Golden prompts

The exact text that would be sent to a provider, for one nf-core tool and one PEGiS tool, frozen.

**A prompt is the one product artifact nobody reviews by running it.** A change to the dossier's
ordering, a hint fragment, a hole's phrasing or the response schema changes what every model is
asked, and without a golden it lands as behaviour nobody looked at. These files are how that
change becomes a diff.

| fixture | what it holds |
|---|---|
| `nfcore_fastqc.analysis.txt` | a source that ships Nextflow and a structured `meta.yml`: machine-readable evidence, and no question about how to write a process |
| `pegi3s_clustalw.analysis.txt` | a source that ships a container and prose, where every port is a hole |
| `pegi3s_clustalw.implementation.txt` | the module-authoring prompt, which only a container-only source ever gets |
| `*.manifest.json` | what the dossier is made of, and what the budget left out |

**The manifest is beside the prompt rather than inside it**, because the two are read for
different reasons: the prompt to judge the question, the manifest to judge whether the question
was asked with everything available.

There is no `implementation` golden for nf-core. §5.6 says that prompt may bind a contract to the
existing process and must not emit replacement Nextflow, so a source that already wrote the
module never sees one.

Regenerate after reading the diff:

    uv run pytest packages/mendel-forge/tests/test_prompt_goldens.py --regenerate

**Read it properly.** A regenerated prompt golden is the moment to ask whether the change makes
the question clearer or merely different — §5.9 requires a before/after evaluation report for
exactly that reason, and this diff is what it is a report about.

## What these already caught

`ports.name.v1` did not exist. `ScaffoldHole.hint` falls back to `HINTS[kind]` but a hole may
carry a `prompt_hint_id` override, and `bundle._KINDS` sets one for a port's *name* — a `TYPE`
hole whose default fragment is the wrong one. Every unit test checked the table; none carried an
override, so eight ids resolved and the ninth was missing. The first attempt to render a real
nf-core scaffold failed on it.
