"""Bound historical L3 coverage at the public port reference without daily pixel masks."""
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_candidate_chl_date_sensitivity import support_by_date
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none


def audit(raw_dir, regional, cells):
    support = support_by_date(regional)
    port = cells['port_reference_pixel']
    if (regional['diagnostic_box'] != cells['diagnostic_box']
            or len(support) != cells['days']
            or [p['dataset_version_id'] for p in regional['products']]
            != [p['dataset_version_id'] for p in cells['products']]):
        raise ValueError('Regional and cell censuses are incompatible')
    eligible = [day for day, counts in support.items() if counts[0] > 0]
    fixed = [cell for cell in cells['cell_results'] if cell['l4_finite_days'] == len(support)]
    if (port not in fixed or regional['days_l3_has_finite_outside_l4_support'] != 0
            or any(cell['l3_finite_days'] for cell in cells['cell_results'] if cell not in fixed)
            or sum(cell['l3_finite_days'] for cell in fixed) != sum(support[d][0] for d in eligible)
            or max(counts[0] for counts in support.values()) > len(fixed)):
        raise ValueError('Cannot infer complete days from the fixed support')
    full = [day for day in eligible if support[day][0] == len(fixed)]
    partial = [day for day in eligible if support[day][0] < len(fixed)]
    n = port['l3_finite_days'] - len(full)
    if not 0 < n <= len(partial):
        raise ValueError('Inconsistent port finite-day count')
    weights = {}
    combined = Counter()
    for year, gear, _, rows in strata(raw_dir):
        dates = Counter()
        for _, _, end in rows[TRIP].drop_duplicates().itertuples(index=False, name=None):
            timestamp = date_or_none(end)
            if timestamp is None or timestamp.date() not in support:
                raise ValueError('Candidate date missing or outside census')
            dates[timestamp.date()] += 1
        weights[f'{year}_{gear}'] = dates
        combined.update(dates)
    weights['all'] = combined
    bounds = {}
    for label, dates in weights.items():
        guaranteed = sum(dates[day] for day in full)
        ranked = sorted(dates[day] for day in partial)
        regional_count = guaranteed + sum(ranked)
        lower, upper = guaranteed + sum(ranked[:n]), guaranteed + sum(ranked[-n:])
        bounds[label] = dict(candidate_keys=sum(dates.values()), regional_any=regional_count,
                             keys_on_full_days=guaranteed,
                             port_possible_min=lower, port_possible_max=upper,
                             regional_only_min=regional_count-upper,
                             regional_only_max=regional_count-lower)
    return dict(calendar_days=len(support), regional_any_days=len(eligible),
                fixed_support_cells=len(fixed), full_days=len(full), partial_days=len(partial),
                port_finite_days=port['l3_finite_days'], port_finite_partial_days=n,
                regional_only_days=len(partial)-n, bounds=bounds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('raw_dir', 'regional', 'cells'):
        parser.add_argument(argument, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.raw_dir, json.loads(args.regional.read_text()),
                           json.loads(args.cells.read_text())), indent=2))


