"""Count Access data-page offset flags, not recover or publish deleted records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from access_parser import AccessParser
from audit_ifop_artisanal import SOURCES, table

MDBTOOLS_SOURCE = 'https://raw.githubusercontent.com/mdbtools/mdbtools/v1.0.0/src/libmdb/data.c'


def audit(raw_dir):
    results = []
    for year, (digest, _) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != digest:
            raise ValueError('Source archive changed')
        db = next((raw_dir/str(year)).rglob(f'DATOS {year} ARTESANAL DCS-PDA.accdb'))
        parser = AccessParser(str(db))
        if parser.version != 5 or parser.page_size != 4096:
            raise ValueError('This audit is restricted to observed ACE5/4096-byte format')
        raw = db.read_bytes()
        for gear, name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                           ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            owner = parser.catalog[name]
            t = parser.get_table(name)
            flags, pages = Counter(), 0
            # Independently scan page bytes. ACE5 layout: owner at +4, count
            # at +12 and little-endian 16-bit row offsets at +14.
            for start in range(0, len(raw), 4096):
                page = raw[start:start+4096]
                if page[:2] != b'\x01\x01' or struct.unpack_from('<I', page, 4)[0] != owner:
                    continue
                pages += 1
                count = struct.unpack_from('<H', page, 12)[0]
                if 14+2*count > len(page):
                    raise ValueError('Invalid row-offset table')
                for off in struct.unpack_from('<'+'H'*count, page, 14):
                    flags[f'0x{off & 0xf000:04x}'] += 1
            if pages != len(t.table.linked_pages):
                raise ValueError('Raw page scan disagrees with linked-page count')
            exported = len(table(db, name))
            metadata = int(t.table_header.number_of_rows)
            deleted = sum(n for flag, n in flags.items() if int(flag, 16) & 0x4000)
            results.append({
                'year': year, 'gear': gear, 'source_sha256': digest,
                'database_version': parser.version, 'page_size_bytes': 4096,
                'data_pages_with_matching_owner': pages,
                'tdef_metadata_rows': metadata,
                'mdb_count_metadata_rows': int(subprocess.check_output(['mdb-count', str(db), name])),
                'mdb_export_parsed_rows': exported,
                'offset_slots': sum(flags.values()), 'offset_high_flags': dict(sorted(flags.items())),
                'offset_slots_with_0x4000': deleted,
                'exported_rows_plus_0x4000_slots': exported+deleted,
                'metadata_minus_exported_rows_plus_0x4000_slots': metadata-exported-deleted,
            })
    return {'schema_version': 'ifop_access_offset_flags_v1',
            'flag_semantics_source': MDBTOOLS_SOURCE,
            'flag_semantics_source_retrieved_sha256': 'c98a5d9633ad80fe14ee3623fee93c36e8ffbf69fde0af65afce2a0f73b9003e',
            'flag_semantics_source_lines': [337, 338, 347],
            'flag_semantics': {'0x4000': 'deleted-row flag in mdbtools v1.0.0',
                               '0x8000': 'lookup flag in mdbtools v1.0.0'},
            'access_parser_version_for_catalog_and_tdef_only': '0.0.6',
            'results': results, 'training_ready': False,
            'limitations': [
                'resident page-slot counts are not an audit of historical deletions or database completeness',
                'does not recover deleted payloads or certify 4078 as all originally collected records',
                'matching owner pages scanned; no inference about previously reassigned or overwritten pages',
                'all nonzero high-bit patterns retained without guessing undocumented bits',
                'no original rows, deleted payloads, table owner numbers or individual identifiers published']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
