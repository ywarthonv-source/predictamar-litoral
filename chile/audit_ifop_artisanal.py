"""Inspect private copies of public IFOP artisanal annexes; emit aggregates only.

Requires mdbtools and pandas. Source archives must already be downloaded.
Candidate trip keys and diagnostic coordinates are not certified fishing units.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import zipfile

import pandas as pd

SOURCES = {
    2025: ('c1e36a8987af6442ede3880204e2f266590a555442b5fe017c9c17c59f4f4d74',
           'https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_I_Anexos.zip'),
    2024: ('b297d0f67f0a3fbd74c0d439cfb20892144360a480b33fc40d0f7ccc25cee029',
           'https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2025/P-581216_Informe_Gestion_anexos.zip'),
}
TRIP = ['COD_BARCO', 'FECHA_HORA_ZARPE', 'FECHA_HORA_RECALADA']
LANCE = TRIP + ['NUMERO_LANCE_EX', 'FECHA_LANCE']


def table(db, name):
    raw = subprocess.check_output(['mdb-export', str(db), name])
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('Incomplete or malformed export: '+name)
    return pd.DataFrame(rows[1:], columns=rows[0])


def date_or_none(value):
    try:
        return datetime.strptime(value, '%m/%d/%y %H:%M:%S')
    except ValueError:
        return None


def diagnostic_dms(value, limit):
    try:
        number = abs(float(value))
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    deg = int(number // 10000)
    minute = int(number % 10000 // 100)
    second = number % 100
    if deg > limit or minute >= 60 or second >= 60:
        return None
    return -(deg + minute/60 + second/3600)


def summary(data, gear):
    port = data[data.PUERTO_RECALADA.eq('560')].copy()
    selected = port[port.ESPECIE_OBJETIVO.eq('1')].copy()
    effort_name = 'LONGITUD_RED' if gear == 'enmalle' else 'NUMERO_DE_ANZUELOS'
    weight = pd.to_numeric(selected.PESO, errors='coerce')
    effort = pd.to_numeric(selected[effort_name], errors='coerce')
    dates = selected.FECHA_LANCE.map(date_or_none)
    lat = selected.LATITUD.map(lambda v: diagnostic_dms(v, 90))
    lon = selected.LONGITUD.map(lambda v: diagnostic_dms(v, 180))
    groups = selected.groupby(TRIP, dropna=False)
    species = groups.COD_ESPECIE.agg(set)
    zero_only = selected.COD_ESPECIE.eq('999') & weight.eq(0)
    positive_hake = selected.COD_ESPECIE.eq('1') & weight.gt(0)
    valid_dates = dates.dropna()
    nonzero_other = selected.COD_ESPECIE.ne('1') & selected.COD_ESPECIE.ne('999') & weight.gt(0)
    return {
        'all_exported_rows': len(data), 'portales_all_rows': len(port),
        'portales_hake_target_rows': len(selected),
        'candidate_trip_count': len(species),
        'candidate_lance_count': len(selected[LANCE].drop_duplicates()),
        'missing_trip_key_rows': int(selected[TRIP].eq('').any(axis=1).sum()),
        'duplicate_candidate_lance_species_rows': int(selected.duplicated(LANCE+['COD_ESPECIE']).sum()),
        'species_code_rows': selected.COD_ESPECIE.value_counts().to_dict(),
        'positive_hake_rows': int(positive_hake.sum()),
        'explicit_hake_zero_rows': int((selected.COD_ESPECIE.eq('1') & weight.eq(0)).sum()),
        'explicit_no_capture_code999_zero_rows': int(zero_only.sum()),
        'code999_positive_weight_rows': int((selected.COD_ESPECIE.eq('999') & weight.gt(0)).sum()),
        'code999_missing_weight_rows': int((selected.COD_ESPECIE.eq('999') & weight.isna()).sum()),
        'candidate_trips_only_code999': int(species.map(lambda s: s == {'999'}).sum()),
        'candidate_trips_without_hake_row_not_imputed_zero': int(species.map(lambda s: '1' not in s).sum()),
        'other_species_positive_rows': int(nonzero_other.sum()),
        'missing_weight_rows': int(weight.isna().sum()),
        'effort_field': effort_name,
        'positive_effort_rows': int(effort.gt(0).sum()),
        'missing_effort_rows': int(effort.isna().sum()),
        'effort_conflicting_candidate_trips': int(groups[effort_name].nunique(dropna=False).gt(1).sum()),
        'position_conflicting_candidate_trips': int(groups[['LATITUD', 'LONGITUD']].nunique(dropna=False).max(axis=1).gt(1).sum()),
        'positive_hake_with_positive_effort_rows': int((positive_hake & effort.gt(0)).sum()),
        'code999_zero_with_positive_effort_rows': int((zero_only & effort.gt(0)).sum()),
        'reported_caladas_counts_row_weighted': selected.N_CALADAS.value_counts().to_dict(),
        'unparseable_lance_date_rows': int(dates.isna().sum()),
        'lance_date_min': valid_dates.min().isoformat() if len(valid_dates) else None,
        'lance_date_max': valid_dates.max().isoformat() if len(valid_dates) else None,
        'lance_year_counts_row_weighted': valid_dates.map(lambda d: str(d.year)).value_counts().to_dict(),
        'invalid_dms_syntax_rows': int((lat.isna() | lon.isna()).sum()),
        'southwest_dms_diagnostic_range': {
            'lat': [float(lat.min()), float(lat.max())] if lat.notna().any() else None,
            'lon': [float(lon.min()), float(lon.max())] if lon.notna().any() else None},
        'retained_weight_nonempty_rows': int(selected.CAPTURA_RETENIDA.ne('').sum()),
        'discard_weight_nonempty_rows': int(selected.VOLUMEN_DESCARTE.ne('').sum()),
    }


def audit(raw_dir, independent_parser=False):
    reports = []
    for year, (expected_hash, url) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
        if digest != expected_hash:
            raise ValueError('Source version mismatch: '+str(year))
        destination = raw_dir/str(year)
        destination.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                if 'ARTESANAL' in member or 'digos BASE' in member or member.endswith('.xls'):
                    (destination/Path(member).name).write_bytes(z.read(member))
        db = destination/f'DATOS {year} ARTESANAL DCS-PDA.accdb'
        codes = destination/'Códigos BASE DATOS_mod.accdb'
        ports = table(codes, 'Maestro Puertos')
        species = table(codes, 'Maestro especies')
        portales = ports[ports.NOMBRE.str.strip().str.upper().eq('PORTALES')]
        if list(portales.CODIGO) != ['560']:
            raise ValueError('Unexpected Portales code')
        species_map = species[species.COD_ESPECIE.isin(['1', '27', '999'])]
        source = {'year': year, 'url': url, 'sha256': digest,
                  'artisanal_db_sha256': hashlib.file_digest(db.open('rb'), 'sha256').hexdigest(),
                  'portales_code': '560',
                  'species_codes': species_map[['COD_ESPECIE', 'NOMBRE_ESPECIE', 'NOMBRE_CIENTIFICO']].to_dict('records'),
                  'tables': {}}
        parser = None
        if independent_parser:
            from access_parser import AccessParser
            parser = AccessParser(str(db))
        names = subprocess.check_output(['mdb-tables', '-1', str(db)], text=True).splitlines()
        for gear in ['enmalle', 'espinel']:
            name = next(n for n in names if n.startswith('BITACORAS '+gear.upper()))
            data = table(db, name)
            info = summary(data, gear)
            info['table_name'] = name
            info['mdb_count_metadata'] = int(subprocess.check_output(['mdb-count', str(db), name], text=True))
            info['metadata_row_count_matches_export'] = info['mdb_count_metadata'] == len(data)
            if parser:
                parsed = parser.parse_table(name)
                counts = {len(v) for v in parsed.values()}
                if len(counts) != 1:
                    raise ValueError('Independent parser column lengths disagree')
                info['access_parser_rows'] = next(iter(counts))
                info['independent_parser_row_count_matches'] = next(iter(counts)) == len(data)
                if not info['independent_parser_row_count_matches']:
                    raise ValueError('Independent parsers disagree on row count')
            source['tables'][gear] = info
        reports.append(source)
        del parser
    return {'schema_version': 'public_ifop_artisanal_audit_v1',
            'method': 'mdbtools export; optional access-parser row-count cross-check',
            'sources': reports,
            'training_ready': False,
            'limitations': [
                'candidate trip/lance keys not yet certified; no labels imputed from missing species rows',
                'code999 denotes a reported no-capture trip, not proof of perfect species detection',
                'coordinates parsed diagnostically as positive DDMMSS in southwest hemisphere; require geographic validation',
                'report years and actual date ranges are checked separately',
                'net length/hooks do not alone resolve soak time, selectivity or sampling bias',
                'public download does not establish commercial reuse permission',
                'no raw identifiers, original rows, CPUE estimates or operational recommendations published']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--check-access-parser', action='store_true')
    args = p.parse_args()
    result = audit(args.raw_dir, args.check_access_parser)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
