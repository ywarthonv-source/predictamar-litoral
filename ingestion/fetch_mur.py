"""Capa MUR L4 opcional sobre recortes NetCDF ya descargados de NASA.

La adquisición autenticada ocurre fuera del ensamblador: este lector no abre
sesiones, pide contraseñas ni descarga grillas globales. Conserva una sola
fecha, máscara, error del análisis y dt_1km_data con su signo. Un archivo final
solo se admite mediante el modo histórico explícito; no prueba disponibilidad
NRT ni disponibilidad histórica a la hora de una faena.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
from io import BytesIO
import logging
from math import asin, cos, radians, sin, sqrt
from numbers import Real
import os
from pathlib import Path
import re
import traceback

import numpy as np
import pandas as pd
import xarray as xr


logger = logging.getLogger(__name__)
DATASET_ID = "MUR-JPL-L4-GLOB-v4.1"
COLLECTION_ID = "C1996881146-POCLOUD"
PRODUCT_VERSION = "04.1"
STANDARD_NAME = "sea_surface_foundation_temperature"
VARIABLES = ("analysed_sst", "analysis_error", "mask", "dt_1km_data")
QUALITY_VARIABLES = ("analysis_error", "dt_1km_data")
NATIVE_UNITS = "kelvin"
UNITS = "degree_Celsius"
NATIVE_GRID_STEP_DEG = 0.01
HALO_CELLS = 2
COORDINATE_TOLERANCE_DEG = 1e-5  # redondeo float32, no búsqueda de otra celda
DEFAULT_MAX_NOMINAL_AGE_HOURS = 72.0  # política MUR provisional, no persistencia de frentes
MAX_ALLOWED_AGE_HOURS = 168.0
MAX_FIELD_SPAN_DEG = 2.0
MAX_LOCAL_FILES = 40
MAX_FILE_BYTES = 32 * 1024 * 1024
DATA_DIRECTORY_ENV = "PREDICTAMAR_MUR_DATA_DIR"
MASK_MEANINGS = (
    "open_sea land open_lake open_sea_with_ice_in_the_grid "
    "open_lake_with_ice_in_the_grid"
)
DATA_SCOPE = "sst_mur_regional_field"
SCOPE_WARNING = (
    "MUR es un análisis L4 multifuente, no una observación independiente por "
    "píxel ni una detección de cardumen. 0.01 grados es espaciamiento de grilla, "
    "no resolución efectiva garantizada. Solo mask=1 se admite como mar "
    "abierto sin otros bits; tierra y huecos no se rellenan ni se desplazan. "
    "dt_1km_data conserva horas con signo, no se interpreta como edad positiva "
    "ni como cobertura de todas las observaciones. analysis_error es el error "
    "estimado del análisis SST, no probabilidad pesquera. El campo técnico "
    "no delimita los 0–10 km desde el litoral. No reemplaza ni promedia OSTIA. "
    "La disponibilidad a as_of y la operación NRT no han sido verificadas."
)

Matrix = tuple[tuple[float | None, ...], ...]
MaskMatrix = tuple[tuple[int | None, ...], ...]


class MurMode(str, Enum):
    NRT_ONLY = "nrt_only"
    HISTORICAL_DIAGNOSTIC = "historical_diagnostic"


class MurProductStage(str, Enum):
    NRT = "nrt"
    FINAL = "final"
    UNKNOWN = "unknown"


class MurStatus(str, Enum):
    VALIDA_EN_FECHA_NOMINAL = "valida_en_fecha_nominal"
    VALIDA_RECIENTE = "valida_reciente"
    HISTORICA_FINAL = "historica_final"
    SIN_DATOS = "sin_datos"
    ERROR = "error"


def _aware_utc(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe ser un datetime con zona horaria explícita.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class MurOptions:
    as_of_utc: datetime
    max_nominal_age_hours: float = DEFAULT_MAX_NOMINAL_AGE_HOURS
    mode: MurMode = MurMode.NRT_ONLY

    def __post_init__(self):
        object.__setattr__(self, "as_of_utc", _aware_utc(self.as_of_utc, "as_of_utc"))
        age = self.max_nominal_age_hours
        if (not isinstance(age, Real) or isinstance(age, bool)
                or not np.isfinite(age) or not 0 < age <= MAX_ALLOWED_AGE_HOURS):
            raise ValueError("max_nominal_age_hours debe ser finito, > 0 y <= 168.")
        if not isinstance(self.mode, MurMode):
            raise ValueError("mode debe ser MurMode, no un indicador implícito.")
        object.__setattr__(self, "max_nominal_age_hours", float(age))


@dataclass(frozen=True)
class MurBounds:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float


@dataclass(frozen=True)
class MurGrid:
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    sst_kelvin: Matrix
    sst_celsius: Matrix
    analysis_error_kelvin: Matrix
    mask: MaskMatrix
    dt_1km_hours: Matrix


@dataclass(frozen=True)
class MurProvenance:
    dataset_id: str = DATASET_ID
    collection_id: str = COLLECTION_ID
    expected_product_version: str = PRODUCT_VERSION
    product_version: str | None = None
    product_stage: MurProductStage = MurProductStage.UNKNOWN
    stage_basis: str = "not_read"
    source_access: str = "provided_dataset"
    source_file_name: str | None = None
    source_file_sha256: str | None = None
    product_created_at_utc: datetime | None = None
    read_at_utc: datetime | None = None
    availability_as_of_verified: bool = False
    availability_basis: str = "historical_availability_not_verified"
    operational_use_verified: bool = False


@dataclass(frozen=True)
class MurField:
    requested_date: date
    requested_bounds: MurBounds
    query_bounds: MurBounds
    options: MurOptions
    nominal_product_date: date | None
    time_utc: datetime | None
    nominal_age_hours: float | None
    matches_requested_nominal_date: bool | None
    provenance: MurProvenance
    grid: MurGrid
    derivation_support: MurGrid
    halo_cells: int
    halo_complete: bool
    n_grid_cells: int
    n_marine_cells: int
    n_valid_cells: int
    n_analysis_error_cells: int
    n_dt_1km_cells: int
    coverage_fraction: float | None
    coverage_denominator: str
    median_zonal_spacing_km: float | None
    median_meridional_spacing_km: float | None
    missing_quality_variables: tuple[str, ...]
    variables: tuple[str, ...]
    standard_name: str
    native_units: str
    units: str
    processing_level: str
    native_grid_step_deg: float
    mask_meanings: str
    dt_1km_units: str
    dt_1km_interpretation: str
    nominal_age_basis: str
    data_scope: str
    field_is_operational_domain: bool
    scope_warning: str
    status: MurStatus
    reason: str | None = None
    error_type: str | None = None


def validate_request(min_lat, max_lat, min_lon, max_lon, target_date, options):
    for name, value, limit in (
        ("minimum_latitude", min_lat, 90), ("maximum_latitude", max_lat, 90),
        ("minimum_longitude", min_lon, 180), ("maximum_longitude", max_lon, 180),
    ):
        if (not isinstance(value, Real) or isinstance(value, bool)
                or not np.isfinite(value) or not -limit <= value <= limit):
            raise ValueError(f"{name} debe ser finita y estar dentro de ±{limit}.")
    if not min_lat < max_lat or not min_lon < max_lon:
        raise ValueError("Los límites mínimos deben ser menores que los máximos.")
    if max_lat - min_lat > MAX_FIELD_SPAN_DEG or max_lon - min_lon > MAX_FIELD_SPAN_DEG:
        raise ValueError("El campo MUR no puede exceder 2 grados por eje.")
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError("target_date debe ser datetime.date.")
    if not isinstance(options, MurOptions):
        raise ValueError("options debe ser MurOptions con as_of explícito.")
    bounds = MurBounds(*map(float, (min_lat, max_lat, min_lon, max_lon)))
    halo = HALO_CELLS * NATIVE_GRID_STEP_DEG
    query = MurBounds(
        max(-90.0, min_lat - halo), min(90.0, max_lat + halo),
        max(-180.0, min_lon - halo), min(180.0, max_lon + halo),
    )
    return bounds, query


def _empty_field(bounds, query, target_date, options):
    grid = MurGrid((), (), (), (), (), (), ())
    return MurField(
        requested_date=target_date, requested_bounds=bounds, query_bounds=query,
        options=options, nominal_product_date=None, time_utc=None,
        nominal_age_hours=None, matches_requested_nominal_date=None,
        provenance=MurProvenance(), grid=grid, derivation_support=grid,
        halo_cells=HALO_CELLS, halo_complete=False, n_grid_cells=0,
        n_marine_cells=0, n_valid_cells=0, n_analysis_error_cells=0, n_dt_1km_cells=0,
        coverage_fraction=None, coverage_denominator="mask_1_cells_in_requested_field",
        median_zonal_spacing_km=None, median_meridional_spacing_km=None,
        missing_quality_variables=QUALITY_VARIABLES, variables=VARIABLES,
        standard_name=STANDARD_NAME, native_units=NATIVE_UNITS, units=UNITS,
        processing_level="L4", native_grid_step_deg=NATIVE_GRID_STEP_DEG,
        mask_meanings=MASK_MEANINGS, dt_1km_units="hours",
        dt_1km_interpretation="signed_offset_preserved_not_observation_age",
        nominal_age_basis="elapsed_hours_since_native_analysis_time_utc",
        data_scope=DATA_SCOPE, field_is_operational_domain=False,
        scope_warning=SCOPE_WARNING, status=MurStatus.SIN_DATOS,
        reason="no_admissible_product",
    )


def _failure(empty, exc, reason):
    # No texto de excepción, líneas fuente, URL firmadas ni locales sensibles.
    trace = " > ".join(f"{f.filename}:{f.lineno}:{f.name}"
                       for f in traceback.extract_tb(exc.__traceback__))
    logger.error("Fallo MUR %s (%s); traza: %s", reason, type(exc).__name__, trace)
    return replace(empty, status=MurStatus.ERROR, reason=reason, error_type=type(exc).__name__)


def _canonicalise(da):
    aliases = {old: new for old, new in (("lat", "latitude"), ("lon", "longitude"))
               if old in da.dims and new not in da.dims}
    da = da.rename(aliases)
    axes = ("time", "latitude", "longitude")
    if set(da.dims) != set(axes):
        raise ValueError("Se requieren exactamente time, latitude y longitude.")
    for axis in axes:
        if axis not in da.coords or da[axis].dims != (axis,):
            raise ValueError("Las coordenadas deben ser ejes unidimensionales.")
    if "scale_factor" in da.attrs or "add_offset" in da.attrs or "_FillValue" in da.attrs:
        raise ValueError("MUR requiere datos CF decodificados, sin doble escalado.")
    if da.dtype.kind not in "fiu":
        raise ValueError("Se requieren valores numéricos; use decode_timedelta=False.")
    return da.transpose(*axes)


def _metadata(ds):
    attrs = ds.attrs
    if attrs.get("id") not in {DATASET_ID, "MUR-JPL-L4-GLOB-v04.1"}:
        raise ValueError("El archivo no identifica MUR v4.1.")
    version = str(attrs.get("product_version", ""))
    if version not in {"04.1", "4.1"} or attrs.get("processing_level") != "L4":
        raise ValueError("Versión o nivel de procesamiento MUR incompatible.")
    # La historia del FINAL menciona el NRT sustituido. No se busca 'nrt' ahí.
    title = str(attrs.get("title", "")).casefold()
    final = bool(re.search(r"\bfinal\b", title))
    nrt = bool(re.search(r"\bnrt\b|near[- ]real[- ]time", title))
    if final and nrt:
        raise ValueError("El título declara etapas de producto contradictorias.")
    stage = (MurProductStage.FINAL if final else MurProductStage.NRT if nrt
             else MurProductStage.UNKNOWN)
    created = None
    if attrs.get("date_created"):
        stamp = pd.Timestamp(attrs["date_created"])
        if pd.isna(stamp):
            raise ValueError("date_created es NaT.")
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        created = stamp.to_pydatetime()
    return version, stage, created


def _validated_arrays(ds):
    arrays = {name: _canonicalise(ds[name]) for name in VARIABLES if name in ds}
    if "analysed_sst" not in arrays or "mask" not in arrays:
        raise ValueError("SST y máscara MUR son obligatorias.")
    sst, mask = arrays["analysed_sst"], arrays["mask"]
    if sst.attrs.get("units") not in {NATIVE_UNITS, "K"}:
        raise ValueError("SST MUR debe estar en kelvin.")
    if sst.attrs.get("standard_name") != STANDARD_NAME:
        raise ValueError("La SST no es temperatura de fundación.")
    if (str(mask.attrs.get("flag_meanings", "")).split() != MASK_MEANINGS.split()
            or np.asarray(mask.attrs.get("flag_masks", [])).reshape(-1).tolist() != [1, 2, 4, 8, 16]):
        raise ValueError("La semántica de mask MUR cambió.")
    if "analysis_error" in arrays and arrays["analysis_error"].attrs.get("units") not in {NATIVE_UNITS, "K"}:
        raise ValueError("analysis_error debe estar en kelvin.")
    if "dt_1km_data" in arrays and arrays["dt_1km_data"].attrs.get("units") != "hours":
        raise ValueError("dt_1km_data debe conservar horas nativas con signo.")
    for other in arrays.values():
        for axis in ("time", "latitude", "longitude"):
            if not np.array_equal(sst[axis].values, other[axis].values):
                raise ValueError("Las variables deben compartir exactamente los ejes.")
    for axis, limit in (("latitude", 90), ("longitude", 180)):
        values = np.asarray(sst[axis].values, dtype=np.float64)
        if (not np.all(np.isfinite(values)) or np.any(np.abs(values) > limit)
                or len(np.unique(values)) != len(values)):
            raise ValueError("Eje espacial inválido o duplicado.")
        if len(values) > 1:
            step = np.diff(np.sort(values))
            if not np.allclose(step, NATIVE_GRID_STEP_DEG, rtol=.002, atol=1e-6):
                raise ValueError("Se requiere grilla nativa 0.01°, sin coordenadas omitidas.")
            if np.ptp(values) > MAX_FIELD_SPAN_DEG + 2 * HALO_CELLS * NATIVE_GRID_STEP_DEG + 2e-5:
                raise ValueError("Se requiere un recorte regional, no una grilla global.")
    if sst.sizes["time"] != 1 or sst.time.dtype.kind != "M":
        raise ValueError("Cada producto debe contener una única fecha CF decodificada.")
    stamp = pd.Timestamp(sst.time.values[0])
    if pd.isna(stamp):
        raise ValueError("Coordenada temporal NaT.")
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return arrays, stamp.to_pydatetime()


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dp = radians(float(lat2) - float(lat1))
    dl = radians(float(lon2) - float(lon1))
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(min(1.0, max(0.0, a))))


def grid_spacing(grid):
    lats, lons = grid.latitudes, grid.longitudes
    dx = [haversine_km(lat, a, lat, b) for lat in lats for a, b in zip(lons, lons[1:])]
    dy = [haversine_km(a, 0, b, 0) for a, b in zip(lats, lats[1:])]
    return float(np.median(dx)) if dx else None, float(np.median(dy)) if dy else None


def _matrix(values, valid, convert=float):
    return tuple(tuple(convert(v) if ok else None for v, ok in zip(row, mask))
                 for row, mask in zip(values, valid))


def _make_grid(arrays):
    sst = arrays["analysed_sst"]
    t = np.asarray(sst.values, dtype=np.float64)
    mask = np.asarray(arrays["mask"].values, dtype=np.float64)
    known_mask = np.isfinite(mask) & (mask >= 1) & (mask <= 31) & (mask == np.trunc(mask))
    valid = known_mask & (mask == 1) & np.isfinite(t) & (t > 0)
    error = (np.asarray(arrays["analysis_error"].values, dtype=np.float64)
             if "analysis_error" in arrays else np.full_like(t, np.nan))
    dt = (np.asarray(arrays["dt_1km_data"].values, dtype=np.float64)
          if "dt_1km_data" in arrays else np.full_like(t, np.nan))
    valid_error = valid & np.isfinite(error) & (error >= 0)
    valid_dt = valid & np.isfinite(dt) & (dt >= -127) & (dt <= 127) & (dt == np.trunc(dt))
    return MurGrid(
        tuple(map(float, sst.latitude.values)), tuple(map(float, sst.longitude.values)),
        _matrix(t, valid), _matrix(t - 273.15, valid), _matrix(error, valid_error),
        _matrix(mask, known_mask, int), _matrix(dt, valid_dt),
    )


def crop_grid(grid, bounds):
    eps = COORDINATE_TOLERANCE_DEG
    ii = [i for i, x in enumerate(grid.latitudes)
          if bounds.minimum_latitude - eps <= x <= bounds.maximum_latitude + eps]
    jj = [j for j, x in enumerate(grid.longitudes)
          if bounds.minimum_longitude - eps <= x <= bounds.maximum_longitude + eps]
    def crop(matrix):
        return tuple(tuple(matrix[i][j] for j in jj) for i in ii)
    return MurGrid(
        tuple(grid.latitudes[i] for i in ii), tuple(grid.longitudes[j] for j in jj),
        *(crop(m) for m in (grid.sst_kelvin, grid.sst_celsius, grid.analysis_error_kelvin,
                           grid.mask, grid.dt_1km_hours)),
    )


def _select_field(ds, empty):
    version, stage, created = _metadata(ds)
    arrays, stamp = _validated_arrays(ds)
    age = (empty.options.as_of_utc - stamp).total_seconds() / 3600
    result = replace(
        empty, time_utc=stamp, nominal_product_date=stamp.date(), nominal_age_hours=age,
        matches_requested_nominal_date=stamp.date() == empty.requested_date,
        provenance=replace(empty.provenance, product_version=version, product_stage=stage,
                           stage_basis="product_title", product_created_at_utc=created),
        missing_quality_variables=tuple(n for n in QUALITY_VARIABLES if n not in arrays),
    )
    if stamp.date() > empty.requested_date or not 0 <= age <= empty.options.max_nominal_age_hours:
        return replace(result, reason="outside_nominal_age_window")
    if stage is MurProductStage.UNKNOWN:
        return replace(result, reason="unknown_product_stage")
    if empty.options.mode is MurMode.NRT_ONLY:
        if stage is not MurProductStage.NRT:
            return replace(result, reason="final_product_requires_historical_mode")
        if created is None:
            return replace(result, reason="product_creation_time_unknown")
        if created > empty.options.as_of_utc:
            return replace(result, reason="product_created_after_as_of")
    query, bounds = empty.query_bounds, empty.requested_bounds
    eps = COORDINATE_TOLERANCE_DEG
    subset = {
        name: da.sortby("latitude").sortby("longitude").isel(time=0).sel(
            latitude=slice(query.minimum_latitude - eps, query.maximum_latitude + eps),
            longitude=slice(query.minimum_longitude - eps, query.maximum_longitude + eps),
        ) for name, da in arrays.items()
    }
    support = _make_grid(subset)
    grid = crop_grid(support, bounds)
    n_grid = len(grid.latitudes) * len(grid.longitudes)
    n_marine = sum(v == 1 for row in grid.mask for v in row)
    n_valid = sum(v is not None for row in grid.sst_celsius for v in row)
    halo_ok = False
    if n_grid:
        i0, i1 = support.latitudes.index(grid.latitudes[0]), support.latitudes.index(grid.latitudes[-1])
        j0, j1 = support.longitudes.index(grid.longitudes[0]), support.longitudes.index(grid.longitudes[-1])
        halo_ok = (i0 >= HALO_CELLS and j0 >= HALO_CELLS
                   and len(support.latitudes) - 1 - i1 >= HALO_CELLS
                   and len(support.longitudes) - 1 - j1 >= HALO_CELLS)
    dx, dy = grid_spacing(support)
    status = (MurStatus.HISTORICA_FINAL if stage is MurProductStage.FINAL
              else MurStatus.VALIDA_EN_FECHA_NOMINAL if stamp.date() == empty.requested_date
              else MurStatus.VALIDA_RECIENTE)
    return replace(
        result, grid=grid, derivation_support=support, halo_complete=halo_ok,
        n_grid_cells=n_grid, n_marine_cells=n_marine, n_valid_cells=n_valid,
        n_analysis_error_cells=sum(v is not None for row in grid.analysis_error_kelvin for v in row),
        n_dt_1km_cells=sum(v is not None for row in grid.dt_1km_hours for v in row),
        coverage_fraction=n_valid / n_marine if n_marine else None,
        median_zonal_spacing_km=dx, median_meridional_spacing_km=dy,
        status=status if n_valid else MurStatus.SIN_DATOS,
        reason=None if n_valid else "no_valid_sst_in_requested_field",
    )


def mur_field_from_dataset(
    ds, minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude,
    target_date, *, options: MurOptions,
) -> MurField:
    """Transformación pura de UN producto CF; no consulta red, archivos ni reloj."""
    bounds, query = validate_request(
        minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude, target_date, options)
    empty = _empty_field(bounds, query, target_date, options)
    try:
        return _select_field(ds, empty)
    except Exception as exc:
        return _failure(empty, exc, "invalid_dataset")


def fetch_mur_field(
    minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude,
    target_date, *, options: MurOptions, data_directory: Path | str | None = None,
) -> MurField:
    """Lee un directorio de recortes diarios .nc/.nc4, sin acceso a NASA.

    Configure data_directory al inyectar el proveedor, o PREDICTAMAR_MUR_DATA_DIR.
    No recorre subdirectorios ni escribe archivos. Selecciona la fecha admisible
    más reciente con SST en el campo; nunca mosaicos ni dos versiones de un día.
    Un archivo ilegible o ambiguo no provoca un fallback silencioso.
    """
    bounds, query = validate_request(
        minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude, target_date, options)
    empty = _empty_field(bounds, query, target_date, options)
    empty = replace(empty, provenance=replace(empty.provenance, source_access="local_netcdf"))
    directory = data_directory if data_directory is not None else os.environ.get(DATA_DIRECTORY_ENV)
    if directory is None or str(directory).strip() == "":
        return replace(empty, status=MurStatus.ERROR, reason="mur_directory_not_configured")
    try:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError("El directorio de recortes MUR no existe.")
        paths = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".nc", ".nc4"})
        if len(paths) > MAX_LOCAL_FILES:
            raise ValueError("El directorio excede el límite de recortes del lector.")
        candidates = []
        dates_seen = set()
        for path in paths:
            if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
                raise ValueError("Se requieren recortes regulares de tamaño acotado.")
            # Valores y hash provienen de los mismos bytes aunque un proceso
            # de actualización sustituya el archivo mientras hacemos la lectura.
            with path.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if not 0 < len(raw) <= MAX_FILE_BYTES:
                raise ValueError("El recorte supera el tamaño permitido o está vacío.")
            with xr.open_dataset(BytesIO(raw), engine="h5netcdf", decode_timedelta=False) as ds:
                result = _select_field(ds, empty)
            if result.nominal_product_date in dates_seen:
                raise ValueError("Más de un producto para la misma fecha nominal MUR.")
            dates_seen.add(result.nominal_product_date)
            result = replace(result, provenance=replace(
                result.provenance, source_file_name=path.name,
                source_file_sha256=hashlib.sha256(raw).hexdigest(),
                read_at_utc=datetime.now(timezone.utc),
            ))
            candidates.append(result)
        # Las fechas fuera de ventana no se presentan como el último dato utilizable.
        eligible = [r for r in candidates if r.reason != "outside_nominal_age_window"]
        eligible.sort(key=lambda r: r.time_utc, reverse=True)
        return next((r for r in eligible if r.n_valid_cells), eligible[0] if eligible else empty)
    except Exception as exc:
        return _failure(empty, exc, "source_failure")
