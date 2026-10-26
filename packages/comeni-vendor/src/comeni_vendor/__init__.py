"""Fetch pinned module source into registry layers and verify vendored contents.

Vendoring is an I/O operation performed before a layer is committed. Pipeline construction reads
the resulting layer from disk and does not fetch source. ``add`` replaces a module copy and writes
its declaration; ``check`` compares stored content with its declaration or pinned upstream.
"""

from comeni_vendor.ops import CheckResult, add, check

__all__ = ["CheckResult", "add", "check"]
