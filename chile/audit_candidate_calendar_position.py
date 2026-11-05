"""Check calendar sensitivity, source row accounting and recorded operation endpoints."""
import argparse
from collections import Counter, defaultdict
from datetime import timedelta
import json
from pathlib import Path

import pandas as pd

from audit_candidate_coverage import strata
from audit_ifop_alignment_inputs import verified_member
from audit_ifop_artisanal import TRIP, date_or_none, diagnostic_dms


def september(rows, year):
    output = {}
    for field in ['FECHA_HORA_RECALADA', 'FECHA_LANCE']:
        dates = rows[field].map(date_or_none)
        matches = dates.map(lambda d: pd.notna(d) and d.year == year and d.month == 9)
        hake = rows.loc[matches & rows.COD_ESPECIE.eq('1')]
        output[field] = {
            'all_port_rows': int(matches.sum()),
            'hake_rows': len(hake),
            'hake_positive_weight_rows': int(pd.to_numeric(hake.PESO, errors='coerce').gt(0).sum()),
            'hake_rows_target_code_1': int(hake.ESPECIE_OBJETIVO.eq('1').sum()),
            'hake_rows_other_target_code': int((~hake.ESPECIE_OBJETIVO.isin(['1',''])).sum()),
            'hake_rows_blank_target_code': int(hake.ESPECIE_OBJETIVO.eq('').sum()),
            'unparsed_port_dates': int(dates.isna().sum()),
        }
    return output


def audit(raw_dir):
    results, union = [], defaultdict(set)
    for year, gear, digest, source in strata(raw_dir, full_tables=True):
        port = source[source.PUERTO_RECALADA.eq('560')]
        rows = port[port.ESPECIE_OBJETIVO.eq('1')]
        if rows[TRIP].eq('').any(axis=1).any():
            raise ValueError('Incomplete key')
        counts = Counter({'same_day_keys':0,'cross_day_keys':0,
                          'same_day_keys_with_date_invariant_under_offsets_0_3_4':0})
        weekdays = [0]*7
        month_days = defaultdict(set)
        for _, group in rows.groupby(TRIP):
            first = group.iloc[0]
            start = date_or_none(first.FECHA_HORA_ZARPE)
            end = date_or_none(first.FECHA_HORA_RECALADA)
            if start is None or end is None or start > end:
                raise ValueError('Unusable candidate dates')
            day = end.date()
            month = end.strftime('%Y-%m')
            weekdays[day.weekday()] += 1
            month_days[month].add(day)
            union[month].add(day)
            if start.date() == day:
                counts['same_day_keys'] += 1
                invariant = all((value+timedelta(hours=offset)).date()==day
                                for value in (start,end) for offset in (0,3,4))
                counts['same_day_keys_with_date_invariant_under_offsets_0_3_4'] += int(invariant)
            else:
                counts['cross_day_keys'] += 1
        codes = {'hake':rows.COD_ESPECIE.eq('1'), 'code999':rows.COD_ESPECIE.eq('999'),
                 'blank':rows.COD_ESPECIE.eq('')}
        codes['other'] = ~rows.COD_ESPECIE.isin(['1','999',''])
        weights = pd.to_numeric(rows.PESO,errors='coerce')
        breakdown = {k:{'rows':int(v.sum()),'positive':int((v&weights.gt(0)).sum()),
                        'zero':int((v&weights.eq(0)).sum()),'negative':int((v&weights.lt(0)).sum()),
                        'missing_or_nonnumeric':int((v&weights.isna()).sum())} for k,v in codes.items()}
        if sum(v['rows'] for v in breakdown.values()) != len(rows):
            raise ValueError('Row accounting failed')
        workbook = verified_member(raw_dir/f'gestion_{year}_anexos.zip',raw_dir/str(year),'Descripción de Campos.xls')
        dictionary = pd.read_excel(workbook,sheet_name=f'Bitácora {gear.capitalize()}',header=None)
        position_fields = {str(row.iloc[0]):int(i)+1 for i,row in dictionary.iterrows()
                           if str(row.iloc[0]).startswith(('LATITUD','LONGITUD_'))
                           and ('CALADO' in str(row.iloc[0]) or 'VIRADO' in str(row.iloc[0]))}
        endpoint_columns = [col for col in rows if col.startswith(('LATITUD','LONGITUD_'))
                            and ('CALADO' in col or 'VIRADO' in col)]
        endpoint_counts = {col:int(rows[col].ne('').sum()) for col in endpoint_columns}
        start_pair = (['LATITUD_INI_VIRADO','LONGITUD_INI_VIRADO'] if gear=='enmalle'
                      else ['LATITUD_INICIO_CALADO','LONGITUD_INICIO_CALADO'])
        generic = rows[['LATITUD','LONGITUD']].apply(pd.to_numeric, errors='coerce')
        endpoint = rows[start_pair].apply(pd.to_numeric, errors='coerce')
        endpoint.columns = generic.columns
        comparable = generic.notna().all(axis=1) & endpoint.notna().all(axis=1)
        equal = generic.eq(endpoint).all(axis=1)
        different = comparable & ~equal
        deltas = {}
        for column, limit in [('LATITUD',90),('LONGITUD',180)]:
            before = generic.loc[different,column].astype(str).map(lambda v: diagnostic_dms(v,limit))
            after = endpoint.loc[different,column].astype(str).map(lambda v: diagnostic_dms(v,limit))
            delta = (before-after).abs().dropna()
            deltas[column] = float(delta.max()) if len(delta) else None
        source_returns = source.FECHA_HORA_RECALADA.map(date_or_none)
        port_returns = port.FECHA_HORA_RECALADA.map(date_or_none)
        def july_august(dates):
            return int(dates.map(lambda d:pd.notna(d) and d.year==year and d.month in (7,8)).sum())
        results.append({'year':year,'gear':gear,'source_sha256':digest,'source_rows':len(source),
                        'selected_rows':len(rows),'row_code_and_weight_breakdown':breakdown,
                        'calendar':dict(counts),'return_weekday_keys_monday_to_sunday':weekdays,
                        'return_days_by_month':{m:len(days) for m,days in sorted(month_days.items())},
                        'september_portales_without_target_filter':september(port,year),
                        'july_august_return_rows_full_table':july_august(source_returns),
                        'july_august_return_rows_portales_all_targets':july_august(port_returns),
                        'position_dictionary_endpoint_rows':position_fields,
                        'endpoint_column_nonempty_selected_rows':endpoint_counts,
                        'generic_vs_start_endpoint':{'start_pair':start_pair,
                                                     'comparable_numeric_rows':int(comparable.sum()),
                                                     'exact_numeric_pair_equal_rows':int((comparable & equal).sum()),
                                                     'different_candidate_keys':len(rows.loc[different,TRIP].drop_duplicates()),
                                                     'max_diagnostic_absolute_delta_degrees_on_different_rows':deltas},
                        'generic_position_complete_selected_rows':int((rows.LATITUD.ne('')&rows.LONGITUD.ne('')).sum())})
    return {'schema_version':'portales_candidate_calendar_position_v1','results':results,
            'union_return_days_by_recorded_month':{m:len(days) for m,days in sorted(union.items())},
            'evaluation_ready':False,'training_ready':False,
            'limits':['tested offsets are conditional hypotheses, not a source clock certification',
                      'september counts describe exports, not all fishing or legal compliance',
                      'weekday coverage does not identify a sampling calendar',
                      'presence of coordinates does not establish their operational origin']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.raw_dir)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
