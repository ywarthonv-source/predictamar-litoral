"""Audit downloaded ASIPA DwC-A and Sernapesca data; never infer absences/CPUE.

Run with --raw-dir outside Git. Detailed rows remain there; only aggregate
audit_summary.json is suitable for review in the source repository.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd

TARGET_PREFIXES = {"reineta": "Brama australis", "merluza_comun": "Merluccius gayi"}
TARGET_NAMES = {"Brama australis": "reineta", "Merluccius gayi": "merluza_comun",
                "Merluccius gayi gayi": "merluza_comun"}
SITE_LAT, SITE_LON = -33.031145882327884, -71.5900592190291


def distance_km(lat, lon):
    """Great circle distance to official reference point, not distance to coast."""
    lat = np.radians(lat)
    a = np.sin((lat - math.radians(SITE_LAT)) / 2) ** 2
    a += np.cos(lat) * math.cos(math.radians(SITE_LAT)) * np.sin(
        (np.radians(lon) - math.radians(SITE_LON)) / 2
    ) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def target_key(name):
    # Never transfer the Peruvian subspecies into the Chilean target silently.
    return TARGET_NAMES.get(name.strip(), "")


def counts(series):
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).items()}


def event_summary(frame):
    lat = pd.to_numeric(frame.decimalLatitude, errors="coerce")
    lon = pd.to_numeric(frame.decimalLongitude, errors="coerce")
    valid = lat.between(-90, 90) & lon.between(-180, 180) & ~((lat == 0) & (lon == 0))
    days = pd.to_datetime(frame.year + "-" + frame.month + "-" + frame.day, format="%Y-%m-%d", errors="coerce")
    event_days = pd.to_datetime(frame.eventDate,format="%m/%d/%Y %H:%M:%S",errors="coerce").dt.normalize()
    comparable=days.notna()&event_days.notna()
    geo = frame.loc[valid, ["decimalLatitude", "decimalLongitude"]]
    return {
        "events": len(frame), "unique_event_ids": int(frame.id.nunique()),
        "counts_unit": "Darwin Core Event rows; not independent/deduplicated fishing operations",
        "source_block_counts": counts(frame.id.str.split('_').str[1]),
        "date_summary_basis": "year/month/day components; NOT a certified fishing date",
        "eventDate_component_disagreements": int((comparable&days.ne(event_days)).sum()),
        "invalid_eventDate_rows": int(event_days.isna().sum()),
        "capture_absence_use_permitted": False,
        "valid_coordinate_events": int(valid.sum()),
        "unique_coordinate_pairs": len(geo.drop_duplicates()),
        "most_repeated_coordinate_count": int(geo.value_counts().iloc[0]) if len(geo) else 0,
        "distinct_dates": int(days.nunique()),
        "first_date": str(days.min().date()) if days.notna().any() else None,
        "last_date": str(days.max().date()) if days.notna().any() else None,
        "years": counts(frame.year), "datasets": counts(frame.datasetName),
        "localities": counts(frame.locality),
        "sample_size_units": counts(frame.sampleSizeUnit),
        "sampling_protocol_nonempty": int(frame.samplingProtocol.ne("").sum()),
        "depth_fields_nonempty": int((frame.minimumDepthInMeters.ne("") | frame.maximumDepthInMeters.ne("")).sum()),
        "elevation_fields_nonempty": int((frame.minimumElevationInMeters.ne("") | frame.maximumElevationInMeters.ne("")).sum()),
    }


def audit(raw_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / "asipa_demersales_1_5.zip"
    report = {
        "schema_version": "chile_public_data_audit_v1",
        "research_only": True,
        "counts_unit": "original Darwin Core Event rows, not deduplicated or independent fishing operations",
        "operation_counts_validated": False,
        "superseding_review_file": "review_reconciliation.json; run reconcile_review.py for cross-block comparison",
        "asipa_sha256": hashlib.file_digest(archive_path.open("rb"), "sha256").hexdigest(),
        "asipa_license": "CC-BY-NC-4.0; intended commercial use unresolved",
        "study_support": "30/60 nautical mile circles and regional box are diagnostic only, not an approved fishing area",
        "regional_box": {"lat_min": -34, "lat_max": -32, "lon_min": -73, "lon_max": -71.3},
        "warnings": ["No absence/zero is inferred from missing taxa.",
                     "Occurrence quantity is not assumed to be total catch; no CPUE computed.",
                     "Event locality can be landing/sampling port, not fishing location.",
                     "Positive elevation fields are not reinterpreted as depth.",
                     "Rows sharing coordinates, trips or sampling context are not independent samples.",
                     "Capture and biological blocks can share time/position; original regional/national/radius counts are not operation counts.",
                     "eventDate and year/month/day differ; neither is certified here as fishing date.",
                     "Biological block absent is excluded as a capture-zero label pending source clarification."],
    }
    with zipfile.ZipFile(archive_path) as z:
        ns = {"d": "http://rs.tdwg.org/dwc/text/"}
        meta = ET.fromstring(z.read("meta.xml"))
        report["dwca_tables"] = {}
        for table in list(meta):
            name = table.find("d:files/d:location", ns).text
            report["dwca_tables"][name] = {
                "uncompressed_bytes": z.getinfo(name).file_size,
                "field_terms": [a.attrib["term"] for a in table.findall("d:field", ns)],
            }
        events = pd.read_csv(z.open("event.txt"), sep="\t", dtype=str,
                             keep_default_na=False, quoting=csv.QUOTE_NONE)
        report["all_events"] = event_summary(events)
        lat = pd.to_numeric(events.decimalLatitude, errors="coerce")
        lon = pd.to_numeric(events.decimalLongitude, errors="coerce")
        events["site_distance_km"] = distance_km(lat, lon)
        events["in_regional_box"] = lat.between(-34, -32) & lon.between(-73, -71.3)
        selected = []
        occurrence_rows = 0
        all_taxa = {}
        all_status = {}
        for chunk in pd.read_csv(z.open("occurrence.txt"), sep="\t", dtype=str,
                                 keep_default_na=False, quoting=csv.QUOTE_NONE, chunksize=100000):
            occurrence_rows += len(chunk)
            for name, n in chunk.scientificName.value_counts().items():
                all_taxa[name] = all_taxa.get(name, 0) + int(n)
            for name, n in chunk.occurrenceStatus.value_counts().items():
                all_status[name] = all_status.get(name, 0) + int(n)
            keys = chunk.scientificName.map(target_key)
            sub = chunk.loc[keys.ne("")].copy()
            sub["target_species"] = keys[keys.ne("")]
            selected.append(sub)
        target = pd.concat(selected, ignore_index=True)
        report["occurrence_rows"] = occurrence_rows
        report["all_taxa_count"] = len(all_taxa)
        report["occurrence_statuses"] = all_status
        report["target_taxa"] = {n: c for n, c in all_taxa.items() if target_key(n)}
        report["target_occurrence_rows"] = len(target)
        report["target_unique_occurrence_ids"] = int(target.occurrenceID.nunique())
        report["target_orphan_rows"] = int((~target.id.isin(events.id)).sum())
        indexed = events.set_index("id", drop=False)
        detail_frames = []
        report["species"] = {}
        for key in TARGET_PREFIXES:
            occ = target[target.target_species.eq(key)]
            ev = indexed.loc[indexed.index.isin(occ.id)]
            quantities = pd.to_numeric(occ.organismQuantity, errors="coerce")
            species = {"occurrence_rows": len(occ), "quantity_units": counts(occ.organismQuantityType),
                       "numeric_quantity_rows": int(quantities.notna().sum()),
                       "zero_quantity_rows": int(quantities.eq(0).sum()),
                       "occurrence_status": counts(occ.occurrenceStatus)}
            labels = occ.groupby("id").occurrenceStatus.agg(set)
            species["events_with_conflicting_status"] = int(labels.map(lambda x: "present" in x and "absent" in x).sum())
            for label, mask in {
                "national": np.ones(len(ev), dtype=bool),
                "portales_locality": ev.locality.str.contains("PORTALES", case=False, na=False),
                "regional_box": ev.in_regional_box,
                "within_30nm": ev.site_distance_km.le(30 * 1.852),
                "within_60nm": ev.site_distance_km.le(60 * 1.852),
            }.items():
                selected_events = ev.loc[mask]
                selected_occ = occ[occ.id.isin(selected_events.id)]
                species[label] = event_summary(selected_events)
                species[label]["occurrence_status_rows"] = counts(selected_occ.occurrenceStatus)
                species[label]["events_with_declared_presence"] = int(selected_occ.loc[selected_occ.occurrenceStatus.eq("present"), "id"].nunique())
                species[label]["events_with_declared_absence"] = int(selected_occ.loc[selected_occ.occurrenceStatus.eq("absent"), "id"].nunique())
                quantity_keys = ["id", "scientificName", "organismQuantity", "organismQuantityType", "occurrenceStatus"]
                species[label]["unique_event_species_quantity_status_combinations"] = len(selected_occ[quantity_keys].drop_duplicates())
                species[label]["occurrence_rows"] = len(selected_occ)
                species[label]["events_with_different_quantity_values"] = int(selected_occ.groupby("id").organismQuantity.nunique().gt(1).sum())
            report["species"][key] = species
            local = ev[ev.in_regional_box | ev.locality.str.contains("PORTALES", case=False)]
            # Preserve original quantities and labels, do not collapse to catch/CPUE.
            detail = occ[occ.id.isin(local.id)].merge(local.drop(columns="id"),
                       left_on="id", right_index=True, suffixes=("_occurrence", "_event"), validate="many_to_one")
            detail_frames.append(detail)
        pd.concat(detail_frames, ignore_index=True).to_csv(raw_dir / "asipa_targets_regional_private.csv", index=False)
        # Audit measurement types for all extensions without reading 357 MB at once.
        types, units, measurement_rows = {}, {}, 0
        for chunk in pd.read_csv(z.open("extendedmeasurementorfact.txt"), sep="\t", dtype=str,
                                 keep_default_na=False, quoting=csv.QUOTE_NONE, chunksize=200000):
            measurement_rows += len(chunk)
            for n,c in chunk.measurementType.value_counts().items(): types[n] = types.get(n,0)+int(c)
            for n,c in chunk.measurementUnit.value_counts().items(): units[n] = units.get(n,0)+int(c)
        report["measurements"] = {"rows": measurement_rows, "types": types, "units": units}
    landings = pd.read_csv(raw_dir / "sernapesca_desembarques_2000_2023.csv", sep=";", encoding="cp1252", dtype=str, keep_default_na=False)
    portales = landings[landings.puerto_desembarque.str.contains("PORTALES", case=False)]
    target_landings = portales[portales.especie.str.contains("^Reineta$|^Merluza Com[uú]n$", case=False, regex=True)]
    report["landings"] = {"rows": len(landings), "columns": list(landings.columns),
        "year_range": [landings["año"].min(), landings["año"].max()],
        "portales_rows": len(portales), "portales_names": counts(portales.puerto_desembarque),
        "portales_species_rows": counts(portales.especie),
        "targets": {name: {"rows": len(g), "years": sorted(g["año"].unique().tolist()), "agent_types": counts(g.tipo_agente)}
                    for name,g in target_landings.groupby("especie")},
        "note": "Monthly landing aggregates, without haul position or effort; numeric tonnes not used until decimal conventions verified."}
    valparaiso = landings[landings.puerto_desembarque.eq("Valparaiso") & landings.especie.str.contains("^Reineta$|^Merluza Com[uú]n$", case=False, regex=True)]
    report["landings"]["valparaiso_targets"] = {name: {"rows":len(g),"first_year":g["año"].min(),"last_year":g["año"].max(),"agent_types":counts(g.tipo_agente)} for name,g in valparaiso.groupby("especie")}
    target_landings.to_csv(raw_dir / "portales_target_landings_private.csv", index=False)
    (output_dir / "audit_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"events":len(events),"occurrence_rows":occurrence_rows,
                      "species":{k:{label:v[label]["events"] for label in ["national","portales_locality","regional_box","within_30nm","within_60nm"]} for k,v in report["species"].items()},
                      "landings_targets": report["landings"]["targets"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--raw-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    audit(args.raw_dir,args.output_dir)
