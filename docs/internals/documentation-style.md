# Documentation style

*Serves: **all four steps**. This page keeps the public books from drifting back into
implementation notes or CLI-first tutorials.*

The wiki should read like product documentation for a low-code scientific app. It can be exact
without making the reader start from internals.

## Rules

| Rule | Meaning |
|---|---|
| App first | Start from the browser workflow unless the page is explicitly advanced reference. |
| One example | Reuse the RNA-seq counts example across user guides so the story compounds. |
| Examples before schemas | Teach with a worked case, then link to exact reference. |
| Screens where UI matters | Use screenshots or screenshot placeholders for visual workflows. |
| Alpha is explicit | Separate current alpha behavior from stable concepts and expected changes. |
| CLI is secondary | Present commands as advanced or equivalent paths, not the product spine. |
| Internals absorb history | Bug history, package names, and algorithm edge cases belong here. |

## Alpha language

Use this pattern when a surface is moving:

| Label | Use it for |
|---|---|
| Current alpha behavior | what a user can do today |
| Expected to change | UI, input, or API details that are not stable |
| Stable concept | the idea the user should keep learning anyway |

Inputs, natural-language goal entry, run submission, and AI-assisted forge drafting should use
this pattern until they settle.

## Screenshot placeholders

Placeholder screenshots live under `docs/assets/screenshots/` and are intentionally named after
the screen they will eventually show. Replace the SVG placeholder with a real capture at the
same path when the screen is stable enough.

Do not use a diagram where the user needs to recognize the interface. Use a screenshot for
screen anatomy and a diagram for concepts such as boundaries, routing, and lifecycle.
