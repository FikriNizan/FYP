"""Inspect a redacted synthetic contract fixture offline. No app/DB/provider is started."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture',type=Path)
    args=parser.parse_args()
    data=json.loads(args.fixture.read_text(encoding='utf-8'))
    if data.get('format')!='m6-synthetic-contract-replay-1':
        parser.error('Select a redacted M6 synthetic contract fixture')
    from churn_backend import ai_drafts, repository as repo
    report=ai_drafts.audit_output(repo.encode(data['output']),data['evidence'])
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
