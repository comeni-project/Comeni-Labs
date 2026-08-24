"""Run management: launch, watch, remember. **Impure** — this is the half that touches the world.

`wiener-core` decides; nothing here does. A subprocess is started, a POST is received, Postgres
is written, a Redis stream is appended to — and every decision behind those actions was made by
a pure function that could be replayed in a test with no infrastructure at all.

`docs/design/wiener.md` §3.
"""
