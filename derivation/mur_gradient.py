"""Gradiente centrado del MISMO campo MUR, con calidad local del soporte.

No impone umbral de frente ni presupone que 100% de SST L4 sea 100% de
observaciones infrarrojas recientes. No usa OSTIA ni combina temperaturas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

import numpy as np

from ingestion.fetch_mur import (
    DATASET_ID, NATIVE_GRID_STEP_DEG, NATIVE_UNITS, UNITS as SOURCE_UNITS,
    Matrix, MurBounds, MurField, MurOptions, MurProvenance, MurStatus,
    crop_grid, haversine_km,
)


ALGORITHM_VERSION = "mur_central_haversine_v1"
UNITS = "degree_Celsius km-1"
FORMULA = "sqrt((dSST/dx)^2 + (dSST/dy)^2)"
METHOD = "x:centrada;y:centrada"
BoolMatrix = tuple[tuple[bool | None, ...], ...]
IntMatrix = tuple[tuple[int | None, ...], ...]
SCOPE_WARNING = (
    "Gradiente experimental de un único campo MUR L4. Requiere centro y "
    "cuatro vecinos cardinales con SST y mask=1; no mezcla fechas, interpola, "
    "rellena ni usa diferencias unilaterales. Se deriva con halo antes de "
    "recortar. Espaciamiento de grilla y tamaño del soporte no son resolución "
    "efectiva. El máximo de analysis_error en cinco celdas no es incertidumbre "
    "del gradiente: se desconoce su covarianza. Los extremos de dt_1km_data "
    "conservan su signo y solo se informan si las cinco celdas lo tienen. "
    "No certifican edad, frescura ni calidad de todas las observaciones. "
    "Un gradiente calculable no demuestra un frente ni presencia de peces."
)


class MurGradientStatus(str, Enum):
    VALIDO = "valido"
    SIN_GRADIENTES = "sin_gradientes"
    FUENTE_SIN_DATOS = "fuente_sin_datos"
    FUENTE_ERROR = "fuente_error"


@dataclass(frozen=True)
class MurGradientField:
    requested_date: date
    requested_bounds: MurBounds
    query_bounds: MurBounds
    options: MurOptions
    source_nominal_product_date: date | None
    source_time_utc: datetime | None
    source_nominal_age_hours: float | None
    source_provenance: MurProvenance
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    gradient_c_per_km: Matrix
    eastward_gradient_c_per_km: Matrix
    northward_gradient_c_per_km: Matrix
    source_analysis_error_max_kelvin: Matrix
    analysis_error_support_complete: BoolMatrix
    source_dt_1km_min_hours: Matrix
    source_dt_1km_max_hours: Matrix
    dt_1km_support_complete: BoolMatrix
    n_dt_1km_support_cells: IntMatrix
    full_3x3_support: BoolMatrix
    support_adjacent_to_land: BoolMatrix
    data_edge: BoolMatrix
    method: tuple[tuple[str | None, ...], ...]
    n_source_valid_cells: int
    n_marine_cells: int
    n_gradient_cells: int
    n_gradient_cells_with_complete_dt_1km: int
    gradient_coverage_fraction: float | None
    coverage_denominator: str
    median_zonal_spacing_km: float | None
    median_meridional_spacing_km: float | None
    median_zonal_stencil_km: float | None
    median_meridional_stencil_km: float | None
    source_variable: str
    source_status: str
    source_reason: str | None
    source_error_type: str | None
    algorithm_version: str
    formula: str
    units: str
    data_scope: str
    field_is_operational_domain: bool
    scope_warning: str
    status: MurGradientStatus


def _array(matrix, rows, cols):
    if len(matrix) != rows or any(len(row) != cols for row in matrix):
        raise ValueError("Matriz y coordenadas del soporte MUR no coinciden.")
    return np.asarray([[np.nan if v is None else float(v) for v in row]
                       for row in matrix], dtype=np.float64).reshape(rows, cols)


def _validate_source(field):
    if (field.units != SOURCE_UNITS or field.native_units != NATIVE_UNITS
            or field.provenance.dataset_id != DATASET_ID):
        raise ValueError("La derivada requiere un campo MUR con unidades trazables.")
    support = field.derivation_support
    for coords, limit in ((support.latitudes, 90), (support.longitudes, 180)):
        values = np.asarray(coords, dtype=np.float64)
        if (values.ndim != 1 or not np.all(np.isfinite(values))
                or np.any(np.abs(values) > limit) or np.any(np.diff(values) <= 0)
                or (values.size > 1 and not np.allclose(
                    np.diff(values), NATIVE_GRID_STEP_DEG, rtol=.002, atol=1e-6))):
            raise ValueError("El soporte MUR debe tener ejes crecientes, finitos y nativos.")
    rows, cols = len(support.latitudes), len(support.longitudes)
    k, c, error, mask, dt = (_array(m, rows, cols) for m in (
        support.sst_kelvin, support.sst_celsius, support.analysis_error_kelvin,
        support.mask, support.dt_1km_hours))
    if not np.allclose(k - 273.15, c, atol=1e-9, rtol=0, equal_nan=True):
        raise ValueError("Kelvin y Celsius del campo fuente no son coherentes.")
    if field.grid != crop_grid(support, field.requested_bounds):
        raise ValueError("El campo no coincide con el recorte de su soporte.")
    return c, error, mask, dt


def derive_mur_gradient(field: MurField) -> MurGradientField:
    """Transformación pura: un campo diario, sin IO ni consultas al reloj."""
    if not isinstance(field, MurField):
        raise ValueError("field debe ser MurField.")
    output = field.grid
    rows, cols = len(output.latitudes), len(output.longitudes)
    def blank():
        return [[None] * cols for _ in range(rows)]
    east, north, magnitude = blank(), blank(), blank()
    errors, errors_complete = blank(), blank()
    dt_min, dt_max, dt_complete, dt_count = blank(), blank(), blank(), blank()
    square_ok, near_land, edges, methods = blank(), blank(), blank(), blank()
    spans_x, spans_y = [], []
    n_gradient = n_complete_dt = 0
    if field.status is MurStatus.ERROR:
        status = MurGradientStatus.FUENTE_ERROR
    elif field.status is MurStatus.SIN_DATOS:
        status = MurGradientStatus.FUENTE_SIN_DATOS
    elif field.status in {
        MurStatus.VALIDA_EN_FECHA_NOMINAL, MurStatus.VALIDA_RECIENTE, MurStatus.HISTORICA_FINAL,
    }:
        c, error, mask, dt = _validate_source(field)
        support = field.derivation_support
        lats, lons = support.latitudes, support.longitudes
        valid = np.isfinite(c) & (c > -273.15) & (mask == 1)
        valid_error = np.isfinite(error) & (error >= 0)
        valid_dt = np.isfinite(dt) & (dt >= -127) & (dt <= 127) & (dt == np.trunc(dt))
        lat_index = {v: i for i, v in enumerate(lats)}
        lon_index = {v: j for j, v in enumerate(lons)}
        def inside(i, j):
            return 0 <= i < len(lats) and 0 <= j < len(lons)
        for ri, lat in enumerate(output.latitudes):
            i = lat_index[lat]
            for rj, lon in enumerate(output.longitudes):
                j = lon_index[lon]
                if not valid[i, j]:
                    continue
                cross = ((i, j), (i-1, j), (i+1, j), (i, j-1), (i, j+1))
                square = [(a, b) for a in range(i-1, i+2) for b in range(j-1, j+2)]
                square_ok[ri][rj] = bool(all(inside(a, b) and valid[a, b] for a, b in square))
                edges[ri][rj] = not square_ok[ri][rj]
                coast = {(a+di, b+dj) for a, b in cross
                         for di in (-1, 0, 1) for dj in (-1, 0, 1)}
                if any(inside(a, b) and np.isfinite(mask[a, b]) and int(mask[a, b]) & 2
                       for a, b in coast):
                    near_land[ri][rj] = True
                elif all(inside(a, b) and mask[a, b] == 1 for a, b in coast):
                    near_land[ri][rj] = False
                if not all(inside(a, b) and valid[a, b] for a, b in cross):
                    continue
                dx = haversine_km(lat, lons[j-1], lat, lons[j+1])
                dy = haversine_km(lats[i-1], lon, lats[i+1], lon)
                if not np.isfinite(dx + dy) or min(dx, dy) <= 1e-9:
                    raise ValueError("Soporte geográfico degenerado para una derivada centrada.")
                gx = float((c[i, j+1] - c[i, j-1]) / dx)
                gy = float((c[i+1, j] - c[i-1, j]) / dy)
                east[ri][rj], north[ri][rj] = gx, gy
                magnitude[ri][rj] = float(np.hypot(gx, gy))
                methods[ri][rj] = METHOD
                errors_complete[ri][rj] = bool(all(valid_error[a, b] for a, b in cross))
                if errors_complete[ri][rj]:
                    errors[ri][rj] = float(max(error[a, b] for a, b in cross))
                count = sum(bool(valid_dt[a, b]) for a, b in cross)
                dt_count[ri][rj], dt_complete[ri][rj] = count, count == 5
                if count == 5:
                    dt_min[ri][rj] = float(min(dt[a, b] for a, b in cross))
                    dt_max[ri][rj] = float(max(dt[a, b] for a, b in cross))
                    n_complete_dt += 1
                spans_x.append(dx)
                spans_y.append(dy)
                n_gradient += 1
        status = MurGradientStatus.VALIDO if n_gradient else MurGradientStatus.SIN_GRADIENTES
    else:
        raise ValueError("Estado de fuente MUR desconocido.")
    def matrix(values):
        return tuple(tuple(row) for row in values)
    return MurGradientField(
        requested_date=field.requested_date, requested_bounds=field.requested_bounds,
        query_bounds=field.query_bounds, options=field.options,
        source_nominal_product_date=field.nominal_product_date, source_time_utc=field.time_utc,
        source_nominal_age_hours=field.nominal_age_hours, source_provenance=field.provenance,
        latitudes=output.latitudes, longitudes=output.longitudes,
        gradient_c_per_km=matrix(magnitude), eastward_gradient_c_per_km=matrix(east),
        northward_gradient_c_per_km=matrix(north), source_analysis_error_max_kelvin=matrix(errors),
        analysis_error_support_complete=matrix(errors_complete),
        source_dt_1km_min_hours=matrix(dt_min), source_dt_1km_max_hours=matrix(dt_max),
        dt_1km_support_complete=matrix(dt_complete), n_dt_1km_support_cells=matrix(dt_count),
        full_3x3_support=matrix(square_ok), support_adjacent_to_land=matrix(near_land),
        data_edge=matrix(edges), method=matrix(methods),
        n_source_valid_cells=field.n_valid_cells, n_marine_cells=field.n_marine_cells,
        n_gradient_cells=n_gradient, n_gradient_cells_with_complete_dt_1km=n_complete_dt,
        gradient_coverage_fraction=n_gradient / field.n_marine_cells if field.n_marine_cells else None,
        coverage_denominator=field.coverage_denominator,
        median_zonal_spacing_km=field.median_zonal_spacing_km,
        median_meridional_spacing_km=field.median_meridional_spacing_km,
        median_zonal_stencil_km=float(np.median(spans_x)) if spans_x else None,
        median_meridional_stencil_km=float(np.median(spans_y)) if spans_y else None,
        source_variable="analysed_sst", source_status=field.status.value,
        source_reason=field.reason, source_error_type=field.error_type,
        algorithm_version=ALGORITHM_VERSION, formula=FORMULA, units=UNITS,
        data_scope="sst_mur_regional_gradient", field_is_operational_domain=False,
        scope_warning=SCOPE_WARNING, status=status,
    )
