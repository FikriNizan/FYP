"""Run the same local checks as GitHub CI; no customer database is opened."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-only", action="store_true", help="Skip the Node.js frontend checks")
    args = parser.parse_args()
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "backend")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT)
    if args.backend_only:
        return
    node = shutil.which("node")
    if not node:
        parser.exit(1, "Backend checks passed. Install Node.js 24 to run frontend checks, or use --backend-only.\n")
    npm = shutil.which("npm")
    if not npm:
        parser.exit(1, "npm is required for React checks. Install Node.js 24.15+ (24.x).\n")
    run([npm, "test"], ROOT / "frontend")
    run([npm, "run", "build"], ROOT / "frontend")


if __name__ == "__main__":
    main()
