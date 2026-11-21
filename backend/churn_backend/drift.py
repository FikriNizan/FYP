"""Population Stability Index (PSI) and the two-sample Kolmogorov-Smirnov (KS) statistic.

Standard library only, so the app and the offline scenario generator share one implementation.
Both describe whether two distributions differ; neither is a test of model accuracy or of causes.

PSI = sum((a - e) * ln(a / e)) over bins, where e is the reference share and a the current share.
* Bins come from the reference only: 10 quantile bins (decile edges, duplicate edges merged), or one
  bin per value when the reference has at most 10 distinct values (plus one bin for unseen values).
* Missing values (None/NaN) form their own bin, because "missing" carries meaning here.
* A zero share is replaced by EPSILON on both sides so the logarithm is defined.
* Reading 0.10 / 0.25 is a convention (Siddiqi 2006; Yurdakul 2018), not a statistical test.

KS = max |F_ref(x) - F_cur(x)| over the non-missing values (the statistic only; no p-value is
reported, because at n = 1,000 tiny shifts look "significant" and ties make p-values unreliable).
"""
import bisect
import math

BINS = 10
EPSILON = 1e-4
VALUE_BIN_LIMIT = 10
PSI_CONVENTION = (0.10, 0.25)


def missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def split(values, categorical=False):
    present = [str(v) if categorical else float(v) for v in values if not missing(v)]
    return present, len(values) - len(present)


def bin_rule(reference, bins=BINS, categorical=False):
    """Bins from the reference only. Returns ('values', sorted distinct values) or ('edges', edges).
    Categorical variables always get one bin per reference category."""
    present, _ = split(reference, categorical)
    distinct = sorted(set(present))
    if categorical or len(distinct) <= VALUE_BIN_LIMIT:
        return 'values', distinct
    ordered = sorted(present)
    n = len(ordered)
    # Nearest-rank decile edges; a value equal to an edge falls in the lower bin (right-closed).
    edges = sorted({ordered[max(0, math.ceil(k * n / bins) - 1)] for k in range(1, bins)})
    return 'edges', edges


def shares(values, rule, categorical=False):
    kind, cut = rule
    present, nulls = split(values, categorical)
    counts = [0] * (len(cut) + 1)
    for value in present:
        if kind == 'values':
            index = bisect.bisect_left(cut, value)
            counts[index if index < len(cut) and cut[index] == value else len(cut)] += 1
        else:
            counts[bisect.bisect_left(cut, value)] += 1
    total = len(values)
    return [c / total for c in counts + [nulls]] if total else []


def psi(reference, current, bins=BINS, epsilon=EPSILON, categorical=False):
    rule = bin_rule(reference, bins, categorical)
    expected, actual = shares(reference, rule, categorical), shares(current, rule, categorical)
    value = 0.0
    for e, a in zip(expected, actual):
        if e == a:
            continue  # Identical shares contribute exactly zero (also when both are zero).
        e, a = max(e, epsilon), max(a, epsilon)
        value += (a - e) * math.log(a / e)
    return value


def ks(reference, current):
    """Two-sample KS statistic on non-missing values (same value as scipy.stats.ks_2samp(...).statistic)."""
    first, _ = split(reference)
    second, _ = split(current)
    if not first or not second:
        return None
    first, second = sorted(first), sorted(second)
    statistic = 0.0
    for x in sorted(set(first) | set(second)):
        gap = abs(bisect.bisect_right(first, x) / len(first) - bisect.bisect_right(second, x) / len(second))
        statistic = max(statistic, gap)
    return statistic


def null_share(values):
    return sum(1 for v in values if missing(v)) / len(values) if values else None


def compare(reference, current, categorical=False):
    """PSI, KS (numeric only) and the change in missing share for one variable."""
    return dict(psi=psi(reference, current, categorical=categorical), ks=None if categorical else ks(reference, current),
                null_share_reference=null_share(reference), null_share_current=null_share(current),
                changed_values=sum(1 for r, c in zip(reference, current) if not (missing(r) and missing(c)) and r != c))


def reading(value):
    """Plain wording for a PSI value under the conventional cut-offs (not a test)."""
    if value is None:
        return 'Not available'
    low, high = PSI_CONVENTION
    return 'Little shift' if value < low else 'Moderate shift' if value < high else 'Large shift'
