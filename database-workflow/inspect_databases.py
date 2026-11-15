"""Read-only inventory of TxB databases; never import or start the Flask app."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

TABLES = (
    "batches", "predictions", "reviews", "review_history", "actions",
    "schema_migrations", "reviewed_cases", "case_events", "follow_ups",
    "follow_up_events", "supplemental_evidence", "supplemental_history",
    "review_case_links", "observed_outcomes",
)
CORE = {"batches", "predictions", "reviews", "review_history", "actions"}


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def json_value(value):
    if isinstance(value, bytes):
        return {"blob_sha256": hashlib.sha256(value).hexdigest()}
    return value


def hash_rows(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps([json_value(v) for v in row], ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def candidate_name(path):
    name = path.name.lower()
    return (".sqlite" in name or name.endswith(".db") or ".db-" in name) and not name.endswith(
        ("-wal", "-shm", "-journal"))


def candidates(project, extra=()):
    found = {}
    for folder in (project / "backend" / "instance", project / "artifacts"):
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file() and candidate_name(path):
                    found[str(path.resolve())] = path.resolve()
    for path in project.glob("*"):
        if path.is_file() and candidate_name(path):
            found[str(path.resolve())] = path.resolve()
    for path in extra:
        resolved = Path(path).expanduser().resolve()
        found[str(resolved)] = resolved
    return sorted(found.values(), key=lambda path: str(path).casefold())


def inspect_database(path):
    path = Path(path).resolve()
    result = {"path": str(path), "exists": path.is_file()}
    if not result["exists"]:
        result["error"] = "File does not exist; it was not created."
        return result
    info = path.stat()
    result.update(bytes=info.st_size,
                  modified_utc=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat())
    try:
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                result["error"] = "Not a SQLite database header; no repair attempted."
                return result
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only = ON")
            db.execute("BEGIN")
            names = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            result["app_database"] = CORE <= names
            result["quick_check"] = [row[0] for row in db.execute("PRAGMA quick_check(1)")]
            result["foreign_key_issues"] = [list(row) for row in
                                           db.execute("PRAGMA foreign_key_check").fetchmany(20)]
            counts, hashes = {}, {}
            for table in TABLES:
                if table not in names:
                    continue
                counts[table] = db.execute("SELECT COUNT(*) FROM " + identifier(table)).fetchone()[0]
                columns = db.execute("PRAGMA table_info(" + identifier(table) + ")").fetchall()
                primary = [col["name"] for col in sorted(columns, key=lambda col: col["pk"]) if col["pk"]]
                order = primary or [col["name"] for col in columns]
                query = "SELECT * FROM " + identifier(table) + " ORDER BY " + ",".join(map(identifier, order))
                hashes[table] = hash_rows(db.execute(query))
            result.update(table_counts=counts, table_content_sha256=hashes)
            result["schema_version"] = (db.execute(
                "SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
                if "schema_migrations" in names else None)
            if CORE <= names:
                scoring_columns = ("prediction_id", "batch_id", "cus_id", "risk",
                                   "review_alert", "evidence_json", "features_json")
                result["scoring_evidence_sha256"] = hash_rows(db.execute(
                    "SELECT " + ",".join(map(identifier, scoring_columns)) +
                    " FROM predictions ORDER BY prediction_id"))
                batches = []
                for batch in db.execute(
                        "SELECT batch_id,cutoff_month,source_kind,record_count "
                        "FROM batches ORDER BY cutoff_month,batch_id").fetchall():
                    item = dict(batch)
                    item["predictions"] = db.execute(
                        "SELECT COUNT(*) FROM predictions WHERE batch_id=?", (batch["batch_id"],)).fetchone()[0]
                    for table in ("reviews", "observed_outcomes", "reviewed_cases"):
                        item[table] = (db.execute(
                            "SELECT COUNT(*) FROM " + identifier(table) +
                            " t JOIN predictions p ON t.prediction_id=p.prediction_id WHERE p.batch_id=?",
                            (batch["batch_id"],)).fetchone()[0] if table in names else None)
                    batches.append(item)
                result["batches"] = batches
            db.rollback()
    except (sqlite3.Error, OSError, ValueError) as error:
        result["error"] = str(error)
    return result


def build_report(project, extra=()):
    project = Path(project).resolve()
    default = project / "backend" / "instance" / "churn.sqlite"
    environment = os.environ.get("CHURN_DB_PATH")
    shell_target = Path(environment).expanduser().resolve() if environment else default.resolve()
    paths = candidates(project, [default, shell_target, *extra])
    databases = [inspect_database(path) for path in paths]
    for item in databases:
        item["is_default_working_path"] = Path(item["path"]) == default.resolve()
        item["is_next_launch_target_in_this_shell"] = Path(item["path"]) == shell_target
    groups = {}
    for item in databases:
        if "scoring_evidence_sha256" in item:
            groups.setdefault(item["scoring_evidence_sha256"], []).append(item["path"])
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project), "default_working_database": str(default.resolve()),
        "this_shell": {"CHURN_DB_PATH": environment,
                       "VITE_API_TARGET": os.environ.get("VITE_API_TARGET"),
                       "next_backend_launch_database": str(shell_target)},
        "scope": "Database connections are read-only; Flask was not imported, started or migrated. "
                 "This shell's environment does not identify the environment of an already running server.",
        "databases": databases,
        "same_scoring_evidence_groups": [paths for paths in groups.values() if len(paths) > 1],
        "selection": "No database was selected, restored, merged, reset or deleted. "
                     "Dates, sizes and larger row counts alone do not establish which file is authoritative.",
    }


def print_summary(report, report_path):
    print("READ-ONLY DATABASE INVENTORY")
    print("Project:", report["project_root"])
    print("Default working path:", report["default_working_database"])
    print("CHURN_DB_PATH in this shell:", repr(report["this_shell"]["CHURN_DB_PATH"]))
    print("VITE_API_TARGET in this shell:", repr(report["this_shell"]["VITE_API_TARGET"]))
    print("These settings do not prove what an already running server uses.")
    for item in report["databases"]:
        labels = []
        if item["is_default_working_path"]:
            labels.append("DEFAULT WORKING PATH")
        if item["is_next_launch_target_in_this_shell"]:
            labels.append("NEXT LAUNCH IN THIS SHELL")
        print("\n" + item["path"] + (" [" + "; ".join(labels) + "]" if labels else ""))
        if item.get("error"):
            print("  ERROR:", item["error"])
            continue
        if not item.get("app_database"):
            print("  Not recognised as a complete TxB app database.")
            continue
        counts = item.get("table_counts", {})
        print("  Schema:", item["schema_version"], "| quick_check:", ",".join(item["quick_check"]),
              "| foreign-key issues:", len(item["foreign_key_issues"]))
        print("  " + " | ".join(f"{name}={counts.get(name, 'not present')}" for name in
              ("predictions", "reviews", "reviewed_cases", "follow_up_events", "observed_outcomes")))
        for batch in item.get("batches", []):
            print("  ", batch["cutoff_month"], batch["batch_id"][:12],
                  f"predictions={batch['predictions']} reviews={batch['reviews']} outcomes={batch['observed_outcomes']}")
    print("\nFull report:", report_path)
    print("No source database records were changed. No working-file choice was made.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--database", type=Path, action="append", default=[],
                        help="Also inspect an explicit path outside the normal folders")
    parser.add_argument("--out", type=Path, help="New JSON report; existing files are never overwritten")
    args = parser.parse_args()
    try:
        report = build_report(args.project_root, args.database)
        destination = (args.out or args.project_root.resolve() / "artifacts" /
                       ("database-audit-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        + "-" + uuid.uuid4().hex[:6] + ".json")).resolve()
        if destination.suffix.lower() != ".json":
            raise ValueError("The report output must be a new .json file.")
        if destination.exists():
            raise FileExistsError("Report already exists; choose a new --out path.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        print_summary(report, destination)
        return 0
    except (OSError, sqlite3.Error, ValueError) as error:
        print("Audit stopped:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
