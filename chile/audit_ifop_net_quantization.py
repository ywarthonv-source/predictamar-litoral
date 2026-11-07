"""Aggregate net-length quantization and month sensitivity, with no identifiers."""
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
    key = TRIP + ['PUERTO_RECALADA']
    eligible = hake[valid & hake.PUERTO_RECALADA.ne('') & ~hake.duplicated(key, keep=False)]
    portales = eligible[eligible.PUERTO_RECALADA.eq('560')]
    print(year, 'Portales keys with port / without port', len(portales),
          int((valid & hake.PUERTO_RECALADA.eq('560') & ~hake.duplicated(TRIP, keep=False)).sum()))
    for name, group in [('all', eligible), ('Portales', portales)]:
        net = group.net
        fits = (net - (net / 40.5).round() * 40.5).abs().le(0.5)
        panels = pd.to_numeric(group.NUMERO_PANIOS, errors='coerce')
        has_panels = np.isfinite(panels) & panels.gt(0)
        print(name, 'keys, distinct lengths, fits, positive panels, fits observed panels',
              len(group), net.nunique(), int(fits.sum()), int(has_panels.sum()),
              int((has_panels & (net - panels * 40.5).abs().le(0.5)).sum()))
        print('exceptions', net[~fits].value_counts().sort_index().to_dict())
        print("most frequent implied lengths per panel", (net[has_panels] / panels[has_panels]).round(2).value_counts().head(8).to_dict())
    log_kg = np.log(portales.kg)
    log_net = np.log(portales.net)
    print('variance log kg, net, ratio; covariance',
          log_kg.var(), log_net.var(), (log_kg-log_net).var(), log_kg.cov(log_net))
    mismatch = portales[(portales.net - pd.to_numeric(portales.NUMERO_PANIOS)*40.5).abs().gt(0.5)]
    print('Portales mismatched length and panels', mismatch.groupby(['net', 'NUMERO_PANIOS']).size().to_dict())
    implied = eligible.net / pd.to_numeric(eligible.NUMERO_PANIOS)
    print('implied panel lengths rounded to metres', implied.round().value_counts().sort_index().to_dict())
    panels = pd.to_numeric(eligible.NUMERO_PANIOS, errors='coerce')
    modules = (40.5, 42, 45, 48, 55, 65)
    matches = pd.DataFrame({
        module: (eligible.net - panels * module).abs().le(0.5) for module in modules
    })
    print('observed panels matching each module', matches.sum().to_dict())
    print('union and overlap', int(matches.any(axis=1).sum()),
          int(matches.sum(axis=1).gt(1).sum()))
    for port, group in matches.groupby(eligible.PUERTO_RECALADA):
        counts = group.sum()
        best = counts.max()
        dominant = counts.index[counts.eq(best)].tolist() if best else []
        print('port, keys, dominant tested modules, matching keys', port, len(group), dominant, int(best))
    book = verified_member(root/f'gestion_{year}_anexos.zip', root/str(year), 'Descripción de Campos.xls')
    sheet = pd.read_excel(book, sheet_name='Bitácora Enmalle', header=None)
    print('dictionary', [(i+1, r.dropna().tolist()) for i,r in sheet.iterrows()
                         if r.iloc[0] in ('LONGITUD_RED','NUMERO_PANIOS')])

    if year != 2025:
        continue
    dates = hake.FECHA_HORA_RECALADA.map(date_or_none)
    semester = hake[dates.dt.year.eq(year) & dates.dt.month.le(6)]
    selected = semester[valid.reindex(semester.index) & semester.PUERTO_RECALADA.ne('')
                        & ~semester.duplicated(key, keep=False)]
    print('semester eligible rows with full-year key conflict', len(selected.index.difference(eligible.index)))
    for name, group in [('all', selected),
                        ('without_curanipe', selected[selected.PUERTO_RECALADA.ne(curanipe)])]:
        months = dates.loc[group.index].dt.month
        retained = group[~months.isin([2, 3])]
        print(name, 'without Feb/Mar', len(retained), round(1000*retained.kg.sum()/retained.net.sum(), 2))
        print('monthly ratios', {m: round(1000*g.kg.sum()/g.net.sum(), 2)
                                 for m,g in group.groupby(months)})


