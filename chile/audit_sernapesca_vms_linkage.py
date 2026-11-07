"""Check two public Sernapesca VMS samples for a documented join to IFOP."""
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none


SAMPLES = {
    2024: ('20240619', '2024/06', 'Radio Call Sign (RC)', 'Location date',
           '%d/%m/%Y %H:%M:%S', 'Latitude', 'Longitude'),
    2025: ('20250618', '2025/08', 'call_sign', 'loc_date',
           '%Y-%m-%d %H:%M:%S', 'latitude', 'longitude'),
}


def audit(ifop_root, sample_root):
    candidates = {}
    for year, gear, _, rows in strata(ifop_root):
        candidates.setdefault(year, {})[gear] = rows[TRIP].drop_duplicates()
    results = {}
    for year, (label, upload, identifier, timestamp, fmt, lat, lon) in SAMPLES.items():
        path = sample_root / f'vms_{year}.csv'
        frame = pd.read_csv(path, sep=';', dtype=str, encoding='utf-8-sig', keep_default_na=False)
        days = pd.to_datetime(frame[timestamp], format=fmt, errors='raise').dt.date
        latitude = pd.to_numeric(frame[lat].str.rstrip('°'), errors='raise')
        longitude = pd.to_numeric(frame[lon].str.rstrip('°'), errors='raise')
        inside = latitude.between(-34, -32) & longitude.between(-73, -71)
        id_fields = [identifier] + (['internal_ref'] if 'internal_ref' in frame else [])
        ids = {col: set(frame[col].str.strip().str.upper()) - {''} for col in id_fields}
        strata_results = {}
        for gear, trips in candidates[year].items():
            boat_codes = set(trips.COD_BARCO.str.strip().str.upper()) - {''}
            returns = trips.FECHA_HORA_RECALADA.map(date_or_none)
            strata_results[gear] = {
                'candidate_keys': len(trips),
                'candidate_boat_codes': len(boat_codes),
                'keys_with_recorded_return_on_report_label_day': int(
                    returns.dt.strftime('%Y%m%d').eq(label).sum()),
                'exact_code_strings_shared': {col: len(boat_codes & v) for col, v in ids.items()},
            }
        results[year] = {
            'url': f'https://www.sernapesca.cl/app/uploads/{upload}/report_31_{label}_flota_artesanal.csv',
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'columns': list(frame.columns),
            'position_rows': len(frame),
            'first_recorded_date': min(days).isoformat(),
            'last_recorded_date': max(days).isoformat(),
            'rows_in_diagnostic_box': int(inside.sum()),
            'unique_nonblank_identifier_strings': {col: len(v) for col, v in ids.items()},
            'by_gear': strata_results,
        }
    return results


if __name__ == '__main__':
    print(json.dumps(audit(*map(Path, sys.argv[1:])), ensure_ascii=False, indent=2))
