"""Coarse land/coast and candidate-trip checks; never excludes source records."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd
import pyproj
import shapefile
from shapely.geometry import Point, box, shape
from shapely.ops import transform, unary_union

from audit_ifop_artisanal import SOURCES, TRIP, date_or_none, diagnostic_dms, table

LAND_SHA = 'e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc'
REGION = box(-80, -40, -65, -25)


def coast_reference(archive):
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    if digest != LAND_SHA:
        raise ValueError('Unexpected land source version')
    with zipfile.ZipFile(archive) as z:
        version = z.read('ne_10m_land.VERSION.txt').decode().strip()
        reader = shapefile.Reader(shp=io.BytesIO(z.read('ne_10m_land.shp')),
                                 shx=io.BytesIO(z.read('ne_10m_land.shx')))
        polygons = [shape(s.__geo_interface__) for s in reader.iterShapes()
                    if box(*s.bbox).intersects(REGION)]
    land = unary_union(polygons)
    if not land.is_valid:
        raise ValueError('Invalid land reference; no silent geometry repair')
    # Union before taking the boundary removes partition seams. Clip only the
    # boundary, so the clip-box edges never masquerade as coastline.
    coast = land.boundary.intersection(REGION)
    project = pyproj.Transformer.from_crs(4326, 32719, always_xy=True).transform
    coast_m = transform(project, coast)
    return land, coast_m, project, version, digest


def point_check(lon, lat, land, coast, project):
    if lon is None or lat is None:
        return None, None
    point = Point(lon, lat)
    if not REGION.contains(point):
        return None, None
    distance = Point(*project(lon, lat)).distance(coast)/1000
    return bool(land.covers(point)), distance


def audit(raw_dir, land_archive):
    land, coast, project, version, digest = coast_reference(land_archive)
    controls = {}
    for name, lon, lat in [('offshore_control', -72, -33),
                           ('inland_control', -70.5, -33.5),
                           ('portales_reference', -71.5900592190291, -33.031145882327884)]:
        on_land, distance = point_check(lon, lat, land, coast, project)
        controls[name] = {'on_generalized_land': on_land, 'distance_to_generalized_coast_km': distance}
    if controls['offshore_control']['on_generalized_land'] or not controls['inland_control']['on_generalized_land']:
        raise ValueError('Independent geographic control checks failed')
    reports = []
    for year, (source_hash, url) in SOURCES.items():
        archive = raw_dir/f'gestion_{year}_anexos.zip'
        if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != source_hash:
            raise ValueError('Unexpected source archive')
        db = raw_dir/str(year)/f'DATOS {year} ARTESANAL DCS-PDA.accdb'
        for gear, table_name in [('enmalle', f'BITACORAS ENMALLE Centro Sur {year}'),
                                 ('espinel', f'BITACORAS ESPINEL Centro Sur-  Sur Austral {year}')]:
            data = table(db, table_name)
            rows = data[data.PUERTO_RECALADA.eq('560') & data.ESPECIE_OBJETIVO.eq('1')].copy()
            rows['diagnostic_lat'] = rows.LATITUD.map(lambda v: diagnostic_dms(v, 90))
            rows['diagnostic_lon'] = rows.LONGITUD.map(lambda v: diagnostic_dms(v, 180))
            points = rows[['diagnostic_lon', 'diagnostic_lat']].drop_duplicates()
            cache = {}
            for lon, lat in points.itertuples(index=False, name=None):
                cache[(lon, lat)] = point_check(lon, lat, land, coast, project)
            results = [cache[(lon, lat)] for lon, lat in rows[['diagnostic_lon', 'diagnostic_lat']].itertuples(index=False, name=None)]
            rows['on_land'] = [r[0] for r in results]
            rows['coast_distance_km'] = [r[1] for r in results]
            grouped = rows.groupby(TRIP, dropna=False)
            trips = grouped.first().reset_index()
            caladas = grouped.N_CALADAS.agg(lambda x: pd.to_numeric(x, errors='coerce').max())
            numbers = grouped.NUMERO_LANCE_EX.nunique(dropna=False)
            times = {name: trips[name].map(date_or_none) for name in TRIP[1:]+['FECHA_LANCE']}
            start, end, lance = (times[c] for c in [TRIP[1], TRIP[2], 'FECHA_LANCE'])
            parsed = start.notna() & end.notna() & lance.notna()
            duration = (end-start).dt.total_seconds()/3600
            positions_per_trip = grouped[['LATITUD', 'LONGITUD']].nunique(dropna=False).max(axis=1)
            reports.append({
                'year': year, 'gear': gear, 'source_archive_sha256': source_hash,
                'selected_rows': len(rows), 'candidate_trips': len(trips),
                'unique_diagnostic_coordinate_pairs': len(points),
                'outside_reference_region_or_unparsed_rows': int(rows.coast_distance_km.isna().sum()),
                'on_generalized_land_rows': int(rows.on_land.eq(True).sum()),
                'on_generalized_land_unique_points': sum(v[0] is True for v in cache.values()),
                'on_generalized_land_more_than_2km_rows': int((rows.on_land.eq(True) & rows.coast_distance_km.gt(2)).sum()),
                'on_generalized_land_more_than_5km_rows': int((rows.on_land.eq(True) & rows.coast_distance_km.gt(5)).sum()),
                'within_2km_generalized_coast_either_side_rows': int(rows.coast_distance_km.le(2).sum()),
                'maximum_inland_distance_km': float(rows.loc[rows.on_land.eq(True), 'coast_distance_km'].max()) if rows.on_land.eq(True).any() else None,
                'candidate_trips_with_multiple_positions': int(positions_per_trip.gt(1).sum()),
                'candidate_trips_declaring_multiple_caladas': int(caladas.gt(1).sum()),
                'multiple_caladas_but_single_lance_number_trips': int((caladas.gt(1) & numbers.eq(1)).sum()),
                'candidate_trips_missing_caladas': int(caladas.isna().sum()),
                'candidate_trips_unparseable_start_end_or_lance_time': int((~parsed).sum()),
                'candidate_trips_with_return_before_departure': int((parsed & duration.lt(0)).sum()),
                'candidate_trips_with_zero_trip_duration': int((parsed & duration.eq(0)).sum()),
                'candidate_trips_with_lance_outside_trip_times': int((parsed & ((lance < start) | (lance > end))).sum()),
                'trip_duration_hours_median': float(duration.median()),
                'trip_duration_hours_min': float(duration.min()),
                'trip_duration_hours_max': float(duration.max()),
            })
    return {'schema_version': 'ifop_coarse_geography_and_trip_v1',
            'reference': {'dataset': 'Natural Earth land', 'version': version,
                          'sha256': digest, 'nominal_scale': '1:10 million, not 10 metres',
                          'url': 'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip',
                          'source_page': 'https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/',
                          'licence': 'public domain', 'metric_crs': 'EPSG:32719',
                          'diagnostic_region_lon_lat': [-80, -40, -65, -25]},
            'controls': controls, 'results': reports,
            'limitations': ['all coordinates use a diagnostic southwest-DDMMSS interpretation',
                            'generalized coastline is not authoritative for nearshore positions',
                            '2/5 km thresholds are exploratory review flags, not calibrated accuracy bounds',
                            'no rows removed, no location corrected, no geometry approved',
                            'candidate trip keys and catch/effort scope still require certification'],
            'training_ready': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True)
    p.add_argument('--land-archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.raw_dir, args.land_archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
