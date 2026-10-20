---
title: Explanation
description: Understand pipeline construction, decisions, data boundaries, and registry knowledge.
---

# Explanation

These pages explain the concepts behind Comeni and the reasons for its design.
Use the [tutorials](../tutorials/index.md) to learn through an example or the
[how-to guides](../how-to/index.md) when you need instructions.

| Question | Read |
|---|---|
| How do building, reviewing and running fit together? | [The product loop](pipeline-lifecycle.md) |
| What are drafts, artifacts, gates and runs? | [Core words](pipeline-concepts.md) |
| Why was a tool or setting chosen? | [The four tiers](decision-tiers.md) and [How tools get chosen](tool-selection.md) |
| Which inputs are used to build, and which to run? | [Inputs in the alpha](inputs-and-data.md) |
| What knowledge does the registry contribute? | [The registry](registry.md) |
| Which boundaries must implementation preserve? | [Invariants](invariants.md) |
| How does the authoring conversation progress? | [Authoring protocol](authoring-protocol.md) |
| How are protocol transitions represented? | [Authoring protocol diagram](diagrams/authoring-protocol.md) |
| How should the app phrase questions and decisions? | [Product voice](product-language.md) |
| Why do the screens look the way they do? | [Visual identity](visual-identity.md) |

## Implementation and registry design

| Subject | Explanation |
|---|---|
| Component ownership and pipeline construction | [Architecture](architecture.md) |
| Package ownership, dependencies and consumers | [Package responsibilities](package-boundaries.md) |
| Builder model behavior, queues and storage | [Mendel AI ownership](mendel-ai-ownership.md) |
| Semantic contracts and states | [Tool contracts](tool-contracts.md) |
| Data-backed choices and reachable implementations | [Rules](data-backed-rules.md) |
| Overlay replacement and load order | [Registry layers](registry-layers.md) |
