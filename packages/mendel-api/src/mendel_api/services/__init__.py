"""What the API does, as functions rather than as routes.

A route validates, dispatches and serialises. Everything else lives here, so it can be tested
without HTTP and so a second transport could call it unchanged — the same argument
`mendel_forge.ops` makes one package over.
"""
