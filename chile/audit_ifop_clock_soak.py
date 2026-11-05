"""Clock-format soak hypothesis: source histograms, column properties, sensitivity."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
from access_parser import AccessParser

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, diagnostic_dms, table
from audit_ifop_trip_plausibility import haversine


def clock_hours(value):
    if not math.isfinite(value) or value < 0 or value != int(value):
        return None
    hours, minutes = divmod(int(value), 100)
    return hours+minutes/60 if minutes < 60 else None


def histogram(series):
    nums = pd.to_numeric(series, errors='coerce')
    c = Counter()
    for v in nums.dropna():
        if v < 0:
            c['negative'] += 1
        elif v != int(v):
            c['nonintegral'] += 1
        else:
            c[f'{int(v)%100:02d}'] += 1
    return {'source_rows': len(series), 'missing': int(nums.isna().sum()),
            'nonempty_but_nonnumeric': int((series.ne('') & nums.isna()).sum()),
            'last_two_digits_or_invalid_class_counts': dict(sorted(c.items())),
            'integer_clock_minute_overflow': sum(n for k,n in c.items() if k.isdigit() and int(k)>=60)}


def audit(raw_dir):
    results = []
    for year, (digest, _) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != digest:
            raise ValueError('Unexpected source archive')
        db = next((raw_dir/str(year)).rglob(f'DATOS {year} ARTESANAL DCS-PDA.accdb'))
        parser = AccessParser(str(db))
        for gear, name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                           ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            full = table(db, name)
            access_table = parser.get_table(name)
            column = next(c for c in access_table.columns.values() if c.col_name_str == 'HORAS_REPOSO')
            props = getattr(column, 'extra_props', {}) or {}
            selected = full[full.PUERTO_RECALADA.eq('560') & full.ESPECIE_OBJETIVO.eq('1')]
            counts, inferred_minutes, speeds = Counter(), [], []
            for _, g in selected.groupby(TRIP, dropna=False):
                if any(g[f].nunique(dropna=False) != 1 for f in ['HORAS_REPOSO','LATITUD','LONGITUD','PUERTO_ZARPE']):
                    raise ValueError('Within-candidate soak, position or departure-port conflict')
                r = g.iloc[0]
                value = pd.to_numeric(r.HORAS_REPOSO, errors='coerce')
                if pd.isna(value):
                    counts['missing_soak'] += 1
                    continue
                counts['reported_soak'] += 1
                hours = clock_hours(float(value))
                if hours is None:
                    counts['invalid_clock_encoding'] += 1
                    continue
                counts['valid_clock_encoding'] += 1
                inferred_minutes.append(hours*60)
                start,end = date_or_none(r.FECHA_HORA_ZARPE),date_or_none(r.FECHA_HORA_RECALADA)
                duration = (end-start).total_seconds()/3600 if start and end else None
                if duration is None or duration <= 0:
                    counts['invalid_trip_duration'] += 1
                    continue
                counts['clock_soak_within_trip_duration'] += int(hours <= duration)
                remaining = duration-hours
                lat,lon = diagnostic_dms(r.LATITUD,90),diagnostic_dms(r.LONGITUD,180)
                if remaining<=0 or lat is None or lon is None:
                    counts['unusable_navigation_scenario'] += 1
                    continue
                speeds.append((float((2 if r.PUERTO_ZARPE=='560' else 1)*haversine(lat,lon)/remaining/1.852),len(g)))
            for key in ['missing_soak','reported_soak','invalid_clock_encoding','valid_clock_encoding',
                        'invalid_trip_duration','clock_soak_within_trip_duration','unusable_navigation_scenario']:
                counts.setdefault(key,0)
            results.append({'year':year,'gear':gear,'source_sha256':digest,
                            'national_source_row_histogram':histogram(full.HORAS_REPOSO),
                            'column_storage_type_code':int(column.type),
                            'column_properties_inspected': ['Format','InputMask','DefaultValue','DecimalPlaces','DisplayControl'],
                            'column_properties_present':{k:props[k] for k in ['Format','InputMask','DefaultValue','DecimalPlaces','DisplayControl'] if k in props},
                            'local_candidate_clock_compatibility':dict(counts),
                            'clock_minutes_median_among_valid':float(pd.Series(inferred_minutes).median()) if inferred_minutes else None,
                            'clock_minutes_multiple_30':sum(abs(v/30-round(v/30))<1e-9 for v in inferred_minutes),
                            'unvalidated_clock_navigation_scenario':{
                                'usable_candidates':len(speeds),
                                'flags_by_knots':{str(k):{'candidate_trips_flagged':sum(s>k for s,n in speeds),
                                                         'source_rows_flagged':sum(n for s,n in speeds if s>k)} for k in [9,12,15]}}})
    return {'schema_version':'ifop_clock_soak_hypothesis_v1','results':results,
            'access_parser_version':'0.0.6','training_ready':False,'soak_units_validated':False,
            'limitations':['national histograms count source rows, not independent trips',
                           'numeric clock compatibility is not a documented field convention',
                           'column display/default properties are not the original DCS-PDA application form',
                           'no defaults imputed, no clock conversion applied to original data',
                           'clock sensitivity excludes invalid encodings without repairing them',
                           'no individual identifiers, dates or source rows published']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=audit(args.raw_dir)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
