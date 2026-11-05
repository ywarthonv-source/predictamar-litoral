"""Reproduce Claude round-2 cross-tab and September questions, aggregates only."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import pandas as pd

from audit_event_effort import EXPECTED_SHA256


def audit(archive):
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Unexpected source archive')
    with zipfile.ZipFile(archive) as z:
        events = pd.read_csv(z.open('event.txt'), sep='\t', dtype=str, keep_default_na=False)
        p = events[events.locality.eq('PORTALES') & events.id.str.split('_').str[1].eq('14-01')].copy()
        cross = []
        for name, d in p.groupby('datasetName'):
            cross.append({'dataset_name': name, 'event_rows': len(d),
                          'sample_size_unit_rows': d.sampleSizeUnit.value_counts().to_dict(),
                          'nonempty_minimum_elevation_rows': int(d.minimumElevationInMeters.ne('').sum()),
                          'nonempty_maximum_elevation_rows': int(d.maximumElevationInMeters.ne('').sum())})
        sept = p[p.month.astype(int).eq(9)].copy()
        ids = set(sept.id)
        pieces = []
        for chunk in pd.read_csv(z.open('occurrence.txt'), sep='\t', dtype=str,
                                 keep_default_na=False, chunksize=100000):
            pieces.append(chunk[chunk.id.isin(ids)])
        occ = pd.concat(pieces, ignore_index=True)
    occ['kg'] = pd.to_numeric(occ.organismQuantity, errors='coerce').where(occ.organismQuantityType.eq('KILOGRAMO'))
    by_year = []
    for year, d in sept.groupby('year'):
        o = occ[occ.id.isin(d.id)]
        by_year.append({'year': year, 'events': len(d),
                        'component_day_min': int(d.day.astype(int).min()),
                        'component_day_max': int(d.day.astype(int).max()),
                        'scientific_name_occurrence_rows': o.scientificName.value_counts().to_dict(),
                        'rows_missing_kg': int(o.kg.isna().sum()),
                        'duplicate_event_species_rows': int(o.duplicated(['id', 'scientificName']).sum())})
    return {'source_sha256': digest, 'scope': 'PORTALES/14-01 Event rows, all species',
            'dataset_cross_tabs': cross, 'september_by_year': by_year,
            'limitations': ['missing hake row is not an absence label',
                            'no individual event/vessel identifiers published',
                            'calendar strata are not a judgement about legality or abundance']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
