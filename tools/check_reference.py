"""`docs/reference/` documents exactly what the code has — no more, no fewer.

**Every reference page in this repository had drifted from its model by 2026-09-02**, and the
drift was invisible because nothing compared them. `vocabulary-schema.md` was the worst: it named
`Vocabulary` and documented `states` and `entry_channel`, and the real `Vocabulary` has neither —
it is the stacked registry now, and the per-file shape is `TypeDeclaration`, whose seven fields
the page documented two of. Meanwhile `docs/README.md` promised *"a field named here exists in
the code"*, which was false in both directions on that page.

**This does not generate the pages, and that is deliberate.** The models carry no `description=`,
so a generated table would be name, type and default — the mechanical third, and not the part
anybody opens a reference page for. What a field *means* is prose and stays prose. What can be
derived is *coverage*, so that is what is derived: a page must document every field its model has
and no field it does not.

The same shape holds `cli.md` against the two `argparse` parsers, which is where `mendel
conformance` and `mendel lint` were missing entirely and all twelve `forge` verbs were absent.

Run by `make docs` beside the diagnostics check, and by CI.
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
REFERENCE = ROOT / "docs" / "reference"

#: Each page names its own subjects in `Model:` lines, so the mapping is not repeated here —
#: retyping it would be one more thing to go stale, which is the defect this file exists for.
#:
#: **A page declares one `Model:` per table, not one per page.** A contract page documents
#: `ModuleContract` and the nested `InputPort`, `OutputPort` and `NfInput` beside it, and a
#: first version of this check read every row on the page as a claim about the top-level model —
#: reporting twenty-one fake drifts on `contract-schema.md` alone. Splitting on the `Model:`
#: lines is what makes the check true, and it costs the page nothing it should not already
#: say: a reader looking at a field table deserves to know which type it belongs to.
MODEL = re.compile(r"^Model: `([\w.]+)\.(\w+)`", re.M)
#: A documented field is a table row whose first cell is a backticked bare name.
FIELD = re.compile(r"^\| `(\w+)`", re.M)


def _first_table(text: str) -> str:
    """The first contiguous run of `|` lines, or nothing if there is none."""
    rows: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            rows.append(line)
        elif rows:
            break
    return "\n".join(rows)


def _paths() -> list[pathlib.Path]:
    return sorted(REFERENCE.glob("*-schema.md"))


def schema_problems() -> list[str]:
    found: list[str] = []
    for page in _paths():
        text = page.read_text()
        name = page.relative_to(ROOT)
        marks = list(MODEL.finditer(text))
        if not marks:
            found.append(f"{name}: no `Model:` line, so nothing can check it")
            continue
        for index, match in enumerate(marks):
            module, cls = match.groups()
            # **Only the FIRST table after a `Model:` line is that model's field table.**
            #
            # Two weaker rules were tried and both were wrong in the same direction — they
            # swept up tables that are not field tables and reported fields the model "does not
            # have". Running the block to the next `Model:` line read
            # `measurement-schema.md`'s *kinds and bounds* table as four phantom fields;
            # ending it at the next `##` still swallowed `rule-schema.md`'s effects table and
            # the expectations table under a `###`.
            #
            # A reference page is mostly tables, and only some of them describe fields. The
            # honest boundary is not a heading — it is the table itself.
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            block = _first_table(text[match.end():end])
            try:
                model = getattr(importlib.import_module(module), cls)
            except (ImportError, AttributeError) as exc:
                found.append(f"{name}: `Model: {module}.{cls}` does not import — {exc}")
                continue
            if not hasattr(model, "model_fields"):
                found.append(f"{name}: `{module}.{cls}` is not a Pydantic model")
                continue
            real, documented = set(model.model_fields), set(FIELD.findall(block))
            for field in sorted(real - documented):
                found.append(f"{name}: `{cls}.{field}` exists and is not documented")
            for field in sorted(documented - real):
                found.append(f"{name}: documents `{cls}.{field}`, which does not exist")
    return found


def _verbs(parser: argparse.ArgumentParser) -> set[str]:
    """Every verb the parser accepts, whether it uses subparsers or a positional choice.

    `forge` uses `add_subparsers`; `mendel` is one flat parser whose first positional carries
    `choices`. Reading only the first shape is how a check like this reports green over a CLI it
    never looked at, so both are read and the result is asserted non-empty by the caller.
    """
    names: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            names |= set(action.choices)
        elif not action.option_strings and action.choices:
            names |= {str(c) for c in action.choices}
    return names


def cli_problems() -> list[str]:
    page = REFERENCE / "cli.md"
    if not page.exists():
        return [f"{page.relative_to(ROOT)}: missing"]
    text = page.read_text()
    found: list[str] = []
    for prog, module in (("mendel", "mendel_compiler.cli.parse"),
                         ("forge", "mendel_forge.cli.parse")):
        verbs = _verbs(importlib.import_module(module).parser())
        assert verbs, f"read no verbs at all from {module}; the check is not checking"
        for verb in sorted(verbs):
            if not re.search(rf"`{prog} {verb}`", text):
                found.append(f"docs/reference/cli.md: `{prog} {verb}` exists and is undocumented")
    return found


#: Spelled numbers, because that is how this project's prose writes a count.
WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
         "twenty": 20}
#: `**Fourteen fields across the entire surface may hold free text**` and the variants of it
#: that have appeared in this repository's prose.
COUNT = re.compile(r"\b(\w+) fields? (?:across|in) the (?:entire |whole )?surface", re.I)


def egress_problems() -> list[str]:
    """Any page stating how many fields may hold free text states the number the guard holds.

    **This one sentence was wrong in two places at once on 2026-09-02**: the concepts page said
    *seven*, a design document said *exactly two*, and `tests/guards/test_egress.py` held fourteen.
    Nothing compared them, because the guard is a set of tuples and the pages are prose.

    A number repeated in prose is a number that goes stale while everything around it stays
    true — the failure this repository already logged twice as A33, A71 and A72. The answer
    each time was the same: derive it, or check it. This checks it.
    """
    import ast

    source = ast.parse((ROOT / "tests" / "guards" / "test_egress.py").read_text())
    real = None
    for node in source.body:
        if not isinstance(node, ast.Assign):
            continue
        if getattr(node.targets[0], "id", "") == "FREE_TEXT_FIELDS":
            real = len(node.value.elts)
    assert real, "read no FREE_TEXT_FIELDS from the egress guard; the check is not checking"

    found: list[str] = []
    for page in sorted((ROOT / "docs").rglob("*.md")) + sorted(ROOT.glob("*.md")):
        if (ROOT / "docs" / "notes") in page.parents:
            continue  # the record is dated and stays as written
        for word in COUNT.findall(page.read_text()):
            claimed = WORDS.get(word.lower())
            if claimed is None or claimed == real:
                continue
            found.append(
                f"{page.relative_to(ROOT)}: says {word} fields may hold free text; "
                f"`tests/guards/test_egress.py` holds {real}"
            )
    return found


#: A fenced YAML block in the documentation.
FENCE = re.compile(r"```yaml\n(.*?)```", re.S)


def example_problems() -> list[str]:
    """Every rule example in the documentation actually loads.

    **This is the check that matters most, because the failure it catches is the worst one
    here.** On 2026-09-02 `guides/writing-a-rule.md` — the page somebody follows to write their
    first rule — taught `decides: {param: X}` and `decides: {producer_of: T}` throughout. Plan
    1.15 replaced both with `{effect: …, of: <role>}` and **both old forms are refused with a
    validation error**. A reader following that guide could not produce a rule that loads, and
    had no way to know the guide was wrong rather than themselves.

    A wrong field in a table is a papercut. A wrong *example* is a person's afternoon, and it is
    the thing a reader copies. Examples are the part of documentation most worth executing, and
    the only part that can be.

    Scoped to rules because that is the schema whose examples are self-contained — a contract
    example needs a module to check against, and a goal example needs a registry.
    """
    import yaml
    from mendel_resolver.rules.format import Decision

    found: list[str] = []
    checked = 0
    pages = sorted((ROOT / "docs").rglob("*.md"))
    for page in pages:
        if (ROOT / "docs" / "notes") in page.parents:
            continue  # the record is dated; its examples were right when written
        if (ROOT / "docs" / "design") in page.parents:
            continue  # design records argue about formats, including superseded ones
        for block in FENCE.findall(page.read_text()):
            if "decides:" not in block:
                continue
            body = block if block.lstrip().startswith(("declares:", "decisions:")) else (
                "decisions:\n" + block
            )
            try:
                document = yaml.safe_load(body)
            except yaml.YAMLError as exc:
                found.append(f"{page.relative_to(ROOT)}: a rule example is not valid YAML — {exc}")
                continue
            if not isinstance(document, dict):
                continue
            for decision in document.get("decisions") or []:
                if not isinstance(decision, dict) or "decides" not in decision:
                    continue
                checked += 1
                try:
                    Decision.model_validate(decision)
                except Exception as exc:  # noqa: BLE001 — any refusal is the finding
                    reason = str(exc).splitlines()[0]
                    found.append(
                        f"{page.relative_to(ROOT)}: the example `decides: "
                        f"{decision['decides']}` does not load — {reason}"
                    )
    assert checked, "found no rule examples to check at all; the check is not checking"
    return found


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(prog="check_reference.py")
    args.add_argument("--check", action="store_true", help="exit 1 on any disagreement")
    args.parse_args(argv)
    problems = (
        schema_problems() + cli_problems() + egress_problems() + example_problems()
    )
    if problems:
        print(f"{len(problems)} reference page(s) disagree with the code:")
        for line in problems:
            print(f"  {line}")
        return 1
    print(f"docs/reference/ agrees with the code ({len(_paths())} schema pages + cli.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
