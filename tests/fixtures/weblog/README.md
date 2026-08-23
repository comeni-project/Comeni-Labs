# A real `nf-weblog` capture

`failing-run.jsonl` is **thirteen events from an actual Nextflow 25.10.4 run**, captured on
2026-08-23 by pointing `weblog.url` at a local listener. Two tasks succeed, one fails, and the
run ends unsuccessfully — the smallest shape that exercises every branch of the fold.

It is committed because `docs/design/wiener.md` §6 makes replay the way Wiener's determinism is
tested, and a replay corpus has to come from somewhere real. Five things in this file contradict
what the design assumed before it was captured; they are listed in that document's §4.3.

Regenerate with the recipe in §4.0. Do not hand-edit it — an edited capture is a fixture that
asserts what somebody wished had happened.
