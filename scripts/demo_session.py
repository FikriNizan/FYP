"""Phase B demo session (outside the product): a named Test copy showing auto-grading on upload.

    .\\.venv\\Scripts\\python.exe scripts\\demo_session.py build --research-root <R>
    .\\.venv\\Scripts\\python.exe scripts\\demo_session.py build --research-root <R> --rebuild
    .\\.venv\\Scripts\\python.exe scripts\\local_session.py m8-demo --backend-port 5086 --frontend-port 5196

build:
1. Copies the Milestone 6 Test database (artifacts/m6-review.sqlite, read through the SQLite backup API) to
   artifacts/m8-demo.sqlite. Never the Working database. --rebuild replaces only that demo file, and only when its
   origin record marks it as this demo. Re-run it after a new summary batch so the demo carries current summaries.
2. Checks that the copy holds the February, March and April 2024 assessments and nothing later, then removes the
   observed outcomes IN THE COPY ONLY, so no assessment is checked yet.
3. Ensures the May 2024 prepared package exists in artifacts/m8-packages/prepared-2024-05 (features.csv +
   manifest.json). If it is missing it is prepared with the offline milestone-4 script, which only reads the
   research folder; the research folder listing is compared before and after, and any change stops the run.
Then, in the browser: Monthly Assessments -> upload the two May files -> "February 2024 is now ready to check".
"""
import argparse
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import local_session as local  # noqa: E402

PURPOSE = 'm8-demo: Feb-Apr 2024 published, outcomes cleared in this copy; upload May 2024 to see auto-grading'
PACKAGE = ROOT / 'artifacts' / 'm8-packages' / 'prepared-2024-05'
PREPARE_SCRIPT = Path(os.environ.get('TXB_PREPARE_SCRIPT') or
                      ROOT.parent / 'milestone-4-offline-preparation' / 'monthly_prepare_and_verify.py')
EXPECTED_MONTHS = ['2024-02-29', '2024-03-31', '2024-04-30']


def listing(folder):
    spec = importlib.util.spec_from_file_location('opr_scenarios', ROOT / 'scripts' / 'opr_scenarios.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.listing(folder)


def remove_previous_demo():
    """Deletes only artifacts/m8-demo.sqlite (and its origin record and SQLite side files), only if it is this demo."""
    demo, origin = local.M8_DEMO, Path(str(local.M8_DEMO) + '.origin.json')
    if not demo.exists():
        return
    protected = [local.WORKING, local.TEST, local.M6_TEST]
    if any(p.exists() and os.path.samefile(demo, p) for p in protected):
        raise SystemExit('STOPPED: the demo path resolves to a protected database')
    record = json.loads(origin.read_text(encoding='utf-8')) if origin.exists() else {}
    if record.get('purpose') != PURPOSE:
        raise SystemExit('STOPPED: artifacts/m8-demo.sqlite exists but is not recorded as this demo; it was left untouched')
    for path in (demo, Path(str(demo) + '-wal'), Path(str(demo) + '-shm'), origin):
        if path.exists():
            path.unlink()


def clear_outcomes_in_copy():
    with closing(sqlite3.connect(local.M8_DEMO)) as db:
        months = [row[0] for row in db.execute("SELECT DISTINCT cutoff_month FROM batches "
                                               "WHERE source_kind<>'notebook_case_sample' ORDER BY cutoff_month")]
        if months != EXPECTED_MONTHS:
            raise SystemExit(f'STOPPED: the demo copy must hold exactly Feb, Mar and Apr 2024 assessments, found {months}')
        removed = db.execute('DELETE FROM observed_outcomes').rowcount
        db.commit()
        left = db.execute('SELECT count(*) FROM observed_outcomes').fetchone()[0]
    return months, removed, left


def ensure_may_package(research_root):
    if (PACKAGE / 'features.csv').is_file() and (PACKAGE / 'manifest.json').is_file():
        prepared = False
    else:
        if not research_root:
            raise SystemExit('STOPPED: the May 2024 package is missing; pass --research-root to prepare it (read-only)')
        if not PREPARE_SCRIPT.is_file():
            raise SystemExit(f'STOPPED: offline preparation script not found: {PREPARE_SCRIPT}')
        before = listing(research_root)
        subprocess.run([sys.executable, '-I', '-B', str(PREPARE_SCRIPT), 'prepare', '--research-root', str(research_root),
                        '--month', '2024-05', '--out', str(PACKAGE)], check=True)
        if listing(research_root) != before:
            raise SystemExit('STOPPED: the research folder listing changed during preparation')
        prepared = True
    if PREPARE_SCRIPT.is_file():
        subprocess.run([sys.executable, '-I', '-B', str(PREPARE_SCRIPT), 'validate', '--package-dir', str(PACKAGE)],
                       check=True, stdout=subprocess.DEVNULL)
    return prepared


def build(research_root=None, rebuild=False):
    if local.M8_DEMO.exists() and not rebuild:
        raise SystemExit('STOPPED: artifacts/m8-demo.sqlite already exists; use --rebuild to replace this demo copy')
    if rebuild:
        remove_previous_demo()
    copied = local.new_test(local.M6_TEST, local.M8_DEMO, PURPOSE)
    months, removed, left = clear_outcomes_in_copy()
    prepared = ensure_may_package(research_root)
    return dict(database=str(local.M8_DEMO), source=str(local.M6_TEST), assessments=months,
                outcomes_removed_in_copy=removed, outcomes_left=left, may_package=str(PACKAGE),
                may_package_prepared_now=prepared, copy=copied,
                launch=r'.\.venv\Scripts\python.exe scripts\local_session.py m8-demo --backend-port 5086 --frontend-port 5196')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('build')
    command.add_argument('--research-root', help='Read-only research folder, used only if the May package is missing')
    command.add_argument('--rebuild', action='store_true', help='Replace the existing demo copy (only this demo file)')
    args = parser.parse_args(argv)
    print(json.dumps(build(args.research_root, args.rebuild), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
