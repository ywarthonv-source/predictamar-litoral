"""Campo OLCI L3 opcional, independiente de la referencia puntual L4.

Se selecciona una sola fecha nominal UTC, nunca un mosaico de fechas. La
antigüedad se mide desde su etiqueta diaria, no desde una hora de adquisición
inventada. La disponibilidad histórica al instante as_of NO se presume.
Los valores permanecen nativos; tierra, huecos y calidad desconocida no son
ceros. El soporte de dos celdas se conserva para derivar antes de recortar.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import logging
from math import asin, cos, radians, sin, sqrt
from numbers import Real
import traceback

import copernicusmarine
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)
PRODUCT_ID = "OCEANCOLOUR_GLO_BGC_L3_NRT_009_101"
DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D"
DATASET_VERSION = "202207"
DATASET_PART = "default"
VARIABLES = ("CHL", "CHL_uncertainty", "flags")
STANDARD_NAME = "mass_concentration_of_chlorophyll_a_in_sea_water"
UNITS = "milligram m-3"
UNCERTAINTY_UNITS = "%"
NATIVE_GRID_STEP_DEG = 1.0 / 180.0
HALO_CELLS = 2  # un vecino para la derivada y otro para su proximidad a tierra
DEFAULT_MAX_NOMINAL_AGE_HOURS = 72.0  # política operativa provisional, no pesquera
MAX_ALLOWED_AGE_HOURS = 168.0
MAX_FIELD_SPAN_DEG = 2.0
MAX_CHL_MG_M3 = 1000.0
MAX_UNCERTAINTY_PCT = 327.67
DATA_SCOPE = "chlorophyll_olci_regional_field"
SCOPE_WARNING = (
    "Campo superficial OLCI L3 diario procesado por Copernicus-GlobColour; "
    "no es una medición in situ ni una detección de cardumen. La etiqueta "
    "300m no es la resolución efectiva: se mide el espaciamiento de la grilla. "
    "El recuadro y su margen de consulta no son el dominio operativo de "
    "0–10 km desde el litoral. No se rellenan celdas ni se mezclan fechas. "
    "flags solo identifica LAND, no todas las causas de ausencia o error. "
    "La incertidumbre porcentual no es probabilidad de pesca ni se presupone "
    "una desviación estándar con errores independientes. La fecha nominal "
    "no es una hora exacta de observación; la disponibilidad histórica al "
    "as_of no está verificada. Esta capa no sustituye la referencia L4."
)

Matrix = tuple[tuple[float | None, ...], ...]
FlagMatrix = tuple[tuple[int | None, ...], ...]


class ChlorophyllFieldStatus(str, Enum):
    VALIDA_EN_FECHA_NOMINAL = "valida_en_fecha_nominal"
    VALIDA_RECIENTE = "valida_reciente"
    SIN_DATOS = "sin_datos"
    ERROR = "error"


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe ser un datetime con zona horaria explícita.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ChlorophyllOptions:
    """Activación explícita y política temporal propia de OLCI.

    72 h se cuentan desde la etiqueta nominal UTC. No certifican que un
    frente persista 72 h. as_of es obligatorio y nunca se infiere del día
    local de la solicitud.
    """

    as_of_utc: datetime
    max_nominal_age_hours: float = DEFAULT_MAX_NOMINAL_AGE_HOURS

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of_utc", _aware_utc(self.as_of_utc, "as_of_utc"))
        age = self.max_nominal_age_hours
        if (
            not isinstance(age, Real) or isinstance(age, bool)
            or not np.isfinite(age) or not 0 < age <= MAX_ALLOWED_AGE_HOURS
        ):
            raise ValueError("max_nominal_age_hours debe ser finito, > 0 y <= 168.")
        object.__setattr__(self, "max_nominal_age_hours", float(age))


@dataclass(frozen=True)
class ChlorophyllBounds:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float


@dataclass(frozen=True)
class ChlorophyllGrid:
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    chlorophyll_mg_m3: Matrix
    uncertainty_pct: Matrix
    flags: FlagMatrix  # 0=mar, 1=tierra, None=flag inválido/desconocido


@dataclass(frozen=True)
class ChlorophyllField:
    requested_date: date
    requested_bounds: ChlorophyllBounds
    query_bounds: ChlorophyllBounds
    options: ChlorophyllOptions
    nominal_product_date: date | None
    time_utc: datetime | None
    nominal_age_hours: float | None
    matches_requested_nominal_date: bool | None
    retrieved_at_utc: datetime | None
    availability_as_of_verified: bool
    availability_basis: str
    source_access: str
    grid: ChlorophyllGrid
    derivation_support: ChlorophyllGrid
    halo_cells: int
    halo_complete: bool
    n_grid_cells: int
    n_marine_cells: int
    n_valid_cells: int
    n_uncertainty_cells: int
    coverage_fraction: float | None
    coverage_denominator: str
    median_zonal_resolution_km: float | None
    median_meridional_resolution_km: float | None
    product_id: str
    dataset_id: str
    requested_dataset_version: str
    dataset_version: str | None
    dataset_part: str | None
    version_basis: str
    variables: tuple[str, ...]
    units: str
    uncertainty_units: str
    processing_level: str
    native_grid_step_deg: float
    flags_meanings: str
    field_is_operational_domain: bool
    data_scope: str
    scope_warning: str
    status: ChlorophyllFieldStatus
    reason: str | None = None
    error_type: str | None = None


def _bounds_and_query(min_lat, max_lat, min_lon, max_lon, target_date, options):
    for name, value, limit in (
        ("minimum_latitude", min_lat, 90), ("maximum_latitude", max_lat, 90),
        ("minimum_longitude", min_lon, 180), ("maximum_longitude", max_lon, 180),
    ):
        if (
            not isinstance(value, Real) or isinstance(value, bool)
            or not np.isfinite(value) or not -limit <= value <= limit
        ):
            raise ValueError(f"{name} debe ser finita y estar dentro de ±{limit}.")
    if not min_lat < max_lat or not min_lon < max_lon:
        raise ValueError("Los límites mínimos deben ser menores que los máximos.")
    if max_lat - min_lat > MAX_FIELD_SPAN_DEG or max_lon - min_lon > MAX_FIELD_SPAN_DEG:
        raise ValueError("El campo OLCI no puede exceder 2 grados por eje.")
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError("target_date debe ser datetime.date, no datetime ni texto.")
    if not isinstance(options, ChlorophyllOptions):
        raise ValueError("options debe ser ChlorophyllOptions con as_of explícito.")
    bounds = ChlorophyllBounds(*map(float, (min_lat, max_lat, min_lon, max_lon)))
    halo = HALO_CELLS * NATIVE_GRID_STEP_DEG
    query = ChlorophyllBounds(
        max(-90.0, float(min_lat) - halo), min(90.0, float(max_lat) + halo),
        max(-180.0, float(min_lon) - halo), min(180.0, float(max_lon) + halo),
    )
    return bounds, query


def _empty_field(bounds, query, target_date, options, retrieved_at_utc=None):
    grid = ChlorophyllGrid((), (), (), (), ())
    return ChlorophyllField(
        requested_date=target_date, requested_bounds=bounds, query_bounds=query,
        options=options, nominal_product_date=None, time_utc=None,
        nominal_age_hours=None, matches_requested_nominal_date=None,
        retrieved_at_utc=retrieved_at_utc, availability_as_of_verified=False,
        availability_basis="historical_availability_not_verified",
        source_access="provided_dataset", grid=grid, derivation_support=grid,
        halo_cells=HALO_CELLS, halo_complete=False,
        n_grid_cells=0, n_marine_cells=0, n_valid_cells=0, n_uncertainty_cells=0,
        coverage_fraction=None, coverage_denominator="marine_cells_in_requested_field",
        median_zonal_resolution_km=None, median_meridional_resolution_km=None,
        product_id=PRODUCT_ID, dataset_id=DATASET_ID,
        requested_dataset_version=DATASET_VERSION, dataset_version=None,
        dataset_part=None, version_basis="not_stored_in_provided_dataset",
        variables=VARIABLES, units=UNITS, uncertainty_units=UNCERTAINTY_UNITS,
        processing_level="L3", native_grid_step_deg=NATIVE_GRID_STEP_DEG,
        flags_meanings="LAND", field_is_operational_domain=False,
        data_scope=DATA_SCOPE, scope_warning=SCOPE_WARNING,
        status=ChlorophyllFieldStatus.SIN_DATOS, reason="no_admissible_time",
    )


def _failure(empty, exc, reason):
    # Traza sin texto de la excepción, líneas fuente ni locales que puedan
    # contener URL firmadas, credenciales u otros valores sensibles.
    frames = traceback.extract_tb(exc.__traceback__)
    trace = " > ".join(f"{f.filename}:{f.lineno}:{f.name}" for f in frames)
    logger.error("Fallo OLCI %s (%s); traza: %s", reason, type(exc).__name__, trace)
    return replace(empty, status=ChlorophyllFieldStatus.ERROR,
                   reason=reason, error_type=type(exc).__name__)


def _canonicalise(da, name):
    aliases = {}
    for canonical, alias in (("latitude", "lat"), ("longitude", "lon")):
        if canonical not in da.dims and alias in da.dims:
            aliases[alias] = canonical
    da = da.rename(aliases)
    axes = ("time", "latitude", "longitude")
    if set(da.dims) != set(axes):
        raise ValueError(f"{name}: se requieren exactamente time, latitude y longitude.")
    for axis in axes:
        if axis not in da.coords or da[axis].dims != (axis,):
            raise ValueError(f"{name}: coordenada {axis} no es un eje unidimensional.")
    if "scale_factor" in da.attrs or "add_offset" in da.attrs:
        raise ValueError(f"{name}: requiere datos CF decodificados, sin escalar dos veces.")
    return da.transpose(*axes)


def _validated_arrays(ds):
    arrays = [_canonicalise(ds[name], name) for name in VARIABLES]
    chl, unc, flags = arrays
    for other in arrays[1:]:
        for axis in ("time", "latitude", "longitude"):
            if not np.array_equal(chl[axis].values, other[axis].values):
                raise ValueError("CHL, incertidumbre y flags deben compartir exactamente la grilla.")
    if chl.attrs.get("units") not in {UNITS, "mg m-3"}:
        raise ValueError("Unidades de CHL ausentes o incompatibles.")
    if chl.attrs.get("standard_name") != STANDARD_NAME or unc.attrs.get("units") != "%":
        raise ValueError("Identidad de CHL o unidades de incertidumbre incompatibles.")
    if (
        str(flags.attrs.get("flag_meanings", "")).split() != ["LAND"]
        or np.asarray(flags.attrs.get("flag_masks", [])).reshape(-1).tolist() != [1]
    ):
        raise ValueError("La semántica de flags cambió; no se supondrán bits de calidad.")
    for axis, limit in (("latitude", 90), ("longitude", 180)):
        values = np.asarray(chl[axis].values, dtype=np.float64)
        if (
            not np.all(np.isfinite(values)) or np.any(np.abs(values) > limit)
            or len(np.unique(values)) != len(values)
        ):
            raise ValueError(f"Eje {axis} inválido o duplicado.")
        steps = np.diff(np.sort(values))
        if steps.size and not np.allclose(steps, NATIVE_GRID_STEP_DEG, rtol=.005, atol=1e-6):
            raise ValueError(f"{axis}: grilla no nativa o con coordenadas omitidas.")
    stamps = []
    for raw in chl.time.values:
        stamp = pd.Timestamp(raw)
        if pd.isna(stamp):
            raise ValueError("Coordenada temporal NaT.")
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        stamps.append(stamp.to_pydatetime())
    if len({stamp.date() for stamp in stamps}) != len(stamps):
        raise ValueError("Más de un campo para la misma fecha nominal: selección ambigua.")
    return arrays, stamps


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia esférica en float64; no usa diferencias de radianes float32."""
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dp, dl = radians(float(lat2) - float(lat1)), radians(float(lon2) - float(lon1))
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(min(1.0, max(0.0, a))))


def grid_resolution(grid):
    lats, lons = grid.latitudes, grid.longitudes
    zonal = [haversine_km(lat, a, lat, b) for lat in lats for a, b in zip(lons, lons[1:])]
    meridional = [haversine_km(a, 0, b, 0) for a, b in zip(lats, lats[1:])]
    return (float(np.median(zonal)) if zonal else None,
            float(np.median(meridional)) if meridional else None)


def _matrix(values, valid):
    return tuple(tuple(float(v) if ok else None for v, ok in zip(row, mask))
                 for row, mask in zip(values, valid))


def _grid(chl, unc, flags):
    c, u, f = (np.asarray(da.values, dtype=np.float64) for da in (chl, unc, flags))
    known_flags = np.isfinite(f) & np.isin(f, [0, 1])
    valid = known_flags & (f == 0) & np.isfinite(c) & (c > 0) & (c <= MAX_CHL_MG_M3)
    valid_unc = valid & np.isfinite(u) & (u >= 0) & (u <= MAX_UNCERTAINTY_PCT + 1e-5)
    return ChlorophyllGrid(
        latitudes=tuple(map(float, chl.latitude.values)),
        longitudes=tuple(map(float, chl.longitude.values)),
        chlorophyll_mg_m3=_matrix(c, valid), uncertainty_pct=_matrix(u, valid_unc),
        flags=tuple(tuple(int(v) if ok else None for v, ok in zip(row, mask))
                    for row, mask in zip(f, known_flags)),
    )


def crop_grid(grid, bounds):
    ii = [i for i, x in enumerate(grid.latitudes) if bounds.minimum_latitude <= x <= bounds.maximum_latitude]
    jj = [j for j, x in enumerate(grid.longitudes) if bounds.minimum_longitude <= x <= bounds.maximum_longitude]
    def crop(matrix):
        return tuple(tuple(matrix[i][j] for j in jj) for i in ii)
    return ChlorophyllGrid(
        tuple(grid.latitudes[i] for i in ii), tuple(grid.longitudes[j] for j in jj),
        crop(grid.chlorophyll_mg_m3), crop(grid.uncertainty_pct), crop(grid.flags),
    )


def _select_field(ds, empty):
    attrs = getattr(ds, "attrs", {})
    for key, expected in (("cmems_product_id", PRODUCT_ID), ("title", DATASET_ID)):
        if key in attrs and attrs[key] != expected:
            raise ValueError("El archivo declara una identidad de producto diferente.")
    arrays, stamps = _validated_arrays(ds)
    query, bounds, options = empty.query_bounds, empty.requested_bounds, empty.options
    selected = []
    for da in arrays:
        da = da.sortby("latitude").sortby("longitude")
        da = da.sel(latitude=slice(query.minimum_latitude, query.maximum_latitude),
                    longitude=slice(query.minimum_longitude, query.maximum_longitude))
        selected.append(da)
    if not all(selected[0].sizes[axis] for axis in ("time", "latitude", "longitude")):
        return replace(empty, reason="empty_dataset")
    candidates = []
    for index, stamp in enumerate(stamps):
        nominal = stamp.date()
        nominal_start = datetime.combine(nominal, datetime.min.time(), tzinfo=timezone.utc)
        age = (options.as_of_utc - nominal_start).total_seconds() / 3600
        if (
            nominal <= empty.requested_date and stamp <= options.as_of_utc
            and nominal_start + timedelta(days=1) <= options.as_of_utc
            and 0 <= age <= options.max_nominal_age_hours
        ):
            candidates.append((stamp, index, age))
    latest_empty = None
    for stamp, index, age in sorted(candidates, reverse=True):
        support = _grid(*(da.isel(time=index) for da in selected))
        grid = crop_grid(support, bounds)
        n_grid = len(grid.latitudes) * len(grid.longitudes)
        n_marine = sum(v == 0 for row in grid.flags for v in row)
        n_valid = sum(v is not None for row in grid.chlorophyll_mg_m3 for v in row)
        n_unc = sum(v is not None for row in grid.uncertainty_pct for v in row)
        halo_ok = False
        if n_grid:
            i0, i1 = support.latitudes.index(grid.latitudes[0]), support.latitudes.index(grid.latitudes[-1])
            j0, j1 = support.longitudes.index(grid.longitudes[0]), support.longitudes.index(grid.longitudes[-1])
            halo_ok = (i0 >= HALO_CELLS and j0 >= HALO_CELLS
                       and len(support.latitudes) - 1 - i1 >= HALO_CELLS
                       and len(support.longitudes) - 1 - j1 >= HALO_CELLS)
        zx, zy = grid_resolution(support)
        status = (ChlorophyllFieldStatus.VALIDA_EN_FECHA_NOMINAL
                  if stamp.date() == empty.requested_date else ChlorophyllFieldStatus.VALIDA_RECIENTE)
        result = replace(
            empty, nominal_product_date=stamp.date(), time_utc=stamp,
            nominal_age_hours=age, matches_requested_nominal_date=stamp.date() == empty.requested_date,
            grid=grid, derivation_support=support, halo_complete=halo_ok,
            n_grid_cells=n_grid, n_marine_cells=n_marine, n_valid_cells=n_valid,
            n_uncertainty_cells=n_unc, coverage_fraction=n_valid / n_marine if n_marine else None,
            median_zonal_resolution_km=zx, median_meridional_resolution_km=zy,
            status=status if n_valid else ChlorophyllFieldStatus.SIN_DATOS,
            reason=None if n_valid else "no_valid_chlorophyll_in_requested_field",
        )
        if n_valid:
            return result
        if latest_empty is None:
            latest_empty = result
    return latest_empty if latest_empty is not None else empty


def chlorophyll_field_from_dataset(
    ds, minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude,
    target_date, *, options: ChlorophyllOptions, retrieved_at_utc: datetime | None = None,
) -> ChlorophyllField:
    """Ruta local reproducible; no consulta la red ni inventa la versión del archivo.

    Requiere arrays CF decodificados (por ejemplo xr.open_dataset por defecto).
    Datos inválidos producen ERROR, argumentos inválidos producen ValueError.
    Si el archivo no contiene halo, sus bordes quedarán sin soporte completo.
    """
    bounds, query = _bounds_and_query(
        minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude, target_date, options)
    retrieved = _aware_utc(retrieved_at_utc, "retrieved_at_utc") if retrieved_at_utc is not None else None
    empty = _empty_field(bounds, query, target_date, options, retrieved)
    try:
        return _select_field(ds, empty)
    except Exception as exc:
        return _failure(empty, exc, "invalid_dataset")


def fetch_chlorophyll_field(
    minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude,
    target_date, *, options: ChlorophyllOptions,
) -> ChlorophyllField:
    """Consulta versionada única, con halo; sin fuente alternativa ni relleno."""
    bounds, query = _bounds_and_query(
        minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude, target_date, options)
    empty = replace(
        _empty_field(bounds, query, target_date, options),
        source_access="copernicus_query", dataset_version=DATASET_VERSION,
        dataset_part=DATASET_PART, version_basis="explicit_version_and_part_in_query",
    )
    start = options.as_of_utc - timedelta(hours=options.max_nominal_age_hours)
    last_complete_day_end = options.as_of_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    target_end = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
    end = min(target_end, last_complete_day_end) - timedelta(microseconds=1)
    if start > end:
        return replace(empty, reason="outside_age_window")
    try:
        with copernicusmarine.open_dataset(
            dataset_id=DATASET_ID, dataset_version=DATASET_VERSION, dataset_part=DATASET_PART,
            variables=list(VARIABLES),
            minimum_latitude=query.minimum_latitude, maximum_latitude=query.maximum_latitude,
            minimum_longitude=query.minimum_longitude, maximum_longitude=query.maximum_longitude,
            start_datetime=start, end_datetime=end, coordinates_selection_method="inside",
        ) as ds:
            ds.load()
            empty = replace(empty, retrieved_at_utc=datetime.now(timezone.utc))
            return _select_field(ds, empty)
    except Exception as exc:
        return _failure(empty, exc, "source_failure")
