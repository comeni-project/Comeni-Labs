# API settings tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| models per purpose | [test_models_per_purpose.py](test_models_per_purpose.py) |
| settings actions | [test_settings_actions.py](test_settings_actions.py) |
| settings codec | [test_settings_codec.py](test_settings_codec.py) |
| settings reports | [test_settings_reports.py](test_settings_reports.py) |
| settings routes | [test_settings_routes.py](test_settings_routes.py) |
| settings store | [test_settings_store.py](test_settings_store.py) |

Run `uv run pytest packages/mendel-api/tests/settings -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
