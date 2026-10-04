"""The authoring protocol, and the interpreter that runs it.

**The diagram is the program.** `protocol.PROTOCOL` declares the conversation's sections, nodes
and arrows; `docs/design/diagrams/` is drawn from it, the session's legal moves are derived from
it (`state`), and `interpret` runs it. The shell (`mendel-api`) binds a handler to each acting
node and stores where each session rests; nothing here touches a row, a queue or a model.
"""
