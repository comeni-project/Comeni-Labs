"""The handlers, one module per section of the protocol (14.7.8.1). Importing this package
registers them (`services.session.handles`); 1c moves each section's code in beside them."""

from mendel_api.stages import building, describe, gathering, goal, samples  # noqa: F401
