"""Read-only audit of official IFOP Access attachments using mdbtools.

Exports stay outside Git. No raw coordinates, catches, or corrected profiles
are published by this script; aggregate QA is the review artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


def ddmm_to_south_west(values):
    values=pd.to_numeric(values,errors="coerce")
    degrees=np.floor(values/100)
    minutes=values-degrees*100
    return (-(degrees+minutes/60)).where(minutes.between(0,60,inclusive="left"))


def audit(raw_dir,output):
    report={"schema_version":"ifop_cruise_audit_v1","databases":[],
            "warnings":["Cruise trawls are not artisanal enmalle/espinel operations.",
                        "Acoustic rows lack date/time and contain no explicit zero NASC observations; do not infer absence from omitted intervals.",
                        "Survey hauls are identification hauls with selection bias; no operational prediction performance evaluated.",
                        "Source licence/conditions for commercial reuse must be established before product integration."]}
    for database in sorted(raw_dir.glob("ifop*anexos/*.accdb")):
        if database.name.startswith("._"):continue
        names=subprocess.check_output(["mdb-tables","-1",str(database)],text=True).splitlines()
        csv_dir=database.parent/"csv";csv_dir.mkdir(exist_ok=True)
        summary={"file":str(database.relative_to(raw_dir)),
                 "sha256":hashlib.file_digest(database.open("rb"),"sha256").hexdigest(),"tables":{},"quality_flags":[]}
        for index,name in enumerate(names):
            dest=csv_dir/f"{index:02d}.csv"
            with dest.open("w") as stream:subprocess.run(["mdb-export",str(database),name],stdout=stream,check=True)
            data=pd.read_csv(dest)
            summary["tables"][name]={"rows":len(data),"columns":list(data.columns)}
            if name.startswith("ACÚSTICA"):
                valid=data.LAT_M.notna()&data.LON_M.notna()&data.NASC_TOT.notna()
                summary["acoustic"]={"raw_rows":len(data),"rows_with_position_and_nasc":int(valid.sum()),
                    "zero_nasc_rows":int(data.NASC_TOT.eq(0).sum()),"classification_labels":data.R_CLASS.value_counts().to_dict(),
                    "dated_rows":0,"rows_in_latitude_band_32_34S":int((valid&data.LAT_M.between(-34,-32)).sum())}
            elif name.startswith("BITÁCORA"):
                lat=ddmm_to_south_west(data.LAT_INI);lon=ddmm_to_south_west(data.LON_INI)
                regional=lat.between(-34,-32)&lon.between(-73,-71.3)
                date_format="%m/%d/%y %H:%M:%S" if "2024" in name else "%d/%m/%Y"
                dates=pd.to_datetime(data.F_LANCE,format=date_format,errors="coerce")
                expected_year=2024 if "2024" in name else 2025
                correct_year=dates.dt.year.eq(expected_year)
                summary["hauls"]={"rows":len(data),"unique_lance_ids":int(data.LANCE.nunique()),
                    "first_date":str(dates.min().date()),"last_date":str(dates.max().date()),
                    "invalid_dates":int(dates.isna().sum()),"regional_rows":int(regional.sum()),
                    "expected_cruise_year":expected_year,
                    "dates_outside_cruise_year":int((dates.notna()&~correct_year).sum()),
                    "dates_matching_cruise_year":int(correct_year.sum()),
                    "first_date_matching_cruise_year":str(dates[correct_year].min().date()),
                    "last_date_matching_cruise_year":str(dates[correct_year].max().date()),
                    "zero_merluza_rows":int(data.MERLUZA.eq(0).sum()),
                    "regional_zero_merluza_rows":int((regional&data.MERLUZA.eq(0)).sum()),
                    "nonpositive_duration_rows":int(data['DURACIÓN'].le(0).sum()),
                    "duration_over_one_hour_rows":int(data['DURACIÓN'].gt(1).sum()),
                    "latitude_conversion":"source DDMM.m to negative decimal degrees; raw preserved",
                    "source_duration_units":"not assumed from field name; verify report before CPUE"}
                if data['DURACIÓN'].gt(1).any():summary["quality_flags"].append("Unusually long duration needs comparison with deployment/retrieval times before effort standardization.")
                if (~correct_year).any():summary["quality_flags"].append("Haul dates missing or outside cruise year are quarantined; do not fill dates by copying year or neighbouring hauls.")
            elif name.startswith("OCEAN"):
                lat=data.LATITUD;lon=data.LONGITUD
                swapped=lat.between(-80,-65).all()&lon.between(-60,-15).all()
                summary["ocean"]={"rows":len(data),"stations":int(data['ESTACIÓN'].nunique()),
                    "lat_lon_globally_swapped_for_chile":bool(swapped),
                    "year_values":sorted(data['AÑO'].dropna().astype(int).unique().tolist()),
                    "chlorophyll_nonmissing":int(data.CLO_a.notna().sum()),
                    "chlorophyll_zero_rows":int(data.CLO_a.eq(0).sum()),
                    "missing_temperature_rows":int(data.TEMP.isna().sum()),
                    "missing_oxygen_rows":int(data.OXIGENO.isna().sum())}
                # Diagnostic only: report support under an explicit proposed swap.
                use_lat,use_lon=(lon,lat) if swapped else (lat,lon)
                regional=use_lat.between(-34,-32)&use_lon.between(-73,-71.3)
                summary["ocean"]["regional_stations_after_explicit_diagnostic_swap_if_needed"]=int(data.loc[regional,'ESTACIÓN'].nunique())
                if swapped:summary["quality_flags"].append("OCEAN 2025 latitude/longitude columns are globally reversed for Chile. Raw retained; swap is only a documented diagnostic assumption here.")
                if data.CLO_a.eq(0).all():summary["quality_flags"].append("OCEAN 2024 chlorophyll is zero in every row; treat as suspect placeholder until source confirms, not measured zero biomass.")
            elif name.startswith("CAPTURAS"):
                selected=data[data.N_COMUN.str.contains("Merluza com|Reineta",case=False,na=False)]
                summary["capture_species"]={n:{"rows":len(g),"hauls":int(g.LANCE.nunique()),"explicit_zero_rows":int(g['CAPTURA (kg)'].eq(0).sum())} for n,g in selected.groupby("N_COMUN")}
        (csv_dir/"tables.json").write_text(json.dumps(dict(enumerate(names)),ensure_ascii=False,indent=2)+"\n")
        report["databases"].append(summary)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps([{k:v for k,v in d.items() if k in ['file','acoustic','hauls','ocean','quality_flags']} for d in report['databases']],ensure_ascii=False,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();audit(a.raw_dir,a.output)
