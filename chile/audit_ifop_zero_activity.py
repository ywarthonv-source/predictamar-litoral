"""Classify reported catch states and audit declared activity; no absence labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import pandas as pd

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, table

ACTIVITY_TIMES = ['FECHA_HORA_INI_CALADO', 'FECHA_HORA_FIN_CALADO',
                  'FECHA_HORA_INI_VIRADO', 'FECHA_HORA_FIN_VIRADO']


def catch_state(group):
    weight = pd.to_numeric(group.PESO, errors='coerce')
    hake = group.COD_ESPECIE.eq('1')
    code999 = group.COD_ESPECIE.eq('999')
    if (code999 & weight.gt(0)).any():
        return 'conflicting_code999_positive_weight'
    if (hake & weight.gt(0)).any():
        return 'reported_positive_hake'
    if hake.any() and weight[hake].notna().all() and weight[hake].eq(0).all():
        return 'reported_hake_weight_zero'
    if code999.all() and weight.notna().all() and weight.eq(0).all():
        return 'reported_no_capture_trip_code999_zero'
    if not hake.any():
        return 'target_not_listed_no_zero_imputed'
    return 'unresolved_weight'


def audit(raw_dir):
    reports, overlaps = [], []
    for year, (expected_hash, url) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != expected_hash:
            raise ValueError('Unexpected original archive version')
        db = raw_dir/str(year)/f'DATOS {year} ARTESANAL DCS-PDA.accdb'
        gear_keys = {}
        for gear, name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                           ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            full = table(db, name)
            rows = full[full.PUERTO_RECALADA.eq('560') & full.ESPECIE_OBJETIVO.eq('1')].copy()
            if rows[TRIP].eq('').any(axis=1).any():
                raise ValueError('Incomplete candidate trip key')
            effort_column = 'LONGITUD_RED' if gear == 'enmalle' else 'NUMERO_DE_ANZUELOS'
            states, activity, durations = Counter(), defaultdict(Counter), defaultdict(list)
            gear_keys[gear] = set()
            for key, group in rows.groupby(TRIP, dropna=False):
                gear_keys[gear].add(key)
                state = catch_state(group)
                states[state] += 1
                first = group.iloc[0]
                e = pd.to_numeric(group[effort_column], errors='coerce')
                c = pd.to_numeric(group.N_CALADAS, errors='coerce')
                soak = pd.to_numeric(group.HORAS_REPOSO, errors='coerce')
                a = activity[state]
                a['candidate_trips'] += 1
                a['all_rows_positive_declared_effort'] += int(e.gt(0).all())
                a['all_rows_positive_declared_caladas'] += int(c.gt(0).all())
                a['all_rows_positive_declared_soak_hours'] += int(soak.gt(0).all())
                a['all_rows_missing_soak_hours'] += int(soak.isna().all())
                a['conflicting_declared_effort_within_trip'] += int(group[effort_column].nunique(dropna=False) > 1)
                for field in ACTIVITY_TIMES:
                    a['any_nonempty_'+field] += int(group[field].ne('').any())
                start = date_or_none(first.FECHA_HORA_ZARPE)
                end = date_or_none(first.FECHA_HORA_RECALADA)
                lance = date_or_none(first.FECHA_LANCE)
                valid = start is not None and end is not None and lance is not None
                a['parseable_departure_return_lance'] += int(valid)
                if valid:
                    hours = (end-start).total_seconds()/3600
                    a['positive_trip_duration_lance_within_trip'] += int(hours > 0 and start <= lance <= end)
                    durations[state].append(hours)
            result = {'year': year, 'gear': gear, 'source_sha256': expected_hash,
                      'selected_rows': len(rows), 'candidate_trip_count': sum(states.values()),
                      'reported_state_candidate_trip_counts': dict(states),
                      'declared_activity_by_reported_state': {k: dict(v) for k, v in activity.items()},
                      'trip_duration_hours_by_reported_state': {
                          k: {'minimum': min(v), 'median': float(pd.Series(v).median()), 'maximum': max(v)}
                          for k, v in durations.items()}}
            reports.append(result)
        overlaps.append({'year': year, 'cross_gear_candidate_key_overlap': len(gear_keys['enmalle'] & gear_keys['espinel']),
                         'candidate_keys_union': len(gear_keys['enmalle'] | gear_keys['espinel'])})
    return {'schema_version': 'ifop_reported_zero_activity_v1',
            'candidate_trip_key': TRIP, 'results': reports,
            'cross_gear_key_checks': overlaps,
            'zero_labels_validated': False, 'training_ready': False,
            'limitations': [
                'reported activity is internal documentary support, not independent confirmation of fishing',
                'missing target species is never imputed as zero',
                'zero weight and no-capture code are retained as separate reported states',
                'empty deployment/retrieval timestamps are not repaired from other fields',
                'no CPUE estimates, ecological absence labels or recommendations generated']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'states': [{k: t[k] for k in ['year', 'gear', 'reported_state_candidate_trip_counts']} for t in result['results']],
                      'cross_gear_key_checks': result['cross_gear_key_checks']}, ensure_ascii=False, indent=2))
