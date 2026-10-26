# mendel-authoring

The pure authoring core that turns a conversation and canvas edits into a goal, a reviewed draft,
and an auditable pipeline. One declarative protocol defines the stages, acting nodes, forks, and
legal arrows; the interpreter and session transition table are derived from it.

The package depends only on `comeni-core` and Pydantic. It does not access a network, database,
queue, clock, or model provider; `mendel-api` supplies those effects through typed commands and
small declared-data ports.

Documentation:

- [How the authoring protocol works](../../docs/explanation/authoring-protocol.md)
- [Generated protocol diagram](../../docs/explanation/diagrams/authoring-protocol.md)
- [Build and inspect a pipeline](../../docs/how-to/pipelines/build.md)
- [Builder interface reference](../../docs/reference/pipelines/builder-interface.md)
