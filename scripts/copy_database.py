"""Copy an existing app database without overwriting either working copy."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

TABLES = ("batches", "predictions", "reviews", "review_history", "actions")
ROOT = Path(__file__).resolve().parents[1]


def inspect(connection):
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = set(TABLES) - tables
    if missing:
        raise ValueError("Not an attrition app database; missing tables: " + ", ".join(sorted(missing)))
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign-key check failed")
    return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in TABLES}


def copy_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Source database does not exist: " + str(source))
    if source == destination:
        raise ValueError("Choose a different destination; the source is preserved")
    # Read-only source plus SQLite's backup API also includes committed WAL data.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        before = inspect(original)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb"):
            pass  # Exclusive creation refuses an existing destination.
        try:
            with closing(sqlite3.connect(destination)) as copied:
                original.backup(copied)
                after = inspect(copied)
            if before != after:
                raise ValueError("Database counts changed during copying. Stop the app and retry.")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return {"source_preserved": str(source), "destination": str(destination), "tables": after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", type=Path, default=ROOT / "backend" / "instance" / "churn.sqlite")
    args = parser.parse_args()
    try:
        print(json.dumps(copy_database(args.source, args.destination), indent=2))
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, "Copy refused: " + str(error) + "\n")


if __name__ == "__main__":
    main()
