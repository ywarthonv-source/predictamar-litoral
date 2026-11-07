"""Audit holiday sensitivity, September coverage and source discrepancies."""
import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path

import pandas as pd

from audit_candidate_calendar_position import september
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none, diagnostic_dms

# National Monday–Friday holidays from the Gob.cl calendars cited in RONDA_11.md.
HOLIDAYS = {
    2024: '01-01 03-29 05-01 05-21 06-20 07-16 08-15 09-18 09-19 09-20 10-31 11-01 12-25',
    2025: '01-01 04-18 05-01 05-21 06-20 07-16 08-15 09-18 09-19 10-31 12-08 12-25',
}
BOX = {'south': [-34, -32], 'west': [-73, -71]}


def holiday_audit(year, counts):
    holidays = {date.fromisoformat(f'{year}-{day}') for day in HOLIDAYS[year].split()}
    results = {}
    for day in sorted(holidays):
        if day.weekday() not in range(1, 5) or day.month == 9:
            continue
        next_business = day + timedelta(days=1)
        while next_business in holidays or next_business.weekday() >= 5:
            next_business += timedelta(days=1)
        next_recording_weekday = next_business
        while next_recording_weekday in holidays or next_recording_weekday.weekday() not in range(1, 5):
            next_recording_weekday += timedelta(days=1)
        results[day.isoformat()] = {
            'keys_on_holiday': counts[day],
            'next_monday_friday_nonholiday': next_business.isoformat(),
            'keys_on_next_monday_friday_nonholiday': counts[next_business],
            'next_tuesday_friday_nonholiday': next_recording_weekday.isoformat(),
            'keys_on_next_tuesday_friday_nonholiday': counts[next_recording_weekday],
            'keys_one_calendar_day_after': counts[day + timedelta(days=1)],
        }
    return results


def component_changes(generic, start):
    before, after = [abs(float(value)) for value in (generic, start)]
    degree_before = f'{int(before // 10000):03d}'
    degree_after = f'{int(after // 10000):03d}'
    return {
        'degree_digit_positions_changed': [
            name for name, a, b in zip(('hundreds', 'tens', 'units'), degree_before, degree_after)
            if a != b
        ],
        'minute_or_second_changed': abs(before % 10000 - after % 10000) > 1e-8,
    }


def position_conflicts(rows, gear):
    generic_fields = ['LATITUD', 'LONGITUD']
    start_fields = (['LATITUD_INI_VIRADO', 'LONGITUD_INI_VIRADO'] if gear == 'enmalle'
                    else ['LATITUD_INICIO_CALADO', 'LONGITUD_INICIO_CALADO'])
    generic = rows[generic_fields].apply(pd.to_numeric, errors='coerce')
    start = rows[start_fields].apply(pd.to_numeric, errors='coerce')
    start.columns = generic_fields
    different = generic.notna().all(axis=1) & start.notna().all(axis=1) & ~generic.eq(start).all(axis=1)
    patterns = Counter()
    for idx in rows.index[different]:
        def box_state(pair):
            lat, lon = [diagnostic_dms(str(v), limit) for v, limit in zip(pair, (90, 180))]
            if lat is None or lon is None:
                return 'undecodable'
            inside = BOX['south'][0] <= lat <= BOX['south'][1] and BOX['west'][0] <= lon <= BOX['west'][1]
            return 'inside' if inside else 'outside'

        before, after = generic.loc[idx], start.loc[idx]
        pattern = {
            'generic_box_state': box_state(before),
            'start_box_state': box_state(after),
            'latitude_changes': component_changes(before.LATITUD, after.LATITUD),
            'longitude_changes': component_changes(before.LONGITUD, after.LONGITUD),
        }
        patterns[json.dumps(pattern, sort_keys=True)] += 1
    return {
        'conflicting_rows': int(different.sum()),
        'keys_to_quarantine_for_position_conflict': len(rows.loc[different, TRIP].drop_duplicates()),
        'anonymous_patterns': [
            {'rows': count, **json.loads(pattern)} for pattern, count in sorted(patterns.items())
        ],
    }


def audit(raw_dir):
    results, day_counts = [], defaultdict(Counter)
    for year, gear, digest, source in strata(raw_dir, full_tables=True):
        selected = source[source.PUERTO_RECALADA.eq('560') & source.ESPECIE_OBJETIVO.eq('1')]
        grouped = selected.groupby(TRIP)
        blank = Counter({'rows': 0, 'keys_with_hake_row': 0, 'keys_with_positive_hake_row': 0,
                         'keys_without_hake_row': 0, 'keys_with_only_blank_species_rows': 0})
        for _, group in grouped:
            end = date_or_none(group.FECHA_HORA_RECALADA.iloc[0])
            if end is None or end.year != year:
                raise ValueError('Unexpected recalada date in candidate key')
            day_counts[year][end.date()] += 1
            blank_rows = group.COD_ESPECIE.eq('')
            if blank_rows.any():
                hake = group[group.COD_ESPECIE.eq('1')]
                blank['rows'] += int(blank_rows.sum())
                blank['keys_with_hake_row'] += int(not hake.empty)
                blank['keys_with_positive_hake_row'] += int(pd.to_numeric(hake.PESO, errors='coerce').gt(0).any())
                blank['keys_without_hake_row'] += int(hake.empty)
                blank['keys_with_only_blank_species_rows'] += int(blank_rows.all())
        september_counts = september(source, year)
        for counts in september_counts.values():
            counts['unparsed_full_table_dates'] = counts.pop('unparsed_port_dates')
        results.append({
            'year': year, 'gear': gear, 'source_zip_sha256': digest, 'full_table_rows': len(source),
            'candidate_keys': grouped.ngroups, 'september_all_ports': september_counts,
            'blank_species_candidate_keys': dict(blank),
            'position_conflicts': position_conflicts(selected, gear),
        })
    return {
        'schema_version': 'portales_candidate_calendar_followup_v1',
        'coordinate_box_diagnostic_only': BOX,
        'strata': results,
        'holidays_by_recorded_recalada': {year: holiday_audit(year, c) for year, c in sorted(day_counts.items())},
        'evaluation_ready': False, 'training_ready': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.raw_dir), indent=2, allow_nan=False) + '\n')
