"""What is shipped.

`pipeline.yml` is the save file — the artifact an agent sets down, picks up, tunes and
re-emits — and everything here is either part of it or the evidence it carries: the digest
that pins a contract, the lockfile it replaced, the gate verdict, and the doors it crosses.

`egress.py` is here because publication *is* door 4 and the payload is the artifact itself:
what a person reads before publishing and what crosses the boundary cannot disagree.

**No re-exports.** See `declared/__init__.py`.
"""
