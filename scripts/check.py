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
    for file in sorted((ROOT / "frontend" / "src").glob("*.js")):
        run([node, "--check", str(file)], ROOT)
    run([node, "--test", *map(str, sorted((ROOT / "frontend" / "tests").glob("*.test.mjs")))], ROOT)


if __name__ == "__main__":
    main()
