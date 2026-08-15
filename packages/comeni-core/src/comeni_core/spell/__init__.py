"""How a value is written down.

The marked string types every payload field must be one of, the routes that carry a resolved
value to a tool, and the directives Nextflow accepts. All three answer *what may this be
written as*, which is a different question from what it means.

`diagnostics.py` and `yaml_strict.py` stayed at the top level rather than joining these: one
is the error registry and one is a loader, and every group uses both. Filing them here would
be a claim about what they are that is not true.

**No re-exports.** See `declared/__init__.py`.
"""
