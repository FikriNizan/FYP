"""Apply the supplied React source update after checking for local edits.

Run from the newly extracted package. Never updates databases, .venv or .git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe update path")
    if set(path.parts) & {".git", ".venv", "instance", "node_modules", "dist", ".upgrade-backups"}:
        raise ValueError("Protected update path")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Update path escapes project")
    return target


def update(source, destination, apply=False):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("Extract the new package separately and point this script at your existing project")
    if not (destination / "backend" / "app.py").is_file():
        raise ValueError("Destination must be the existing corporate-attrition-app root")
    manifest = json.loads((source / "scripts" / "react_update_manifest.json").read_text(encoding="utf-8"))
    planned = []
    conflicts = []
    for relative, expected in manifest["files"].items():
        supplied, target = safe_path(source, relative), safe_path(destination, relative)
        if not supplied.is_file() or digest(supplied) != expected:
            raise ValueError("Supplied update file differs from manifest: " + relative)
        if target.exists():
            current = digest(target)
            if current == expected:
                continue
            if current != manifest["baseline"].get(relative):
                conflicts.append(relative)
                continue
        planned.append((relative, "copy"))
    for relative in manifest["remove"]:
        target = safe_path(destination, relative)
        if target.exists():
            if digest(target) != manifest["baseline"].get(relative):
                conflicts.append(relative)
            else:
                planned.append((relative, "remove"))
    if conflicts:
        raise ValueError("Local edits found; no update files were written. Review these files before merging:\n" + "\n".join(conflicts))
    result = {"mode":"apply" if apply else "preview", "files_to_change":len(planned),
              "database_preserved":str(destination / "backend" / "instance" / "churn.sqlite")}
    if not apply or not planned:
        return result
    backup = destination / ".upgrade-backups" / datetime.now(timezone.utc).strftime("react-%Y%m%dT%H%M%S%fZ")
    for relative, _operation in planned:
        target = safe_path(destination, relative)
        if target.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    completed = []
    try:
        for relative, operation in planned:
            target = safe_path(destination, relative)
            completed.append(relative)
            if operation == "remove":
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_path(source, relative), target)
    except Exception:
        for relative in reversed(completed):
            target, saved = safe_path(destination, relative), backup / relative
            if saved.exists():
                shutil.copy2(saved, target)
            else:
                target.unlink(missing_ok=True)
        raise
    result["source_backup"] = str(backup)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply after preflight; without this flag only preview")
    args = parser.parse_args()
    try:
        print(json.dumps(update(ROOT, args.destination, args.apply), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
