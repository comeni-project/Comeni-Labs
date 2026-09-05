How this tool reports its own version, as a command that can actually be run inside the container
that was pinned.

Take it from documentation, a Dockerfile, or a usage example — never from what similar tools do.
`--version` is a convention, not a guarantee, and many bioinformatics tools print their version
only as part of a usage message on stderr, or not at all.

If nothing in the evidence shows the tool printing a version, say so and leave it open. A module
that runs an unsupported flag fails in a place that looks like a broken container.
