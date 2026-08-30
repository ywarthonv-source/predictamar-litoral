"""Gradiente OLCI centrado y enmascarado: no clasifica frentes ni pesca."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

import numpy as np

from ingestion.fetch_chlorophyll_field import (
    DATASET_ID, MAX_CHL_MG_M3, MAX_UNCERTAINTY_PCT, NATIVE_GRID_STEP_DEG,
    UNITS as SOURCE_UNITS,
    ChlorophyllBounds, ChlorophyllField, ChlorophyllFieldStatus, ChlorophyllOptions,
    Matrix, crop_grid, haversine_km,
)


ALGORITHM_VERSION = "chlorophyll_central_haversine_v1"
UNITS = "milligram m-3 km-1"
FORMULA = "sqrt((dCHL/dx)^2 + (dCHL/dy)^2)"
METHOD = "x:centrada;y:centrada"
SCOPE_WARNING = (
    "Gradiente experimental derivado de un único campo OLCI L3. "
    "Exige centro y cuatro vecinos cardinales válidos; no interpola, rellena, "
    "mezcla fechas ni aplica diferencias unilaterales. Se calcula con el halo "
    "y se recorta al campo solicitado. El máximo de incertidumbre del soporte "
    "no es incertidumbre del gradiente ni probabilidad. Las advertencias de "
    "tierra, huecos y soporte 3x3 no certifican calidad. Un gradiente calculable "
    "no confirma un frente, una zona favorable ni presencia de peces."
)
BoolMatrix = tuple[tuple[bool | None, ...], ...]


class ChlorophyllGradientStatus(str, Enum):
    VALIDO = "valido"
    SIN_GRADIENTES = "sin_gradientes"
    FUENTE_SIN_DATOS = "fuente_sin_datos"
    FUENTE_ERROR = "fuente_error"


@dataclass(frozen=True)
class ChlorophyllGradientField:
    requested_date: date
    requested_bounds: ChlorophyllBounds
    query_bounds: ChlorophyllBounds
    options: ChlorophyllOptions
    source_nominal_product_date: date | None
    source_time_utc: datetime | None
    source_nominal_age_hours: float | None
    source_retrieved_at_utc: datetime | None
    availability_as_of_verified: bool
    availability_basis: str
    source_access: str
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    gradient_mg_m3_per_km: Matrix
    eastward_gradient_mg_m3_per_km: Matrix
    northward_gradient_mg_m3_per_km: Matrix
    source_uncertainty_max_pct: Matrix
    uncertainty_support_complete: BoolMatrix
    full_3x3_support: BoolMatrix
    support_adjacent_to_land: BoolMatrix
    data_edge: BoolMatrix
    method: tuple[tuple[str | None, ...], ...]
    n_source_valid_cells: int
    n_marine_cells: int
    n_gradient_cells: int
    gradient_coverage_fraction: float | None
    coverage_denominator: str
    median_zonal_resolution_km: float | None
    median_meridional_resolution_km: float | None
    median_zonal_stencil_km: float | None
    median_meridional_stencil_km: float | None
    source_product_id: str
    source_dataset_id: str
    source_requested_dataset_version: str
    source_dataset_version: str | None
    source_dataset_part: str | None
    source_version_basis: str
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
    status: ChlorophyllGradientStatus


def _array(matrix, rows, cols):
    if len(matrix) != rows or any(len(row) != cols for row in matrix):
        raise ValueError("Matriz y coordenadas del soporte OLCI no coinciden.")
    return np.asarray([[np.nan if v is None else float(v) for v in row]
                       for row in matrix], dtype=np.float64).reshape(rows, cols)


def _validate_source(field):
    if field.units != SOURCE_UNITS or field.dataset_id != DATASET_ID:
        raise ValueError("La derivada requiere CHL OLCI en sus unidades nativas.")
    support = field.derivation_support
    for coordinates, limit in ((support.latitudes, 90), (support.longitudes, 180)):
        values = np.asarray(coordinates, dtype=np.float64)
        if (
            values.ndim != 1 or not np.all(np.isfinite(values))
            or np.any(np.abs(values) > limit) or np.any(np.diff(values) <= 0)
            or (values.size > 1 and not np.allclose(
                np.diff(values), NATIVE_GRID_STEP_DEG, rtol=.005, atol=1e-6))
        ):
            raise ValueError("El soporte OLCI debe conservar ejes crecientes, finitos y nativos.")
    rows, cols = len(support.latitudes), len(support.longitudes)
    c, u, f = (_array(m, rows, cols) for m in (
        support.chlorophyll_mg_m3, support.uncertainty_pct, support.flags))
    if field.grid != crop_grid(support, field.requested_bounds):
        raise ValueError("El campo entregado no coincide con el recorte de su soporte.")
    return c, u, f


def derive_chlorophyll_gradient(field: ChlorophyllField) -> ChlorophyllGradientField:
    """Transformación local pura; no consulta ninguna fuente ni el reloj."""
    if not isinstance(field, ChlorophyllField):
        raise ValueError("field debe ser ChlorophyllField.")
    output = field.grid
    rows, cols = len(output.latitudes), len(output.longitudes)
    east = [[None] * cols for _ in range(rows)]
    north = [[None] * cols for _ in range(rows)]
    magnitude = [[None] * cols for _ in range(rows)]
    uncertainty = [[None] * cols for _ in range(rows)]
    unc_complete = [[None] * cols for _ in range(rows)]
    full_3x3 = [[None] * cols for _ in range(rows)]
    near_land = [[None] * cols for _ in range(rows)]
    edges = [[None] * cols for _ in range(rows)]
    methods = [[None] * cols for _ in range(rows)]
    spans_x, spans_y = [], []
    n_gradient = 0
    if field.status == ChlorophyllFieldStatus.ERROR:
        status = ChlorophyllGradientStatus.FUENTE_ERROR
    elif field.status == ChlorophyllFieldStatus.SIN_DATOS:
        status = ChlorophyllGradientStatus.FUENTE_SIN_DATOS
    elif field.status in {
        ChlorophyllFieldStatus.VALIDA_EN_FECHA_NOMINAL,
        ChlorophyllFieldStatus.VALIDA_RECIENTE,
    }:
        c, u, flags = _validate_source(field)
        support = field.derivation_support
        lats, lons = support.latitudes, support.longitudes
        valid = np.isfinite(c) & (c > 0) & (c <= MAX_CHL_MG_M3) & (flags == 0)
        valid_u = np.isfinite(u) & (u >= 0) & (u <= MAX_UNCERTAINTY_PCT + 1e-5)
        lat_indices = {v: i for i, v in enumerate(lats)}
        lon_indices = {v: j for j, v in enumerate(lons)}

        def inside(a, b):
            return 0 <= a < len(lats) and 0 <= b < len(lons)

        for ri, lat in enumerate(output.latitudes):
            i = lat_indices[lat]
            for rj, lon in enumerate(output.longitudes):
                j = lon_indices[lon]
                if not valid[i, j]:
                    continue
                cross = ((i, j), (i-1, j), (i+1, j), (i, j-1), (i, j+1))
                square = [(a, b) for a in range(i-1, i+2) for b in range(j-1, j+2)]
                complete_square = all(inside(a, b) and valid[a, b] for a, b in square)
                full_3x3[ri][rj] = bool(complete_square)
                edges[ri][rj] = not complete_square
                coast_support = {
                    (a+di, b+dj) for a, b in cross
                    for di in (-1, 0, 1) for dj in (-1, 0, 1)
                }
                if any(inside(a, b) and flags[a, b] == 1 for a, b in coast_support):
                    near_land[ri][rj] = True
                elif all(inside(a, b) and flags[a, b] == 0 for a, b in coast_support):
                    near_land[ri][rj] = False
                # None significa que el entorno costero no se pudo determinar.
                if not all(inside(a, b) and valid[a, b] for a, b in cross):
                    continue
                dx = haversine_km(lat, lons[j-1], lat, lons[j+1])
                dy = haversine_km(lats[i-1], lon, lats[i+1], lon)
                if not np.isfinite(dx + dy) or min(dx, dy) <= 1e-9:
                    raise ValueError("Soporte geográfico degenerado para una diferencia centrada.")
                gx = float((c[i, j+1] - c[i, j-1]) / dx)
                gy = float((c[i+1, j] - c[i-1, j]) / dy)
                east[ri][rj], north[ri][rj] = gx, gy
                magnitude[ri][rj] = float(np.hypot(gx, gy))
                methods[ri][rj] = METHOD
                unc_complete[ri][rj] = bool(all(valid_u[a, b] for a, b in cross))
                if unc_complete[ri][rj]:
                    uncertainty[ri][rj] = float(max(u[a, b] for a, b in cross))
                spans_x.append(dx)
                spans_y.append(dy)
                n_gradient += 1
        status = (ChlorophyllGradientStatus.VALIDO if n_gradient
                  else ChlorophyllGradientStatus.SIN_GRADIENTES)
    else:
        raise ValueError("Estado de fuente OLCI desconocido.")

    def matrix(values):
        return tuple(tuple(row) for row in values)

    return ChlorophyllGradientField(
        requested_date=field.requested_date, requested_bounds=field.requested_bounds,
        query_bounds=field.query_bounds, options=field.options,
        source_nominal_product_date=field.nominal_product_date, source_time_utc=field.time_utc,
        source_nominal_age_hours=field.nominal_age_hours,
        source_retrieved_at_utc=field.retrieved_at_utc,
        availability_as_of_verified=field.availability_as_of_verified,
        availability_basis=field.availability_basis, source_access=field.source_access,
        latitudes=output.latitudes, longitudes=output.longitudes,
        gradient_mg_m3_per_km=matrix(magnitude),
        eastward_gradient_mg_m3_per_km=matrix(east),
        northward_gradient_mg_m3_per_km=matrix(north),
        source_uncertainty_max_pct=matrix(uncertainty),
        uncertainty_support_complete=matrix(unc_complete), full_3x3_support=matrix(full_3x3),
        support_adjacent_to_land=matrix(near_land), data_edge=matrix(edges), method=matrix(methods),
        n_source_valid_cells=field.n_valid_cells, n_marine_cells=field.n_marine_cells,
        n_gradient_cells=n_gradient,
        gradient_coverage_fraction=n_gradient / field.n_marine_cells if field.n_marine_cells else None,
        coverage_denominator=field.coverage_denominator,
        median_zonal_resolution_km=field.median_zonal_resolution_km,
        median_meridional_resolution_km=field.median_meridional_resolution_km,
        median_zonal_stencil_km=float(np.median(spans_x)) if spans_x else None,
        median_meridional_stencil_km=float(np.median(spans_y)) if spans_y else None,
        source_product_id=field.product_id, source_dataset_id=field.dataset_id,
        source_requested_dataset_version=field.requested_dataset_version,
        source_dataset_version=field.dataset_version, source_dataset_part=field.dataset_part,
        source_version_basis=field.version_basis, source_variable="CHL", source_status=field.status.value,
        source_reason=field.reason, source_error_type=field.error_type,
        algorithm_version=ALGORITHM_VERSION, formula=FORMULA, units=UNITS,
        data_scope="chlorophyll_olci_regional_gradient", field_is_operational_domain=False,
        scope_warning=SCOPE_WARNING, status=status,
    )
