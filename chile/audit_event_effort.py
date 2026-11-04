"""Audit published event fields; do not infer operational effort or repair units."""
import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
import zipfile

EXPECTED_SHA256 = '251c84804d99b98b2a6f2d1b1cc9106ddc608f987abbf788a72457725d6ce3dd'
FIELDS = ('samplingProtocol', 'sampleSizeValue', 'sampleSizeUnit',
          'minimumElevationInMeters', 'maximumElevationInMeters',
          'verbatimElevation', 'minimumDepthInMeters', 'maximumDepthInMeters')


def audit(archive):
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Unexpected archive version; refuse to mix source versions')
    units, datasets, months, coverage = (collections.Counter() for _ in range(4))
    values = collections.defaultdict(list)
    count = 0
    with zipfile.ZipFile(archive) as z:
        eml_hash = hashlib.sha256(z.read('eml.xml')).hexdigest()
        table_rows = {name: sum(1 for _ in z.open(name)) - 1 for name in
                      ('event.txt', 'occurrence.txt', 'extendedmeasurementorfact.txt')}
        rows = csv.DictReader(io.TextIOWrapper(z.open('event.txt'), encoding='utf-8'),
                              delimiter='\t', quoting=csv.QUOTE_NONE)
        for row in rows:
            if row['locality'] != 'PORTALES' or row['id'].split('_')[1] != '14-01':
                continue
            count += 1
            datasets[row['datasetName']] += 1
            months[int(row['month'])] += 1
            units[row['sampleSizeUnit']] += 1
            coverage.update(f for f in FIELDS if row[f].strip())
            if row['sampleSizeValue'].strip():
                values[row['sampleSizeUnit']].append(float(row['sampleSizeValue']))
    return {
        'schema_version': 'portales_event_fields_v1',
        'source_sha256': digest, 'embedded_eml_sha256': eml_hash,
        'source_eml_url': 'https://gbif-chile.mma.gob.cl/ipt/eml.do?r=asipa_demersales&v=1.5',
        'actual_table_data_rows': table_rows,
        'scope': 'locality PORTALES, source block 14-01, all species; Event rows, not independent trips',
        'event_rows': count, 'dataset_names_as_published': dict(datasets),
        'nonempty_field_rows': {f: coverage[f] for f in FIELDS},
        'sample_size_unit_labels_as_published': dict(units),
        'sample_size_numeric_by_unit_label': {
            unit: {'rows': len(v), 'median': statistics.median(v),
                   'minimum': min(v), 'maximum': max(v),
                   'zero_rows': sum(x == 0 for x in v)} for unit, v in values.items()},
        'event_rows_by_component_month': {str(k): months[k] for k in sorted(months)},
        'limitations': [
            'datasetName labels are documentary evidence, not verified gear for every trip',
            'sampleSize mixes net height and mesh size; neither alone measures fishing effort',
            'no unit conversion, relabelling, deduplication or zero-capture inference performed',
            'component-month counts do not establish cause of seasonal sampling gaps',
            'no fishery validation or training-readiness claim']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
