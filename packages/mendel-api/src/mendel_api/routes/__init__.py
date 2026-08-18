"""HTTP routes. Each validates, dispatches and serialises — nothing else.

The logic lives one module up: `questions.py` holds the projection and the aggregation, so
both can be tested without HTTP. That separation is what the no-logic-in-handlers
constraint means in practice rather than as a slogan.
"""
