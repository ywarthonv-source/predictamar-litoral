"""Audit observed coverage of candidate keys, with aggregate output only."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median

import pandas as pd

from audit_ifop_alignment_inputs import verified_member
from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, table
from audit_ifop_zero_activity import catch_state


def strata(raw_dir, *, full_tables=False):
    for year, (digest, _) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        with archive.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
                raise ValueError('Unexpected ZIP version')
        db = verified_member(archive, raw_dir/str(year), f'DATOS {year} ARTESANAL DCS-PDA.accdb')
        names = [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                 ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]
        for gear, name in names:
            data = table(db, name)
            if full_tables:
                yield year, gear, digest, data
                continue
            selected = data[data.PUERTO_RECALADA.eq('560') & data.ESPECIE_OBJETIVO.eq('1')]
            yield year, gear, digest, selected


def coverage(year, gear, digest, selected):
    if selected[TRIP].eq('').any(axis=1).any():
        raise ValueError('Incomplete candidate key')
    counts, rows_per_key, species = Counter(), Counter(), Counter()
    start_hours, end_hours = [0]*24, [0]*24
    months = defaultdict(Counter)
    days = defaultdict(set)
    for _, group in selected.groupby(TRIP):
        counts['candidate_keys'] += 1
        rows_per_key[len(group)] += 1
        weights = pd.to_numeric(group.PESO, errors='coerce')
        other = ~group.COD_ESPECIE.isin(['1','999',''])
        positive_other = other & weights.gt(0) & weights.map(math.isfinite)
        counts['keys_with_other_species'] += int(other.any())
        counts['keys_with_positive_other_species'] += int(positive_other.any())
        counts['other_species_rows'] += int(other.sum())
        counts['positive_other_species_rows'] += int(positive_other.sum())
        species.update(set(group.loc[positive_other,'COD_ESPECIE']))
        row = group.iloc[0]
        start, end = date_or_none(row.FECHA_HORA_ZARPE), date_or_none(row.FECHA_HORA_RECALADA)
        if start is None or end is None or end < start:
            raise ValueError('Unexpected candidate dates')
        start_hours[start.hour] += 1
        end_hours[end.hour] += 1
        counts['same_recorded_calendar_day'] += int(start.date() == end.date())
        month = end.strftime('%Y-%m')
        months[month][catch_state(group)] += 1
        days[month].add(end.date())
    if sum(k*v for k,v in rows_per_key.items()) != len(selected):
        raise ValueError('Source row conservation failed')
    return {'year':year,'gear':gear,'source_sha256':digest,'selected_rows':len(selected),
            'counts':dict(counts),'rows_per_key':dict(sorted(rows_per_key.items())),
            'distinct_positive_other_species_codes':len(species),
            'departure_hour_0_to_23':start_hours,'return_hour_0_to_23':end_hours,
            'recorded_return_months':{month:{'days_with_keys':len(days[month]),
                                            'states':dict(months[month])} for month in sorted(months)}}


def cell_gradient(cell_path):
    source = json.loads(cell_path.read_text())
    fixed = [c for c in source['cell_results'] if c['l4_finite_days']==source['days']]
    clear = [c for c in fixed if c['globe_land_samples_out_of_400']==0]
    mixed = [c for c in fixed if c['mixed_coastal_cell_diagnostic']]
    columns = defaultdict(list)
    for cell in clear:
        columns[cell['column']].append(cell['l3_finite_days'])
    port = source['port_reference_pixel']['l3_finite_days']
    return {'input_sha256':hashlib.sha256(cell_path.read_bytes()).hexdigest(),
            'fixed_support_cells':len(fixed),'globe_zero_land_cells':len(clear),'globe_mixed_cells':len(mixed),
            'zero_land_median_l3_days':median(c['l3_finite_days'] for c in clear),
            'mixed_median_l3_days':median(c['l3_finite_days'] for c in mixed),
            'zero_land_by_column':{k:{'cells':len(v),'median_l3_days':median(v)} for k,v in sorted(columns.items())},
            'port_cells_fewer_l3_days':sum(c['l3_finite_days']<port for c in fixed),
            'port_cells_equal_l3_days':sum(c['l3_finite_days']==port for c in fixed),
            'port_cells_more_l3_days':sum(c['l3_finite_days']>port for c in fixed)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--cell-support',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = {'schema_version':'portales_candidate_coverage_v1',
              'results':[coverage(*item) for item in strata(args.raw_dir)],
              'cell_gradient_from_published_aggregate':cell_gradient(args.cell_support),
              'recorded_clock_timezone_validated':False,'sampling_frame_validated':False,
              'evaluation_ready':False,'training_ready':False,
              'limitations':['calendar and clock summaries preserve source values',
                             'months with no keys in an export do not measure fishing effort',
                             'other-species rows measure recording, not catch completeness',
                             'longitude is not a measured distance to coast']}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

