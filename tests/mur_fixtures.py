"""Campos MUR sintéticos: no simulan observaciones reales ni requieren NASA."""

from datetime import date, datetime, timezone

import numpy as np
import xarray as xr

import ingestion.fetch_mur as mur


TARGET = date(2026, 8, 28)
AS_OF = datetime(2026, 8, 29, 9, tzinfo=timezone.utc)


def dataset(*, sst=None, mask=None, error=None, dt=None, lats=None, lons=None,
            times=("2026-08-28T09:00:00",), stage="nrt", product_version=None,
            title=None, date_created="20260829T050000Z"):
    lats = np.asarray(lats if lats is not None else -12.50 + .01 * np.arange(7))
    lons = np.asarray(lons if lons is not None else -76.83 + .01 * np.arange(7))
    shape = (len(times), len(lats), len(lons))
    def values(value, default):
        return np.full(shape, default, dtype=float) if value is None else np.asarray(value, dtype=float)
    dims = ("time", "lat", "lon")
    return xr.Dataset({
        "analysed_sst": (dims, values(sst, 295.15), {
            "units": "kelvin", "standard_name": mur.STANDARD_NAME}),
        "analysis_error": (dims, values(error, .4), {"units": "kelvin"}),
        "mask": (dims, values(mask, 1), {
            "flag_masks": np.array([1, 2, 4, 8, 16], dtype=np.int8),
            "flag_meanings": mur.MASK_MEANINGS}),
        "dt_1km_data": (dims, values(dt, -7), {"units": "hours"}),
    }, coords={"time": np.asarray(times, dtype="datetime64[ns]"), "lat": lats, "lon": lons},
        attrs={"id": "MUR-JPL-L4-GLOB-v04.1",
               "product_version": product_version or (
                   mur.PRODUCT_VERSION if stage.casefold() == "final"
                   else mur.NRT_PRODUCT_VERSION),
               "processing_level": "L4",
               "title": title or f"Daily MUR SST, {stage} product",
               "date_created": date_created})


def bounds(ds, first=2, last=4):
    return (float(ds.lat[first]), float(ds.lat[last]),
            float(ds.lon[first]), float(ds.lon[last]))


def parse(ds, *, target=TARGET, as_of=AS_OF, mode=mur.MurMode.NRT_ONLY,
          max_age=72.0, field_bounds=None):
    return mur.mur_field_from_dataset(
        ds, *(bounds(ds) if field_bounds is None else field_bounds), target,
        options=mur.MurOptions(as_of, max_age, mode))


def write_dataset(ds, path):
    ds.to_netcdf(path, engine="h5netcdf")
    return path
