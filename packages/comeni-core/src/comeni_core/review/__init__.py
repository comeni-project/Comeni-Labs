"""What is open, and how it gets closed.

The stage between derivation and approval: a question nobody has answered yet, and the
answer with the provenance of who settled it. Shared by `mendel-forge`, which asks about a
contract it is drafting, and by the resolver, which asks about a pipeline it is building.

**This subpackage must not import `comeni_core.plan`.** `plan/decision.py` imports `Question`
from here, so the reverse edge is a cycle. The order is `spell/ <- review/ <- plan/`, and it
is why `ValueSource` lives in `review/answer.py` rather than in `plan/tiers.py` where it was
first written. See the spec's §9.1.
"""

from comeni_core.review.answer import Answer, ValueSource
from comeni_core.review.question import Candidate, Excerpt, Question

__all__ = ["Answer", "Candidate", "Excerpt", "Question", "ValueSource"]
