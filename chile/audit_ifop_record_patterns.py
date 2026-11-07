from pathlib import Path
import sys
import pandas as pd
from audit_candidate_coverage import strata

def pair_state(raw, numeric):
    blank = raw.apply(lambda col: col.str.strip().eq(''))
    state = blank.sum(axis=1).map({0: 'invalid', 1: 'partial', 2: 'blank'})
    invalid = (~blank & numeric.isna()).any(axis=1)
    return state.mask(invalid, 'invalid').mask(numeric.notna().all(axis=1), 'complete')


for year, gear, _, rows in strata(Path(sys.argv[1]), full_tables=True):
    phase = 'VIRADO' if gear == 'enmalle' else 'CALADO'
    start = [f'{axis}_INI{"" if gear == "enmalle" else "CIO"}_{phase}'
             for axis in ('LATITUD', 'LONGITUD')]
    end = [f'{axis}_FIN_{phase}' for axis in ('LATITUD', 'LONGITUD')]
    hours = [f'FECHA_HORA_{p}_{o}' for p in ('INI','FIN') for o in ('CALADO','VIRADO')]
    generic_raw = rows[['LATITUD', 'LONGITUD']]
    initial_raw = rows[start].set_axis(generic_raw.columns, axis=1)
    generic = generic_raw.apply(pd.to_numeric, errors='coerce')
    initial = initial_raw.apply(pd.to_numeric, errors='coerce')
    comparable = generic.notna().all(axis=1) & initial.notna().all(axis=1)
    position = generic.eq(initial).all(axis=1).map({True:'equal', False:'different'}).where(comparable, 'not_comparable')
    flags = pd.DataFrame({'portales':rows.PUERTO_RECALADA.eq('560'),
                          'time':rows[hours].apply(lambda col:col.str.strip().ne('')).any(axis=1),
                          'end':rows[end].apply(lambda col:col.str.strip().ne('')).any(axis=1),
                          'generic':pair_state(generic_raw, generic),
                          'initial':pair_state(initial_raw, initial),
                          'pair':position})
    print(year, gear, len(rows))
    print(flags.value_counts(sort=False).to_string())
