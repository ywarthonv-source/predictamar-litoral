"""Read public STAC metadata, without credentials or downloading ocean fields."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = 'https://stac.marine.copernicus.eu/metadata/'
PRODUCTS = {
    'OCEANCOLOUR_GLO_BGC_L3_NRT_009_101': 'cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D',
    'OCEANCOLOUR_GLO_BGC_L4_NRT_009_102': 'cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D',
    'OCEANCOLOUR_GLO_BGC_L3_MY_009_103': 'cmems_obs-oc_glo_bgc-plankton_my_l3-multi-4km_P1D',
    'OCEANCOLOUR_GLO_BGC_L4_MY_009_104': 'cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D',
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=25) as response:
        raw = response.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def product_entry(item):
    product, prefix = item
    url = ROOT + product + '/product.stac.json'
    source, digest = fetch(url)
    datasets = []
    for link in source.get('links', []):
        if link.get('rel') != 'item' or not link.get('href', '').startswith(prefix + '_'):
            continue
        dataset_url = urllib.parse.urljoin(url, link['href'])
        dataset, dataset_hash = fetch(dataset_url)
        properties = dataset.get('properties', {})
        datasets.append({'id': dataset.get('id'), 'url': dataset_url,
                         'sha256': dataset_hash,
                         'datetime': properties.get('datetime'),
                         'start_datetime': properties.get('start_datetime'),
                         'end_datetime': properties.get('end_datetime'),
                         'cube_dimensions': properties.get('cube:dimensions'),
                         'asset_temporal_coordinates': {
                             name: asset.get('cube:dimensions', {}).get('time')
                             for name, asset in dataset.get('assets', {}).items()
                             if asset.get('cube:dimensions', {}).get('time') is not None}})
    if not datasets:
        raise ValueError('No matching dataset versions: '+prefix)
    return {'product_id': product, 'requested_dataset_id': prefix,
            'product_url': url, 'product_sha256': digest,
            'product_temporal_extent': source.get('extent', {}).get('temporal'),
            'datasets': datasets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(product_entry, PRODUCTS.items()))
    result = {'schema_version': 'chlorophyll_public_catalogue_v1',
              'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
              'method': 'public STAC urllib GET; not copernicusmarine describe or an Actions run',
              'products': results,
              'limitations': ['metadata extents do not certify daily availability in the pilot box',
                              'do not infer cloud cover or missing-date cause from product extents',
                              'all listed versions are recorded; no default version assumed']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
