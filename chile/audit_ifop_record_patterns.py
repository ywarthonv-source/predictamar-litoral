from pathlib import Path
import sys
import pandas as pd
from audit_candidate_coverage import strata

for year, gear, _, rows in strata(Path(sys.argv[1]), full_tables=True):
    phase = 'VIRADO' if gear == 'enmalle' else 'CALADO'
    start = [f'{axis}_INI{"" if gear == "enmalle" else "CIO"}_{phase}'
             for axis in ('LATITUD', 'LONGITUD')]
    end = [f'{axis}_FIN_{phase}' for axis in ('LATITUD', 'LONGITUD')]
    hours = [f'FECHA_HORA_{p}_{o}' for p in ('INI','FIN') for o in ('CALADO','VIRADO')]
    generic = rows[['LATITUD','LONGITUD']].apply(pd.to_numeric, errors='coerce')
    initial = rows[start].apply(pd.to_numeric, errors='coerce').set_axis(generic.columns, axis=1)
    comparable = generic.notna().all(axis=1) & initial.notna().all(axis=1)
    position = generic.eq(initial).all(axis=1).map({True:'equal', False:'different'}).where(comparable, 'not_comparable')
    flags = pd.DataFrame({'portales':rows.PUERTO_RECALADA.eq('560'),
                          'time':rows[hours].apply(lambda col:col.str.strip().ne('')).any(axis=1),
                          'end':rows[end].apply(lambda col:col.str.strip().ne('')).any(axis=1),
                          'pair':position})
    print(year, gear, len(rows))
    print(flags.value_counts(sort=False).to_string())
