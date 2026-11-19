"""One canonical JSON text for what this project digests or keys by (#595).

Sorted keys and no whitespace: the same value is the same bytes in any process. Drafts'
fingerprints, decision site keys and review fingerprints each spelled it out; they call this now,
with the bytes unchanged, so a digest already stored still matches.

**Not every digest in the project uses it, on purpose.** `forge_review` sorts keys but keeps
JSON's default separators, and `forge_tests` hashes `repr()` pairs; moving either would change
the bytes of digests already stored. `comeni_core.artifact.digest` covers models and directories.
"""

import json


def canonical_json(value) -> str:
    """`value` as JSON with sorted keys and compact separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
