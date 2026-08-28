"""Gradiente térmico derivado del campo diario OSTIA.

La salida es una transformación matemática de un único campo OSTIA. No es una
observación nativa, no aplica umbrales de "frente fuerte" y no afirma presencia
de peces. Los bordes utilizan diferencias unilaterales cuando existe el vecino
necesario; el interior utiliza diferencias centradas. Los faltantes nunca se
rellenan y una componente espacial sin vecinos suficientes deja esa celda sin
gradiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from math import asin, cos, radians, sin, sqrt

import numpy as np

from ingestion.fetch_ostia import (
    VARIABLE_SST,
    Matrix,
    OstiaField,
    OstiaStatus,
    fetch_ostia_field,
)

ALGORITHM_VERSION = "finite_difference_haversine_v1"
FORMULA = "sqrt((dT/dx)^2 + (dT/dy)^2), con diferencias centradas o unilaterales trazables"
UNITS = "degree_Celsius km-1"
DATA_SCOPE = "gradiente_termico_ostia_regional_derivado"
SCOPE_WARNING = (
    "Gradiente térmico calculado por PredictaMAR a partir de un único campo "
    "OSTIA L4 diario gap-free. No es una observación nativa, no detecta "
    "cardúmenes y no incorpora umbrales de favorabilidad. OSTIA es un análisis "
    "espacialmente suavizado y su resolución nominal de 0.05 grados describe "
    "contexto regional, no un frente dentro de cada zona de faena. Las "
    "diferencias centradas y unilaterales usan soportes espaciales distintos; "
    "sus magnitudes no son directamente comparables entre celdas sin consultar "
    "el método trazado. Los faltantes no se rellenan."
)


class ThermalFrontStatus(str, Enum):
    VALIDO = "valido"
    SIN_GRADIENTES = "sin_gradientes"
    FUENTE_SIN_DATOS = "fuente_sin_datos"


@dataclass(frozen=True)
class ThermalFrontField:
    requested_date: date
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float
    source_nominal_product_date: date | None
    source_time_utc: datetime | None
    source_time_local: datetime | None
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    gradient_c_per_km: Matrix
    eastward_gradient_c_per_km: Matrix
    northward_gradient_c_per_km: Matrix
    source_error_max_c: Matrix
    method: tuple[tuple[str | None, ...], ...]
    n_source_valid_cells: int
    n_gradient_cells: int
    gradient_coverage_fraction: float | None
    median_zonal_resolution_km: float | None
    median_meridional_resolution_km: float | None
    source_product_id: str
    source_dataset_id: str
    source_variable: str
    algorithm_version: str
    formula: str
    units: str
    data_scope: str
    scope_warning: str
    status: ThermalFrontStatus


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def _numeric_matrix(matrix: Matrix, rows: int, cols: int, name: str) -> np.ndarray:
    if len(matrix) != rows or any(len(row) != cols for row in matrix):
        raise ValueError(f"{name} no coincide con la geometría declarada del campo OSTIA.")
    return np.asarray(
        [[np.nan if value is None else float(value) for value in row] for row in matrix],
        dtype=float,
    )


def _validate_geometry(field: OstiaField) -> tuple[np.ndarray, np.ndarray]:
    lats = np.asarray(field.latitudes, dtype=float)
    lons = np.asarray(field.longitudes, dtype=float)
    if lats.size and (not np.all(np.isfinite(lats)) or np.any(np.diff(lats) <= 0)):
        raise ValueError("Las latitudes OSTIA deben ser finitas y estrictamente crecientes.")
    if lons.size and (not np.all(np.isfinite(lons)) or np.any(np.diff(lons) <= 0)):
        raise ValueError("Las longitudes OSTIA deben ser finitas y estrictamente crecientes.")
    return lats, lons


def _empty_like(field: OstiaField, status: ThermalFrontStatus) -> ThermalFrontField:
    rows, cols = len(field.latitudes), len(field.longitudes)
    none_matrix: Matrix = tuple(tuple(None for _ in range(cols)) for _ in range(rows))
    method = tuple(tuple(None for _ in range(cols)) for _ in range(rows))
    return ThermalFrontField(
        requested_date=field.requested_date,
        minimum_latitude=field.minimum_latitude,
        maximum_latitude=field.maximum_latitude,
        minimum_longitude=field.minimum_longitude,
        maximum_longitude=field.maximum_longitude,
        source_nominal_product_date=field.nominal_product_date,
        source_time_utc=field.time_utc,
        source_time_local=field.time_local,
        latitudes=field.latitudes,
        longitudes=field.longitudes,
        gradient_c_per_km=none_matrix,
        eastward_gradient_c_per_km=none_matrix,
        northward_gradient_c_per_km=none_matrix,
        source_error_max_c=none_matrix,
        method=method,
        n_source_valid_cells=field.n_valid_cells,
        n_gradient_cells=0,
        gradient_coverage_fraction=(0.0 if field.n_valid_cells else None),
        median_zonal_resolution_km=None,
        median_meridional_resolution_km=None,
        source_product_id=field.product_id,
        source_dataset_id=field.dataset_id,
        source_variable=VARIABLE_SST,
        algorithm_version=ALGORITHM_VERSION,
        formula=FORMULA,
        units=UNITS,
        data_scope=DATA_SCOPE,
        scope_warning=SCOPE_WARNING,
        status=status,
    )


def _axis_derivative(
    values: np.ndarray,
    errors: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    i: int,
    j: int,
    axis: int,
) -> tuple[float, str, tuple[float, ...]] | None:
    center = values[i, j]
    if not np.isfinite(center):
        return None

    length = values.shape[axis]
    index = i if axis == 0 else j
    before = index - 1 if index > 0 else None
    after = index + 1 if index + 1 < length else None

    def value_at(position: int) -> float:
        return values[position, j] if axis == 0 else values[i, position]

    def error_at(position: int) -> float:
        return errors[position, j] if axis == 0 else errors[i, position]

    before_ok = before is not None and np.isfinite(value_at(before))
    after_ok = after is not None and np.isfinite(value_at(after))

    if before_ok and after_ok:
        low, high, method = before, after, "centrada"
        delta = value_at(high) - value_at(low)
    elif after_ok:
        low, high, method = index, after, "adelante"
        delta = value_at(high) - center
    elif before_ok:
        low, high, method = before, index, "atras"
        delta = center - value_at(low)
    else:
        return None

    if axis == 0:
        distance = _haversine_km(lats[low], lons[j], lats[high], lons[j])
    else:
        distance = _haversine_km(lats[i], lons[low], lats[i], lons[high])
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError("La grilla contiene vecinos sin separación geográfica positiva.")

    source_errors = []
    for pos in {index, low, high}:
        error_value = error_at(pos)
        if np.isfinite(error_value) and error_value >= 0:
            source_errors.append(float(error_value))
    return float(delta / distance), method, tuple(source_errors)


def _matrix_tuple(values: np.ndarray) -> Matrix:
    return tuple(
        tuple(float(value) if np.isfinite(value) else None for value in row)
        for row in values
    )


def _median_grid_resolution(lats: np.ndarray, lons: np.ndarray) -> tuple[float | None, float | None]:
    zonal = [
        _haversine_km(lat, lons[j], lat, lons[j + 1])
        for lat in lats
        for j in range(max(0, len(lons) - 1))
    ]
    meridional = [
        _haversine_km(lats[i], lon, lats[i + 1], lon)
        for lon in lons
        for i in range(max(0, len(lats) - 1))
    ]
    return (
        float(np.median(zonal)) if zonal else None,
        float(np.median(meridional)) if meridional else None,
    )


def derive_thermal_front(field: OstiaField) -> ThermalFrontField:
    """Calcula el módulo del gradiente térmico para cada celda admisible."""
    if field.status == OstiaStatus.SIN_DATOS:
        return _empty_like(field, ThermalFrontStatus.FUENTE_SIN_DATOS)

    lats, lons = _validate_geometry(field)
    rows, cols = len(lats), len(lons)
    values = _numeric_matrix(field.sst_celsius, rows, cols, "sst_celsius")
    errors = _numeric_matrix(field.analysis_error_kelvin, rows, cols, "analysis_error_kelvin")

    east = np.full((rows, cols), np.nan, dtype=float)
    north = np.full((rows, cols), np.nan, dtype=float)
    magnitude = np.full((rows, cols), np.nan, dtype=float)
    source_error = np.full((rows, cols), np.nan, dtype=float)
    methods: list[list[str | None]] = [[None for _ in range(cols)] for _ in range(rows)]

    for i in range(rows):
        for j in range(cols):
            dx = _axis_derivative(values, errors, lats, lons, i, j, axis=1)
            dy = _axis_derivative(values, errors, lats, lons, i, j, axis=0)
            if dx is None or dy is None:
                continue
            east[i, j], method_x, errors_x = dx
            north[i, j], method_y, errors_y = dy
            magnitude[i, j] = float(np.hypot(east[i, j], north[i, j]))
            all_errors = errors_x + errors_y
            if all_errors:
                source_error[i, j] = max(all_errors)
            methods[i][j] = f"x:{method_x};y:{method_y}"

    n_source = int(np.isfinite(values).sum())
    n_gradient = int(np.isfinite(magnitude).sum())
    zonal_km, meridional_km = _median_grid_resolution(lats, lons)
    result = ThermalFrontField(
        requested_date=field.requested_date,
        minimum_latitude=field.minimum_latitude,
        maximum_latitude=field.maximum_latitude,
        minimum_longitude=field.minimum_longitude,
        maximum_longitude=field.maximum_longitude,
        source_nominal_product_date=field.nominal_product_date,
        source_time_utc=field.time_utc,
        source_time_local=field.time_local,
        latitudes=field.latitudes,
        longitudes=field.longitudes,
        gradient_c_per_km=_matrix_tuple(magnitude),
        eastward_gradient_c_per_km=_matrix_tuple(east),
        northward_gradient_c_per_km=_matrix_tuple(north),
        source_error_max_c=_matrix_tuple(source_error),
        method=tuple(tuple(row) for row in methods),
        n_source_valid_cells=n_source,
        n_gradient_cells=n_gradient,
        gradient_coverage_fraction=(n_gradient / n_source if n_source else None),
        median_zonal_resolution_km=zonal_km,
        median_meridional_resolution_km=meridional_km,
        source_product_id=field.product_id,
        source_dataset_id=field.dataset_id,
        source_variable=VARIABLE_SST,
        algorithm_version=ALGORITHM_VERSION,
        formula=FORMULA,
        units=UNITS,
        data_scope=DATA_SCOPE,
        scope_warning=SCOPE_WARNING,
        status=(ThermalFrontStatus.VALIDO if n_gradient else ThermalFrontStatus.SIN_GRADIENTES),
    )
    return result


def fetch_thermal_front(
    minimum_latitude: float,
    maximum_latitude: float,
    minimum_longitude: float,
    maximum_longitude: float,
    target_date: date,
) -> ThermalFrontField:
    """Obtiene OSTIA y deriva el frente manteniendo una única fecha y fuente."""
    source = fetch_ostia_field(
        minimum_latitude,
        maximum_latitude,
        minimum_longitude,
        maximum_longitude,
        target_date,
    )
    return derive_thermal_front(source)
