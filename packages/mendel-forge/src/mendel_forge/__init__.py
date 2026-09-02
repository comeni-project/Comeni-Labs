"""The forge: scaffolding and verification for the registry.

`docs/notes/specs/2026-08-16-the-forge.md` is the design. The one property everything here
serves: a scaffold is not a half-built contract, so the forge cannot emit an invalid
declared file — only a valid one, or something that says which fields it is missing.
"""

from mendel_forge.sources import nfcore as _nfcore  # noqa: F401  — registers "nf-core"

__all__: list[str] = []
