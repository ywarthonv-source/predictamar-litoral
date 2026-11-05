"""Finite-value census in the unchanged diagnostic box, not a marine-mask census."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import itertools
import json
from pathlib import Path
import urllib.error

import numpy as np

from audit_arco_time_axes import DATASETS, ROOT, read_axis
from audit_arco_historical_probe import BOX, get, decode, masked_cf


def read_grid(base, metadata, ti, yi, xi, manifest):
    spec,attrs=metadata['CHL/.zarray'],metadata['CHL/.zattrs']
    if attrs['_ARRAY_DIMENSIONS']!=['time','latitude','longitude']:
        raise ValueError('Unexpected variable dimensions')
    vectors=[np.asarray(v,dtype=int) for v in [ti,yi,xi]]
    chunk_ids=[v//c for v,c in zip(vectors,spec['chunks'])]
    keys=list(itertools.product(*(np.unique(v) for v in chunk_ids)))
    if len(keys)>8:
        raise ValueError('At most eight field chunks per read allowed')
    result=np.full(tuple(len(v) for v in vectors),np.nan)
    for key in keys:
        url=base+'/CHL/'+spec.get('dimension_separator','.').join(map(str,key))
        try:raw=get(url,manifest)
        except urllib.error.HTTPError as e:
            if e.code!=404:raise
            manifest.append({'url':url,'http_status':404,'bytes':0,'sha256':None})
            continue
        tile=decode(raw,spec)
        destinations=[np.flatnonzero(v==k) for v,k in zip(chunk_ids,key)]
        source=[v[d]%c for v,d,c in zip(vectors,destinations,spec['chunks'])]
        result[np.ix_(*destinations)]=masked_cf(tile[np.ix_(*source)],spec,attrs)
    return result


def product(item, *, include_reference_2015=True):
    pid,dataset=item;manifest=[]
    stac=json.loads(get(ROOT+pid+'/'+dataset+'/dataset.stac.json',manifest))
    base=stac['assets']['geoChunked']['href'].rstrip('/')
    m=json.loads(get(base+'/.zmetadata',manifest))['metadata']
    axes={k:read_axis(base,m,k,manifest) for k in ['time','latitude','longitude']}
    unit,origin=m['time/.zattrs']['units'].split(' since ',1)
    if unit!='days':raise ValueError('Unexpected temporal units')
    epoch=datetime.fromisoformat(origin.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
    dates=np.asarray([(epoch+timedelta(days=float(v))).date().isoformat() for v in axes['time']])
    ti=np.flatnonzero((dates>='2024-01-01')&(dates<='2025-12-31'))
    selected=dates[ti]
    expected=np.arange(np.datetime64('2024-01-01'),np.datetime64('2026-01-01')).astype(str)
    if not np.array_equal(selected,expected):raise ValueError('Incomplete or ambiguous daily axis')
    yi=np.flatnonzero((axes['latitude']>=BOX['minimum_latitude'])&(axes['latitude']<=BOX['maximum_latitude']))
    xi=np.flatnonzero((axes['longitude']>=BOX['minimum_longitude'])&(axes['longitude']<=BOX['maximum_longitude']))
    data=read_grid(base,m,ti,yi,xi,manifest)
    probe_2015=None
    if include_reference_2015 and '_L4_' in pid:
        # Verify whether the earlier 2015 sample has the same nonfinite cells.
        tb=stac['assets']['timeChunked']['href'].rstrip('/')
        tm=json.loads(get(tb+'/.zmetadata',manifest))['metadata']
        if tm['CHL/.zarray']['shape']!=m['CHL/.zarray']['shape']:
            raise ValueError('Service shapes differ')
        p=np.flatnonzero(dates=='2015-01-15')
        if len(p)!=1:raise ValueError('Ambiguous 2015 day')
        probe_2015=read_grid(tb,tm,p,yi,xi,manifest)[0]
    result={'product_id':pid,'dataset_version_id':dataset,'service':'geoChunked',
            'days':len(ti),'field_chunk_shape':m['CHL/.zarray']['chunks'],
            'grid_shape':[len(yi),len(xi)],'chl_units':m['CHL/.zattrs'].get('units'),
            'field_chunks_fetched':sum('/CHL/' in r['url'] and r.get('http_status')!=404 for r in manifest),
            'bytes_fetched':sum(r['bytes'] for r in manifest),'request_manifest':manifest}
    return result,data,selected,axes['latitude'][yi],axes['longitude'][xi],probe_2015


def stats(v):
    return {'minimum':int(v.min()),'p10':float(np.quantile(v,.1)),
            'median':float(np.median(v)),'p90':float(np.quantile(v,.9)),'maximum':int(v.max())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as ex:out=list(ex.map(product,DATASETS[2:]))
    a,b=out
    if not all(np.array_equal(a[i],b[i]) for i in [2,3,4]):raise ValueError('L3/L4 coordinates differ')
    fa,fb=np.isfinite(a[1]),np.isfinite(b[1]);common=fa&fb
    missing=~fb.any(axis=0);always=fb.all(axis=0)
    coords=[{'row_0based':int(y),'column_0based':int(x),'latitude':float(b[3][y]),'longitude':float(b[4][x])}
            for y,x in np.argwhere(missing)]
    ca,cb=fa.sum(axis=(1,2)),fb.sum(axis=(1,2))
    extra=(fb&~fa).sum(axis=(1,2))
    rows={'first_date':str(a[2][0]),'last_date':str(a[2][-1]),'step_days':1,
          'l3_finite_in_bounds':ca.tolist(),'l4_finite_in_bounds':cb.tolist(),
          'l4_finite_without_l3':extra.tolist()}
    result={'schema_version':'arco_chl_rectangular_census_2024_2025_v1',
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'diagnostic_box':BOX,
            'products':[v[0] for v in out],'grid_cells':int(fa.shape[1]*fa.shape[2]),
            'daily_finite_counts':rows,'l3_daily_count_summary':stats(ca),'l4_daily_count_summary':stats(cb),
            'days_l3_zero_finite':int((ca==0).sum()),'days_l3_at_least_100_finite':int((ca>=100).sum()),
            'days_l3_has_finite_outside_l4_support':int((fa&~fb).any(axis=(1,2)).sum()),
            'common_finite_cell_days':int(common.sum()),
            'maximum_absolute_difference_common':float(np.max(np.abs(a[1][common]-b[1][common]))) if common.any() else None,
            'l4_never_finite_cell_coordinates':coords,
            'l4_always_finite_cells':int(always.sum()),'l4_never_finite_cells':int(missing.sum()),
            'l4_variable_finite_status_cells':int((~always&~missing).sum()),
            'l4_2015_01_15_nonfinite_mask_equals_census_never_finite':bool(np.array_equal(~np.isfinite(b[5]),missing)),
            'training_ready':False,'independent_marine_mask_validated':False,
            'limitations':['finite in provider bounds is not complete ancillary-flag quality validation',
                           '144-cell rectangle and empirical L4 support are not independent marine masks',
                           'L4 without simultaneous L3 is a provenance indicator, not certified interpolation status',
                           'no fish dates, locations, trips or environmental values matched for evaluation',
                           'surface CHL does not establish fish presence or subsurface habitat',
                           'NRT service-window cause, licenses and pilot geometry remain outside this census']}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['daily_finite_counts','products']},ensure_ascii=False,indent=2))

