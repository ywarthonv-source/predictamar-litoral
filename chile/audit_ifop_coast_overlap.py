"""Count row-level agreement of two recorded coordinate pairs with a coarse coast."""
from collections import Counter
from pathlib import Path
import sys

from audit_candidate_coverage import strata
from audit_ifop_artisanal import diagnostic_dms
from audit_ifop_geography import coast_reference, point_check

land, coast, project, _, _ = coast_reference(Path(sys.argv[2]))
for year, gear, _, rows in strata(Path(sys.argv[1])):
    phase = 'INI_VIRADO' if gear == 'enmalle' else 'INICIO_CALADO'
    pairs = {'generic': ['LATITUD', 'LONGITUD'],
             'initial': [f'LATITUD_{phase}', f'LONGITUD_{phase}']}
    for name, fields in pairs.items():
        counts = Counter()
        for lat, lon in rows[fields].itertuples(index=False, name=None):
            y, x = diagnostic_dms(lat, 90), diagnostic_dms(lon, 180)
            if y is None or x is None:
                counts['undecodable'] += 1
                continue
            inside = -34 <= y <= -32 and -73 <= x <= -71
            on_land, distance = point_check(x, y, land, coast, project)
            status = ('unknown' if on_land is None else 'water' if not on_land
                      else 'land_gt5km' if distance > 5 else 'land_le5km')
            counts['inside' if inside else 'outside', status] += 1
        print(year, gear, name, len(rows), dict(sorted(counts.items())))
