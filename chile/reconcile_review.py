"""Reproduce external-review findings without treating linkage keys as trips.

Read the frozen original archive, not the earlier regional extract. Detailed
candidate links remain outside Git. No absence or CPUE is constructed.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import xarray as xr

from audit_public_data import distance_km, target_key


def prepare_events(events):
    result=events.copy()
    result['source_block']=result.id.str.split('_').str[1]
    result['declared_time']=pd.to_datetime(result.eventDate,format='%m/%d/%Y %H:%M:%S',errors='coerce')
    result['component_date']=pd.to_datetime(result.year+'-'+result.month+'-'+result.day,format='%Y-%m-%d',errors='coerce')
    result['lat']=pd.to_numeric(result.decimalLatitude,errors='coerce')
    result['lon']=pd.to_numeric(result.decimalLongitude,errors='coerce')
    result['valid_link_fields']=result.declared_time.notna()&result.lat.between(-90,90)&result.lon.between(-180,180)&~(result.lat.eq(0)&result.lon.eq(0))
    return result


KEYS=['declared_time','lat','lon']


def linking_summary(left,right):
    # These are candidate links, not a certified operational primary key.
    a=left[left.valid_link_fields].groupby(KEYS).size().rename('left_rows').reset_index()
    b=right[right.valid_link_fields].groupby(KEYS).size().rename('right_rows').reset_index()
    shared=a.merge(b,on=KEYS,validate='one_to_one')
    return {'left_events':len(left),'right_events':len(right),
            'left_valid_unique_keys':len(a),'right_valid_unique_keys':len(b),
            'shared_keys':len(shared),'shared_keys_with_multiple_left_events':int(shared.left_rows.gt(1).sum()),
            'shared_keys_with_multiple_right_events':int(shared.right_rows.gt(1).sum()),
            'one_to_one_candidate_keys':int((shared.left_rows.eq(1)&shared.right_rows.eq(1)).sum()),
            'not_certified_operation_counts':True}


def date_summary(events):
    both=events.declared_time.notna()&events.component_date.notna()
    delta=(events.declared_time.dt.normalize()-events.component_date).dt.total_seconds()/86400
    bad=both&delta.ne(0)
    return {'rows':len(events),'both_dates_parseable':int(both.sum()),
            'invalid_eventDate':int(events.declared_time.isna().sum()),
            'invalid_component_date':int(events.component_date.isna().sum()),
            'date_disagreements_among_parseable_rows':int(bad.sum()),
            'disagreements_by_source_block':events.loc[bad,'source_block'].value_counts().to_dict(),
            'median_eventDate_minus_component_days':float(delta[bad].median()) if bad.any() else None,
            'eventDate_semantics':'unconfirmed; only an explicit parsing convention, not certified fishing date'}


def reconcile(raw_dir,output):
    output.mkdir(parents=True,exist_ok=True)
    archive=raw_dir/'asipa_demersales_1_5.zip'
    with zipfile.ZipFile(archive) as z:
        events=prepare_events(pd.read_csv(z.open('event.txt'),sep='\t',dtype=str,keep_default_na=False,quoting=csv.QUOTE_NONE))
        left=events[events.source_block.eq('14-01')]
        right=events[events.source_block.eq('15-01')]
        capture=left[left.locality.eq('PORTALES')]
        biology=right[right.locality.eq('560.0')]
        ids=set(capture.id)|set(biology.id)
        pieces=[]
        for chunk in pd.read_csv(z.open('occurrence.txt'),sep='\t',dtype=str,keep_default_na=False,quoting=csv.QUOTE_NONE,chunksize=100000):
            part=chunk[chunk.id.isin(ids)].copy()
            part['target_species']=part.scientificName.map(target_key)
            pieces.append(part[part.target_species.ne('')])
        occ=pd.concat(pieces,ignore_index=True)
    joined=occ.merge(events[['id','source_block','locality']+KEYS],on='id',validate='many_to_one')
    report={'schema_version':'chile_review_reconciliation_v1',
            'source_sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),
            'key_definition':'eventDate parsed explicitly as MM/DD/YYYY HH:MM:SS plus parsed numeric latitude/longitude; no coordinate rounding',
            'original_counts_unit':'Darwin Core Event rows, NOT independent operations/trips',
            'training_ready':False,
            'global_candidate_links':linking_summary(left,right),
            'portales_text_to_560_candidate_links':linking_summary(capture,biology),
            'global_date_comparison':date_summary(events),
            'portales_capture_date_comparison':date_summary(capture),
            'source_560_date_comparison':date_summary(biology),
            'species':{}}
    for species in ['merluza_comun','reineta']:
        sub=joined[joined.target_species.eq(species)]
        cap=sub[sub.source_block.eq('14-01')]
        bio=sub[sub.source_block.eq('15-01')]
        positive=cap[pd.to_numeric(cap.organismQuantity,errors='coerce').gt(0)&cap.organismQuantityType.eq('KILOGRAMO')]
        positive_keys=positive[KEYS].dropna().drop_duplicates()
        labels=bio.groupby(KEYS).occurrenceStatus.agg(set)
        only_absent=labels[labels.map(lambda x:x=={'absent'})].reset_index()
        links=positive_keys.merge(only_absent,on=KEYS,validate='one_to_one')
        report['species'][species]={'capture_occurrence_rows':len(cap),'capture_event_ids':int(cap.id.nunique()),
                'capture_positive_unique_candidate_keys':len(positive_keys),
                'biology_declared_absent_rows':int(bio.occurrenceStatus.eq('absent').sum()),
                'biology_keys_declaring_only_absent':len(only_absent),
                'positive_capture_keys_with_only_absent_biology':len(links),
                'absent_interpretation':'unresolved; excluded as a capture-zero label',
                'capture_events_per_candidate_key_can_exceed_one':True}
    # Private, review-only registry preserves every capture event; no unsafe collapse.
    registry=capture[['id','eventDate','year','month','day','datasetName','declared_time','component_date','lat','lon']].copy()
    registry['same_key_capture_event_count']=capture.groupby(KEYS).id.transform('size')
    bio_counts=biology.groupby(KEYS).size().rename('same_key_biology_event_count').reset_index()
    registry=registry.merge(bio_counts,on=KEYS,how='left',validate='many_to_one')
    registry['reference_distance_km']=distance_km(registry.lat,registry.lon)
    registry['distance_over_111km_review_flag']=registry.reference_distance_km.gt(111)
    registry['distance_under_2km_review_flag']=registry.reference_distance_km.lt(2)
    registry['capture_date_is_certified']=False
    registry['training_ready']=False
    registry.to_csv(raw_dir/'portales_capture_event_linkage_REVIEW_ONLY.csv',index=False)
    report['private_registry_rows']=len(registry)
    report['private_registry_note']='One row per original capture Event; links are candidates and cannot supply a certified number of operations.'
    # An availability proxy is not an independently validated land/cloud mask.
    l3=xr.open_dataset(raw_dir/'copernicus_october_2026/chlorophyll_l3.nc')
    l4=xr.open_dataset(raw_dir/'copernicus_october_2026/chlorophyll_l4.nc')
    ocean_proxy=np.isfinite(l3.CHL).any('time')|np.isfinite(l4.CHL).any('time')
    cells=int(ocean_proxy.sum())
    daily=np.isfinite(l3.CHL).sum(['latitude','longitude'])
    observed,filled=xr.align(l3.CHL,l4.CHL,join='inner')
    obs=np.isfinite(observed);reconstructed=(~obs)&np.isfinite(filled)
    mask=xr.where(obs,1,xr.where(reconstructed,2,0)).astype('uint8')
    mask.attrs={'flag_values':[0,1,2],'flag_meanings':'no_data L3_available L4_only_available',
                'limitation':'availability provenance proxy, not certified per-cell observed/interpolated or independent land/cloud truth'}
    mask.to_dataset(name='availability_proxy').to_netcdf(raw_dir/'chlorophyll_availability_proxy_REVIEW_ONLY.nc',engine='h5netcdf')
    common_diff=abs(observed-filled).where(obs&np.isfinite(filled))
    report['chlorophyll']={'marine_support_proxy_cells':cells,
        'marine_support_proxy_definition':'union of finite L3/L4 cells across available times; not an independent land mask',
        'l3_dates_in_array':int(l3.sizes['time']),
        'l3_daily_finite_cells':[int(x) for x in daily.values],
        'l3_fraction_on_support_proxy':float(daily.sum()/(cells*l3.sizes['time'])),
        'l3_dates_at_least_80pct_proxy_support':int((daily/cells>=.8).sum()),
        'threshold_80pct_is_exploratory_not_validated':True,
        'common_l3_l4_dates':int(observed.sizes['time']),
        'common_l3_available_cells':int(obs.sum()),
        'common_l4_available_cells':int(np.isfinite(filled).sum()),
        'common_l4_only_cells':int(reconstructed.sum()),
        'maximum_absolute_difference_where_both_available':float(common_diff.max()),
        'inherited_time_coverage_attributes_are_not_used_as_subset_dates':True}
    (output/'review_reconciliation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();reconcile(args.raw_dir,args.output_dir)
