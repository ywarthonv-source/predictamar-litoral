"""Audit version drift and ancillary L3 fields for the fixed public Portales cell."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

from audit_arco_coverage_2024_2025 import read_grid
from audit_arco_historical_probe import get
from audit_arco_time_axes import ROOT, read_axis


def vector_hash(values):
    payload = json.dumps(values, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def audit(reference):
    source = reference['product']
    manifest = []
    url = f"{ROOT}{source['product_id']}/{source['dataset_version_id']}/dataset.stac.json"
    stac = json.loads(get(url, manifest))
    base = stac['assets']['geoChunked']['href'].rstrip('/')
    metadata = json.loads(get(base+'/.zmetadata', manifest))['metadata']
    axes = {name: read_axis(base, metadata, name, manifest)
            for name in ('time', 'latitude', 'longitude')}
    unit, origin = metadata['time/.zattrs']['units'].split(' since ')
    if unit != 'days':
        raise ValueError('Unexpected time units')
    epoch = date.fromisoformat(origin)
    days = np.array([(epoch + timedelta(days=float(value))).isoformat() for value in axes['time']])
    start, end = reference['first_date'], reference['last_date']
    indices = np.flatnonzero((days >= start) & (days <= end))
    expected = np.arange(np.datetime64(start), np.datetime64(end) + 1).astype(str)
    if not np.array_equal(days[indices], expected):
        raise ValueError('Unexpected historical dates')
    cell = reference['port_reference_pixel']
    yi = np.flatnonzero(axes['latitude'] == cell['latitude'])
    xi = np.flatnonzero(axes['longitude'] == cell['longitude'])
    if len(yi) != 1 or len(xi) != 1:
        raise ValueError('Reference cell is ambiguous')
    fields = ('CHL', 'CHL_uncertainty', 'flags')
    def field_series(name):
        records = []
        result = read_grid(base, metadata, indices, yi, xi, records, variable=name)
        return [float(x) if np.isfinite(x) else None for x in result[:, 0, 0]], records

    with ThreadPoolExecutor(max_workers=3) as executor:
        values, records = zip(*executor.map(field_series, fields))
    for requests in records:
        manifest.extend(requests)
    current, uncertainty, flags = values
    previous = reference['chl_daily']
    if len(current) != len(previous):
        raise ValueError('Historical vector lengths differ')
    return {
        'dataset_version_id': source['dataset_version_id'],
        'full_axis_last_date': days[-1].item(),
        'historical_first_date': start, 'historical_last_date': end,
        'reference_vector_sha256': vector_hash(previous),
        'current_vector_sha256': vector_hash(current),
        'days_different_from_published_values': sum(a != b for a, b in zip(current, previous)),
        'ancillary_attributes': {name: metadata[name+'/.zattrs'] for name in fields[1:]},
        'chl_uncertainty_daily': uncertainty, 'flags_daily': flags,
        'request_manifest': manifest,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.reference.read_text())), indent=2, allow_nan=False))
