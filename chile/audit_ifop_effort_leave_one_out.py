"""Audit effort repetition without self-inclusion; no fitted fish model or CPUE."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, table
from audit_ifop_zero_activity import catch_state


def modes(counter):
    positive = {v: n for v, n in counter.items() if n > 0}
    return {v for v, n in positive.items() if n == max(positive.values())} if positive else set()


def constant_effort(data):
    groups = list(data.groupby('vessel'))
    complete = [g for _, g in groups if g.effort.notna().all()]
    repeat = [g for g in complete if len(g) >= 2]
    return {
        'vessels': len(groups),
        'vessels_with_complete_effort': len(complete),
        'complete_vessels_with_one_recorded_effort': sum(g.effort.nunique() == 1 for g in complete),
        'complete_vessels_with_at_least_two_trips': len(repeat),
        'repeat_vessels_with_one_recorded_effort': sum(g.effort.nunique() == 1 for g in repeat),
        'complete_single_trip_vessels': sum(len(g) == 1 for g in complete),
        'trips_with_missing_effort': int(data.effort.isna().sum()),
    }


def auc_scenario(npos, nneg, area):
    # Hanley & McNeil 1982 Eq.1 and exponential-distribution Q approximations.
    # npos=n_A, nneg=n_N. Hypothetical independent observations, no measured AUC.
    q1, q2 = area/(2-area), 2*area*area/(1+area)
    variance = (area*(1-area)+(npos-1)*(q1-area*area)+(nneg-1)*(q2-area*area))/(npos*nneg)
    se = math.sqrt(variance)
    return {'assumed_auc': area, 'standard_error': se,
            'normal_95_interval': [area-1.96*se, area+1.96*se]}


def audit(raw_dir):
    reports = []
    for year, (digest, url) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != digest:
            raise ValueError('Source archive changed')
        db = next((raw_dir/str(year)).rglob(f'DATOS {year} ARTESANAL DCS-PDA.accdb'))
        dictionary = next((raw_dir/str(year)).rglob('Descripción de Campos.xls'))
        for gear, name, sheet in [
            ('enmalle', f'BITACORAS ENMALLE Centro Sur {year}', 'Bitácora Enmalle'),
            ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}', 'Bitácora Espinel')]:
            full = table(db, name)
            rows = full[full.PUERTO_RECALADA.eq('560') & full.ESPECIE_OBJETIVO.eq('1')]
            field = 'LONGITUD_RED' if gear == 'enmalle' else 'NUMERO_DE_ANZUELOS'
            trip_records = []
            for _, g in rows.groupby(TRIP, dropna=False):
                if g[field].nunique(dropna=False) != 1 or g.HORAS_REPOSO.nunique(dropna=False) != 1:
                    raise ValueError('Within-trip effort/soak conflict; cannot take first row')
                r = g.iloc[0]
                start, end = date_or_none(r.FECHA_HORA_ZARPE), date_or_none(r.FECHA_HORA_RECALADA)
                hours = (end-start).total_seconds()/3600 if start and end else None
                trip_records.append({'vessel': r.COD_BARCO, 'state': catch_state(g),
                                     'effort': pd.to_numeric(r[field], errors='coerce'),
                                     'soak': pd.to_numeric(r.HORAS_REPOSO, errors='coerce'),
                                     'caladas': pd.to_numeric(r.N_CALADAS, errors='coerce'),
                                     'hours': hours})
            data = pd.DataFrame(trip_records)
            pos = data[data.state.eq('reported_positive_hake')]
            counters = {v: Counter(g.effort.dropna()) for v, g in pos.groupby('vessel')}
            loo = Counter()
            for r in pos.itertuples():
                if pd.isna(r.effort):
                    loo['missing_effort'] += 1
                    continue
                peer_counts = counters[r.vessel].copy()
                peer_counts[r.effort] -= 1
                reference = modes(peer_counts)
                if not reference:
                    loo['no_other_positive_effort_trip'] += 1
                    continue
                loo['comparable_positive_trips'] += 1
                loo['matches_any_leave_one_out_mode'] += int(r.effort in reference)
                loo['tied_leave_one_out_modes'] += int(len(reference) > 1)
            for key in ['missing_effort', 'no_other_positive_effort_trip', 'comparable_positive_trips',
                        'matches_any_leave_one_out_mode', 'tied_leave_one_out_modes']:
                loo.setdefault(key, 0)
            denominator = loo['comparable_positive_trips']
            loo_result = dict(loo)
            loo_result['match_fraction_among_comparable'] = loo['matches_any_leave_one_out_mode']/denominator if denominator else None
            raw_soak = pd.to_numeric(full.HORAS_REPOSO, errors='coerce')
            desc = pd.read_excel(dictionary, sheet_name=sheet, header=None).fillna('')
            matching = desc[desc.iloc[:, 0].astype(str).eq('HORAS_REPOSO')]
            if len(matching) != 1:
                raise ValueError('Unexpected dictionary row count')
            soak_by_state = {}
            for state, g in data.groupby('state'):
                soak_by_state[state] = {
                    'candidate_trips': len(g), 'missing_soak': int(g.soak.isna().sum()),
                    'positive_soak': int(g.soak.gt(0).sum()),
                    'soak_greater_than_total_trip_hours': int(g.soak.gt(g.hours).sum()),
                    'soak_equal_to_total_trip_hours': int(g.soak.eq(g.hours).sum()),
                }
            reported_zero = data.state.isin(['reported_hake_weight_zero', 'reported_no_capture_trip_code999_zero'])
            nneg = int(reported_zero.sum())
            reports.append({
                'year': year, 'gear': gear, 'source_sha256': digest,
                'candidate_trips': len(data), 'positive_hake_trips': len(pos),
                'positive_effort_leave_one_out': loo_result,
                'constant_effort_all_states': constant_effort(data),
                'constant_effort_positive_hake_only': constant_effort(pos),
                'soak_dictionary': {'sheet': sheet, 'excel_row_1based': int(matching.index[0])+1,
                                    'field': 'HORAS_REPOSO', 'description': str(matching.iloc[0, 1]),
                                    'dictionary_sha256': hashlib.sha256(dictionary.read_bytes()).hexdigest()},
                'soak_full_source_table': {'rows': len(full), 'missing': int(raw_soak.isna().sum()),
                                           'nonempty_strings': int(full.HORAS_REPOSO.ne('').sum())},
                'soak_selected_candidate_trips_summary': {
                    'nonmissing': int(data.soak.notna().sum()),
                    'minimum_reported_value': float(data.soak.min()) if data.soak.notna().any() else None,
                    'median_reported_value': float(data.soak.median()) if data.soak.notna().any() else None,
                    'maximum_reported_value': float(data.soak.max()) if data.soak.notna().any() else None,
                    'greater_than_trip_hours': int(data.soak.gt(data.hours).sum()),
                    'greater_than_trip_hours_with_one_calada': int((data.soak.gt(data.hours) & data.caladas.eq(1)).sum()),
                },
                'soak_selected_candidate_trips_by_state': soak_by_state,
                'hypothetical_auc_precision': {'reported_zero_candidates_assumed_negative': nneg,
                                               'reported_zero_candidate_vessels': int(data.loc[reported_zero, 'vessel'].nunique()),
                                               'scenarios': [auc_scenario(len(pos), nneg, a) for a in [0.7, 0.6]]},
            })
    return {'schema_version': 'ifop_effort_leave_one_out_v1', 'results': reports,
            'training_ready': False, 'zero_labels_validated': False,
            'auc_formula_source': 'https://jhanley.biostat.mcgill.ca/software/Hanley_McNeil_Radiology_82.pdf',
            'limitations': [
                'leave-one-out modes are descriptive, not causal evidence about deployed gear',
                'single-trip vessels excluded from the repeat-vessel constancy denominator',
                'dictionary does not identify whether soak is per set, mean or cumulative across sets',
                'no navigation-time correction applied from unverified soak semantics',
                'hypothetical AUC scenarios use unvalidated negatives and independent-observation approximation',
                'no observed model AUC or cluster-adjusted confidence intervals calculated',
                'no original rows, vessel identifiers or coordinates published']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
