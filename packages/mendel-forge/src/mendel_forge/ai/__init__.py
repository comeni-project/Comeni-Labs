"""What a model is told about one adaptation, and what is done with what it says.

**The dossier is a value, not a string.** §5.3 of the Forge MVP plan asks for a context
manifest recording every omission, and text cannot carry one: once the sections have been
concatenated there is nothing left that knows what did not go in. So the composition is a
list of addressable segments reduced by a pure function, and rendering happens last.

That has a second effect, which is why Task 6 builds it first. Everything up to the moment of
the call — selection, ranking, budget, rendering — is deterministic and can be held to golden
files with **no model involved at all**, which is where most of the defects in a prompt stack
live.

Nothing in this package writes a file. `render.py` composes candidate text and
`Workspace.write_bundle` writes it, so the write boundary stays where Task 5 left it.
"""
