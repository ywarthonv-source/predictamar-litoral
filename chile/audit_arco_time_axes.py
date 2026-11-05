"""Read public ARCO coordinate chunks; no credentials or fish inference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

import numpy as np
import numcodecs

ROOT = 'https://stac.marine.copernicus.eu/metadata/'
DATASETS = [
    ('OCEANCOLOUR_GLO_BGC_L3_NRT_009_101', 'cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D_202411'),
    ('OCEANCOLOUR_GLO_BGC_L4_NRT_009_102', 'cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D_202311'),
    ('OCEANCOLOUR_GLO_BGC_L3_MY_009_103', 'cmems_obs-oc_glo_bgc-plankton_my_l3-multi-4km_P1D_202603'),
    ('OCEANCOLOUR_GLO_BGC_L4_MY_009_104', 'cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D_202603'),
]


def fetch(url, manifest):
    with urllib.request.urlopen(url, timeout=12) as response:
        raw = response.read()
    manifest.append({'url': url, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return raw


def read_axis(base, metadata, name, manifest):
    spec = metadata[name+'/.zarray']
    if spec['zarr_format'] != 2 or len(spec['shape']) != 1:
        raise ValueError('Unexpected coordinate array format')
    size, chunk = spec['shape'][0], spec['chunks'][0]
    chunk_count = (size+chunk-1)//chunk
    print(name, 'size', size, 'chunks', chunk_count, file=sys.stderr, flush=True)
    if chunk_count > 16:
        raise ValueError('Coordinate request budget exceeded: '+str(chunk_count)+' chunks')
    vectors = []
    for i in range((size+chunk-1)//chunk):
        raw = fetch(base+'/'+name+'/'+str(i), manifest)
        if spec.get('compressor'):
            raw = numcodecs.get_codec(spec['compressor']).decode(raw)
        for config in reversed(spec.get('filters') or []):
            raw = numcodecs.get_codec(config).decode(raw)
        vectors.append(np.frombuffer(raw, dtype=spec['dtype']))
    return np.concatenate(vectors)[:size]


def asset_time(asset, manifest):
    base = asset['href'].rstrip('/')
    metadata = json.loads(fetch(base+'/.zmetadata', manifest))['metadata']
    values = read_axis(base, metadata, 'time', manifest)
    attrs = metadata['time/.zattrs']
    unit, origin = attrs['units'].split(' since ', 1)
    factor = {'days': 86400, 'hours': 3600, 'seconds': 1, 'milliseconds': .001}[unit]
    epoch = datetime.fromisoformat(origin.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
    dates = [epoch+timedelta(seconds=float(v)*factor) for v in values]
    steps = np.diff(values.astype(float))*factor
    return {
        'asset_url': base, 'coordinate_size': len(dates), 'coordinate_units': attrs['units'],
        'first_time': dates[0].isoformat(), 'last_time': dates[-1].isoformat(),
        'strictly_increasing': bool(np.all(steps > 0)),
        'all_steps_one_day': bool(np.all(np.abs(steps-86400) < .01)),
        'distinct_dates_2015': len({d.date() for d in dates if d.year == 2015}),
        'distinct_dates_2024': len({d.date() for d in dates if d.year == 2024}),
        'distinct_dates_2025': len({d.date() for d in dates if d.year == 2025}),
        'distinct_dates_2026_october_01_30': len({d.date() for d in dates if d.year == 2026 and d.month == 10 and d.day <= 30}),
    }


def audit(item):
    product, dataset = item
    manifest = []
    url = ROOT+product+'/'+dataset+'/dataset.stac.json'
    source = json.loads(fetch(url, manifest))
    results = {}
    for name in ['timeChunked', 'geoChunked']:
        print(dataset, name, file=sys.stderr, flush=True)
        asset = source.get('assets', {}).get(name)
        if not asset:
            results[name] = {'status': 'asset_not_listed'}
            continue
        try:
            result = asset_time(asset, manifest)
            result['status'] = 'coordinate_chunks_read'
            results[name] = result
        except Exception as e:
            results[name] = {'status': 'unavailable_in_this_execution', 'error': type(e).__name__+': '+str(e)}
    return {'product_id': product, 'dataset_version_id': dataset,
            'services': results, 'request_manifest': manifest}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(audit, DATASETS))
    result = {'schema_version': 'arco_coordinate_axis_audit_v1',
              'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
              'method': 'anonymous HTTPS STAC and Zarr v2 coordinate chunks; not SDK describe or Actions',
              'numcodecs_version': numcodecs.__version__, 'results': results,
              'training_ready': False,
              'limitations': [
                  'coordinate chunks do not establish availability or quality of environmental variable chunks',
                  'no historical CHL field downloaded or matched to fishing records in this execution',
                  'current service axes do not establish why an earlier request had a shorter window',
                  'no authenticated SDK service-forced comparison executed',
                  'no cloud coverage inference, pilot polygon change or operational recommendation']}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
