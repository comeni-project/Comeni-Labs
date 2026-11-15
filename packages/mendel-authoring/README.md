# mendel-authoring

The pure core of the builder: the decisions a person or the builder agent made and who made them,
how they compose a goal, how a resolved pipeline becomes a blueprint and a reviewed draft, and
what a canvas edit means.

The package depends only on `comeni-core` and Pydantic. It does not access a network, database,
queue, clock, or model provider; `mendel-api` stores what it computes and supplies declared
registry data through small ports.

Documentation:

- [How the builder agent works](../../docs/explanation/builder-agent.md)
- [Build and inspect a pipeline](../../docs/how-to/pipelines/build.md)
- [Builder interface reference](../../docs/reference/pipelines/builder-interface.md)
