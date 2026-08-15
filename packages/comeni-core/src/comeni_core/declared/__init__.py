"""What a registry layer holds: contracts, measurements, vocabularies, roles.

Grouped by lifecycle stage so this directory and `ARCHITECTURE.md`'s five stages agree — a
reader asking "where is a contract validated" should not have to know our type names first.

`layered.py` and `layer.py` live here rather than beside the loaders that use them because
stacking is a property *of* declared data: invariant 11 says every kind stacks through one
mechanism, and that mechanism belongs with the kinds it stacks.

**No re-exports.** `comeni_core/__init__.py` is the public surface and this is not a second
one — two ways to spell one thing is how the two come to disagree.
"""
