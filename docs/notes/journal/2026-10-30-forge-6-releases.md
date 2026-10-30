# 2026-10-30 — Forge MVP 6: releases

[The design](../../superpowers/specs/2026-10-30-forge-6-releases-design.md) and
[the plan](../../superpowers/plans/2026-10-30-forge-6-releases.md), on `forge-6-releases`, above MVPs
3–5, for #367 and the release setting #381 left to the forge.

## Where things stand

- Built: `active_registry()`, which every reader now goes through, with a guard; `follow`, an hourly
  worker cron that fetches and switches only to what loads; a pipeline's `release`; `forge_release`,
  at most one being cut; the Releases tab; *Registry release* and *Release in use* in Settings.
- **Decided in the spec:** forging stays on the release in use, not `main`; notes are the fragments
  since the last tag, so a release commits nothing.
- **Found on the way:** the registry cache keyed on content alone, so a release with the same bytes
  as the last would have kept the old paths, and a pipeline's lockfile would have named the wrong
  layer. The root is in the key now.
- `.run/registry` stayed: until a first release exists it is what a stack runs on. Remove it after.
- *Registry release* is text, not a list: a setting's choices are declared and releases are not.
  A wrong version changes nothing and says so.
- **Not done, so #367 stays open:** no real GitHub, no real release, and the `registry/` submodule is
  not pinned to a tag. Not browser-checked. `make verify` not run, and the schema gained a field, so
  it should be before this merges.
- Not merged, not pushed.
