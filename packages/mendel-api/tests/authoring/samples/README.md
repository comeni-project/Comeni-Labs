# API authoring / samples tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| authoring characterise | [test_authoring_characterise.py](test_authoring_characterise.py) |
| authoring samples | [test_authoring_samples.py](test_authoring_samples.py) |
| authoring upload route | [test_authoring_upload_route.py](test_authoring_upload_route.py) |
| characterise excerpt | [test_characterise_excerpt.py](test_characterise_excerpt.py) |
| characterise reading | [test_characterise_reading.py](test_characterise_reading.py) |
| gap explain | [test_gap_explain.py](test_gap_explain.py) |
| gaps | [test_gaps.py](test_gaps.py) |
| inspect | [test_inspect.py](test_inspect.py) |
| measurers | [test_measurers.py](test_measurers.py) |
| protection | [test_protection.py](test_protection.py) |
| sample upload | [test_sample_upload.py](test_sample_upload.py) |

Run `uv run pytest packages/mendel-api/tests/authoring/samples -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../../README.md).
