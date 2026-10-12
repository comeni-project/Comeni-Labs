"""Retention limits are choices, so each reads in words on the menu (Part H spec §5.3).

`keep` is kept until a person deletes it; `0` is *when the run ends*, offered only for a run's
working files; any other value is a number of days.
"""

CHOICES = [("keep", "Kept until deleted"), ("1", "After 1 day"), ("7", "After 7 days"),
           ("30", "After 30 days"), ("90", "After 90 days"), ("365", "After 365 days")]
WHEN_IT_ENDS = ("0", "When the run ends")


def days(value: str) -> int | None:
    """A limit in days, or `None` for kept until deleted by hand."""
    return None if value == "keep" else int(value)
