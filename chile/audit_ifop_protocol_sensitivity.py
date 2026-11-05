from pathlib import Path
import sys
import numpy as np
import pandas as pd
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP

for year, gear, _, rows in strata(Path(sys.argv[1]), full_tables=True):
    local = rows[rows.PUERTO_RECALADA.eq('560') & rows.ESPECIE_OBJETIVO.eq('1')]
    hake = local[local.COD_ESPECIE.eq('1')]
    weight = pd.to_numeric(hake.PESO, errors='coerce')
    lower = 0.2 if gear == 'enmalle' else 0.5
    field = 'LONGITUD_RED' if gear == 'enmalle' else 'NUMERO_DE_ANZUELOS'
    effort = pd.to_numeric(hake[field], errors='coerce')
    eligible = weight.between(lower, 14000) & np.isfinite(effort) & effort.gt(0) & ~hake.duplicated(TRIP, keep=False)
    fallback = pd.to_numeric(hake.CAPTURA_RETENIDA, errors="coerce") + pd.to_numeric(hake.VOLUMEN_DESCARTE, errors="coerce")
    print("zero fallback within range", int((weight.eq(0) & fallback.between(lower, 14000)).sum()), "positive in-range excluded", int((weight.between(lower, 14000) & ~eligible).sum()))
    print(year, gear, len(local), len(hake), int(weight.isna().sum()), int(weight.eq(0).sum()),
          int((weight.gt(0) & weight.lt(lower)).sum()), int(weight.gt(14000).sum()),
          int(eligible.sum()), round(1000 * weight[eligible].sum() / effort[eligible].sum(), 3),
          [c for c in rows if 'ESLORA' in c])
