"""Apply the draft Portales contract in memory and publish aggregate dispositions."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

import pandas as pd

from audit_ifop_alignment_inputs import verified_member
from audit_ifop_artisanal import SOURCES, date_or_none, table
from audit_ifop_zero_activity import catch_state


def audit(raw_dir, contract):
    if contract['status'] != 'draft_inventory_only' or any(contract['readiness'].values()):
        raise ValueError('Expected draft contract with pending readiness checks')
    scope = contract['scope']
    key = contract['unit']['private_candidate_key']
    quantity = contract['reported_quantity']
    results = []
    for year in scope['seasons']:
        digest, _ = SOURCES[year]
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        with archive.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
                raise ValueError('Unexpected ZIP version')
        directory = raw_dir/str(year)
        db = verified_member(archive, directory, f'DATOS {year} ARTESANAL DCS-PDA.accdb')
        dictionary = verified_member(archive, directory, 'Descripción de Campos.xls')
        names = {
            'enmalle': f'BITACORAS ENMALLE Centro Sur {year}',
            'espinel': f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}',
        }
        for gear in scope['source_strata']:
            source = table(db, names[gear])
            dictionary_rows = pd.read_excel(dictionary, sheet_name=f'Bitácora {gear.capitalize()}', header=None)
            weight_row = dictionary_rows[dictionary_rows.iloc[:, 0].eq(quantity['weight_field'])]
            if len(weight_row) != 1 or 'kilo' not in str(weight_row.iloc[0, 1]).casefold():
                raise ValueError('PESO unit could not be reproduced from dictionary')
            selected = source.loc[(source[list(scope['filters'])] == pd.Series(scope['filters'])).all(axis=1)]
            incomplete = selected[key].eq('').any(axis=1)
            complete = selected.loc[~incomplete]
            states, dispositions, flags = Counter(), Counter(), Counter()
            assigned_ordinals = set()
            for _, group in complete.groupby(key, dropna=False):
                ordinals = set(group.index+1)
                if assigned_ordinals & ordinals or len(ordinals) != len(group):
                    raise ValueError('Duplicate source ordinal in candidate grouping')
                assigned_ordinals.update(ordinals)
                state = catch_state(group)
                states[state] += 1
                target = group[group[quantity['species_field']].eq(quantity['species_code'])]
                if state == 'conflicting_code999_positive_weight':
                    dispositions['conflicting_999_quarantined'] += 1
                elif len(target) == 0:
                    dispositions['target_quantity_unset'] += 1
                elif len(target) > 1:
                    dispositions['multiple_target_rows_quarantined'] += 1
                else:
                    weight = pd.to_numeric(target[quantity['weight_field']].iloc[0], errors='coerce')
                    if not math.isfinite(weight) or weight < 0:
                        dispositions['invalid_target_weight_quarantined'] += 1
                    else:
                        label = 'reported_positive_kg' if weight > 0 else 'reported_zero_kg_unvalidated'
                        dispositions[label] += 1
                caladas = pd.to_numeric(group.N_CALADAS, errors='coerce')
                flags['multiple_reported_caladas'] += int(caladas.gt(1).any())
                flags['missing_caladas'] += int(caladas.isna().any())
                flags['conflicting_caladas'] += int(group.N_CALADAS.nunique(dropna=False) > 1)
                if group.FECHA_LANCE.nunique(dropna=False) == 1:
                    row = group.iloc[0]
                    start = date_or_none(row.FECHA_HORA_ZARPE)
                    end = date_or_none(row.FECHA_HORA_RECALADA)
                    lance = date_or_none(row.FECHA_LANCE)
                    flags['lance_equals_return'] += int(lance is not None and lance == end)
                    flags['departure_and_lance_differ_in_calendar_day'] += int(
                        start is not None and lance is not None and start.date() != lance.date())
            if assigned_ordinals != set(complete.index+1) or sum(states.values()) != sum(dispositions.values()):
                raise ValueError('Candidate counts fail conservation checks')
            results.append({
                'year': year, 'gear': gear, 'archive_sha256': digest,
                'archive_member_basename': db.name, 'table': names[gear],
                'weight_dictionary_row_1based': int(weight_row.index[0])+1,
                'selected_source_rows': len(selected), 'rows_without_complete_key': int(incomplete.sum()),
                'rows_traced_to_candidate_keys': len(assigned_ordinals), 'candidate_keys': sum(states.values()),
                'reported_states': dict(states), 'quantity_dispositions': dict(dispositions),
                'diagnostic_flags': dict(flags),
                'keys_in_time_and_position_quarantine': sum(states.values()),
                'keys_with_certified_fish_environment_pair': 0,
            })
    return {'schema_version': 'portales_candidate_inventory_audit_v1',
            'contract_schema_version': contract['schema_version'],
            'reader_version': subprocess.check_output(['mdb-export', '--version'], text=True).strip(),
            'results': results, 'readiness': contract['readiness']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--contract', type=Path, default=Path('chile/candidate_dataset_contract.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.raw_dir, json.loads(args.contract.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
