"""Count historical CHL availability per cell and compare with GLOBE land mask."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from global_land_mask import globe
import numpy as np

from audit_arco_coverage_2024_2025 import product
from audit_arco_historical_probe import BOX
from audit_arco_time_axes import DATASETS


def longest_absence(finite):
    indices = np.flatnonzero(np.r_[True, finite, True])
    return int(np.diff(indices).max()-1)


def audit(contract):
    with ThreadPoolExecutor(max_workers=2) as executor:
        l3, l4 = executor.map(partial(product, include_reference_2015=False), DATASETS[2:])
    if not all(np.array_equal(l3[i],l4[i]) for i in [2,3,4]):
        raise ValueError('L3/L4 coordinates differ')
    l3_finite, l4_finite = np.isfinite(l3[1]), np.isfinite(l4[1])
    lat, lon = l3[3], l3[4]
    sample_offsets = ((np.arange(20)+.5)/20-.5)/24
    rows = []
    for row, latitude in enumerate(lat):
        for col, longitude in enumerate(lon):
            samples_lat, samples_lon = np.meshgrid(latitude+sample_offsets, longitude+sample_offsets, indexing='ij')
            land = int(globe.is_land(samples_lat, samples_lon).sum())
            rows.append({
                'row': row, 'column': col, 'latitude': float(latitude), 'longitude': float(longitude),
                'l3_finite_days': int(l3_finite[:,row,col].sum()),
                'l4_finite_days': int(l4_finite[:,row,col].sum()),
                'l3_longest_gap_days': longest_absence(l3_finite[:,row,col]),
                'globe_land_samples_out_of_400': land,
                'globe_center_on_land': bool(globe.is_land(float(latitude), float(longitude))),
                'mixed_coastal_cell_diagnostic': 0 < land < 400,
            })
    port = json.loads(contract.read_text())['site']['reference_point_wgs84']
    py, px = port['latitude'], port['longitude']
    port_cell = next((r for r in rows if abs(py-r['latitude']) <= 1/48
                      and abs(px-r['longitude']) <= 1/48), None)
    if port_cell is None:
        raise ValueError('Reference point outside cell footprints')
    fixed = [r for r in rows if r['l4_finite_days'] == len(l4[2])]
    never = [r for r in rows if r['l4_finite_days'] == 0]
    any_l3 = l3_finite.any(axis=(1,2))
    months = {}
    for month in range(1,13):
        idx = np.array([int(day[5:7]) == month for day in l3[2]])
        months[str(month)] = {'days': int(idx.sum()), 'days_without_l3': int((idx & ~any_l3).sum())}
    mask_file = Path(globe.__file__).with_name('globe_combined_mask_compressed.npz')
    with mask_file.open('rb') as source:
        mask_sha = hashlib.file_digest(source,'sha256').hexdigest()
    return {
        'schema_version':'arco_cell_support_v1','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
        'products':[l3[0], l4[0]], 'diagnostic_box':BOX,'days':len(l3[2]),
        'mask_source':{'package_version':version('global-land-mask'),'npz_sha256':mask_sha,
                       'source':'https://www.ncei.noaa.gov/node/797',
                       'implementation':'https://github.com/toddkarin/global-land-mask',
                       'sample_grid':'20 by 20 interior midpoints of a 1/24 degree cell'},
        'l4_fixed_support_count':len(fixed),'l4_never_finite_count':len(never),
        'never_finite_all_samples_land':sum(r['globe_land_samples_out_of_400']==400 for r in never),
        'never_finite_center_on_land':sum(r['globe_center_on_land'] for r in never),
        'fixed_support_mixed_count':sum(r['mixed_coastal_cell_diagnostic'] for r in fixed),
        'fixed_support_center_on_land':sum(r['globe_center_on_land'] for r in fixed),
        'l3_fixed_support_days_range':[min(r['l3_finite_days'] for r in fixed),max(r['l3_finite_days'] for r in fixed)],
        'l3_fixed_support_longest_gap_range':[min(r['l3_longest_gap_days'] for r in fixed),max(r['l3_longest_gap_days'] for r in fixed)],
        'l3_days_without_finite_box_values':int((~any_l3).sum()),
        'l3_longest_box_gap_days':longest_absence(any_l3),'monthly_box_availability':months,
        'official_port_reference':port,'port_reference_pixel':port_cell,
        'port_reference_in_center_selection_box':BOX['minimum_latitude']<=py<=BOX['maximum_latitude']
                                                   and BOX['minimum_longitude']<=px<=BOX['maximum_longitude'],
        'cell_results':rows,'training_ready':False,'independent_marine_mask_validated':False,
        'limitations':['GLOBE resampling estimates mixed cells at its own coarse resolution',
                       'L4 finite support includes land and mixed coastal cells',
                       'coastal flag is diagnostic and does not exclude cells',
                       'no ambient values paired with fish or used in a model']}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,default=Path('chile/pilot_contract.json'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = audit(args.contract)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cell_results','products']},ensure_ascii=False,indent=2))
