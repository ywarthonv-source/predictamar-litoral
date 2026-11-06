"""Count exact links from Portales candidates to ancillary IFOP Access tables."""
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys

from audit_candidate_coverage import strata
from audit_ifop_alignment_inputs import verified_member
from audit_ifop_artisanal import TRIP, date_or_none, table


KEY = TRIP + ['COD_PESQUERIA']
KINDS = ('CIAMT', 'IOE', 'BIOLOGICO', 'LONGITUD', 'PRESENCIA', 'COMERCIALIZACIÓN')


def attributes(rows):
    dates, positions = defaultdict(set), defaultdict(set)
    has_date = 'FECHA_LANCE' in rows
    has_position = {'LATITUD', 'LONGITUD'}.issubset(rows)
    cols = KEY + (['FECHA_LANCE'] if has_date else []) + (['LATITUD', 'LONGITUD'] if has_position else [])
    for row in rows[cols].itertuples(index=False, name=None):
        key, values = row[:len(KEY)], row[len(KEY):]
        if has_date and (value := date_or_none(values[0])) is not None:
            dates[key].add(value.date())
        if has_position and all(values[-2:]):
            positions[key].add(values[-2:])
    return dates, positions


def keys(rows):
    return set(rows[KEY].itertuples(index=False, name=None))


def audit(root):
    output = {}
    candidates = defaultdict(dict)
    for year, gear, _, rows in strata(root):
        if rows[KEY].eq('').any(axis=None):
            raise ValueError('Missing candidate linkage field')
        candidates[year][gear] = rows

    for year, by_gear in candidates.items():
        db = verified_member(root / f'gestion_{year}_anexos.zip', root / str(year),
                             f'DATOS {year} ARTESANAL DCS-PDA.accdb')
        names = subprocess.check_output(['mdb-tables', '-1', str(db)], text=True).splitlines()
        output[year] = {}
        primary = {gear: (keys(rows), *attributes(rows)) for gear, rows in by_gear.items()}
        for kind in KINDS:
            matches = [name for name in names if kind in name]
            if not matches and year == 2024 and kind in ('PRESENCIA', 'COMERCIALIZACIÓN'):
                continue
            name, = matches
            aux = table(db, name)
            local = aux[aux.PUERTO_RECALADA.eq('560')]
            complete = local[~local[KEY].eq('').any(axis=1)]
            local_keys = keys(complete)
            other_port_keys = keys(aux.loc[~aux.PUERTO_RECALADA.eq('560'), KEY])
            dates, positions = attributes(complete)
            by_gear_result = {}
            for gear, (main_keys, main_dates, main_positions) in primary.items():
                linked = main_keys & local_keys
                by_gear_result[gear] = {
                    'candidate_keys': len(main_keys),
                    'linked_keys': len(linked),
                    'exact_key_with_other_or_blank_port': len(main_keys & other_port_keys),
                    'linked_with_parsed_lance_day': sum(bool(dates[k]) for k in linked),
                    'linked_with_lance_day_not_in_primary': sum(bool(dates[k] - main_dates[k]) for k in linked),
                    'linked_with_complete_coordinate_pair': sum(bool(positions[k]) for k in linked),
                    'linked_with_pair_not_in_primary': sum(bool(positions[k] - main_positions[k]) for k in linked),
                }
            output[year][kind] = {
                'table': name, 'rows_all_ports': len(aux), 'rows_portales': len(local),
                'portales_rows_incomplete_key': len(local) - len(complete),
                'portales_complete_keys': len(local_keys), 'by_gear': by_gear_result,
            }
    return output


if __name__ == '__main__':
    print(json.dumps(audit(Path(sys.argv[1])), ensure_ascii=False, indent=2))
