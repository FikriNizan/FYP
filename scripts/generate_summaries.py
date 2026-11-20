"""Batch "What stands out" summaries for FLAGGED customers of one saved batch (M6 Test only).

Run after an assessment is published. Reuses ai_drafts evidence, validation, cache identity and
storage. Resumable: customers with a stored draft matching the current cache key are skipped.
The database is always the pinned Milestone 6 Test file; there is deliberately no path option.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
import sys
import time

from local_session import ROOT, selected_database

ARTIFACTS = ROOT / 'artifacts'
# Daily quota is gone, or the per-minute limit persisted through every retry: stop, do not burn calls.
STOP_CODES = {'provider_quota_exhausted', 'provider_rate_limited'}
# Configuration/request failures that would repeat identically for every remaining customer.
STOP_IMMEDIATE = {'not_configured', 'invalid_key_format', 'provider_authentication_failed', 'provider_access_denied',
                  'provider_model_unavailable', 'provider_request_rejected'}
OUTAGE_LIMIT = 3  # Consecutive customers ending in provider_unavailable (each already retried).


def eligible_ids(db, batch_id):
    if not db.execute('SELECT 1 FROM batches WHERE batch_id=?', (batch_id,)).fetchone():
        raise ValueError('Unknown batch ID: ' + batch_id)
    # Saved canonical flag only; never recomputed from risk.
    return [row[0] for row in db.execute('SELECT prediction_id FROM predictions WHERE batch_id=? AND review_alert=1 '
                                         'ORDER BY risk DESC, prediction_id', (batch_id,))]


def classify(ai_drafts, ids):
    """Read-only: load() rolls back its transaction and never calls the provider."""
    from churn_backend.validation import ValidationError
    cached, pending, invalid, hashes = [], [], [], {}
    for prediction_id in ids:
        try:
            state, _, _ = ai_drafts.load('summary', prediction_id)
        except ValidationError:
            invalid.append(prediction_id)
            continue
        hashes[prediction_id] = state['evidence_hash']
        (cached if state['state'] == 'saved' else pending).append(prediction_id)
    return cached, pending, invalid, hashes


def write_rejected(path, prediction_id, model, diagnostic, raw):
    failures = (diagnostic or {}).get('contract_audit', {}).get('failures', [])
    record = dict(prediction_id=prediction_id, captured_at=datetime.now(timezone.utc).isoformat(), model=model,
                  first_rule=(diagnostic or {}).get('rule'),
                  rules=[dict(rule=f.get('rule'), path=f.get('path')) for f in failures], raw_output=raw)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')


def run(args, out=print):
    from flask import g
    from churn_backend import ai_drafts
    from churn_backend.db import get_db
    from churn_backend.validation import ConflictError
    started = time.monotonic()
    ids = eligible_ids(get_db(), args.batch_id)
    cached, pending, invalid, hashes = classify(ai_drafts, ids)
    out(f'Batch {args.batch_id} | eligible (flagged): {len(ids)} | already cached: {len(cached)} | '
        f'to generate: {len(pending)} | invalid evidence: {len(invalid)}')
    if args.dry_run:
        out('Dry run: zero API calls; nothing written.')
        return 0
    # A retry never fires sooner than the minimum request interval.
    base = max(ai_drafts.BATCH['base'], 2 * args.min_interval)
    policy = dict(ai_drafts.BATCH, base=base, cap=max(ai_drafts.BATCH['cap'], base))
    rejected_path = ARTIFACTS / ('m6-rejected-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.jsonl')
    generated, rejected_count, fallbacks, stopped, last, outage = 0, 0, Counter(), None, None, 0
    for prediction_id in pending[:args.limit]:
        if last is not None:
            wait = args.min_interval - (time.monotonic() - last)
            if wait > 0:
                ai_drafts.sleep(wait)
        last = time.monotonic()
        for name in ('genai_rejected_output', 'genai_diagnostic'):
            g.pop(name, None)
        try:
            result = ai_drafts.generate('summary', prediction_id, {'expected_evidence_hash': hashes[prediction_id]},
                                        retry=policy)
        except ConflictError:
            fallbacks['conflict'] += 1
            outage = 0
            continue
        if result['state'] == 'saved':
            generated += 1
            outage = 0
            continue
        code = result['failure_code']
        fallbacks[code] += 1
        outage = outage + 1 if code == 'provider_unavailable' else 0
        if args.keep_rejected and g.get('genai_rejected_output') is not None:
            write_rejected(rejected_path, prediction_id, result.get('model'), g.get('genai_diagnostic'),
                           g.genai_rejected_output)
            rejected_count += 1
        if code in STOP_CODES or code in STOP_IMMEDIATE:
            stopped = code
            break
        if outage >= OUTAGE_LIMIT:
            stopped = 'outage'
            break
    remaining = len(pending) - generated
    if stopped == 'provider_quota_exhausted':
        out(f'Stopped: daily quota exhausted. {remaining} flagged customers remain without a stored summary.')
    elif stopped in STOP_IMMEDIATE:
        out(f'Stopped: {stopped} would repeat for every customer; fix configuration or request first. '
            f'{remaining} flagged customers remain.')
    elif stopped == 'outage':
        out(f'Stopped: Gemini unavailable for {OUTAGE_LIMIT} consecutive customers (likely outage). '
            f'{remaining} flagged customers remain.')
    elif stopped:
        out(f'Stopped: rate limit persisted after retries. {remaining} flagged customers remain.')
    if rejected_count:
        out(f'Rejected outputs kept: {rejected_count} -> {rejected_path}')
    out(f'Generated: {generated} | Fallback by reason: {json.dumps(dict(sorted(fallbacks.items())))} | '
        f'Skipped (cached): {len(cached)} | Remaining: {remaining} | Elapsed: {time.monotonic() - started:.1f}s')
    return 2 if stopped else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Count eligible/cached/to-generate; zero API calls')
    parser.add_argument('--limit', type=int, default=20, help='Maximum customers to generate this run (default 20)')
    parser.add_argument('--min-interval', type=float, default=6.0,
                        help='Minimum seconds between request starts (default 6 = 10 requests/minute)')
    parser.add_argument('--keep-rejected', action='store_true',
                        help='Append rejected outputs and rule IDs to an ignored artifacts/ JSONL file')
    args = parser.parse_args(argv)
    if args.limit < 1 or args.min_interval < 0:
        parser.error('--limit must be at least 1 and --min-interval non-negative')
    # Only checks the variables are set; the key value is never read, printed or stored here.
    if not args.dry_run and (os.environ.get('TXB_GENAI_ENABLED') != '1' or not os.environ.get('GEMINI_API_KEY')):
        parser.error('Configure backend TXB_GENAI_ENABLED=1 and GEMINI_API_KEY locally first (or use --dry-run)')
    database, _, _, _ = selected_database('m6-test')  # Refuses Working, M5 Test and aliases.
    sys.path.insert(0, str(ROOT / 'backend'))
    from churn_backend import create_app
    app = create_app(dict(DATABASE=str(database), TXB_LOCAL_SESSION=True, TXB_LOCAL_MODE='m6-test',
                          TXB_GENAI_KEEP_REJECTED=args.keep_rejected))
    with app.app_context():
        try:
            code = run(args)
        except ValueError as error:
            parser.exit(1, str(error) + '\n')
    raise SystemExit(code)


if __name__ == '__main__':
    main()
