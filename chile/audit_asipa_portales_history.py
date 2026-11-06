"""Aggregate ASIPA Portales capture events by year without exporting microdata."""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
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
        'excluded_event_species': dict(excluded),
        'evaluation_ready': False,
    }


if __name__ == '__main__':
    print(json.dumps(audit(Path(sys.argv[1])), ensure_ascii=False, indent=2))

