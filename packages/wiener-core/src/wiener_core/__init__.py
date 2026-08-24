"""Run state, and what to do about it. **Pure** — invariant 1 covers this package.

Supervision splits into *deciding* and *doing*, and only the doing touches the world.
`fold` turns a sequence of Nextflow events into a `RunState`; `decide` turns a `RunState`
into typed `Intent`s that somebody else performs. Neither reads a clock, opens a socket
or knows that `wiener-api` exists.

`docs/design/wiener.md` §3 is the argument; §6 is the claim this package's tests hold:
same event sequence in -> same run state, same decisions.
"""
