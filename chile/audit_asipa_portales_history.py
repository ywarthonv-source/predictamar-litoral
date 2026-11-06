"""Aggregate ASIPA Portales capture events by year without exporting microdata."""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

from audit_public_data import target_key


SHA256 = '251c84804d99b98b2a6f2d1b1cc9106ddc608f987abbf788a72457725d6ce3dd'


def rows(archive, name):
    with io.TextIOWrapper(archive.open(name), encoding='utf-8-sig', newline='') as source:
        yield from csv.DictReader(source, delimiter='\t', quoting=csv.QUOTE_NONE)


def parsed_days(row):
    try:
        components = date(int(row['year']), int(row['month']), int(row['day']))
    except ValueError:
        components = None
    try:
        event_day = datetime.strptime(row['eventDate'], '%m/%d/%Y %H:%M:%S').date()
    except ValueError:
        event_day = None
    return components, event_day


def concentration(counts):
    ranked = sorted(counts.values(), reverse=True)
    total = sum(ranked)
    result = {'unique': len(ranked), 'total': total}
    cumulative = 0
    for rank, count in enumerate(ranked, 1):
        cumulative += count
        for share in (50, 90):
            if cumulative * 100 >= total * share:
                result.setdefault(f'units_for_{share}_percent', rank)
    return result


def grid_summary(pairs):
    results = {}
    for tolerance in (Decimal('0.0001'), Decimal('0.000001')):
        counts = Counter({'whole_minute': 0, 'tenth_minute_only': 0, 'neither': 0})
        for pair in pairs:
            if all(abs(value * 60 - round(value * 60)) <= tolerance * 60 for value in pair):
                counts['whole_minute'] += 1
            elif all(abs(value * 600 - round(value * 600)) <= tolerance * 600 for value in pair):
                counts['tenth_minute_only'] += 1
            else:
                counts['neither'] += 1
        results[str(tolerance)] = dict(counts)
    return results


GRID_STEPS = (
    ('degree', 1), ('six_minutes', 10), ('three_minutes', 20),
    ('one_minute', 60), ('tenth_minute', 600),
)


def coarsest_grid(values, tolerance=Decimal('0.000001')):
    for name, factor in GRID_STEPS:
        if all(abs(value * factor - round(value * factor)) <= tolerance * factor
               for value in values):
            return name
    return 'neither'


def audit(path):
    with path.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != SHA256:
            raise ValueError('Unexpected ASIPA archive')
    with ZipFile(path) as archive:
        local = {}
        fields = ('coordinateUncertaintyInMeters', 'coordinatePrecision',
                  'georeferenceRemarks', 'footprintWKT')
        field_presence = {}
        for row in rows(archive, 'event.txt'):
            if not field_presence:
                field_presence = {field: field in row for field in fields}
            if row['id'].split('_')[1:2] == ['14-01'] and 'PORTALES' in row['locality'].upper():
                if row['id'] in local:
                    raise ValueError('Duplicate Event identifier')
                local[row['id']] = row
        states = defaultdict(set)
        for row in rows(archive, 'occurrence.txt'):
            if row['id'] in local and (species := target_key(row['scientificName'])):
                states[species, row['id']].add(row['occurrenceStatus'])

    annual = defaultdict(Counter)
    excluded = Counter()
    localities = defaultdict(Counter)
    positions = defaultdict(Counter)
    dates = defaultdict(Counter)
    hake_pairs = defaultdict(set)
    decimal_places = defaultdict(Counter)
    event_grids = defaultdict(lambda: defaultdict(Counter))
    integer_values = defaultdict(Counter)
    longitude_by_integer_latitude = defaultdict(set)
    for (species, event_id), status in states.items():
        if status != {'present'}:
            excluded[f'{species}:status_not_exclusively_present'] += 1
            continue
        row = local[event_id]
        component_day, event_day = parsed_days(row)
        if component_day is None or not 2010 <= component_day.year <= 2022:
            excluded[f'{species}:component_date_missing_or_outside_window'] += 1
            continue
        counts = annual[component_day.year, species]
        counts['event_ids'] += 1
        counts['both_dates_agree'] += int(component_day == event_day)
        counts['event_date_unparseable'] += int(event_day is None)
        counts['dates_disagree'] += int(event_day is not None and component_day != event_day)
        counts['sampling_protocol:' + row['samplingProtocol']] += 1
        counts['dataset:' + row['datasetName']] += 1
        localities[species][row['locality']] += 1
        if row['decimalLatitude'] and row['decimalLongitude']:
            positions[species][float(row['decimalLatitude']), float(row['decimalLongitude'])] += 1
            if species == 'merluza_comun':
                pair = tuple(Decimal(row[field]) for field in ('decimalLatitude', 'decimalLongitude'))
                period = '2010–2016' if component_day.year <= 2016 else '2017–2022'
                for group in ('all', f"{row['datasetName']} | {period}"):
                    hake_pairs[group].add(pair)
                    for axis, values in (('latitude', pair[:1]), ('longitude', pair[1:]), ('pair', pair)):
                        event_grids[group][axis][coarsest_grid(values)] += 1
                if pair[0] == int(pair[0]):
                    longitude_by_integer_latitude[pair[0]].add(pair[1])
                for axis, value in zip(('latitude', 'longitude'), pair):
                    if value == int(value):
                        integer_values[axis][value] += 1
                    decimal_places[axis][max(0, -value.normalize().as_tuple().exponent)] += 1
        dates[species][component_day] += 1
    return {
        'archive_sha256': SHA256,
        'window': [2010, 2022],
        'basis': 'Unique Event IDs per species with exclusively present status, PORTALES locality, capture block 14-01. Year from date components.',
        'annual': {year: {species: dict(annual[year, species]) for species in ('merluza_comun', 'reineta')}
                   for year in range(2010, 2023)},
        'locality_values_by_species': localities,
        'georeferencing_field_presence_in_event': field_presence,
        'coordinate_pair_concentration': {species: concentration(c) for species, c in positions.items()},
        'recorded_day_concentration': {species: concentration(c) for species, c in dates.items()},
        'merluza_unique_pairs_grid_by_stratum': {name: grid_summary(pairs) for name, pairs in hake_pairs.items()},
        'merluza_decimal_places_without_trailing_zeros_by_event': decimal_places,
        'merluza_coarsest_grid_by_event': event_grids,
        'merluza_integer_axis_aggregate': {
            axis: {'unique': len(values), 'event_counts_descending': sorted(values.values(), reverse=True)}
            for axis, values in integer_values.items()
        },
        'merluza_integer_latitude_distinct_longitudes_descending': sorted(
            (len(values) for values in longitude_by_integer_latitude.values()), reverse=True),
        'excluded_event_species': dict(excluded),
        'evaluation_ready': False,
    }


if __name__ == '__main__':
    print(json.dumps(audit(Path(sys.argv[1])), ensure_ascii=False, indent=2))


