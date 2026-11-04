"""Research-only availability audit over a technical box west of Valparaiso.

No fish scores, interpolation, operational geometry, or land-mask inference.
Credentials come only from the normal provider environment; never print them.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PRODUCTS = {
    "temperature": ("cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m", ["thetao"], True, "model_3d"),
    "salinity": ("cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m", ["so"], True, "model_3d"),
    "currents": ("cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m", ["uo", "vo"], True, "model_3d"),
    "oxygen": ("cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m", ["o2"], True, "coarse_model_3d"),
    "ostia": ("METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2", ["analysed_sst", "analysis_error"], False, "L4_analysis_not_direct_observation"),
    "chlorophyll_l3": ("cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D", ["CHL"], False, "L3_observation"),
    "chlorophyll_l4": ("cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D", ["CHL"], False, "L4_interpolated_not_direct_observation"),
}


def summarize_array(da):
    finite = np.isfinite(da)
    xy = [d for d in ("latitude", "longitude") if d in da.dims]
    values = da.values
    good = values[np.isfinite(values)]
    result = {
        "units": da.attrs.get("units"), "dimensions": dict(da.sizes),
        "finite_values": int(finite.sum().item()), "total_values": int(da.size),
        "finite_fraction_box_including_land": float(finite.mean().item()),
        "minimum_native_units": float(good.min()) if good.size else None,
        "maximum_native_units": float(good.max()) if good.size else None,
    }
    if xy and "time" in da.dims:
        spatial_range = da.max(xy, skipna=True) - da.min(xy, skipna=True)
        ranges = spatial_range.values
        ranges = ranges[np.isfinite(ranges)]
        result["median_daily_spatial_range_native_units"] = float(np.median(ranges)) if ranges.size else None
        result["cells_with_any_finite_value"] = int(finite.any("time").sum().item())
        result["daily_finite_cells"] = [int(v) for v in finite.sum(xy).values]
    return result


def run(product, output, start, end):
    import copernicusmarine
    output.mkdir(parents=True, exist_ok=True)
    dataset_id, variables, vertical, kind = PRODUCTS[product]
    request = dict(dataset_id=dataset_id, variables=variables,
                   minimum_latitude=-33.3, maximum_latitude=-32.8,
                   minimum_longitude=-72.1, maximum_longitude=-71.6,
                   start_datetime=start, end_datetime=end+"T23:59:59",
                   coordinates_selection_method="strict-inside")
    if vertical: request.update(minimum_depth=0, maximum_depth=300)
    report = {"schema_version":"chile_copernicus_availability_v1",
              "product":product, "request":request, "source_kind":kind,
              "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
              "copernicusmarine_version":copernicusmarine.__version__,
              "attribution":"E.U. Copernicus Marine Service Information; see provider metadata and licence",
              "technical_box_is_operational_domain":False,
              "fish_predictive_validity":"not_evaluated",
              "note":"Coverage of finite values in technical box is not marine-only coverage or observation certainty. L3 missingness is not attributed solely to cloud."}
    # Non-interactive use is deliberate. Do not prompt or fabricate credentials.
    if not (os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME") and os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD")):
        report["status"]="missing_credentials"
        (output/(product+".json")).write_text(json.dumps(report,indent=2)+"\n")
        return 2
    try:
        ds = copernicusmarine.open_dataset(**request)
        # Load only bounded small request. Retain native vertical levels.
        ds.load()
        path = output/(product+".nc")
        ds.to_netcdf(path,engine="h5netcdf")
        report["data_sha256"]=hashlib.file_digest(path.open("rb"),"sha256").hexdigest()
        report["metadata"]={str(k):str(v) for k,v in ds.attrs.items()}
        times=pd.DatetimeIndex(ds.time.values)
        dates=times.normalize().unique()
        expected=pd.date_range(start,end,freq="D")
        missing=expected.difference(dates)
        report["time"]={"first":str(times.min()),"last":str(times.max()),
                        "unique_dates":len(dates),"expected_dates":len(expected),
                        "missing_dates":[str(v.date()) for v in missing]}
        report["coordinates"]={k:ds[k].values.tolist() for k in ["latitude","longitude","depth"] if k in ds.coords}
        report["variables"]={}
        for name in variables:
            if "depth" in ds[name].dims:
                # Summarize every native depth; never label nearest depth as requested exact depth.
                report["variables"][name]={str(float(depth)):summarize_array(ds[name].sel(depth=depth)) for depth in ds.depth.values}
            else: report["variables"][name]=summarize_array(ds[name])
        report["status"]="downloaded_complete_dates" if not len(missing) else "downloaded_partial_dates"
        code=0 if not len(missing) else 1
    except Exception as exc:
        # Error class is sufficient here; provider error strings can contain signed URLs.
        report.update(status="provider_error",error_type=type(exc).__name__)
        code=1
    (output/(product+".json")).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"product":product,"status":report["status"]}))
    return code


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--product",choices=PRODUCTS,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--start",default="2026-10-01")
    p.add_argument("--end",default="2026-10-30")
    a=p.parse_args()
    raise SystemExit(run(a.product,a.output,a.start,a.end))
