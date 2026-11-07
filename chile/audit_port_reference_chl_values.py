"""Retrieve daily Copernicus L3 values at the previously verified public cell."""
import argparse
import json
from pathlib import Path

import numpy as np

from audit_arco_coverage_2024_2025 import product
from audit_arco_time_axes import DATASETS


def audit(reference):
    metadata, data, axis, lat, lon, _ = product(DATASETS[2], include_reference_2015=False)
    cell = reference['port_reference_pixel']
    y, x = cell['row'], cell['column']
    if (metadata['dataset_version_id'] != reference['product']['dataset_version_id']
            or metadata['chl_units'] != reference['product']['chl_units']
            or (lat[y], lon[x]) != (cell['latitude'], cell['longitude'])):
        raise ValueError('Historical product, units or reference coordinates changed')
    dates = axis.tolist()
    previous = reference['public_environmental_axis']
    values = data[:, y, x]
    finite = np.isfinite(values)
    if (previous['step_days'] != 1
            or (dates[0], dates[-1]) != (previous['first_date'], previous['last_date'])
            or finite.tolist() != previous['l3_finite_at_reference']):
        raise ValueError('Daily values do not reproduce the published date axis and mask')
    return {
        'product': metadata,
        'port_reference_pixel': cell,
        'first_date': dates[0],
        'last_date': dates[-1],
        'step_days': 1,
        'finite_days': int(finite.sum()),
        'chl_daily': [float(value) if present else None for value, present in zip(values, finite)],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.reference.read_text())), allow_nan=False, indent=2))
