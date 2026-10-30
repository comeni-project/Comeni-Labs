# 2026-10-30 — Forge MVP 4: tests as Wiener runs

[The design](../../superpowers/specs/2026-10-30-forge-4-tests-design.md) and
[the plan](../../superpowers/plans/2026-10-30-forge-4-tests.md), on `forge-4-tests`, above
`forge-3-forging`, for #365.

## Where things stand

- **Decided (operator):** Mendel's worker submits forge tests to Wiener through one narrow
  interface, rather than the browser carrying them: publishing needs a result the server checked.
  The builder's Run button is unchanged. The pages were built from the issue, because the canvas
  could not be read while its account was out of tokens: compare them with boards 4–6.
- Built: `declares: test`, loaded beside each tool; a sixth piece; `build_test_pipeline`, which
  makes the IR directly so routing cannot choose another tool; `TestRunner` and `WienerRunner`;
  `forge_test_run`, a cron every 30 seconds, and `proven()` for MVP 5's gate; the AI drafting from
  `main.nf.test`; the page.
- **Not done, so #365 stays open:** tests for the ten existing tools, and any real run. Everything
  is tested against a fake runner and no pipeline has reached Wiener. The first real run may change
  `WienerRunner`, the samplesheet row or the pattern check.
- Not browser-checked: the stack was not started, to spare the machine.
- `declares: test` is a new kind, so an older engine refuses a layer holding one (`MD0011`):
  `ENGINE_REF` must move, and `registry.yml` must place `test`, before the first forge pull
  request. `tests/registry/test_registry_layer.py` allows that one kind until then.
- Not merged, not pushed.
