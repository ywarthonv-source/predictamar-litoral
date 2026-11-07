"""Read historical L3 support at the public Portales reference and count candidate dates."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

import numpy as np

from audit_arco_coverage_2024_2025 import product
from audit_arco_time_axes import DATASETS
from audit_candidate_chl_date_sensitivity import support_by_date
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none


def audit(raw_dir, regional, cells):
    metadata, data, axis, lat, lon, _ = product(DATASETS[2], include_reference_2015=False)
    reference = cells['port_reference_pixel']
    y, x = reference['row'], reference['column']
    if (metadata['dataset_version_id'] != regional['products'][0]['dataset_version_id']
            or (lat[y], lon[x]) != (reference['latitude'], reference['longitude'])):
        raise ValueError('Historical product or reference coordinates changed')
    regional_dates = support_by_date(regional)
    days = [date.fromisoformat(d) for d in axis.tolist()]
    if days != list(regional_dates):
        raise ValueError('Unexpected time axis')
    finite = np.isfinite(data)
    if (finite.sum(axis=(1, 2)).tolist() != [regional_dates[d][0] for d in days]
            or int(finite[:, y, x].sum()) != reference['l3_finite_days']):
        raise ValueError('Historical support differs from published censuses')

    mask = finite[:, y, x].tolist()
    local = dict(zip(days, mask))
    result = {}
    combined = Counter()
    for year, gear, _, rows in strata(raw_dir):
        counts = Counter(candidate_keys=0, regional_any=0, port_finite=0)
        for _, _, end in rows[TRIP].drop_duplicates().itertuples(index=False, name=None):
            day = date_or_none(end).date()
            counts['candidate_keys'] += 1
            counts['regional_any'] += int(regional_dates[day][0] > 0)
            counts['port_finite'] += int(local[day])
        result[f'{year}_{gear}'] = dict(counts)
        combined.update(counts)
    result['all'] = dict(combined)
    return {
        'product': metadata, 'port_reference_pixel': reference,
        'public_environmental_axis': {'first_date': axis[0].item(), 'last_date': axis[-1].item(),
                                      'step_days': 1, 'l3_finite_at_reference': mask},
        'aggregate_by_stratum': result,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('raw_dir', 'regional', 'cells'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.raw_dir, json.loads(args.regional.read_text()),
                           json.loads(args.cells.read_text())), indent=2))
