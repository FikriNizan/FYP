"""Explicit Working/Test launch and deliberate SQLite sandbox creation."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen

from copy_database import copy_database, inspect

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT / 'backend' / 'instance' / 'churn.sqlite'
M6_TEST = ROOT / 'artifacts' / 'm6-review.sqlite'
M8_DEMO = ROOT / 'artifacts' / 'm8-demo.sqlite'  # Phase B demo, built by scripts/demo_session.py
TEST = ROOT / 'artifacts' / 'm5-review-20261116-030542.sqlite'
BACKEND_URL = 'http://127.0.0.1:5000'
FRONTEND_URL = 'http://127.0.0.1:5173'


def resolved_existing(path):
    target = Path(path).resolve(strict=True)
    if not target.is_file():
        raise ValueError('Database path is not a file: ' + str(target))
    with closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as db:
        counts = inspect(db)
        has_version = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
        version = db.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0] if has_version else 0
        months = db.execute('SELECT cutoff_month,record_count FROM batches ORDER BY cutoff_month').fetchall()
    return target, version, months, counts


def selected_database(mode):
    if mode not in ('working','test','m6-test','m8-demo'):
        raise ValueError('Choose Working or Test explicitly')
    paths = {'working': WORKING, 'test': TEST, 'm6-test': M6_TEST, 'm8-demo': M8_DEMO}
    target, version, months, counts = resolved_existing(paths[mode])
    if mode == 'working' and target != WORKING.absolute():
        raise ValueError('Working path resolves outside the confirmed Working database')
    if mode == 'test' and (target != TEST.absolute() or os.path.samefile(target,WORKING)):
        raise ValueError('Test path is not the confirmed reusable sandbox')
    if mode == 'working' and version < 4:
        raise ValueError('Working schema is old. Exercise the migration on a copy first.')
    if mode == 'm6-test' and (target != M6_TEST.absolute() or os.path.samefile(target,WORKING) or os.path.samefile(target,TEST)):
        raise ValueError('Milestone 6 Test must be its own confirmed file')
    if mode == 'm8-demo' and (target != M8_DEMO.absolute() or any(p.exists() and os.path.samefile(target,p) for p in (WORKING,TEST,M6_TEST))):
        raise ValueError('The demo must be its own confirmed Test copy')
    if version > 6:
        raise ValueError('Database schema is newer than this app')
    return target, version, months, counts


def free_port(port):
    with socket.socket() as listener:
        listener.settimeout(.3)
        try:
            listener.bind(('127.0.0.1',port))
        except OSError as error:
            raise RuntimeError(f'Port {port} is occupied. Stop the existing server yourself, then retry.') from error


def child_environment(mode, database):
    env = os.environ.copy()
    env.pop('CHURN_DB_PATH',None)
    env.pop('VITE_API_TARGET',None)
    env.update(CHURN_DB_PATH=str(database), VITE_API_TARGET=BACKEND_URL,
               TXB_LOCAL_SESSION='1', TXB_LOCAL_MODE=mode)
    # Milestone 7: read-only OPR scenario package (files only; never a database).
    env.setdefault('TXB_SCENARIO_DIR', str(ROOT / 'artifacts' / 'm7-scenarios' / 'm7-opr-2'))
    return env


def expected_identity(mode, database):
    return dict(mode=mode,database_filename=database.name,
        database_path_sha256=hashlib.sha256(str(database).casefold().encode('utf-8')).hexdigest())


def read_context(url):
    with urlopen(url+'/api/runtime-context', timeout=2) as response:
        return json.load(response)


def await_context(url, child, expected, deadline=25):
    end=time.monotonic()+deadline
    while time.monotonic()<end:
        if child.poll() is not None:
            raise RuntimeError(f'Server process {child.pid} exited before readiness')
        try:
            context=read_context(url)
            if all(context.get(key)==value for key,value in expected.items()):
                return context
            raise RuntimeError('Runtime database identity does not match the selected mode/path')
        except (OSError,TimeoutError,ValueError):
            time.sleep(.2)
    raise RuntimeError('Server did not become ready at '+url)


WINDOWS_NODE = r'C:\Program Files\nodejs\node.exe'


def runtime_paths(root, platform=None, environ=None, which=shutil.which):
    """Project Python, Node and Vite for this platform. Windows keeps the existing .venv\\Scripts layout and
    Node default; elsewhere the virtual environment uses bin/ and Node is found on PATH. TXB_NODE_EXE wins."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    windows = platform.startswith('win')
    python = Path(root) / '.venv' / ('Scripts' if windows else 'bin') / ('python.exe' if windows else 'python')
    node = environ.get('TXB_NODE_EXE') or which('node') or (WINDOWS_NODE if windows else 'node')
    vite = Path(root) / 'frontend' / 'node_modules' / 'vite' / 'bin' / 'vite.js'
    return python, Path(node), vite


def stop_owned(children):
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
    for child in reversed(children):
        if child.poll() is None:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def launch(mode, backend_port=5000, frontend_port=5173):
    global BACKEND_URL, FRONTEND_URL
    if backend_port == frontend_port or not all(1024 <= p <= 65535 for p in (backend_port,frontend_port)):
        raise ValueError('Choose distinct unprivileged backend/frontend ports')
    BACKEND_URL=f'http://127.0.0.1:{backend_port}'
    FRONTEND_URL=f'http://127.0.0.1:{frontend_port}'
    if mode not in ('m6-test','m8-demo'):
        raise ValueError('Use milestone-5 code for Working/Milestone 5 Test; this branch launches m6-test or m8-demo')
    database, prior_version, months, counts = selected_database(mode)
    free_port(backend_port)
    free_port(frontend_port)
    env=child_environment(mode,database)
    python,node,vite=runtime_paths(ROOT)
    if not python.is_file() or not node.is_file() or not vite.is_file():
        raise ValueError('Local Python, Node or Vite is missing; install the existing project dependencies')
    before_backups=set(database.parent.glob(database.name+'-pre-migration-*'))
    children=[]
    expected=expected_identity(mode,database)
    try:
        backend=subprocess.Popen([str(python),'-m','flask','--app','app','run','--host','127.0.0.1',
                                  '--port',str(backend_port),'--no-reload'],cwd=ROOT/'backend',env=env)
        children.append(backend)
        backend_context=await_context(BACKEND_URL,backend,expected)
        frontend=subprocess.Popen([str(node),str(vite),'--host','127.0.0.1','--port',str(frontend_port),'--strictPort'],
                                  cwd=ROOT/'frontend',env=env)
        children.append(frontend)
        frontend_context=await_context(FRONTEND_URL,frontend,expected)
        if backend_context != frontend_context:
            raise RuntimeError('Frontend proxy and backend runtime contexts differ')
        if backend_context['schema_version'] != 6:
            raise RuntimeError('This app requires schema version 6 (migrated automatically with a backup)')
        new_backups=sorted(set(database.parent.glob(database.name+'-pre-migration-*'))-before_backups)
        print('\nLOCAL SESSION',flush=True)
        print('Mode:',mode.title(),'| Database:',database,flush=True)
        print('Schema:',prior_version,'->',backend_context['schema_version'],
              '| Backup:',', '.join(map(str,new_backups)) if new_backups else 'none',flush=True)
        print('Assessments:',', '.join(f'{month} ({count})' for month,count in months),
              '| Predictions:',counts['predictions'],flush=True)
        print('Backend:',BACKEND_URL,'PID:',backend.pid,flush=True)
        print('Frontend:',FRONTEND_URL,'PID:',frontend.pid,flush=True)
        print('Verified: Vite /api -> this backend ->',database.name,flush=True)
        print('Stop: Ctrl+C in this terminal.\n',flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        raise RuntimeError('A local server exited; the owned companion will be stopped')
    except KeyboardInterrupt:
        print('\nStopping this local session.',flush=True)
    finally:
        stop_owned(children)


def new_test(source, destination, purpose):
    source,_,_,_=resolved_existing(source)
    destination=Path(destination).resolve()
    if destination.parent != (ROOT/'artifacts').resolve():
        raise ValueError('New test sandbox must be directly inside artifacts/')
    if destination.exists():
        raise FileExistsError('Destination already exists: '+str(destination))
    if destination in (WORKING.resolve(),TEST.resolve()):
        raise ValueError('Cannot overwrite a confirmed database')
    metadata=Path(str(destination)+'.origin.json')
    if metadata.exists():
        raise FileExistsError('Copy metadata already exists: '+str(metadata))
    result=copy_database(source,destination)
    record=dict(source=str(source),destination=str(destination),
                created_at_utc=datetime.now(timezone.utc).isoformat(),purpose=purpose)
    with metadata.open('x',encoding='utf-8') as handle:
        json.dump(record,handle,indent=2)
    return dict(**result,metadata=str(metadata))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('working')
    sub.add_parser('test')
    m6=sub.add_parser('m6-test')
    m6.add_argument('--backend-port',type=int,default=5000)
    m6.add_argument('--frontend-port',type=int,default=5173)
    demo=sub.add_parser('m8-demo')
    demo.add_argument('--backend-port',type=int,default=5000)
    demo.add_argument('--frontend-port',type=int,default=5173)
    fresh=sub.add_parser('new-test')
    fresh.add_argument('--source',required=True)
    fresh.add_argument('--destination',required=True)
    fresh.add_argument('--purpose',required=True)
    args=parser.parse_args()
    try:
        if args.command=='new-test':
            print(json.dumps(new_test(args.source,args.destination,args.purpose),indent=2))
        else:
            launch(args.command, getattr(args,'backend_port',5000),getattr(args,'frontend_port',5173))
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as error:
        parser.exit(1,str(error)+'\n')


if __name__=='__main__':
    main()
