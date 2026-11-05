"""Test numerical compatibility of soak hypotheses without relabelling units."""
import argparse
from collections import Counter
from bisect import bisect_left
import hashlib
import json
from pathlib import Path

import pandas as pd

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, diagnostic_dms, table
from audit_ifop_trip_plausibility import haversine


def summary(values):
    s = pd.Series(values, dtype=float)
    return {'n': len(s), 'minimum': float(s.min()) if len(s) else None,
            'median': float(s.median()) if len(s) else None,
            'maximum': float(s.max()) if len(s) else None}


def audit(raw_dir):
    results = []
    for year, (digest, _) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != digest:
            raise ValueError('Source archive changed')
        db = next((raw_dir/str(year)).rglob(f'DATOS {year} ARTESANAL DCS-PDA.accdb'))
        for gear, name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                           ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            full = table(db, name)
            selected = full[full.PUERTO_RECALADA.eq('560') & full.ESPECIE_OBJETIVO.eq('1')]
            # Prior observed records use the whole source table, including other
            # ports/target species. They are not the true preceding fishing trip.
            histories = {}
            for key, _ in full.groupby(TRIP, dropna=False):
                vessel, departure, arrival = key
                start, end = date_or_none(departure), date_or_none(arrival)
                if vessel and start is not None and end is not None and end > start:
                    histories.setdefault(vessel, []).append((start, end))
            histories = {v: sorted(set(records)) for v, records in histories.items()}
            a, b, values = Counter(), Counter(), Counter()
            previous_interval_hours, previous_departure_gap_hours = [], []
            scenario_speeds = []
            for key, g in selected.groupby(TRIP, dropna=False):
                if any(g[f].nunique(dropna=False) != 1 for f in ['HORAS_REPOSO','LATITUD','LONGITUD','PUERTO_ZARPE']):
                    raise ValueError('Ambiguous candidate fields')
                first = g.iloc[0]
                start, end = date_or_none(key[1]), date_or_none(key[2])
                soak = pd.to_numeric(first.HORAS_REPOSO, errors='coerce')
                if pd.isna(soak):
                    a['missing_soak'] += 1
                    continue
                a['with_soak'] += 1
                values[float(soak)] += 1
                if start is None or end is None or end <= start:
                    a['invalid_trip_time'] += 1
                    continue
                hours = (end-start).total_seconds()/3600
                compatible = bool(0 <= soak/60 <= hours)
                a['minutes_compatible_with_trip_duration'] += int(compatible)
                a['minutes_exceed_trip_duration'] += int(not compatible)
                remaining = hours-soak/60
                lat = diagnostic_dms(first.LATITUD, 90)
                lon = diagnostic_dms(first.LONGITUD, 180)
                if remaining > 0 and lat is not None and lon is not None:
                    distance = haversine(lat, lon)
                    speed = (2 if first.PUERTO_ZARPE == '560' else 1)*distance/remaining/1.852
                    scenario_speeds.append((float(speed), len(g)))
                else:
                    a['minutes_scenario_nonpositive_time_or_bad_coordinate'] += 1
                records = histories.get(key[0], [])
                starts = [s for s, e in records]
                i = bisect_left(starts, start)-1
                if i < 0:
                    b['no_prior_observed_departure_same_gear_year'] += 1
                    continue
                prior_start = starts[i]
                tied = [(s,e) for s,e in records if s == prior_start]
                if len(tied) != 1:
                    b['ambiguous_prior_same_departure_time'] += 1
                    continue
                prior_end = tied[0][1]
                if prior_end > start:
                    b['prior_observed_record_overlaps_current'] += 1
                    continue
                interval = (end-prior_start).total_seconds()/3600
                b['comparable_with_prior_observed_record'] += 1
                b['hours_compatible_with_prior_departure_current_return'] += int(0 <= soak <= interval)
                b['hours_exceed_prior_departure_current_return'] += int(not 0 <= soak <= interval)
                previous_interval_hours.append(interval)
                previous_departure_gap_hours.append((start-prior_start).total_seconds()/3600)
            for k in ['with_soak','missing_soak','invalid_trip_time','minutes_compatible_with_trip_duration',
                      'minutes_exceed_trip_duration','minutes_scenario_nonpositive_time_or_bad_coordinate']:
                a.setdefault(k, 0)
            for k in ['no_prior_observed_departure_same_gear_year','ambiguous_prior_same_departure_time',
                      'prior_observed_record_overlaps_current','comparable_with_prior_observed_record',
                      'hours_compatible_with_prior_departure_current_return','hours_exceed_prior_departure_current_return']:
                b.setdefault(k, 0)
            n = a['with_soak']-a['invalid_trip_time']
            aa = dict(a)
            aa['compatibility_fraction'] = a['minutes_compatible_with_trip_duration']/n if n else None
            bb = dict(b)
            den = b['comparable_with_prior_observed_record']
            bb['compatibility_fraction_among_comparable'] = b['hours_compatible_with_prior_departure_current_return']/den if den else None
            bb['prior_departure_to_current_return_hours'] = summary(previous_interval_hours)
            bb['observed_departure_gap_hours'] = summary(previous_departure_gap_hours)
            results.append({
                'year': year, 'gear': gear, 'source_sha256': digest,
                'candidate_trips': selected.groupby(TRIP, dropna=False).ngroups,
                'hypothesis_A_minutes_compatibility': aa,
                'hypothesis_B_prior_observed_record_compatibility': bb,
                'reported_soak_value_frequencies': {str(k): v for k,v in sorted(values.items())},
                'reported_soak_multiples': {
                    str(m): sum(n for v,n in values.items() if abs(v/m-round(v/m)) < 1e-9)
                    for m in [10,30,60]},
                'unvalidated_minutes_navigation_scenario': {
                    'usable_candidates': len(scenario_speeds),
                    'flags_by_knots': {str(k): {
                        'candidate_trips_flagged': sum(s > k for s,n in scenario_speeds),
                        'source_rows_flagged': sum(n for s,n in scenario_speeds if s > k)} for k in [9,12,15]},
                },
            })
    return {'schema_version': 'ifop_soak_hypothesis_compatibility_v1', 'results': results,
            'training_ready': False, 'soak_units_validated': False,
            'limitations': [
                'compatibility tests do not distinguish true units, gear carryover or source errors',
                'previous sampled record may be separated by many unobserved trips and does not link the same gear',
                'prior record search is within one gear/year and all rows of that table, not across years or gears',
                'hypothesis B is not exhaustive: deployment could precede multiple trips',
                'failure of both A and B does not establish a residual cause by exclusion',
                'minutes navigation is an unvalidated sensitivity scenario; original flags and values unchanged',
                'no original rows, vessel identifiers or exact trip timestamps published']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
