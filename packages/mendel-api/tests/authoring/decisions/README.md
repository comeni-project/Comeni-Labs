# API authoring / decisions tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| change command | [test_change_command.py](test_change_command.py) |
| change readers | [test_change_readers.py](test_change_readers.py) |
| changes | [test_changes.py](test_changes.py) |
| checked authoring edit | [test_checked_authoring_edit.py](test_checked_authoring_edit.py) |
| correction forks | [test_correction_forks.py](test_correction_forks.py) |
| decision constraints | [test_decision_constraints.py](test_decision_constraints.py) |
| decision migration | [test_decision_migration.py](test_decision_migration.py) |
| decisions heard | [test_decisions_heard.py](test_decisions_heard.py) |
| decisions service | [test_decisions_service.py](test_decisions_service.py) |
| draft deletion | [test_draft_deletion.py](test_draft_deletion.py) |
| extraction into rows | [test_extraction_into_rows.py](test_extraction_into_rows.py) |
| fact corrections | [test_fact_corrections.py](test_fact_corrections.py) |
| fact disagreements | [test_fact_disagreements.py](test_fact_disagreements.py) |
| fact views | [test_fact_views.py](test_fact_views.py) |
| heard replies | [test_heard_replies.py](test_heard_replies.py) |
| known | [test_known.py](test_known.py) |
| no quote outlives its reply | [test_no_quote_outlives_its_reply.py](test_no_quote_outlives_its_reply.py) |
| proposal envelopes | [test_proposal_envelopes.py](test_proposal_envelopes.py) |
| suggestions | [test_suggestions.py](test_suggestions.py) |

Run `uv run pytest packages/mendel-api/tests/authoring/decisions -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../../README.md).
