"""What was asked for, and what the data measurably looks like.

A shape, never data. Invariant 15: `Goal` holds type ids, states and declared measurements —
"paired, 150bp, reverse-stranded, twelve samples" is true of thousands of studies and
identifies nobody.

The module is `asked.py` rather than `goal.py`: a `goal` inside a `goal` is a stutter, and the
way out is a better name rather than a re-exporting `__init__`. The package is what was asked
for; the module is the asking.

`profile.pyi` sits beside `profile.py` because a `.pyi` **replaces** its module for a type
checker rather than adding to it — a stub left in another directory makes the module it
describes invisible.

**No re-exports.** See `declared/__init__.py`.
"""
