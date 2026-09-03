---
title: Tools
description: Every tool, type, rule and measurement in the loaded registry.
---

# Tools

Everything the platform currently knows how to do. **These pages are generated** from the
registry you built the site against — `mendel docs --registry <your layer>` — so a laboratory
running its own layer gets its own catalogue here.

[Browse the catalogue](catalogue.md), grouped by the org that supplies each tool. The
individual tool pages don't appear in the sidebar themselves, because their set depends on
which registry you built against and can't be known ahead of time — but every one is reachable
from the catalogue, and searchable too.

## How to read a tool page

Use tool pages to answer practical questions before adding or trusting a step:

| Question | Look for |
|---|---|
| What job does this tool do? | roles |
| What can it consume? | input ports and accepted types |
| What can it produce? | output ports, types, and states |
| Why might Comeni choose it? | rules, priorities, and competing tools |
| What evidence backs the definition? | provenance and citations |

The catalogue describes the loaded registry, not every tool that exists in bioinformatics. If a
tool is missing, go to [Using the forge](../registry/using-the-forge.md) or
[Writing a contract](../registry/writing-a-contract.md).
