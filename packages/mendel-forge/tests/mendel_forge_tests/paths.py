"""Stable locations for forge test fixtures, independent of test-file grouping."""

from support.paths import PACKAGES

TESTS = PACKAGES / "mendel-forge" / "tests"
FIXTURES = TESTS / "fixtures"
