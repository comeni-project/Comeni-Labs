/** The generated schema names the builder uses, in one place.
 *
 * **Because the generated names are not stable across model changes.** FastAPI splits a model
 * into `Foo-Input` and `Foo-Output` when it appears in both a request and a response with
 * differing optionality, and merges them back when it does not — so `DraftGraph` was
 * `DraftGraph-Input` for one commit and `DraftGraph` the next, purely because a nested field
 * changed type. It also namespaces a name that collides: three classes are called `Verdict`
 * (`comeni_core.review.verdict`, `mendel_forge.verify`, `mendel_forge.drift`), so none of them
 * gets the short name.
 *
 * Neither is a bug in the generator — both are it telling the truth about an ambiguous name.
 * What is a bug is spreading that truth across six files, so a regenerate breaks them one at a
 * time with an error that names TypeScript rather than the API. One import site, one edit.
 *
 * `make client` regenerates `schema.d.ts`; **never hand-edit it**. This file is the seam.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type DraftGraph = S["DraftGraph"];
export type DraftEdge = S["DraftEdge"];
export type DraftNode = S["DraftNode"];
export type DraftLabel = S["DraftLabel"];
export type DraftParam = S["DraftParam"];

export type Built = S["BuiltPipeline"];
export type Step = S["StepView"];
export type Setting = S["SettingView"];
export type PortView = S["PortView"];
export type Module = S["ModuleView"];

export type Verdict = S["comeni_core__review__verdict__Verdict"];
export type Finding = S["Finding"];
export type Compatibility = S["Compatibility"];
export type Comparison = S["Comparison"];
export type AlignedStep = S["AlignedStep"];

export type DraftOut = S["DraftOut"];
export type Kept = S["Kept"];

/** A gate — Mendel's artifact checking itself. **Not a pipeline run**, which is Wiener's and
 *  has no type here on purpose: `docs/design/execution-boundary.md` §3. */
export type GateView = S["GateView"];
export type GateIn = S["GateIn"];
