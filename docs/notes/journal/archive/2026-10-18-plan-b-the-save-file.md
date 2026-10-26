# 2026-10-18 — Part I.0 Plan B: the save file

Plan B of the I.0 spec (§8, less §8.4, deferred to #357), from
[the plan](../../superpowers/plans/2026-10-18-part-i0b-the-save-file.md), on `plan-b-save-file`.
Mid-execution the operator set a rule that reshaped it: **no backward compatibility before
v0.1.0**, because nobody uses Comeni yet.

## Where things stand

- **`pipeline.yml` is version 7**: `intent` (want, constraints) and `facts` (inputs,
  measurements with their source) at the top; `Pipeline.goal` is computed from them. A stated
  value's source is `said`. Only version 7 is read; any other is refused (MD0207).
- **A starter is a v7 file with only `intent` and `facts`**: `mendel build examples/rnaseq.yml`.
  There is no `--goal` and no separate goal format.
- **Each layer says where to fetch it** (`source`, `commit`, `dirty`), read with git in
  `mendel_compiler.locate`; MD0231 / MD0232 warn; `upgrade` names the commit to check out.
- `make check` passes (4224). `make verify` and the final review are the plan's last steps.

## Decisions (operator)

- §8.4, opening a saved file into a draft: deferred (#357); nothing opens a file today.
- Rename `goal` → `said`, then: no compatibility at all before v0.1.0. The dev database and
  the test database were reset rather than migrated.

## Traps

- The dev database volume `comeni-labs_comeni-pg` was removed; the next `make dev` creates it
  empty. Stored sessions from before are gone.
- `tests/golden/spine/main.nf` is not what the example builds; `tests/golden/example/main.nf` is.
- Tests take the example through `tests/support/example.py` (`example_goal`, `example_mapping`),
  never by loading the YAML into `Goal`.
- A recorded blueprint or pipeline fixture must be version 7; converting an old one needs the
  upgrader from git history (`574b7853`).
