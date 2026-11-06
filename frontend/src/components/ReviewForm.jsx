import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { decisionLabel } from '../format.js';
import { ErrorNotice } from './Common.jsx';

function initialFields(review) {
  return { decision: review.decision === 'awaiting_review' ? '' : review.decision, reason: review.reason || '', reviewer: review.reviewer || '', owner: review.owner || '', next_action_date: review.next_action_date || '', operations_notes: review.operations_notes || '', finance_notes: review.finance_notes || '' };
}
export default function ReviewForm({ customer, workflow }) {
  const id = customer.prediction_id;
  const draft = workflow.drafts[id];
  const [fields, setFields] = useState(() => draft?.fields || initialFields(customer.review));
  const [expectedVersion,setExpectedVersion] = useState(() => draft?.expectedVersion ?? customer.review.version);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(Boolean(draft));
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const change = event => {
    const next = { ...fields, [event.target.name]: event.target.value };
    setFields(next); setDirty(true);
    workflow.rememberDraft(id, { fields: next, expectedVersion });
  };
  const submit = async event => {
    event.preventDefault();
    if (workflow.saving) return;
    workflow.setSaving(true); setError(null);
    workflow.rememberDraft(id, { fields, expectedVersion });
    try {
      await api.saveReview(id, { ...fields, next_action_date: fields.next_action_date || null, expected_version: expectedVersion });
      workflow.saved(customer);
    } catch (error) { if (mounted.current) setError(error); }
    finally { workflow.setSaving(false); }
  };
  const discard = () => {
    setFields(initialFields(customer.review));setExpectedVersion(customer.review.version);
    setDirty(false);setError(null);workflow.discardDraft(id);
  };
  return <aside id="decision-section" className="panel review-sidebar"><h2>Record committee decision</h2><p className="muted">Save your judgement. Outreach can be recorded later.</p>
    <form className="review-form" onSubmit={submit}><fieldset disabled={workflow.saving}>
      <label htmlFor="decision">Decision</label><select id="decision" name="decision" value={fields.decision} onChange={change} required><option value="">Choose a decision</option>{['prioritise','monitor','no_immediate_action'].map(value => <option key={value} value={value}>{decisionLabel(value)}</option>)}</select>
      <label htmlFor="reason">Decision reason</label><textarea id="reason" name="reason" value={fields.reason} onChange={change} required maxLength={4000} />
      <label htmlFor="reviewer">Reviewed by</label><input id="reviewer" name="reviewer" value={fields.reviewer} onChange={change} required maxLength={200} />
      <label htmlFor="owner">RM / action owner (optional)</label><input id="owner" name="owner" value={fields.owner} onChange={change} maxLength={200} />
      <label htmlFor="next_action_date">Next follow-up date (optional)</label><input id="next_action_date" name="next_action_date" type="date" value={fields.next_action_date} onChange={change} />
      <details><summary>Notes from each perspective (optional)</summary><label htmlFor="operations_notes">Operations notes</label><textarea id="operations_notes" name="operations_notes" value={fields.operations_notes} onChange={change} maxLength={4000} /><label htmlFor="finance_notes">Finance notes</label><textarea id="finance_notes" name="finance_notes" value={fields.finance_notes} onChange={change} maxLength={4000} /></details>
      <div className="form-actions"><button className="primary" type="submit">{workflow.saving ? 'Saving…' : 'Save decision'}</button><button type="button" disabled={!dirty || error?.status===409} onClick={discard}>Discard decision changes</button></div>
    </fieldset>
    <p className={'form-state '+(dirty ? 'is-dirty' : '')} role="status">{dirty ? 'Unsaved changes' : customer.review.version ? 'Saved decision · version '+customer.review.version : 'No decision saved yet'}</p>
    {error && <><ErrorNotice message={error.message} />{error.status === 409 && <><p className="muted">Your unsaved draft is still shown. Copy any notes you need before loading the saved review.</p><button type="button" onClick={() => { workflow.discardDraft(id); workflow.refresh(); }}>Discard draft and load latest decision</button></>}</>}
    </form>
  </aside>;
}
