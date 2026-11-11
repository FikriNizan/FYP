import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def initialise():
    path = Path(current_app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    existing = db.execute("SELECT 1 FROM sqlite_master WHERE name='predictions'").fetchone()
    versioned = db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
    version = db.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0] if versioned else 0
    if version > 3:
        raise RuntimeError("Database schema is newer than this application")
    if version == 3:
        return
    # SQLite backup includes committed WAL pages. Never overwrite an earlier backup.
    if existing:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = path.with_name(path.name + '-pre-migration-' + stamp)
        with backup.open('xb'):
            pass
        with closing(sqlite3.connect(backup)) as copied:
            db.backup(copied)
    directory = Path(__file__).parent
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        # A second process may have upgraded while this connection waited for the lock.
        version = db.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
        if version == 3:
            db.commit()
            return
        if version < 1:
            for statement in (directory / 'schema.sql').read_text().split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute("INSERT INTO schema_migrations VALUES (1,?)", (datetime.now(timezone.utc).isoformat(),))
        if version < 2:
            for statement in (directory / 'migrations' / '002_reviewed_cases.sql').read_text().split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute("INSERT INTO schema_migrations VALUES (2,?)", (datetime.now(timezone.utc).isoformat(),))
        for statement in (directory / 'migrations' / '003_supplemental_continuity.sql').read_text().split(';'):
            if statement.strip():
                db.execute(statement)
        db.execute("INSERT INTO schema_migrations VALUES (3,?)", (datetime.now(timezone.utc).isoformat(),))
        db.commit()
    except Exception:
        db.rollback()
        raise
