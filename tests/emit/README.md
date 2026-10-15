# Workflow emission tests

Tests exercise compiler output and cross-package construction. `test_counts.py` includes slow real-tool cases; select them with `make slow`. Other files cover channel names, fan-in, fan-out, joins, inputs, profiling and scope overrides.

| Subject | File |
|---|---|
| channel names | [test_channel_names.py](test_channel_names.py) |
| counts | [test_counts.py](test_counts.py) |
| draft labels | [test_draft_labels.py](test_draft_labels.py) |
| end to end | [test_end_to_end.py](test_end_to_end.py) |
| fan in | [test_fan_in.py](test_fan_in.py) |
| fan out | [test_fan_out.py](test_fan_out.py) |
| input form | [test_input_form.py](test_input_form.py) |
| join | [test_join.py](test_join.py) |
| profiling | [test_profiling.py](test_profiling.py) |
| runnable | [test_runnable.py](test_runnable.py) |
| samplesheet | [test_samplesheet.py](test_samplesheet.py) |
| scope override | [test_scope_override.py](test_scope_override.py) |
| two channels of one type | [test_two_channels_of_one_type.py](test_two_channels_of_one_type.py) |

Run `uv run pytest tests/emit -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
