"""The JSON column type every table uses.

Shape versions (a stamp per row, goldens, an upgrader per change) were removed on 2026-11-16
(#511): there is no backward compatibility before v0.1.0, so a migration that changes a JSON
column's shape rewrites or drops what it holds, and nothing checks a row's shape on load.
"""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

Json = JSON().with_variant(JSONB(), "postgresql")
"""Every JSON column's type: `JSONB` in Postgres, plain JSON in the SQLite the suite runs on."""
