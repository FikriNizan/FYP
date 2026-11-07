import { isNumber } from './format.js';

// Display widths only; saved measures and model policy are never changed.
export const ratioWidth = (value, total) => isNumber(value) && isNumber(total) && total > 0
  ? Math.min(100, Math.max(0, value / total * 100)) : 0;

export function balanceShares(operating, deposit) {
  if (!isNumber(operating) || !isNumber(deposit) || operating < 0 || deposit < 0 || operating + deposit <= 0) return null;
  const operatingTenths = Math.round(operating / (operating + deposit) * 1000);
  return { operating:operatingTenths / 10, deposit:(1000 - operatingTenths) / 10 };
}

export function relativeEstimateWidths(fee, waiver) {
  if (!isNumber(fee) || !isNumber(waiver) || Math.max(fee, waiver) <= 0) return null;
  const larger = Math.max(fee, waiver);
  return { fee:ratioWidth(fee, larger), waiver:ratioWidth(waiver, larger) };
}
