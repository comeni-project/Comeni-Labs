# API forge tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| adaptations use the adaptation layout | [test_adaptations_use_the_adaptation_layout.py](test_adaptations_use_the_adaptation_layout.py) |
| aggregate | [test_aggregate.py](test_aggregate.py) |
| answer all | [test_answer_all.py](test_answer_all.py) |
| answer all route | [test_answer_all_route.py](test_answer_all_route.py) |
| answer route | [test_answer_route.py](test_answer_route.py) |
| answers | [test_answers.py](test_answers.py) |
| attention | [test_attention.py](test_attention.py) |
| band order | [test_band_order.py](test_band_order.py) |
| blocked band | [test_blocked_band.py](test_blocked_band.py) |
| candidates | [test_candidates.py](test_candidates.py) |
| compare | [test_compare.py](test_compare.py) |
| contract status | [test_contract_status.py](test_contract_status.py) |
| contracts route | [test_contracts_route.py](test_contracts_route.py) |
| decide service | [test_decide_service.py](test_decide_service.py) |
| drift route | [test_drift_route.py](test_drift_route.py) |
| forge candidate | [test_forge_candidate.py](test_forge_candidate.py) |
| forge catalogue | [test_forge_catalogue.py](test_forge_catalogue.py) |
| forge jobs | [test_forge_jobs.py](test_forge_jobs.py) |
| forge routes | [test_forge_routes.py](test_forge_routes.py) |
| forge services | [test_forge_services.py](test_forge_services.py) |
| forge state | [test_forge_state.py](test_forge_state.py) |
| full cycle | [test_full_cycle.py](test_full_cycle.py) |
| lookup | [test_lookup.py](test_lookup.py) |
| module page | [test_module_page.py](test_module_page.py) |
| propose service | [test_propose_service.py](test_propose_service.py) |
| questions | [test_questions.py](test_questions.py) |
| queue route | [test_queue_route.py](test_queue_route.py) |
| queue service | [test_queue_service.py](test_queue_service.py) |
| sources route | [test_sources_route.py](test_sources_route.py) |
| sources service | [test_sources_service.py](test_sources_service.py) |
| suggested | [test_suggested.py](test_suggested.py) |
| tools | [test_tools.py](test_tools.py) |
| validate route | [test_validate_route.py](test_validate_route.py) |
| visits | [test_visits.py](test_visits.py) |

Run `uv run pytest packages/mendel-api/tests/forge -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
