"""Review distance/time and within-vessel effort patterns; no causal inference."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, diagnostic_dms, table
from audit_ifop_zero_activity import catch_state

PORT = (-33.031145882327884, -71.5900592190291)


def haversine(lat, lon):
    p1, p2 = math.radians(PORT[0]), math.radians(lat)
    delta = math.radians(lon-PORT[1])
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(delta/2)**2
    return 6371.0088*2*math.atan2(math.sqrt(a), math.sqrt(max(0, 1-a)))


def duration_summary(values):
    x = pd.Series(values, dtype=float).dropna()
    return {'n': len(x), 'minimum': float(x.min()) if len(x) else None,
            'median': float(x.median()) if len(x) else None,
            'maximum': float(x.max()) if len(x) else None}


def audit(raw_dir):
    reports = []
    for year, (digest, url) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != digest:
            raise ValueError('Source archive changed')
        db = raw_dir/str(year)/f'DATOS {year} ARTESANAL DCS-PDA.accdb'
        for gear, name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                           ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            full = table(db, name)
            rows = full[full.PUERTO_RECALADA.eq('560') & full.ESPECIE_OBJETIVO.eq('1')]
            effort_field = 'LONGITUD_RED' if gear == 'enmalle' else 'NUMERO_DE_ANZUELOS'
            trips = []
            for key, g in rows.groupby(TRIP, dropna=False):
                first = g.iloc[0]
                start, end = date_or_none(first.FECHA_HORA_ZARPE), date_or_none(first.FECHA_HORA_RECALADA)
                hours = (end-start).total_seconds()/3600 if start and end else None
                lat, lon = diagnostic_dms(first.LATITUD, 90), diagnostic_dms(first.LONGITUD, 180)
                distance = haversine(lat, lon) if lat is not None and lon is not None else None
                round_trip = first.PUERTO_ZARPE == '560'
                # Full trip time is conservative: it includes fishing and stops.
                # 2*d applies only when departure and return are both Portales.
                speed = ((2 if round_trip else 1)*distance/hours/1.852
                         if distance is not None and hours is not None and hours > 0 else None)
                state = catch_state(g)
                trips.append({'vessel': first.COD_BARCO, 'state': state,
                              'all_code999': bool(g.COD_ESPECIE.eq('999').all()),
                              'effort': pd.to_numeric(first[effort_field], errors='coerce'),
                              'hours': hours, 'distance': distance,
                              'portales_departure': round_trip,
                              'required_average_speed_knots': speed, 'rows': len(g)})
            data = pd.DataFrame(trips)
            positive = data[data.state.eq('reported_positive_hake')]
            modes = positive.groupby('vessel').effort.agg(lambda x: set(x.dropna().mode()))
            modal_results = {}
            cohorts = {
                'reported_positive_hake': data.state.eq('reported_positive_hake'),
                'all_code999_including_conflict': data.all_code999,
                'code999_zero_only': data.state.eq('reported_no_capture_trip_code999_zero'),
                'reported_hake_weight_zero': data.state.eq('reported_hake_weight_zero')}
            for label, mask in cohorts.items():
                cohort = data[mask]
                comparable = cohort[cohort.vessel.map(lambda v: v in modes.index and bool(modes[v])) & cohort.effort.notna()]
                matches = sum(r.effort in modes[r.vessel] for r in comparable.itertuples())
                vessels = set(cohort.vessel)
                peers = positive[positive.vessel.isin(vessels)]
                modal_results[label] = {
                    'candidate_trips': len(cohort), 'vessels': len(vessels),
                    'trips_with_positive_trip_mode_reference': len(comparable),
                    'trips_without_usable_reference': len(cohort)-len(comparable),
                    'effort_matches_any_positive_mode': int(matches),
                    'match_fraction_among_comparable': matches/len(comparable) if len(comparable) else None,
                    'duration_hours': duration_summary(cohort.hours),
                    'positive_peer_trips_same_vessels_duration_hours': duration_summary(peers.hours)}
            speeds = {}
            for threshold in [9, 12, 15]:
                flagged = data.required_average_speed_knots.gt(threshold)
                speeds[str(threshold)] = {'candidate_trips_flagged': int(flagged.sum()),
                                          'source_rows_flagged': int(data.loc[flagged, 'rows'].sum())}
            extreme = data.loc[data.distance.idxmax()]
            reports.append({'year': year, 'gear': gear, 'source_sha256': digest,
                            'candidate_trips': len(data),
                            'departure_other_than_portales_trips': int((~data.portales_departure).sum()),
                            'unusable_distance_duration_trips': int(data.required_average_speed_knots.isna().sum()),
                            'distance_duration_review_by_speed_knots': speeds,
                            'maximum_distance_case_derived': {
                                'distance_to_portales_km': float(extreme.distance),
                                'trip_duration_hours': float(extreme.hours),
                                'required_average_speed_knots': float(extreme.required_average_speed_knots)},
                            'positive_trip_vessels_with_tied_effort_modes': int(modes.map(len).gt(1).sum()),
                            'effort_modal_comparison': modal_results})
    return {'schema_version': 'ifop_distance_time_effort_modes_v1',
            'reference_point_lat_lon': list(PORT),
            'reference_source': 'Subpesca caleta 214 reference point; not exact vessel departure berth',
            'results': reports, 'training_ready': False,
            'limitations': ['9/12/15 knots are exploratory scenarios, not measured vessel limits',
                            'round-trip bound used only when both reported ports are Portales',
                            'diagnostic southwest DDMMSS and candidate trip key remain assumptions',
                            'modal equality cannot distinguish stable deployed gear from copied equipment attributes',
                            'positive-trip mode comparison is in-sample and descriptive, not a statistical identification test',
                            'no individual identifiers, coordinates, raw rows or corrected labels published']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps([{k: t[k] for k in ['year','gear','distance_duration_review_by_speed_knots',
                                       'maximum_distance_case_derived','effort_modal_comparison']}
                      for t in result['results']], ensure_ascii=False, indent=2))
