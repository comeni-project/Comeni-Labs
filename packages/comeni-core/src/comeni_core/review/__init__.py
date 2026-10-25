"""Shared models for open review questions and provenance-bearing answers.

The dependency direction is ``spell <- review <- plan``. Review must not import plan because plan
decision models specialize ``Question`` and ``Answer``.
"""

from comeni_core.review.answer import Answer, ValueSource
from comeni_core.review.question import Candidate, Excerpt, Question

__all__ = ["Answer", "Candidate", "Excerpt", "Question", "ValueSource"]
