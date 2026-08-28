"""Par térmico vertical de modelo para PredictaMAR Litoral.

Este módulo implementa conjuntamente las variables ``temperature_10m`` y
``delta_sst_t10``. No llama primero al fetcher superficial y después a otro
fetcher: abre UNA sola vez el mismo dataset de temperatura potencial y exige
que superficie y profundidad procedan del mismo timestamp y de la misma celda.

Fuente oficial:
  producto        GLOBAL_ANALYSISFORECAST_PHY_001_024
  dataset         cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i
  versión/parte   202406 / default
  variable        thetao (degree_Celsius)
  cadencia        instantánea cada 6 horas

El eje oficial tiene 50 niveles. En la versión declarada, el nivel superficial
es aproximadamente 0.494025 m y el más próximo a 10 m es aproximadamente
9.572997 m. El código NO sustituye silenciosamente 9.572997 por 10.0: selecciona
el nivel nativo más cercano, comprueba que esté dentro de una tolerancia de
identidad de 1.5 m y expone siempre ambas profundidades efectivas.

``delta_sst_t10_celsius`` es una DIFERENCIA de temperatura:

    thetao_superficie - thetao_nivel_cercano_a_10m

Su unidad es degree_Celsius. No es un gradiente en degree_Celsius/m, no detecta
por sí sola una termoclina, no detecta cardúmenes y no activa scoring.

Diseño fail-safe:
  * si falta cualquiera de los dos niveles, el par se descarta completo;
  * si uno de los valores es NaN, el par se descarta completo;
  * no se mezclan timestamps, celdas ni fallbacks independientes;
  * no se interpola vertical, espacial ni temporalmente;
  * los errores de uso se propagan y los fallos de fuente producen SIN_DATOS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from numbers import Real

import copernicusmarine
import pandas as pd

from ingestion.fetch_temperature import (
    DATASET_ID,
    MAX_TEMPORAL_OFFSET_HOURS,
    MAX_VALID_CELL_DISTANCE_KM,
    TZ_PUCUSANA,
    VARIABLE,
    _haversine_km,
    _local_window_to_utc,
    _temporal_offset_hours,
)

logger = logging.getLogger(__name__)

PRODUCT_ID = "GLOBAL_ANALYSISFORECAST_PHY_001_024"
DATASET_VERSION = "202406"
DATASET_PART = "default"

SURFACE_DEPTH_REQUESTED_M = 0.0
TEMPERATURE_10M_DEPTH_REQUESTED_M = 10.0

# Se omite minimum_depth para no solicitar 0.0 m, que está fuera del eje real.
# El techo incluye el nivel oficial 11.405 m y permite elegir dinámicamente el
# nivel nativo más próximo a 10 m sin descargar los 50 niveles.
DEPTH_QUERY_MAX_M = 12.0

# Regla de identidad de la variable, no umbral pesquero. Evita llamar "~10 m"
# a un nivel alejado si el esquema del producto cambia o llega incompleto.
MAX_TARGET_DEPTH_DEVIATION_M = 1.5

OFFICIAL_SURFACE_DEPTH_M = 0.49402499198913574
OFFICIAL_NEAREST_10M_DEPTH_M = 9.572997093200684

UNITS_TEMPERATURE = "degree_Celsius"
DELTA_FORMULA = "thetao_surface - thetao_nearest_native_10m"
ALGORITHM_VERSION = "vertical_thermal_pair_v1"
DATA_SCOPE = "estructura_termica_vertical_regional_modelo"
DATA_SCOPE_WARNING = (
    "Par térmico vertical regional de referencia obtenido del modelo global "
    "Copernicus a 1/12 de grado (aprox. 8-9 km). Superficie y nivel cercano "
    "a 10 m proceden siempre del mismo dataset, versión, parte, timestamp y "
    "celda; las profundidades nativas efectivas se declaran en la salida. "
    "PredictaMAR no interpola niveles ni rellena valores ausentes. "
    "delta_sst_t10 es thetao de superficie menos thetao del nivel nativo más "
    "cercano a 10 m, en degree_Celsius: es una diferencia, no un gradiente "
    "vertical ni una detección de termoclina. El producto aporta contexto "
    "regional, no una medición in situ en Pucusana; no detecta cardúmenes y "
    "no activa scoring."
)


class VerticalThermalStatus(str, Enum):
    VALIDA_EN_VENTANA = "valida_en_ventana"
    VALIDA_CERCANA_EN_TIEMPO = "valida_cercana_en_tiempo"
    SIN_DATOS = "sin_datos"


@dataclass(frozen=True)
class VerticalThermalSample:
    time_utc: datetime
    time_local: datetime
    surface_temperature_celsius: float
    temperature_10m_celsius: float
    delta_sst_t10_celsius: float
    inside_requested_window: bool
    temporal_offset_hours: float


@dataclass(frozen=True)
class VerticalThermalReading:
    lat: float
    lon: float
    date: date
    hour_start_local: int
    hour_end_local: int
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    samples: tuple[VerticalThermalSample, ...] = field(default_factory=tuple)
    n_native_times_in_window: int = 0
    n_pairs: int = 0
    n_missing_pairs: int = 0
    coverage_fraction: float | None = None
    surface_depth_requested_m: float = SURFACE_DEPTH_REQUESTED_M
    surface_depth_actual_m: float | None = None
    temperature_10m_depth_requested_m: float = TEMPERATURE_10M_DEPTH_REQUESTED_M
    temperature_10m_depth_actual_m: float | None = None
    vertical_separation_m: float | None = None
    cell_lat: float | None = None
    cell_lon: float | None = None
    distance_km: float | None = None
    product_id: str = PRODUCT_ID
    dataset_id: str = DATASET_ID
    dataset_version: str = DATASET_VERSION
    dataset_part: str = DATASET_PART
    variable: str = VARIABLE
    units_temperature: str = UNITS_TEMPERATURE
    delta_formula: str = DELTA_FORMULA
    algorithm_version: str = ALGORITHM_VERSION
    data_scope: str = DATA_SCOPE
    scope_warning: str = DATA_SCOPE_WARNING
    status: VerticalThermalStatus = VerticalThermalStatus.SIN_DATOS


def _validate_inputs(lat: float, lon: float, target_date: date) -> None:
    for name, value, lower, upper in (
        ("lat", lat, -90.0, 90.0),
        ("lon", lon, -180.0, 180.0),
    ):
        if (
            not isinstance(value, Real)
            or isinstance(value, bool)
            or not isfinite(float(value))
            or not lower <= float(value) <= upper
        ):
            raise ValueError(
                f"{name} inválida: {value!r}. Debe ser un número finito entre "
                f"{lower:g} y {upper:g}."
            )
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError("target_date debe ser datetime.date.")


def _empty_reading(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int,
    hour_end: int,
    window_start_utc: datetime | None,
    window_end_utc: datetime | None,
    n_native_times_in_window: int = 0,
) -> VerticalThermalReading:
    return VerticalThermalReading(
        lat=float(lat),
        lon=float(lon),
        date=target_date,
        hour_start_local=hour_start,
        hour_end_local=hour_end,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        samples=(),
        n_native_times_in_window=n_native_times_in_window,
        n_pairs=0,
        n_missing_pairs=n_native_times_in_window,
        coverage_fraction=0.0 if n_native_times_in_window > 0 else None,
        surface_depth_actual_m=None,
        temperature_10m_depth_actual_m=None,
        vertical_separation_m=None,
        cell_lat=None,
        cell_lon=None,
        distance_km=None,
        status=VerticalThermalStatus.SIN_DATOS,
    )


def _select_native_depths(depth_values) -> tuple[float, float] | None:
    """Elige superficie y nivel nativo más próximo a 10 m, sin interpolar."""
    finite_depths = sorted(
        {float(value) for value in depth_values if isfinite(float(value))}
    )
    if len(finite_depths) < 2:
        return None
    surface = finite_depths[0]
    candidates = [value for value in finite_depths if value > surface]
    if not candidates:
        return None
    target = min(
        candidates,
        key=lambda value: (abs(value - TEMPERATURE_10M_DEPTH_REQUESTED_M), value),
    )
    if abs(target - TEMPERATURE_10M_DEPTH_REQUESTED_M) > MAX_TARGET_DEPTH_DEVIATION_M:
        return None
    return surface, target


def _cell_candidates(da, lat: float, lon: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for lat_value in da.latitude.values:
        for lon_value in da.longitude.values:
            cell_lat = float(lat_value)
            cell_lon = float(lon_value)
            distance = _haversine_km(lat, lon, cell_lat, cell_lon)
            if distance <= MAX_VALID_CELL_DISTANCE_KM:
                out.append((distance, cell_lat, cell_lon))
    out.sort(key=lambda item: (item[0], item[1], item[2]))
    return out


def _native_pair_at(
    da,
    t_native,
    surface_depth: float,
    target_depth: float,
    cell_lat: float,
    cell_lon: float,
) -> tuple[float, float] | None:
    """Devuelve dos valores nativos completos o None; nunca completa medio par."""
    surface = float(
        da.sel(
            time=t_native,
            depth=surface_depth,
            latitude=cell_lat,
            longitude=cell_lon,
        ).values
    )
    target = float(
        da.sel(
            time=t_native,
            depth=target_depth,
            latitude=cell_lat,
            longitude=cell_lon,
        ).values
    )
    if not (isfinite(surface) and isfinite(target)):
        return None
    return surface, target


def _make_sample(
    t_utc: datetime,
    surface: float,
    target: float,
    inside_requested_window: bool,
    temporal_offset_hours: float,
) -> VerticalThermalSample:
    return VerticalThermalSample(
        time_utc=t_utc,
        time_local=t_utc.astimezone(TZ_PUCUSANA),
        surface_temperature_celsius=surface,
        temperature_10m_celsius=target,
        delta_sst_t10_celsius=surface - target,
        inside_requested_window=inside_requested_window,
        temporal_offset_hours=temporal_offset_hours,
    )


def fetch_vertical_thermal_pair(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> VerticalThermalReading:
    """Obtiene ``temperature_10m`` y ``delta_sst_t10`` como pares estrictos.

    En la ventana solicitada se elige una única celda: primero la de mayor
    cantidad de pares completos y, en empate, la de menor distancia. Si no
    existe ningún par dentro de la ventana, se permite un único timestamp
    nativo cercano según el mismo límite temporal del fetcher SST; ambos
    niveles usan juntos ese fallback o ninguno lo usa.
    """
    _validate_inputs(lat, lon, target_date)
    window_start_utc, window_end_utc = _local_window_to_utc(
        target_date, hour_start, hour_end
    )
    query_start = window_start_utc - timedelta(hours=MAX_TEMPORAL_OFFSET_HOURS)
    query_end = window_end_utc + timedelta(hours=MAX_TEMPORAL_OFFSET_HOURS)

    n_in_window = 0
    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            dataset_part=DATASET_PART,
            variables=[VARIABLE],
            minimum_longitude=float(lon) - 0.05,
            maximum_longitude=float(lon) + 0.05,
            minimum_latitude=float(lat) - 0.05,
            maximum_latitude=float(lat) + 0.05,
            maximum_depth=DEPTH_QUERY_MAX_M,
            start_datetime=query_start,
            end_datetime=query_end,
            # Sin minimum_depth y sin coordinates_selection_method='nearest'.
        )

        required_coords = ("time", "depth", "latitude", "longitude")
        if VARIABLE not in ds or any(name not in ds.coords for name in required_coords):
            raise ValueError(
                f"Esquema incompleto para {VARIABLE!r}; se requieren "
                f"{required_coords}."
            )
        if ds.time.size == 0 or ds.depth.size == 0:
            return _empty_reading(
                lat,
                lon,
                target_date,
                hour_start,
                hour_end,
                window_start_utc,
                window_end_utc,
            )

        selected_depths = _select_native_depths(ds.depth.values)
        if selected_depths is None:
            logger.warning(
                "No hay un par de niveles compatible con superficie y ~10 m "
                "para (%s, %s) %s [%s/%s]",
                lat,
                lon,
                target_date,
                DATASET_ID,
                DATASET_VERSION,
            )
            return _empty_reading(
                lat,
                lon,
                target_date,
                hour_start,
                hour_end,
                window_start_utc,
                window_end_utc,
            )
        surface_depth, target_depth = selected_depths
        da = ds[VARIABLE]

        in_window: list[tuple[datetime, object]] = []
        out_window: list[tuple[float, int, datetime, object]] = []
        for raw_time in da.time.values:
            native_time = pd.Timestamp(raw_time).to_pydatetime()
            if native_time.tzinfo is not None:
                t_utc = native_time.astimezone(timezone.utc)
                t_native = t_utc.replace(tzinfo=None)
            else:
                t_utc = native_time.replace(tzinfo=timezone.utc)
                t_native = native_time
            offset = _temporal_offset_hours(
                t_utc, window_start_utc, window_end_utc
            )
            if offset == 0.0:
                in_window.append((t_utc, t_native))
            elif offset <= MAX_TEMPORAL_OFFSET_HOURS:
                before_flag = 0 if t_utc < window_start_utc else 1
                out_window.append((offset, before_flag, t_utc, t_native))

        n_in_window = len(in_window)
        candidates = _cell_candidates(da, float(lat), float(lon))
        if not candidates:
            return _empty_reading(
                lat,
                lon,
                target_date,
                hour_start,
                hour_end,
                window_start_utc,
                window_end_utc,
                n_in_window,
            )

        if in_window:
            best = None
            for distance, cell_lat, cell_lon in candidates:
                pairs: list[tuple[datetime, float, float]] = []
                for t_utc, t_native in in_window:
                    pair = _native_pair_at(
                        da,
                        t_native,
                        surface_depth,
                        target_depth,
                        cell_lat,
                        cell_lon,
                    )
                    if pair is not None:
                        pairs.append((t_utc, pair[0], pair[1]))
                if not pairs:
                    continue
                key = (-len(pairs), distance, cell_lat, cell_lon)
                if best is None or key < best[0]:
                    best = (key, cell_lat, cell_lon, distance, pairs)

            if best is not None:
                _, cell_lat, cell_lon, distance, pairs = best
                samples = tuple(
                    _make_sample(t_utc, surface, target, True, 0.0)
                    for t_utc, surface, target in sorted(pairs)
                )
                n_pairs = len(samples)
                return VerticalThermalReading(
                    lat=float(lat),
                    lon=float(lon),
                    date=target_date,
                    hour_start_local=hour_start,
                    hour_end_local=hour_end,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                    samples=samples,
                    n_native_times_in_window=n_in_window,
                    n_pairs=n_pairs,
                    n_missing_pairs=n_in_window - n_pairs,
                    coverage_fraction=n_pairs / n_in_window,
                    surface_depth_actual_m=surface_depth,
                    temperature_10m_depth_actual_m=target_depth,
                    vertical_separation_m=target_depth - surface_depth,
                    cell_lat=cell_lat,
                    cell_lon=cell_lon,
                    distance_km=distance,
                    status=VerticalThermalStatus.VALIDA_EN_VENTANA,
                )

        out_window.sort(key=lambda item: (item[0], item[1], item[2]))
        for offset, _before_flag, t_utc, t_native in out_window:
            for distance, cell_lat, cell_lon in candidates:
                pair = _native_pair_at(
                    da,
                    t_native,
                    surface_depth,
                    target_depth,
                    cell_lat,
                    cell_lon,
                )
                if pair is None:
                    continue
                sample = _make_sample(t_utc, pair[0], pair[1], False, offset)
                return VerticalThermalReading(
                    lat=float(lat),
                    lon=float(lon),
                    date=target_date,
                    hour_start_local=hour_start,
                    hour_end_local=hour_end,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                    samples=(sample,),
                    n_native_times_in_window=n_in_window,
                    n_pairs=1,
                    n_missing_pairs=n_in_window,
                    coverage_fraction=0.0 if n_in_window > 0 else None,
                    surface_depth_actual_m=surface_depth,
                    temperature_10m_depth_actual_m=target_depth,
                    vertical_separation_m=target_depth - surface_depth,
                    cell_lat=cell_lat,
                    cell_lon=cell_lon,
                    distance_km=distance,
                    status=VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO,
                )

        return _empty_reading(
            lat,
            lon,
            target_date,
            hour_start,
            hour_end,
            window_start_utc,
            window_end_utc,
            n_in_window,
        )
    except Exception:
        logger.exception(
            "Fallo al obtener par térmico vertical para (%s, %s) %s [%s/%s]",
            lat,
            lon,
            target_date,
            DATASET_ID,
            DATASET_VERSION,
        )
        return _empty_reading(
            lat,
            lon,
            target_date,
            hour_start,
            hour_end,
            window_start_utc,
            window_end_utc,
            n_in_window,
        )


def fetch_temperature_10m_pair(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> VerticalThermalReading:
    """Alias público con el nombre de la señal principal del bloque."""
    return fetch_vertical_thermal_pair(
        lat, lon, target_date, hour_start=hour_start, hour_end=hour_end
    )
