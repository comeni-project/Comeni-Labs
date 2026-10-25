# comeni-vendor

`comeni-vendor` fetches pinned module source into a registry layer and checks that the stored copy
still matches its declaration. Maintainers run it before committing registry changes; pipeline
construction reads the resulting layer from disk and performs no source fetch.

## Vendor a module

```bash
comeni-vendor add nf-core:star/align \
  --sha 6d46786420b4d7bc88eba026eb389c0c5535d120 \
  --licence MIT \
  --registry ../comeni-registry

comeni-vendor check --registry ../comeni-registry              # offline: was it hand-edited?
comeni-vendor check --registry ../comeni-registry --upstream   # online: does it match the pin?
```

`add` writes two things beside each other:

```
tools/nf-core/star/align/
    module.yml     where the code came from, at which commit, under which licence
    module/        selected upstream files; replaced wholesale by the next add
```

The layer must already contain `LICENSES/<SPDX identifier>.txt`. By default, `add` excludes the
upstream `tests/` directory and records that exclusion in `module.yml`. Use `--repo`, `--path`, and
repeatable `--exclude` options for sources not covered by the built-in `nf-core` mapping.

## Check vendored content

The two check modes answer different questions:

- `check` is offline. It recomputes each `module/` digest and detects local edits.
- `check --upstream` fetches the pinned commit and verifies the selected upstream content.

A laboratory module with `upstream: null` reports `unpinned`, not `ok`, because no comparison was
performed. Missing module directories and mismatches make the command fail.

## Architectural boundary

Network and filesystem operations live here rather than in the pure compiler. See
[package responsibilities](../../docs/explanation/package-boundaries.md) for the dependency and
consumer boundary, and the registry's [vendoring guide](../../registry/README.md#vendoring-a-tool)
for the layer-side workflow.
