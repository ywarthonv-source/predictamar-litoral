"""Aggregate declared net lengths by boat and compare calendar anchors."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_alignment_inputs import verified_member
from audit_ifop_artisanal import TRIP, date_or_none, table

root = Path(sys.argv[1])
for year, gear, _, rows in strata(root, full_tables=True):
    if gear != 'enmalle':
        continue
    catalog = verified_member(root/f'gestion_{year}_anexos.zip', root/str(year),
                              'Códigos BASE DATOS_mod.accdb')
    ports = table(catalog, 'Maestro Puertos')
    curanipe, = ports.loc[ports.NOMBRE.str.strip().str.casefold().eq('curanipe'), 'CODIGO']
    hake = rows[rows.ESPECIE_OBJETIVO.eq('1') & rows.COD_ESPECIE.eq('1')].copy()
    hake['kg'] = pd.to_numeric(hake.PESO, errors='coerce')
    hake['net'] = pd.to_numeric(hake.LONGITUD_RED, errors='coerce')
    valid = hake.kg.between(0.2, 14000) & np.isfinite(hake.net) & hake.net.gt(0)
    local = hake[valid & hake.PUERTO_RECALADA.eq('560') & ~hake.duplicated(TRIP, keep=False)]
    boats = local.groupby('COD_BARCO').net
    modes = boats.agg(lambda x: set(x.mode()))
    nonmodal = sum(row.net not in modes[row.COD_BARCO] for row in local.itertuples())
    print(year, 'Portales frequencies', local.net.value_counts().sort_index().to_dict())
    print('boats, single trip, constant repeaters, variable repeaters, tied modes, outside modes',
          boats.ngroups, int(boats.size().eq(1).sum()),
          int((boats.size().gt(1) & boats.nunique().eq(1)).sum()),
          int(boats.nunique().gt(1).sum()), int(modes.map(len).gt(1).sum()), nonmodal)

    for field in ('FECHA_HORA_RECALADA', 'FECHA_HORA_ZARPE', 'FECHA_LANCE'):
        dates = hake[field].map(date_or_none)
        window = hake[dates.dt.year.eq(year) & dates.dt.month.le(6)].copy()
        valid_window = (valid.reindex(window.index)
                        & ~window.duplicated(TRIP + ['PUERTO_RECALADA'], keep=False))
        eligible = window[valid_window & window.PUERTO_RECALADA.ne('')]
        print(field, 'unparsed dates', int(dates.isna().sum()))
        for name, group in [('all', eligible),
                            ('without_curanipe', eligible[eligible.PUERTO_RECALADA.ne(curanipe)])]:
            ratio = 1000 * group.kg / group.net
            months = dates.loc[group.index].dt.month.value_counts().reindex(range(1,7), fill_value=0)
            print(name, len(group), months.tolist(),
                  round(1000 * group.kg.sum() / group.net.sum(), 2), round(ratio.mean(), 2))
