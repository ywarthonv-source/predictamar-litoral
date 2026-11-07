from collections import Counter
from pathlib import Path
import re
import sys
import pandas as pd
from audit_candidate_coverage import strata
from audit_ifop_artisanal import diagnostic_dms
from audit_ifop_alignment_inputs import verified_member

root = Path(sys.argv[1])
for year, gear, _, rows in strata(root, full_tables=True):
    local = rows[rows.PUERTO_RECALADA.eq('560') & rows.ESPECIE_OBJETIVO.eq('1')]
    print(year, gear, 'boat_code_shapes', sorted(Counter(
        (len(v), bool(re.fullmatch('[0-9]+', v))) for v in local.COD_BARCO).items()))
    book = verified_member(root/f'gestion_{year}_anexos.zip', root/str(year), 'Descripción de Campos.xls')
    sheet = pd.read_excel(book, sheet_name=f'Bitácora {gear.capitalize()}', header=None)
    print('dictionary', [(i+1, row.dropna().tolist()) for i,row in sheet.iterrows() if row.iloc[0]=='COD_BARCO'])
    start = ['LATITUD_INI_VIRADO','LONGITUD_INI_VIRADO'] if gear=='enmalle' else ['LATITUD_INICIO_CALADO','LONGITUD_INICIO_CALADO']
    for label, fields in [('generic',['LATITUD','LONGITUD']), ('initial',start)]:
        counts = Counter()
        for lat,lon in local[fields].itertuples(index=False,name=None):
            y,x = diagnostic_dms(lat,90),diagnostic_dms(lon,180)
            if y is None or x is None:
                counts['undecodable'] += 1
            elif y == 0 or x == 0:
                counts['zero_component'] += 1
            elif -34 <= y <= -32 and -73 <= x <= -71:
                counts['inside_diagnostic_box'] += 1
            else:
                counts['outside_diagnostic_box'] += 1
        print(label, dict(counts))
