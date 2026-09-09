"""The living pipeline's authoring protocol.

`types.py` is the vocabulary both halves agree on; `state.py` (Task 3) is the pure transition
function over it. Nothing in this package talks to a provider or a database — that is
`services/authoring_ai.py` and `services/authoring.py`, which is the same split `review/` keeps
in `comeni-core`: the question is a type, and who answers it is somebody else's problem.
"""
