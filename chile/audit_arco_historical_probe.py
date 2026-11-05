"""Bounded CHL availability probe in an existing diagnostic box, not fish data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

import numpy as np
import numcodecs

from audit_arco_time_axes import ROOT, DATASETS, read_axis

DATES = ['2015-01-15', '2024-01-15', '2025-01-15']
BOX = {'minimum_latitude': -33.3, 'maximum_latitude': -32.8,
       'minimum_longitude': -72.1, 'maximum_longitude': -71.6}


def get(url, manifest):
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read(8*1024*1024+1)
    if len(raw) > 8*1024*1024:
        raise ValueError('Per-object 8 MiB read limit exceeded')
    manifest.append({'url': url, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    if sum(r['bytes'] for r in manifest) > 16*1024*1024:
        raise ValueError('Per-product 16 MiB budget exceeded')
    return raw


def decode(raw, spec):
    expected = int(np.prod(spec['chunks']))*np.dtype(spec['dtype']).itemsize
    if expected > 16*1024*1024:
        raise ValueError('Decoded chunk budget exceeded')
    if spec.get('compressor'):
        raw = numcodecs.get_codec(spec['compressor']).decode(raw)
    for config in reversed(spec.get('filters') or []):
        raw = numcodecs.get_codec(config).decode(raw)
    values = np.frombuffer(raw, dtype=spec['dtype'])
    if values.nbytes != expected:
        raise ValueError('Unexpected decoded chunk length')
    return values.reshape(spec['chunks'], order=spec['order'])


def masked_cf(raw, spec, attrs):
    values = raw.astype(float)
    mask = ~np.isfinite(values)
    for fill in [spec.get('fill_value'), attrs.get('_FillValue'), attrs.get('missing_value')]:
        if fill is not None:
            fill = float(fill)
            if np.isfinite(fill):
                mask |= values == fill
    if 'valid_min' in attrs:
        mask |= values < attrs['valid_min']
    if 'valid_max' in attrs:
        mask |= values > attrs['valid_max']
    values = values*attrs.get('scale_factor', 1)+attrs.get('add_offset', 0)
    values[mask] = np.nan
    return values


def audit(item):
    product, dataset = item
    manifest, samples = [], {}
    source_url = ROOT+product+'/'+dataset+'/dataset.stac.json'
    stac = json.loads(get(source_url, manifest))
    base = stac['assets']['timeChunked']['href'].rstrip('/')
    metadata = json.loads(get(base+'/.zmetadata', manifest))['metadata']
    lat = read_axis(base, metadata, 'latitude', manifest)
    lon = read_axis(base, metadata, 'longitude', manifest)
    time = read_axis(base, metadata, 'time', manifest)
    yi = np.flatnonzero((lat >= BOX['minimum_latitude']) & (lat <= BOX['maximum_latitude']))
    xi = np.flatnonzero((lon >= BOX['minimum_longitude']) & (lon <= BOX['maximum_longitude']))
    if not len(yi) or not len(xi):
        raise ValueError('Empty diagnostic box')
    spec, attrs = metadata['CHL/.zarray'], metadata['CHL/.zattrs']
    if spec['zarr_format'] != 2 or attrs['_ARRAY_DIMENSIONS'] != ['time','latitude','longitude'] or spec['chunks'][0] != 1:
        raise ValueError('Unexpected CHL layout; this probe requires time chunks of one day')
    unit, origin = metadata['time/.zattrs']['units'].split(' since ', 1)
    if unit != 'days' or metadata['time/.zattrs'].get('calendar') not in ['Gregorian','gregorian','standard']:
        raise ValueError('Unexpected time convention')
    epoch = datetime.fromisoformat(origin.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
    if not np.isfinite(time).all():
        raise ValueError('Missing time coordinates')
    days = np.array([(epoch+timedelta(days=float(v))).date().isoformat() for v in time])
    ychunks, xchunks = np.unique(yi//spec['chunks'][1]), np.unique(xi//spec['chunks'][2])
    if len(ychunks)*len(xchunks)*len(DATES) > 8:
        raise ValueError('At most eight CHL chunks per product allowed')
    reports = []
    for date in DATES:
        indices = np.flatnonzero(days == date)
        if len(indices) != 1:
            raise ValueError('Requested day absent or ambiguous: '+date)
        ti = int(indices[0])
        grid = np.full((len(yi),len(xi)), np.nan)
        missing_chunks = 0
        for yc in ychunks:
            for xc in xchunks:
                chunk_key = spec.get('dimension_separator','.').join(map(str,[ti,int(yc),int(xc)]))
                url = base+'/CHL/'+chunk_key
                try:
                    raw = get(url, manifest)
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise
                    manifest.append({'url': url, 'http_status': 404, 'bytes': 0, 'sha256': None})
                    missing_chunks += 1
                    continue
                tile = decode(raw, spec)
                ym, xm = np.flatnonzero(yi//spec['chunks'][1] == yc), np.flatnonzero(xi//spec['chunks'][2] == xc)
                sub = tile[0][np.ix_(yi[ym]%spec['chunks'][1],xi[xm]%spec['chunks'][2])]
                grid[np.ix_(ym,xm)] = masked_cf(sub, spec, attrs)
        finite = grid[np.isfinite(grid)]
        reports.append({'date': date, 'grid_cells': grid.size, 'finite_in_provider_bounds': len(finite),
                        'finite_fraction_rectangular_grid': len(finite)/grid.size,
                        'missing_objects_http404': missing_chunks,
                        'minimum': float(finite.min()) if len(finite) else None,
                        'median': float(np.median(finite)) if len(finite) else None,
                        'maximum': float(finite.max()) if len(finite) else None})
        samples[date] = grid
    report = {'product_id': product, 'dataset_version_id': dataset, 'service': 'timeChunked',
              'grid_shape': [len(yi),len(xi)],
              'latitude_subset_sha256': hashlib.sha256(lat[yi].tobytes()).hexdigest(),
              'longitude_subset_sha256': hashlib.sha256(lon[xi].tobytes()).hexdigest(),
              'native_selected_extent': {'lat_min': float(lat[yi].min()), 'lat_max': float(lat[yi].max()),
                                         'lon_min': float(lon[xi].min()), 'lon_max': float(lon[xi].max())},
              'chl_units': attrs.get('units'), 'coverage_content_type': attrs.get('coverage_content_type'),
              'variable_metadata': {k:attrs.get(k) for k in ['missing_value','valid_min','valid_max','scale_factor','add_offset']},
              'zarr_fill_value': spec.get('fill_value'), 'probes': reports,
              'request_manifest': manifest,
              'compressed_field_chunks_fetched': sum('/CHL/' in r['url'] and r.get('http_status') != 404 for r in manifest),
              'bytes_fetched': sum(r['bytes'] for r in manifest)}
    return report, samples


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(executor.map(audit, DATASETS[2:]))
    l3, l4 = outputs
    if any(l3[0][k] != l4[0][k] for k in ['grid_shape','latitude_subset_sha256','longitude_subset_sha256','chl_units']):
        raise ValueError('L3 and L4 sample grids or units differ')
    comparisons = []
    for date in DATES:
        a,b = l3[1][date],l4[1][date]
        common = np.isfinite(a) & np.isfinite(b)
        comparisons.append({'date': date, 'common_finite_cells': int(common.sum()),
                            'l4_finite_without_l3': int((np.isfinite(b) & ~np.isfinite(a)).sum()),
                            'maximum_absolute_difference_common': float(np.max(np.abs(a[common]-b[common]))) if common.any() else None})
    result = {'schema_version': 'arco_historical_chl_probe_v1',
              'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
              'diagnostic_box': BOX, 'dates_selected_a_priori': DATES,
              'method': 'anonymous HTTPS Zarr v2 chunks; masks fill/missing and provider valid bounds',
              'zarr_specification': 'https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html',
              'numcodecs_version': numcodecs.__version__, 'products': [o[0] for o in outputs],
              'l3_l4_comparisons': comparisons, 'training_ready': False,
              'limitations': [
                  'three preselected days are not a historical availability census',
                  'rectangular grid includes possible land; no independent marine mask or cloud fraction',
                  'ancillary quality flags and CHL uncertainty not downloaded or applied',
                  'L4 interpolation and agreement with L3 are not independent observational validation',
                  'no fish records matched, no species evidence, model, pilot polygon approval or recommendation',
                  'anonymous direct read is not SDK describe or an authenticated service-forced comparison',
                  'no claim about NRT short-window cause or subsurface habitat from surface CHL']}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
