# API authoring tests

Session tests cover commands, state transitions, model handoffs and stored build progress.
Shared scenarios live in `mendel_api_tests`; fixture scope is described in the parent index.

Related groups: [decisions](decisions/README.md) and [samples](samples/README.md).

| Behavior | File |
|---|---|
| Model calls and stored invocations | [test_authoring_ai.py](test_authoring_ai.py) |
| Stored session position | [test_authoring_at.py](test_authoring_at.py) |
| Diagram, handler and recorder bindings | [test_authoring_binding.py](test_authoring_binding.py) |
| Stored blueprints and build progress | [test_authoring_building.py](test_authoring_building.py) |
| Canvas graph, metadata and query count | [test_authoring_canvas.py](test_authoring_canvas.py) |
| Changes inferred from conversation | [test_authoring_chat_changes.py](test_authoring_chat_changes.py) |
| Command recording and queued jobs | [test_authoring_commands.py](test_authoring_commands.py) |
| Quoted wants and facts | [test_authoring_describe_heard.py](test_authoring_describe_heard.py) |
| Session transition dispatch | [test_authoring_dispatch.py](test_authoring_dispatch.py) |
| Transactions and post-commit jobs | [test_authoring_facade.py](test_authoring_facade.py) |
| Required questions and typed facts | [test_authoring_gathering.py](test_authoring_gathering.py) |
| Preview and retained artifact bytes | [test_authoring_keep.py](test_authoring_keep.py) |
| Consultant build and tier-4 stops | [test_authoring_no_mode.py](test_authoring_no_mode.py) |
| Saved alternative views | [test_authoring_preview.py](test_authoring_preview.py) |
| Committed prompt contracts | [test_authoring_prompts.py](test_authoring_prompts.py) |
| Tier-4 answers and refusals | [test_authoring_resolver.py](test_authoring_resolver.py) |
| HTTP conversation | [test_authoring_routes.py](test_authoring_routes.py) |
| Stored session lifecycle | [test_authoring_service.py](test_authoring_service.py) |
| State-machine transitions | [test_authoring_state.py](test_authoring_state.py) |
| Protocol data contracts | [test_authoring_types.py](test_authoring_types.py) |
| Blueprint construction against the registry | [test_blueprint.py](test_blueprint.py) |
| Resolver evidence in build cards | [test_build_plan.py](test_build_plan.py) |
| Step review through the facade | [test_stage_four_shell.py](test_stage_four_shell.py) |

Run `uv run pytest packages/mendel-api/tests/authoring -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
