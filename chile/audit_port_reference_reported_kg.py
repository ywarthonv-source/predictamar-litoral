"""Compare reported positive kg and reference CHL by recorded return day and gear."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
import math
from pathlib import Path
from statistics import median
import sys

import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none
from audit_ifop_zero_activity import catch_state


def summarize(days, cap):
    kept = [(chl, weights) for chl, weights in days if chl <= cap]
    ranked = pd.DataFrame([(chl, median(weights)) for chl, weights in kept], columns=['chl', 'kg']).rank()
    correlation = ranked.chl.corr(ranked.kg) if len(ranked) > 1 else math.nan
    return {
        'days': len(kept), 'candidate_keys': sum(len(weights) for _, weights in kept),
        'spearman_chl_vs_daily_median_positive_kg': float(correlation) if math.isfinite(correlation) else None,
    }


def audit(raw_dir, reference):
    start = date.fromisoformat(reference['first_date'])
    concentrations = reference['chl_daily']
    axis = {start + timedelta(days=i): chl for i, chl in enumerate(concentrations)}
    if reference['step_days'] != 1 or max(axis).isoformat() != reference['last_date']:
        raise ValueError('Unexpected CHL axis')
    p95 = float(pd.Series(concentrations).quantile(.95))
    output = {}
    totals = Counter()
    for year, gear, _, rows in strata(raw_dir):
        if rows[TRIP].eq('').any(axis=None):
            raise ValueError('Incomplete candidate key')
        counts = Counter()
        grouped_days = defaultdict(list)
        for (_, _, end), group in rows.groupby(TRIP):
            day = date_or_none(end).date()
            chl = axis[day]
            counts['candidate_keys'] += 1
            counts['keys_with_chl'] += int(chl is not None)
            if catch_state(group) == 'conflicting_code999_positive_weight':
                continue
            target = group.loc[group.COD_ESPECIE.eq('1'), 'PESO']
            if len(target) != 1:
                continue
            weight = pd.to_numeric(target.iloc[0], errors='coerce')
            if not math.isfinite(weight) or weight <= 0:
                continue
            counts['positive_kg_keys'] += 1
            if chl is not None:
                grouped_days[day].append(float(weight))
        pairs = [(axis[day], weights) for day, weights in grouped_days.items()]
        output[f'{year}_{gear}'] = {
            'counts': dict(counts),
            'complete': summarize(pairs, math.inf),
            'excluding_above_environmental_p95': summarize(pairs, p95),
        }
        totals.update(counts)
    return {'historical_l3_p95_mg_m3': p95, 'counts_all_strata': dict(totals), 'by_stratum': output}


if __name__ == '__main__':
    raw_dir, values = map(Path, sys.argv[1:])
    print(json.dumps(audit(raw_dir, json.loads(values.read_text())), allow_nan=False, indent=2))
