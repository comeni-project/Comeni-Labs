# Forge ai tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| ai context | [test_ai_context.py](test_ai_context.py) |
| ai evaluate | [test_ai_evaluate.py](test_ai_evaluate.py) |
| ai generate | [test_ai_generate.py](test_ai_generate.py) |
| ai prompts | [test_ai_prompts.py](test_ai_prompts.py) |
| ai render | [test_ai_render.py](test_ai_render.py) |
| ai schemas | [test_ai_schemas.py](test_ai_schemas.py) |
| ai select | [test_ai_select.py](test_ai_select.py) |
| model path is optional | [test_model_path_is_optional.py](test_model_path_is_optional.py) |
| ops model fill | [test_ops_model_fill.py](test_ops_model_fill.py) |

Run `uv run pytest packages/mendel-forge/tests/ai -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
