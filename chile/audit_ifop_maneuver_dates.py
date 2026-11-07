"""Compare recorded dates where a maneuver timestamp is present."""
from pathlib import Path
import sys

import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_artisanal import date_or_none

for year, gear, _, rows in strata(Path(sys.argv[1]), full_tables=True):
    phase = 'VIRADO' if gear == 'enmalle' else 'CALADO'
    field = f'FECHA_HORA_INI_{phase}'
    anchors = rows[[field, 'FECHA_LANCE', 'FECHA_HORA_RECALADA']].apply(
        lambda col: pd.to_datetime(col.map(date_or_none)))
    complete = anchors.dropna()
    if complete.empty:
        continue
    days = complete.apply(lambda col: col.dt.normalize())
    print(year, gear, 'maneuver nonempty, parsed triple, lance same day as maneuver, '
          'recalada same day as maneuver, both same day, lance equals recalada exactly',
          int(rows[field].str.strip().ne('').sum()), len(complete),
          int(days.FECHA_LANCE.eq(days[field]).sum()),
          int(days.FECHA_HORA_RECALADA.eq(days[field]).sum()),
          int((days.FECHA_LANCE.eq(days[field]) & days.FECHA_HORA_RECALADA.eq(days[field])).sum()),
          int(complete.FECHA_LANCE.eq(complete.FECHA_HORA_RECALADA).sum()))
