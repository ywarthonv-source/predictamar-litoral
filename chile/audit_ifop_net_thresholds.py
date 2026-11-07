"""Count descriptive net thresholds without assigning compliance."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP

for year, gear, _, rows in strata(Path(sys.argv[1]), full_tables=True):
    if gear != 'enmalle':
        continue
    hake = rows[rows.ESPECIE_OBJETIVO.eq('1') & rows.COD_ESPECIE.eq('1')]
    weight = pd.to_numeric(hake.PESO, errors='coerce')
    net = pd.to_numeric(hake.LONGITUD_RED, errors='coerce')
    key = TRIP + ['PUERTO_RECALADA']
    keep = (weight.between(0.2, 14000) & np.isfinite(net) & net.gt(0)
            & hake.PUERTO_RECALADA.ne('') & ~hake.duplicated(key, keep=False))
    selected = hake.loc[keep, ['PUERTO_RECALADA', 'NUMERO_PANIOS']].copy()
    selected['net'] = net[keep]
    selected['panels'] = pd.to_numeric(selected.NUMERO_PANIOS, errors='coerce')
    for label, group in [('all', selected),
                         ('Portales', selected[selected.PUERTO_RECALADA.eq('560')])]:
        print(year, label, 'keys, panels 25 / 26–35 / >35, lengths >1300 / >1800',
              len(group), int(group.panels.eq(25).sum()), int(group.panels.between(26, 35).sum()),
              int(group.panels.gt(35).sum()), int(group.net.gt(1300).sum()), int(group.net.gt(1800).sum()))
    over = selected[selected.net.gt(1800)]
    print('port and panel count frequencies', over.groupby(['PUERTO_RECALADA', 'panels'], dropna=False).size().to_dict())
    print('lengths >1300 omitted by restricting to off-grid lengths',
          int((selected.net.gt(1300) & (selected.net - (selected.net / 40.5).round()*40.5).abs().le(0.5)).sum()))
    print('size columns', [c for c in rows if 'ESLORA' in c or 'CATEGOR' in c])
