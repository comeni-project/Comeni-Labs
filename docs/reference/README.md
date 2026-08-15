# Reference

What each declared file may contain, field by field, and what the CLI does. Read one when you
know what you want and need the spelling.

**Start with [`pipeline-schema.md`](pipeline-schema.md)** if you are driving Mendel: it is the
file you read and edit, and everything else here describes an input to producing one.

| | |
|---|---|
| [`pipeline-schema.md`](pipeline-schema.md) | the save file — every step, setting and reason |
| [`diagnostics.md`](diagnostics.md) | every code, what it says, and whether it refuses |
| [`cli.md`](cli.md) | the verbs and their flags |
| [`goal-schema.md`](goal-schema.md) | what you ask for |
| [`contract-schema.md`](contract-schema.md) [`rule-schema.md`](rule-schema.md) [`measurement-schema.md`](measurement-schema.md) [`vocabulary-schema.md`](vocabulary-schema.md) | what a registry layer holds, one page per `DeclaredKind` |

Every page here describes a Pydantic model in `packages/comeni-core`. A field named here exists
in the code, and `diagnostics.md` is generated from `comeni_core/diagnostics.yml` rather than
maintained beside it.
