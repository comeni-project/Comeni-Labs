# Reference

What each declared file may contain, field by field, and what the CLI does. Read one when you
know what you want and need the spelling.

**Start with [`pipeline-schema.md`](pipeline-schema.md)** if you are driving Mendel: it is the
file you read and edit, and everything else here describes an input to producing one.

| | |
|---|---|
| [`pipeline-schema.md`](pipeline-schema.md) | the save file — every step, setting and reason |
| [`glossary.md`](glossary.md) | **the eight words the interface uses** — start here if a screen is using a word at you |
| [`diagnostics.md`](diagnostics.md) | every code, what it says, and whether it refuses |
| [`cli.md`](cli.md) | the verbs and their flags |
| [`goal-schema.md`](goal-schema.md) | what you ask for |
| [`contract-schema.md`](contract-schema.md) [`rule-schema.md`](rule-schema.md) [`measurement-schema.md`](measurement-schema.md) [`vocabulary-schema.md`](vocabulary-schema.md) | what a registry layer holds — the four kinds you write by hand |

**A field named here exists in the code, and that is checked rather than promised.** Each field
table sits under a `Model:` line naming the Pydantic model it describes, and
`tools/check_reference.py` fails the build if a page documents a field the model does not have,
misses one it does, or if the CLI grows a verb nobody wrote down. `make docs` runs it, and so
does CI.

That check was written on 2026-09-02, when **all five schema pages disagreed with their models**
and this paragraph claimed otherwise.

`diagnostics.md` goes further and is *generated* from `comeni_core/diagnostics.yml`.

A layer has six `DeclaredKind`s and four of them have a page here. The other two are small
enough to state in full:

- **`role`** — one line naming a job a contract can do, e.g. `alignment`. Roles are **closed**:
  a contract naming one no layer declares fails to load (`MD0302`). A role is the only thing a
  tier-3 rule may target, and it is coarser than a contract on purpose — that is what lets one
  rule choose between STAR and HISAT2 without naming either in its key.
- **`module`** — vendored tool source under `tools/<org>/<tool>/module/`. Not authored: it is a
  verbatim copy of somebody else's work, replaced wholesale by `comeni-vendor`, and a hand edit
  fails CI.

[Registry layers](../guides/registry-layers.md) covers how all six stack.
