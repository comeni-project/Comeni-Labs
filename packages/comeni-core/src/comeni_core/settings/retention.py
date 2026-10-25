"""Retention choices and conversion to optional day limits.

`keep` means no automatic deletion, `0` means when a run ends, and other values are day counts.
"""

CHOICES = [("keep", "Kept until deleted"), ("1", "After 1 day"), ("7", "After 7 days"),
           ("30", "After 30 days"), ("90", "After 90 days"), ("365", "After 365 days")]
WHEN_IT_ENDS = ("0", "When the run ends")


def days(value: str) -> int | None:
    """A limit in days, or `None` for kept until deleted by hand."""
    return None if value == "keep" else int(value)
