"""The command line: what a verb is called, and what a refusal says.

`mendel build` — goal in, pipeline directory out; `mendel profile` — measure first.

A package rather than a module since issue #41 — `cli.py` was 851 lines. The split is by
**what a verb does to a pipeline**, not by verb name:

| module | verbs | loads |
|---|---|---|
| here | `explain`, and dispatch | nothing |
| `artifact_verbs` | `emit`, `publish` | a `pipeline.yml` |
| `resolve_verbs` | `build`, `upgrade`, `profile` | a registry, and resolves |
| `parse` | — | — |
| `report` | — | — |

Three verbs share the entire resolution path, so a module each would copy it three times.

**`cli.py` is the only thing that touches disk.** Everything else takes objects and returns
objects, which is what makes the golden-file tests possible at all: a stage you can only
exercise through the filesystem is a stage whose output you compare by hand.
"""

import re
import sys
from pathlib import Path

from comeni_core.declared.measurement import BadMeasurementValueError, UnknownMeasurementError
from mendel_resolver.router import UnroutableError
from mendel_resolver.rules import RuleValidationError
from pydantic import ValidationError

from mendel_compiler import conformance
from mendel_compiler.cli import artifact_verbs, layer_verbs, parse, resolve_verbs

_CODE = re.compile(r"\bMD0\d{3}\b")
"""Deliberately `MD` only: `mendel` raises no forge code, and matching one here would
point a reader at `mendel explain` for a refusal `forge` produced. The forge CLI has its
own, over `MF`."""


def _with_pointer(message: str) -> str:
    """A coded refusal names its code and says how to read the long form.

    `mendel explain` has existed since Plan 1.6 and nothing on this path mentioned it, so the
    one verb that explains a code was undiscoverable from the failure that needed it. Dozens
    of `ValueError` sites embed a real code and the CLI printed the raw message. Audit A75,
    issue #36.

    The **first** code in the message, because a refusal names one thing: a message quoting a
    second code is quoting it as context — `MD0311`'s fix block names `MD0313` — and pointing
    a reader at the context rather than at their error would be worse than pointing them
    nowhere.
    """
    found = _CODE.search(message)
    return f"{message}\n  run: mendel explain {found.group()}" if found else message


_PIPELINE_MODELS = frozenset(
    {
        "Pipeline",
        "Step",
        "StepInput",
        "Setting",
        "CallArg",
        "MetaEntry",
        "ExtArgs",
        "ModuleRef",
        "Channel",
        "Why",
        "PremiseRecord",
        "Emitted",
        "EmittedFile",
        "RegistryProvenance",
        "AiProvenance",
        "LockedLayer",
    }
)
"""The models a `pipeline.yml` is made of. Named so a failure in one blames the right file."""


def _blame(title: str) -> str:
    """Which file the reader should open, from the model that failed to validate.

    A41 made this a heuristic and special-cased `ModuleContract` alone — a contract author's
    mistake is not the operator's, and blaming "this goal" sent them to the one file they did
    not write. **A74 is the same defect one model over**: a `Pipeline`-family failure fell
    through to "this goal", and `emit` and `upgrade` take a `pipeline.yml`, not a goal. The
    artifact's own header says `goal:` is inert to `emit`, so a reader who had just edited
    `steps:` was told the goal was wrong and sent to the one section that could not have
    caused it.

    An explicit set rather than a second special case, because a special case is what needed
    fixing: `test_every_pipeline_model_blames_the_pipeline_file` derives the set from
    `Pipeline` itself, so a model added tomorrow is covered or the test fails.
    """
    if title == "ModuleContract":
        return "contract"
    if title in _PIPELINE_MODELS:
        return "this pipeline file"
    return "this goal"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Wraps `_build` so a user mistake is a message, not a traceback."""
    try:
        return _build(argv)
    except UnroutableError as exc:
        print(_with_pointer(f"mendel: cannot route this goal — {exc}"), file=sys.stderr)
    except ValidationError as exc:
        print(_with_pointer(f"mendel: {_blame(exc.title)} is not valid —\n{exc}"), file=sys.stderr)
    except RuleValidationError as exc:
        print(_with_pointer(f"mendel: a rule table will not load —\n{exc}"), file=sys.stderr)
    except (UnknownMeasurementError, BadMeasurementValueError) as exc:
        print(_with_pointer(f"mendel: this goal's profile is not valid — {exc}"), file=sys.stderr)
    except (OSError, KeyError, ValueError) as exc:
        # `ValueError` last, and it catches a lot on purpose: a symlink in a layer, a
        # duplicate YAML key, an `add_states` for a type nothing declares, A35's joined
        # `UnknownStateError`. Every one of them is a refusal this code chose to make, and
        # every one of them reached the user as a traceback. `ValidationError` is caught
        # above and `RuleValidationError` above that, so the specific messages still win.
        print(_with_pointer(f"mendel: {exc}"), file=sys.stderr)
    return 2


def _build(argv: list[str] | None = None) -> int:
    """Parse, then hand off. Every branch here returns before a registry is loaded.

    `explain` loads nothing at all, and `emit` and `publish` read a `pipeline.yml` — so the
    only path that reaches `layers.load` is the last line, and that is the shape the split
    follows.
    """
    parser = parse.parser()
    args = parser.parse_args(argv)
    # Before anything loads: `explain` is documentation, and asking it for a code while a
    # registry will not load would answer the wrong question.
    if args.command == "explain":
        if not args.target:
            parser.error("explain needs a code, e.g. `mendel explain MD0104`")
        print(conformance.explain(args.target))
        return 0

    # `docs` acts on a layer and produces no pipeline, so it returns before every flag below,
    # all of which describe a pipeline this verb never makes. It resolves nothing either: it
    # loads a layer and reads what the contracts say, which is why it lives in `layer_verbs`.
    if args.command == "docs":
        if args.out is None:
            parser.error("docs needs --out")
        if not args.registry:
            parser.error("docs needs at least one --registry")
        return layer_verbs._docs_verb(args.registry, args.out, args.check)

    # `conformance` acts on a layer too, and produces no pipeline. It exists because
    # `comeni-registry`'s CI could not ask whether its own contracts agree with their own
    # modules until Plan 5A put both in the layer — before that the check needed a goal, a
    # build and a checkout holding two repositories.
    if args.command == "conformance":
        if not args.registry:
            parser.error("conformance needs at least one --registry")
        return layer_verbs._conformance_verb(args.registry)

    # `--check` belongs to `docs` alone. On any other verb it would be a flag that silently
    # means nothing, which is the defect `--dry-run` and `--force` each carry a guard for.
    if args.check:
        parser.error("--check is for `docs`; it asks whether the pages match the data")

    # `--dry-run` belongs to `upgrade` alone: it means "re-resolve and compare", and there
    # is nothing to compare a fresh `build` against. Accepting it elsewhere would make it a
    # flag that silently means "do nothing".
    if args.dry_run and args.command != "upgrade":
        parser.error("--dry-run is for `upgrade`; it is what `verify` would have been")

    # `--force` belongs to `upgrade` alone, for the same reason: it authorises overwriting a
    # *different* pipeline's directory, and only `upgrade` writes into a directory a person
    # names rather than one it just built. On `build` it would silently mean nothing.
    if args.force and args.command != "upgrade":
        parser.error("--force is for `upgrade`; it authorises overwriting another pipeline")

    # `publish` takes no `--out`, and that is the shape of the verb rather than an omission.
    # It does not produce a new pipeline; it certifies the one it was given — runs the gate
    # and stamps the verdict into that directory's `pipeline.yml`. `upgrade` is the opposite
    # and must never write in place, because what you had is the evidence.
    if args.command == "publish":
        if args.out is not None:
            parser.error(
                "publish takes no --out: it certifies the pipeline you give it, in place. "
                "Use `mendel upgrade <pipeline.yml> --out <dir>` to produce a new one."
            )
    # `--dry-run` writes nothing, so demanding somewhere to write would be argparse
    # describing the wrong verb — the same reason `explain` is handled above it.
    elif args.out is None and not args.dry_run:
        parser.error(f"{args.command} needs --out")

    # Before the registry loads, and deliberately: `emit` reads no registry, no vocabulary
    # and no measurements. That is the whole point of materialising the pipeline — a
    # laboratory can archive a validated pipeline and regenerate its Nextflow years later
    # without the registry it was built against, which is the part that resolves differently
    # as it changes. Loading one here would make that untrue while the tests still passed.
    if args.command == "emit":
        if not args.target:
            parser.error("emit needs a pipeline.yml, e.g. `mendel emit build/pipeline.yml`")
        return artifact_verbs._emit_verb(Path(args.target), args.out)

    # `publish` certifies the artifact on disk and re-resolves nothing (A50). Like `emit`, it
    # needs no registry and no network: `pipeline.yml` is self-contained, so certification only
    # asks "do the files on disk pass the gate?" — a question the registry does not answer.
    # Sharing `upgrade`'s re-resolution path made publish re-resolve against whatever `--registry`
    # was installed, silently swap the pipeline, erase human overrides, and stamp a gate on the
    # result: the door with no undo certifying a pipeline nobody read.
    if args.command == "publish":
        if not args.target:
            parser.error("publish needs a pipeline.yml, e.g. `mendel publish build/pipeline.yml`")
        return artifact_verbs._publish_verb(Path(args.target), args.gate)

    # A layer is a directory, not a contracts folder: all three kinds of registry data
    # stack together, so a laboratory can ship its own types and rules alongside its
    # modules. Only contracts stacked before the 2026-08-03 audit.
    return resolve_verbs.run(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
