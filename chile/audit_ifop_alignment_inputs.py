"""Check date anchors and ambiguous soak values in IFOP source tables."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

import pandas as pd

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, table

DATE_FIELDS = ['FECHA_HORA_ZARPE', 'FECHA_HORA_RECALADA', 'FECHA_LANCE']
DICTIONARY_FIELDS = DATE_FIELDS + ['LATITUD', 'LONGITUD']


def verified_member(archive, root, name):
    """Use an existing extraction only after matching its bytes to the ZIP."""
    path = next(root.rglob(name))
    with zipfile.ZipFile(archive) as source:
        members = [m for m in source.namelist() if Path(m).name == name]
        if len(members) != 1:
            raise ValueError('Ambiguous archive member: '+name)
        with source.open(members[0]) as member, path.open('rb') as local:
            if hashlib.file_digest(member, 'sha256').digest() != hashlib.file_digest(local, 'sha256').digest():
                raise ValueError('Extracted source differs from archive: '+name)
    return path


def audit(raw_dir, check_access_parser=False):
    results = []
    for year, (digest, _) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        with archive.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
                raise ValueError('Unexpected ZIP version')
        root = raw_dir/str(year)
        db = verified_member(archive, root, f'DATOS {year} ARTESANAL DCS-PDA.accdb')
        dictionary = verified_member(archive, root, 'Descripción de Campos.xls')
        independent = None
        if check_access_parser:
            from access_parser import AccessParser
            independent = AccessParser(str(db))
        for gear, name, sheet in [
            ('enmalle', f'BITACORAS ENMALLE Centro Sur {year}', 'Bitácora Enmalle'),
            ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}', 'Bitácora Espinel'),
        ]:
            source = table(db, name)
            values = pd.to_numeric(source.HORAS_REPOSO, errors='coerce').dropna()
            integers = [int(v) for v in values if v >= 0 and v == int(v)]
            overflow = Counter(v for v in integers if v % 100 >= 60)
            suffixes = Counter(v % 100 for v in integers)
            selected = source[source.PUERTO_RECALADA.eq('560') & source.ESPECIE_OBJETIVO.eq('1')]
            counts = Counter()
            for _, rows in selected.groupby(TRIP, dropna=False):
                counts['candidate_keys'] += 1
                if rows.FECHA_LANCE.nunique(dropna=False) != 1:
                    counts['conflicting_lance_timestamps'] += 1
                    continue
                if rows[['LATITUD', 'LONGITUD']].nunique(dropna=False).max() != 1:
                    counts['conflicting_reported_positions'] += 1
                start, end, lance = [date_or_none(rows.iloc[0][f]) for f in DATE_FIELDS]
                if None in (start, end, lance):
                    counts['unparseable_anchor'] += 1
                    continue
                counts['parsed_keys'] += 1
                counts['lance_outside_reported_trip'] += int(not start <= lance <= end)
                counts['different_departure_return_calendar_days'] += int(start.date() != end.date())
                counts['lance_day_differs_from_departure'] += int(lance.date() != start.date())
                counts['lance_day_differs_from_return'] += int(lance.date() != end.date())
                counts['lance_time_equals_departure'] += int(lance == start)
                counts['lance_time_equals_return'] += int(lance == end)
            fields = pd.read_excel(dictionary, sheet_name=sheet, header=None)
            dictionary_rows = {str(row.iloc[0]):int(i)+1 for i,row in fields.iterrows()
                               if row.iloc[0] in DICTIONARY_FIELDS}
            if set(dictionary_rows) != set(DICTIONARY_FIELDS):
                raise ValueError('Dictionary fields differ')
            for key in ['conflicting_lance_timestamps', 'conflicting_reported_positions', 'unparseable_anchor']:
                counts.setdefault(key, 0)
            result = {
                'year': year, 'gear': gear, 'source_sha256': digest,
                'source_rows': len(source),
                'reported_soak_numeric_rows': len(values),
                'overflow_full_value_frequencies': dict(sorted(overflow.items())),
                'suffix_contrasts': {str(k):suffixes[k] for k in [0,15,25,30,45,50,75]},
                'suffix_01_to_09_rows': sum(suffixes[k] for k in range(1,10)),
                'full_values_1_to_9_rows': sum(1 <= v <= 9 for v in integers),
                'dictionary_sheet': sheet, 'dictionary_rows_1based': dictionary_rows,
                'candidate_date_checks': dict(sorted(counts.items())),
            }
            if independent is not None:
                parsed = pd.DataFrame(independent.parse_table(name))
                mask = pd.to_numeric(parsed.PUERTO_RECALADA, errors='coerce').eq(560)
                mask &= pd.to_numeric(parsed.ESPECIE_OBJETIVO, errors='coerce').eq(1)
                local = parsed[mask].drop_duplicates(TRIP+['FECHA_LANCE'])
                result['access_parser_cross_check'] = {
                    'source_rows': len(parsed), 'unique_candidate_lance_keys': len(local),
                    'lance_timestamp_equals_return': int(local.FECHA_LANCE.eq(local.FECHA_HORA_RECALADA).sum()),
                }
            results.append(result)
    return {'schema_version':'ifop_alignment_inputs_v1','results':results,
            'training_ready':False,'timezone_validated':False,'position_origin_validated':False,
            'limitations':['date checks compare recorded clock and calendar fields without assuming timezone',
                           'candidate keys do not certify fishing trips or lances',
                           'overflow frequencies do not identify sentinels without a source rule',
                           'no individual dates, positions, identities or rows published']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-access-parser', action='store_true')
    args = parser.parse_args()
    result = audit(args.raw_dir, args.check_access_parser)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
