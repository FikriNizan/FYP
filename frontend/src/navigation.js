export const assessmentLink = (path, batch) => path + '?batch_id=' + encodeURIComponent(batch);
export function preferredBatches(items) {
  return items.toSorted((a,b) => b.cutoff_month.localeCompare(a.cutoff_month)
    || Number(b.source_kind === 'saved_shap_export') - Number(a.source_kind === 'saved_shap_export')
    || b.imported_at.localeCompare(a.imported_at));
}
