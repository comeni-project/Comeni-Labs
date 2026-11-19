"""One canonical JSON text (#595)."""

import json

from mendel_authoring.canonical import canonical_json


def test_the_canonical_text_is_the_bytes_each_digest_was_made_from():
    """Drafts, decision sites and reviews each wrote `json.dumps(sort_keys, compact)`; they call
    `canonical_json` now, and digests already stored must still match, so the bytes are pinned."""
    value = {"b": [1, {"y": None, "x": "é"}], "a": True}
    assert canonical_json(value) == json.dumps(value, sort_keys=True, separators=(",", ":"))
    assert canonical_json(value) == '{"a":true,"b":[1,{"x":"\\u00e9","y":null}]}'
