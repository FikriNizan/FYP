import { api } from './api.js';
import { escapeHtml as e, isNumber, percent, money, count, monthLabel, forecastLabel,
  decisionLabel, activityChange, driverLabel, driverValue } from './format.js';

const app = document.querySelector('#app');
const selector = document.querySelector('#batch-select');
const notification = document.querySelector('#notification');
const drafts = new Map();
let batches = [], selectedBatch, routeVersion = 0, saving = false, activeHash = '';
let filter = 'flagged', query = '', offset = 0;
const limit = 50;
const route = (page = 'overview', batch = selectedBatch) => '#' + page + '?batch_id=' + encodeURIComponent(batch);
const badge = c => `<span class="badge ${c.review_alert ? 'flagged' : ''}">${c.review_alert ? 'For review' : 'Below review threshold'}</span>`;
const errorPanel = message => `<div class="error" role="alert">${e(message)}</div>`;
const pair = (label, value) => `<dt>${e(label)}</dt><dd>${e(value)}</dd>`;
const readForm = form => Object.fromEntries(new FormData(form));

function setBusy(value) { app.setAttribute('aria-busy', String(value)); }
function notify(message) { notification.textContent = message; }
function saveDraft(form, id, expectedVersion) {
  drafts.set(id, { fields: readForm(form), expectedVersion });
  document.querySelector('#draft-status').textContent = 'Unsaved changes';
}
function batchDescription(batch) {
  const source = batch.source;
  return `${monthLabel(batch.cutoff_month)} · ${count(batch.record_count)} customers${batch.source_kind === 'notebook_case_sample' ? ' (case sample)' : ''} · ${source.customer_names_loaded ? 'names' : 'IDs'}${source.flow_history_loaded ? ' + trends' : ''} · ${batch.batch_id.slice(0, 6)}`;
}

async function render() {
  if (saving) { history.replaceState(null, '', activeHash || route()); return; }
  activeHash = location.hash;
  const token = ++routeVersion;
  const [page, search = ''] = location.hash.slice(1).split('?');
  const requested = new URLSearchParams(search).get('batch_id');
  if (requested && !batches.some(b => b.batch_id === requested)) {
    app.innerHTML = errorPanel('This assessment is not available. Choose another assessment above.');
    setBusy(false); return;
  }
  selectedBatch = requested || selectedBatch || batches[0]?.batch_id;
  selector.value = selectedBatch;
  document.querySelector('#overview-link').href = route();
  document.querySelector('.brand').href = route();
  document.querySelector('#page-context').textContent = page?.startsWith('customer/') ? 'Customer review' : '';
  setBusy(true);
  app.innerHTML = '<p>Loading assessment…</p>';
  try {
    if (!selectedBatch) {
      app.innerHTML = '<section class="panel empty"><h1>No assessments available</h1><p>Import a prepared assessment to begin.</p></section>';
    } else if (page?.startsWith('customer/')) {
      const result = await api.customer(decodeURIComponent(page.slice(9)), selectedBatch);
      if (token !== routeVersion) return;
      renderCustomer(result.customer, result.batch);
    } else {
      const params = { q: query, limit, offset };
      if (filter !== 'all') params.flagged = true;
      if (filter === 'awaiting') params.decision = 'awaiting_review';
      const [summary, list] = await Promise.all([api.summary(selectedBatch), api.customers(selectedBatch, params)]);
      if (token !== routeVersion) return;
      renderOverview(summary, list);
    }
  } catch (error) {
    if (token === routeVersion) {
      app.innerHTML = errorPanel(error.message) + '<button id="retry">Try again</button>';
      document.querySelector('#retry').onclick = render;
    }
  } finally { if (token === routeVersion) setBusy(false); }
}

function renderOverview(summary, list) {
  const finance = summary.finance;
  const aggregate = (key, label) => {
    const value = finance['flagged_' + key];
    return `<div class="signal"><span>${e(label)}</span><span class="signal-value">${money(value.total)}<br><small class="muted">${count(value.records_with_value)} of ${count(value.records)} have values</small></span></div>`;
  };
  app.innerHTML = `
    <div class="heading"><div><h1>Monthly overview</h1><p class="muted">Information through ${e(monthLabel(summary.batch.cutoff_month))} · Forecast ${e(forecastLabel(summary.batch.cutoff_month))}</p></div></div>
    <div class="stats">
      <div class="stat"><span>Customers assessed</span><strong class="number">${count(summary.population)}</strong></div>
      <div class="stat"><span>Flagged for review</span><strong class="number">${count(summary.flagged)}</strong><small class="muted">${count(summary.below_threshold)} below the review threshold</small></div>
      <div class="stat"><span>Flagged, Awaiting review</span><strong class="number">${count(summary.flagged_review_counts.awaiting_review)}</strong><small class="muted">${count(summary.flagged_review_counts.prioritise)} prioritised for RM</small></div>
    </div>
    <section class="panel"><h2>Customer review queue</h2><p class="muted">Highest predicted risk first. Consider the evidence from both Operations and Finance before deciding.</p>
      <div class="toolbar"><div class="filters" role="group" aria-label="Customer filter">
        ${[['flagged','Flagged'],['awaiting','Flagged · awaiting review'],['all','All customers']].map(([key,label]) => `<button data-filter="${key}" aria-pressed="${filter === key}">${label}</button>`).join('')}
      </div><form class="search" id="search"><label for="query" class="muted">Find customer</label><input id="query" name="query" type="search" placeholder="Company name or ID" value="${e(query)}"><button type="submit">Search</button></form></div>
      <div class="table-wrap"><table><thead><tr><th scope="col">Customer</th><th scope="col">Predicted risk</th><th scope="col">Committee decision</th><th scope="col">Review</th></tr></thead><tbody>
      ${list.items.map(c => `<tr><td><a class="customer-name" href="${route('customer/' + encodeURIComponent(c.cus_id))}">${e(c.customer_name || 'Customer ' + c.cus_id)}</a><div class="muted">ID ${e(c.cus_id)}</div></td><td><strong>${percent(c.calibrated_risk)}</strong><br>${badge(c)}</td><td>${e(decisionLabel(c.review.decision))}</td><td><a class="button" href="${route('customer/' + encodeURIComponent(c.cus_id))}">Open review</a></td></tr>`).join('') || '<tr><td colspan="4">No customers match these filters.</td></tr>'}
      </tbody></table></div>
      <div class="pagination"><span class="muted">${list.total ? `${offset + 1}–${Math.min(offset + limit, list.total)}` : '0'} of ${count(list.total)} customers</span><div class="pagination-controls"><button id="previous" ${offset === 0 ? 'disabled' : ''}>Previous</button><button id="next" ${offset + limit >= list.total ? 'disabled' : ''}>Next</button></div></div>
    </section>
    <section class="panel"><details><summary>Financial context for flagged customers</summary>
      ${aggregate('non_fd_balance_myr','Operating account balances')}${aggregate('fd_balance_myr','Fixed deposit balances')}${aggregate('estimated_monthly_fee_myr','Estimated monthly fees')}${aggregate('estimated_monthly_waiver_myr','Estimated monthly waivers')}
      <p class="muted">Balances are exposures. Fees and waivers are separate historical estimates; they do not establish profit or potential savings.</p>
    </details></section>`;
  for (const button of app.querySelectorAll('[data-filter]')) button.onclick = () => { filter = button.dataset.filter; offset = 0; render(); };
  document.querySelector('#search').onsubmit = event => { event.preventDefault(); query = document.querySelector('#query').value.trim(); offset = 0; render(); };
  document.querySelector('#previous').onclick = () => { offset = Math.max(0, offset - limit); render(); };
  document.querySelector('#next').onclick = () => { offset += limit; render(); };
}

function signal(driver) {
  return `<div class="signal"><span><strong>${e(driverLabel(driver))}</strong><br><small class="muted">${e(driver.group)}</small></span><span class="signal-value">${e(driverValue(driver))}</span></div>`;
}
function flowChart(history, baseline) {
  if (!history.length) return '<p class="muted">No transaction history was provided for this assessment.</p>';
  const rows = history.filter(r => isNumber(r.combined_flow_myr));
  if (!rows.length) return '<p class="muted">Transaction values are not available.</p>';
  const top = Math.max(1, ...rows.map(r => r.combined_flow_myr), isNumber(baseline) ? baseline : 0) * 1.1;
  const x = i => 80 + i * (650 / rows.length);
  const y = value => 215 - (value / top) * 170;
  return `<svg class="chart" viewBox="0 0 780 255" role="img" aria-label="Monthly combined transaction values, with a zero baseline. Exact amounts are in the table below.">
    ${[0, .5, 1].map(f => `<line class="grid" x1="75" x2="750" y1="${y(f*top)}" y2="${y(f*top)}"/><text x="4" y="${y(f*top)+4}">${(f*top/1e6).toFixed(1)}m</text>`).join('')}
    ${rows.map((r,i) => `<rect x="${x(i)}" y="${y(r.combined_flow_myr)}" width="${650/rows.length*.65}" height="${Math.max(0,215-y(r.combined_flow_myr))}" fill="${i >= rows.length-3 ? '#6154d9' : '#9ca9bf'}"><title>${e(monthLabel(r.snapshot_month))}: ${e(money(r.combined_flow_myr))}</title></rect><text x="${x(i)}" y="238">${e(new Date(r.snapshot_month+'T00:00:00Z').toLocaleDateString('en-MY',{month:'short',timeZone:'UTC'}))}</text>`).join('')}
    ${isNumber(baseline) ? `<line class="baseline" x1="75" x2="750" y1="${y(baseline)}" y2="${y(baseline)}"/>` : ''}
  </svg><div class="legend"><span>Earlier months</span><span>Latest three observed months</span></div>
  <p class="muted">Combined incoming and successful outgoing transactions, MYR. ${isNumber(baseline) ? 'Dashed line: trailing twelve-month monthly average.' : ''}</p>
  <details><summary>Read exact monthly amounts</summary><div class="table-wrap"><table><thead><tr><th scope="col">Month</th><th scope="col">Incoming</th><th scope="col">Successful outgoing</th><th scope="col">Combined</th></tr></thead><tbody>${history.map(r => `<tr><td>${e(monthLabel(r.snapshot_month))}</td><td>${money(r.inbound_myr)}</td><td>${money(r.outbound_success_myr)}</td><td>${money(r.combined_flow_myr)}</td></tr>`).join('')}</tbody></table></div></details>`;
}

function renderCustomer(c, batch) {
  const ops = c.operations, finance = c.finance, explanation = c.explanation;
  const draft = drafts.get(c.prediction_id);
  const review = draft?.fields || c.review;
  const fields = (name, label, type = 'text') => `<label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${e(review[name] || '')}" ${name === 'reviewer' ? 'required maxlength="200"' : ''}>`;
  const higher = explanation.higher_risk_drivers || [], lower = explanation.lower_risk_drivers || [];
  app.innerHTML = `
    <div class="heading"><div><h1>${e(c.customer_name || 'Customer ' + c.cus_id)}</h1><p class="muted">ID ${e(c.cus_id)} · ${e(monthLabel(c.cutoff_month))} assessment · ${e(c.customer_type || 'Type not provided')}</p></div><span class="badge">${e(decisionLabel(c.review.decision))}</span></div>
    <div class="review-layout"><div>
      <section class="panel"><div class="prediction-stats"><div><h2>Predicted risk</h2><strong class="number ${c.review_alert ? 'risk' : ''}">${percent(c.calibrated_risk)}</strong><p class="muted">For ${e(forecastLabel(c.cutoff_month))}</p>${badge(c)}</div>
      <div><h2>Observed activity</h2><strong class="number">${e(activityChange(ops.combined_flow_mean_3m_myr, ops.combined_flow_mean_12m_myr))}</strong><p class="muted">Latest three-month average versus the trailing twelve-month average</p></div></div>
      <details><summary>What do these numbers mean?</summary><p><strong>Risk estimate:</strong> the model estimates the chance that average combined transaction activity over the next three months will be at most half of the positive trailing twelve-month average. It does not predict account closure.</p><p><strong>Review threshold:</strong> ${percent(c.probability_cutoff,2)}. This sets which predictions are flagged. It is different from the 50% activity rule used to define the outcome.</p><p><strong>Observed activity:</strong> already recorded transactions; this is separate from the forecast. An outcome has not been loaded for this assessment.</p></details></section>
      <section class="panel"><h2>Signals to investigate</h2><p class="muted">These signals raised the model’s estimate. Discuss them across Operations and Finance; they do not confirm a cause.</p>
        ${higher.slice(0,3).map(signal).join('') || '<p>No higher-risk signals were supplied.</p>'}
        <details><summary>More model signals</summary>${higher.slice(3).map(signal).join('')}<h3 class="spaced">Signals lowering the estimate</h3>${lower.map(signal).join('') || '<p>No lower-risk signals were supplied.</p>'}</details>
        <details><summary>Technical explanation</summary><p>SHAP values explain the model in calibrated log-odds. They are not probability percentage points.</p><div class="technical">${e(JSON.stringify({base_logodds:explanation.base_logodds,higher_risk_drivers:higher,lower_risk_drivers:lower,other_features_contribution_logodds:explanation.other_features_contribution_logodds,probability_clip_adjustment_logodds:explanation.probability_clip_adjustment_logodds},null,2))}</div><p class="muted">Batch ${e(batch.batch_id)} · ${count(c.feature_count)} supplied model inputs</p></details>
      </section>
      <section class="panel"><h2>Recorded transaction activity</h2>${flowChart(c.flow_history,ops.combined_flow_mean_12m_myr)}</section>
      <div class="two-columns"><section class="panel"><h2>Operations perspective</h2><dl>
        ${pair('Login failure rate · latest 3 months',percent(ops.login_failure_rate_3m))}${pair('Outgoing payment failure rate · latest 3 months',percent(ops.outbound_failure_rate_3m))}${pair('Bank-attributed payment failure rate',percent(ops.outbound_bank_failure_rate_3m))}${pair('Sessions without transactions',percent(ops.passive_session_rate_3m))}
      </dl><p class="muted spaced">Check the service experience with the customer. These measures do not establish the reason for reduced activity.</p></section>
      <section class="panel"><h2>Finance perspective</h2><dl>${pair('Operating account balances',money(finance.non_fd_balance_myr))}${pair('Fixed deposit balances',money(finance.fd_balance_myr))}${pair('Estimated monthly fees',money(finance.estimated_monthly_fee_myr))}${pair('Estimated monthly waivers',money(finance.estimated_monthly_waiver_myr))}</dl><p class="muted spaced">Balances show exposure. Fees and waivers are separate historical estimates, not verified profit or retention savings.</p></section></div>
    </div><aside class="panel review-sidebar"><h2>Committee review decision</h2><p class="muted">Save the decision after considering both perspectives. Record completed follow-up separately, after it happens.</p>
      <form id="review-form" class="review-form"><fieldset id="review-fields"><label for="decision">Decision</label><select id="decision" name="decision" required><option value="">Choose a decision</option>${['prioritise','monitor','no_immediate_action'].map(d => `<option value="${d}" ${review.decision===d ? 'selected' : ''}>${decisionLabel(d)}</option>`).join('')}</select>
      <label for="reason">Decision reason</label><textarea id="reason" name="reason" required maxlength="4000">${e(review.reason)}</textarea>
      ${fields('reviewer','Reviewed by')}${fields('owner','RM / action owner (optional)')}${fields('next_action_date','Next follow-up date (optional)','date')}
      <details><summary>Notes from each perspective (optional)</summary><label for="operations_notes">Operations notes</label><textarea id="operations_notes" name="operations_notes" maxlength="4000">${e(review.operations_notes)}</textarea><label for="finance_notes">Finance notes</label><textarea id="finance_notes" name="finance_notes" maxlength="4000">${e(review.finance_notes)}</textarea></details>
      <button class="primary" type="submit">Save decision</button></fieldset><p class="muted" id="draft-status">${draft ? 'Unsaved changes' : c.review.version ? 'Saved decision · version '+c.review.version : 'No decision saved yet'}</p><div id="save-message" role="status" aria-live="polite"></div></form>
    </aside></div>`;
  const form = document.querySelector('#review-form');
  const expectedVersion = draft?.expectedVersion ?? c.review.version;
  form.addEventListener('input', () => saveDraft(form, c.prediction_id, expectedVersion));
  form.onsubmit = async event => {
    event.preventDefault();
    if (saving) return;
    const body = { ...readForm(form), expected_version: expectedVersion };
    body.next_action_date ||= null;
    saveDraft(form, c.prediction_id, expectedVersion);
    saving = true;
    selector.disabled = true;
    document.querySelector('#review-fields').disabled = true;
    document.querySelector('#save-message').textContent = 'Saving…';
    let saved = false;
    try {
      await api.saveReview(c.prediction_id, body);
      saved = true;
      drafts.delete(c.prediction_id);
      notify('Decision saved. The model prediction and recorded transaction history are unchanged.');
    } catch (error) {
      const message = document.querySelector('#save-message');
      message.innerHTML = errorPanel(error.message);
      if (error.status === 409) {
        message.insertAdjacentHTML('beforeend','<p class="muted">Your unsaved draft is still shown. Copy any notes you need before loading the saved review.</p><button type="button" id="load-latest">Discard draft and load latest decision</button>');
        document.querySelector('#load-latest').onclick = () => { drafts.delete(c.prediction_id); render(); };
      }
    } finally {
      saving = false;
      selector.disabled = false;
      document.querySelector('#review-fields').disabled = false;
    }
    if (saved) await render();
  };
}

selector.addEventListener('change', () => {
  offset = 0;
  const [page] = location.hash.slice(1).split('?');
  location.hash = route(page || 'overview', selector.value);
});
// Avoid navigation during an in-flight write; unsaved drafts survive navigation in this tab.
document.addEventListener('click', event => {
  if (saving && event.target.closest('a[href^="#"]')) event.preventDefault();
});
window.addEventListener('beforeunload', event => {
  if (saving || drafts.size) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('hashchange', render);

async function start() {
  try {
    const result = await api.months();
    // Prefer the latest full export, then latest import, matching the backend's default.
    batches = result.items.toSorted((a,b) => b.cutoff_month.localeCompare(a.cutoff_month)
      || Number(b.source_kind==='saved_shap_export')-Number(a.source_kind==='saved_shap_export')
      || b.imported_at.localeCompare(a.imported_at));
    selector.innerHTML = batches.map(b => `<option value="${e(b.batch_id)}">${e(batchDescription(b))}</option>`).join('') || '<option>No assessments</option>';
    selector.disabled = !batches.length;
    await render();
  } catch (error) { app.innerHTML = errorPanel(error.message); setBusy(false); }
}
start();
