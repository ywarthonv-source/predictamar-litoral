"""Contrast recorded maneuver dates per complete enmalle trip key."""
from pathlib import Path
import sys

import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none

phases = ['FECHA_HORA_INI_CALADO', 'FECHA_HORA_INI_VIRADO']
key = TRIP + ['PUERTO_RECALADA']
for year, gear, _, source in strata(Path(sys.argv[1]), full_tables=True):
    if gear != 'enmalle':
        continue
    rows = source[source.ESPECIE_OBJETIVO.eq('1')].copy()
    rows = rows[~rows[key].eq('').any(axis=1)]
    for phase in phases:
        rows[phase] = pd.to_datetime(rows[phase].map(date_or_none))
    paired = rows.dropna(subset=phases)
    unique_pairs = paired[key + phases].drop_duplicates()
    consistent = unique_pairs[~unique_pairs.duplicated(key, keep=False)].copy()
    print(year, 'target trips, trips with both, conflicts, Portales with both',
          len(rows[key].drop_duplicates()), len(paired[key].drop_duplicates()),
          len(unique_pairs[key].drop_duplicates())-len(consistent),
          paired.loc[paired.PUERTO_RECALADA.eq('560'), key].drop_duplicates().shape[0])
    consistent['return'] = pd.to_datetime(consistent.FECHA_HORA_RECALADA.map(date_or_none))
    consistent['depart'] = pd.to_datetime(consistent.FECHA_HORA_ZARPE.map(date_or_none))
    ordered = consistent.depart.le(consistent[phases[0]]) & consistent[phases[0]].le(consistent[phases[1]])
    ordered &= consistent[phases[1]].le(consistent['return'])
    print('invalid order or missing trip timestamps', int((~ordered).sum()))
    good = consistent[ordered].copy()
    good['return_virado'] = good['return'].dt.normalize().eq(good[phases[1]].dt.normalize())
    good['calado_virado'] = good[phases[0]].dt.normalize().eq(good[phases[1]].dt.normalize())
    good['calado_return'] = good[phases[0]].dt.normalize().eq(good['return'].dt.normalize())
    good['hours'] = (good['return']-good[phases[1]]).dt.total_seconds()/3600
    for port, group in [('all', good), *good.groupby('PUERTO_RECALADA')]:
        print(port, len(group), int(group.return_virado.sum()), int(group.calado_virado.sum()),
              int(group.calado_return.sum()), group.hours.quantile([.05, .5, .95]).round(2).tolist())
