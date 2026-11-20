"""Create once/resume the named M6 sandbox, migrate and verify business rows.

Original Working and M5 Test are opened read-only. No outcomes/scenarios are loaded.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from local_session import ROOT, WORKING, TEST, M6_TEST, new_test, resolved_existing


def business_snapshot(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity check failed')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                if r[0] not in ('schema_migrations','sqlite_sequence','ai_drafts','ai_reservations')]
        result={}
        for name in tables:
            rows=sorted(json.dumps(tuple(r),ensure_ascii=True,separators=(',',':')) for r in db.execute('SELECT * FROM "'+name+'"'))
            result[name]=dict(count=len(rows),sha256=hashlib.sha256('\n'.join(rows).encode()).hexdigest())
        version=db.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]
        return dict(schema_version=version,tables=result)


def prepare():
    before={str(path):business_snapshot(path) for path in (WORKING,TEST)}
    created=not M6_TEST.exists()
    if created:
        new_test(TEST,M6_TEST,'Reusable Milestone 6 Gemini decision-support verification; preserve original M5 Test')
    target,_,_,_=resolved_existing(M6_TEST)
    if target!=M6_TEST.absolute() or any(target.samefile(p) for p in (WORKING,TEST)):
        raise ValueError('Milestone 6 copy aliases a protected database')
    prior=business_snapshot(target)
    sys.path.insert(0,str(ROOT/'backend'))
    from churn_backend import create_app
    create_app(dict(DATABASE=str(target),TESTING=True))
    after=business_snapshot(target)
    if prior['tables']!=after['tables']:
        raise ValueError('Business records changed during cache migration')
    originals={str(path):business_snapshot(path) for path in (WORKING,TEST)}
    if originals!=before:
        raise ValueError('An original database changed during verification')
    report=dict(database=str(target),created=created,before=prior,after=after,
        originals_unchanged=True,originals=originals,
        change='Schema migration 5 adds ai_drafts/ai_reservations and a schema version; existing business rows unchanged')
    initial=ROOT/'artifacts'/'m6-data-verification.json'
    output=initial if not initial.exists() else ROOT/'artifacts'/'m6-data-current-verification.json'
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    prepare()
