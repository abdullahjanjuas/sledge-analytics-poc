"""Run one or more .sql files against the database.   Usage: python -m src.apply_sql sql/01_schema.sql"""
import sys
from pathlib import Path

from .db import connect


def main(paths: list[str]) -> None:
    with connect() as conn:  # the 'with' block commits at the end (or rolls back on error)
        for p in paths:
            sql = Path(p).read_text(encoding="utf-8")
            conn.execute(sql)
            print(f"applied {p}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m src.apply_sql FILE.sql [FILE2.sql ...]")
    main(sys.argv[1:])
