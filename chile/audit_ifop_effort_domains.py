"""Compare diagnostic enmalle ratios without inferring official effort semantics."""
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
    dates = rows.FECHA_HORA_RECALADA.map(date_or_none)
    window = dates.dt.year.eq(year)
    if year == 2025:
        window &= dates.dt.month.le(6)
    hake = rows[window & rows.ESPECIE_OBJETIVO.eq('1') & rows.COD_ESPECIE.eq('1')]
    weight = pd.to_numeric(hake.PESO, errors='coerce')
    effort = pd.to_numeric(hake.LONGITUD_RED, errors='coerce')
    key = TRIP + ['PUERTO_RECALADA']
    keep = (weight.between(0.2, 14000) & np.isfinite(effort) & effort.gt(0)
            & ~hake.duplicated(key, keep=False))
    for domain, scope in [('Portales', hake.PUERTO_RECALADA.eq('560')),
                          ('todos', hake.PUERTO_RECALADA.ne('')),
                          ('sin Curanipe', ~hake.PUERTO_RECALADA.isin(['', curanipe]))]:
        selected = keep & scope
        kg, metres = weight[selected], effort[selected]
        if metres.empty:
            raise ValueError(f'Empty domain: {year} {domain}')
        ratio = 1000 * kg / metres
        percentiles = metres.quantile([0.05, 0.5, 0.95])
        print(year, domain, len(ratio), round(1000*kg.sum()/metres.sum(), 2),
              round(ratio.mean(), 2), round(ratio.median(), 2),
              percentiles.round(2).tolist(), int(metres.le(percentiles.iloc[0]).sum()))
