"""The HTTP surface.

**Impure**, and the only package that may reach a database or a socket on the build path's
behalf — see invariant 1. The arrow is `mendel-api -> everything`, never the reverse.
"""
