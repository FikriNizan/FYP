"""Explicit, repeatable Monitoring delivery scenario on the confirmed Test sandbox only."""
import argparse
import json
import os
from pathlib import Path
import sys

from local_session import ROOT, TEST, WORKING, selected_database

APRIL = 'bf0e828cdd426ae496ff36bd207acfcd02dccd928eebd14eea5027ce45c9204a'
ACTION_DATE = '2024-05-15'
MARKER = 'Local Test: Monitoring delivery scenario on 2024-05-15'


def safe_test_database(path=TEST):
    selected,_,_,_=selected_database('test')
    candidate=Path(path).resolve(strict=True)
    if candidate != selected or os.path.samefile(candidate,WORKING):
        raise ValueError('Scenario writes are allowed only in the confirmed reusable Test sandbox')
    return selected


def run():
    database=safe_test_database()
    os.environ['CHURN_DB_PATH']=str(database)
    sys.path.insert(0,str(ROOT/'backend'))
    from churn_backend import create_app, outcomes
    from churn_backend.db import get_db
    app=create_app()
    client=app.test_client()
    with app.app_context():
        row=get_db().execute("SELECT c.case_id,p.cus_id FROM reviewed_cases c "
            "JOIN predictions p ON p.prediction_id=c.prediction_id "
            "JOIN predictions april ON april.cus_id=p.cus_id "
            "JOIN observed_outcomes o ON o.prediction_id=april.prediction_id "
            "WHERE c.status='open' AND april.batch_id=? ORDER BY p.cus_id,c.case_id LIMIT 1",(APRIL,)).fetchone()
        if row is None:
            raise ValueError('No open linked case with an accepted April outcome exists in Test')
        case_id,customer_id=row['case_id'],row['cus_id']
        before=outcomes.report(APRIL)['outcome_coverage']
    response=client.get('/api/cases/'+case_id)
    if response.status_code!=200:
        raise RuntimeError('Could not load the selected case')
    case=response.json['case']
    matching=[task for task in case['follow_ups']
              if any(event.get('notes')==MARKER for event in task['history'])]
    if len(matching)>1:
        raise RuntimeError('Duplicate marked scenario tasks need manual review')
    if matching and matching[0]['current']['action_status']=='delivered':
        return dict(database=str(database),case_id=case_id,customer_id=customer_id,
                    follow_up_id=matching[0]['follow_up_id'],already_delivered=True,
                    before=before,after=before)
    if matching:
        task=matching[0]
        if task['current']['action_status']!='planned':
            raise RuntimeError('Marked scenario task is not planned or delivered')
    else:
        body=dict(expected_version=case['version'],action_type='rm_visit',action_status='planned',
                  action_date=ACTION_DATE,notes=MARKER,recorded_by='Local Test')
        response=client.post('/api/cases/'+case_id+'/follow-ups',json=body)
        if response.status_code!=201:
            raise RuntimeError('Planning rejected: '+str(response.json))
        updated=response.json['case']
        new_ids={task['follow_up_id'] for task in updated['follow_ups']} - {task['follow_up_id'] for task in case['follow_ups']}
        if len(new_ids)!=1:
            raise RuntimeError('Could not identify the newly planned test task')
        task=next(task for task in updated['follow_ups'] if task['follow_up_id'] in new_ids)
        case=updated
        with app.app_context():
            planned_coverage=outcomes.report(APRIL)['outcome_coverage']
        if planned_coverage['documented_delivery']!=before['documented_delivery']:
            raise RuntimeError('A planned task unexpectedly changed documented delivery')
    body=dict(expected_version=case['version'],action_type='rm_visit',action_status='delivered',
              action_date=ACTION_DATE,notes=MARKER,recorded_by='Local Test')
    response=client.post('/api/cases/'+case_id+'/follow-ups/'+task['follow_up_id']+'/events',json=body)
    if response.status_code!=201:
        raise RuntimeError('Delivery rejected: '+str(response.json))
    with app.app_context():
        after=outcomes.report(APRIL)['outcome_coverage']
    return dict(database=str(database),case_id=case_id,customer_id=customer_id,
                follow_up_id=task['follow_up_id'],already_delivered=False,before=before,after=after)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Required; this command writes one Test-only scenario')
    args=parser.parse_args()
    if not args.apply:
        parser.exit(1,'Pass --apply to run the explicit Test-only scenario.\n')
    try:
        print(json.dumps(run(),indent=2))
    except (OSError,ValueError,RuntimeError) as error:
        parser.exit(1,str(error)+'\n')


if __name__=='__main__':
    main()
