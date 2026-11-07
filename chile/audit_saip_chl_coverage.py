"""Bounded ARCO check for the fixed Portales reference pixel."""
import json
from datetime import date, timedelta
import numpy as np
from audit_arco_coverage_2024_2025 import read_grid
from audit_arco_historical_probe import get
from audit_arco_time_axes import DATASETS, ROOT, read_axis

CELL = (-33.020835876464844, -71.60416412353516)


def audit(item, start, end):
    product, version = item
    requests = []
    source = json.loads(get(f"{ROOT}{product}/{version}/dataset.stac.json", requests))
    base = source["assets"]["geoChunked"]["href"].rstrip("/")
    metadata = json.loads(get(base + "/.zmetadata", requests))["metadata"]
    attrs = metadata["time/.zattrs"]
    if attrs["units"] != "days since 1900-01-01":
        raise ValueError("Unexpected time axis units")
    axes = {name: read_axis(base, metadata, name, requests)
            for name in ("latitude", "longitude")}
    y, x = [np.flatnonzero(axes[name] == coord)
            for name, coord in zip(axes, CELL)]
    if len(y) != 1 or len(x) != 1:
        raise ValueError("Reference pixel is absent or ambiguous")
    spec = metadata["time/.zarray"]
    begin = attrs.get("validStartIndex", 0)
    if begin:
        import numcodecs
        chunk_size = spec["chunks"][0]
        values = np.concatenate([
            np.frombuffer(numcodecs.get_codec(spec["compressor"]).decode(
                get(f"{base}/time/{i}", requests)), dtype=spec["dtype"])
            for i in range(begin // chunk_size,
                           (spec["shape"][0] + chunk_size - 1) // chunk_size)
        ])
        values = values[begin % chunk_size:begin % chunk_size + spec["shape"][0] - begin]
    else:
        values = read_axis(base, metadata, "time", requests)
    dates = np.array([(date(1900, 1, 1) + timedelta(days=float(v))).isoformat()
                      for v in values])
    if not np.all(np.diff(values) == 1):
        raise ValueError("Unexpected discontinuity on valid time axis")
    mask = (dates >= start) & (dates <= end)
    positions = np.flatnonzero(mask) + begin
    field = read_grid(base, metadata, positions, y, x, requests)[:, 0, 0]
    return {
        "version": version, "cell": CELL,
        "time_metadata": {key: attrs.get(key) for key in ("validStartDate", "validStartIndex")},
        "valid_axis_first": dates[0], "valid_axis_last": dates[-1],
        "units": metadata["CHL/.zattrs"]["units"], "manifest": requests,
        "chl": {day: float(value) if np.isfinite(value) else None
                for day, value in zip(dates[mask], field)},
    }


if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [executor.submit(audit, DATASETS[i], "2026-01-01", "2026-11-03")
                for i in (2, 0)]
        print(json.dumps([job.result() for job in jobs], indent=2, allow_nan=False))
