"""Default read-only legacy inventory. Application is owned by the frozen Alembic upgrade."""

import argparse
import json

from mendel_api.db import engine
from mendel_api.services.decision_migration import inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="read-only inventory (the default)")
    parser.parse_args()
    with engine.connect() as connection:
        print(json.dumps(inventory(connection), indent=2))


if __name__ == "__main__":
    main()
