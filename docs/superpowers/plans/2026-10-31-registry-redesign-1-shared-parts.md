# Registry redesign, slice 1: shared parts

**Spec:** [registry redesign](../specs/2026-10-31-registry-redesign-design.md). **Issues:** #424, part
of #429. **Branch:** `registry-redesign-1-shared-parts`. **Size:** S, about one session.

The operator chose to proceed without approving each plan (2026-10-31, "you can implement").

## Steps

- [x] `GET /registry/choices`: every type, job and tool as a picker needs them, ordered by the server.
- [x] `toolShape`: the tool's pins and job, from forge items.
- [x] `Tracker`: the six pieces, replacing the rail. Keeps the `Pieces` navigation.
- [x] `ToolDiagram`: pins around a block, picking one jumps to it.
- [x] `RegistryPicker`: search, groups, made by and read by, a sheet at 390 wide.
- [x] Control styles: hover, press, focus, chosen, pending, in one place (#424).
- [x] Page frame: registry pages and the bar above them share one edge.
- [x] #429: the page background, and the chosen and rejected states.
- [x] Wire the picker into type and job questions.
- [x] Browser check at 1440 and 390, both themes, against the boards.

## Deviations

- The tracker gained a compact bar at phone width: six labels forced the page to scroll sideways.
- When every piece is approved, a piece can now be reopened, with *Back to Assembly*. The old rail
  never allowed it, and pins would have led nowhere.

## Compared with the boards

Side by side on 2026-10-31 at about 1870 wide, 1000 and 390. Fixed: frame padding, sub-tab pills, tool
panel heading and padding, the picker as a floating card opening on the current answer. Kept on
purpose: a status under each tracker step, because it says what is waiting.

## Known limits

- **Jobs have no declared description.** Roles are bare names, so the picker shows what is declared:
  the tools doing a job and what they read and make. Descriptions need a registry change, in its
  own repository, and are recorded as a follow-up.
- Six types have no `explain`; the picker falls back to the family's description.
