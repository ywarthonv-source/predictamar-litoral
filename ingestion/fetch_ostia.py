"""
Campo diario de SST observada OSTIA — PredictaMAR Litoral.

FUENTE OFICIAL:
  producto  SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001
  dataset   METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2
  variables analysed_sst y analysis_error

OSTIA es un análisis L4 diario y gap-free producido por Met Office a partir
de observaciones satelitales e in situ. "Gap-free" describe el procesamiento
del proveedor: no convierte el producto en una medición puntual ni directa en
Pucusana. PredictaMAR no interpola ni rellena el campo recibido.

Este módulo devuelve un CAMPO ESPACIAL, no una lectura puntual. El recuadro es
un argumento técnico explícito y no se confunde con el alcance operativo de
0–10 km desde el litoral. Los valores nativos se conservan en kelvin y se
incluye además la conversión exacta a grados Celsius para permitir compararlos
con la SST de modelo y derivar gradientes comprensibles.

No contiene umbrales pesqueros, ranking, scoring ni afirmaciones de presencia
de cardumen.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from numbers import Real
from zoneinfo import ZoneInfo

import copernicusmarine
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PRODUCT_ID = "SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001"
DATASET_ID = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
VARIABLE_SST = "analysed_sst"
VARIABLE_ERROR = "analysis_error"
STANDARD_NAME = "sea_surface_foundation_temperature"
UNITS_NATIVE = "kelvin"
UNITS_CELSIUS = "degree_Celsius"
NOMINAL_RESOLUTION_DEG = 0.05
PROCESSING_LEVEL = "L4"

TZ_PUCUSANA = ZoneInfo("America/Lima")

# OSTIA representa medias diarias UTC. El PUM las define de medianoche a
# medianoche y centradas al mediodía, pero el eje servido por Copernicus puede
# aparecer etiquetado a las 00:00 UTC. Por eso la FECHA nominal se obtiene del
# día UTC de la coordenada cruda y nunca de su conversión a America/Lima.
#
# La latencia operacional puede hacer que la última fecha nominal disponible
# sea anterior a la solicitada. Este fallback es provisional y siempre queda
# expuesto; no implica validez pesquera.
MAX_NOMINAL_AGE_DAYS = 2

DATA_SCOPE = "sst_observada_ostia_regional_referencia"
DATA_SCOPE_WARNING = (
    "SST de fundación observada OSTIA, producto L4 diario gap-free procesado "
    "por Met Office a partir de observaciones satelitales e in situ. No es una "
    "medición puntual ni in situ en Pucusana y no detecta cardúmenes. El campo "
    "corresponde a una única fecha nominal y coordenada temporal nativa, y al "
    "recuadro técnico solicitado. La coordenada temporal cruda se conserva "
    "como procedencia y nunca se convierte a hora local para decidir qué día "
    "representa el producto. "
    "PredictaMAR no interpola ni rellena celdas: los faltantes permanecen como "
    "faltantes. La resolución nominal de 0.05 grados sigue siendo regional para "
    "un alcance litoral de 0–10 km."
)


class OstiaStatus(str, Enum):
    VALIDA_EN_FECHA_NOMINAL = "valida_en_fecha_nominal"
    VALIDA_RECIENTE = "valida_reciente"
    SIN_DATOS = "sin_datos"


Matrix = tuple[tuple[float | None, ...], ...]


@dataclass(frozen=True)
class OstiaField:
    requested_date: date
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float
    nominal_product_date: date | None
    time_utc: datetime | None
    time_local: datetime | None
    nominal_age_days: int | None
    matches_requested_nominal_date: bool | None
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    sst_kelvin: Matrix
    sst_celsius: Matrix
    analysis_error_kelvin: Matrix
    n_grid_cells: int
    n_valid_cells: int
    coverage_fraction: float | None
    product_id: str
    dataset_id: str
    variables: tuple[str, str]
    standard_name: str
    native_units: str
    converted_units: str
    processing_level: str
    nominal_resolution_deg: float
    data_scope: str
    scope_warning: str
    status: OstiaStatus


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and np.isfinite(value)


def _validate_bounds(
    minimum_latitude: float,
    maximum_latitude: float,
    minimum_longitude: float,
    maximum_longitude: float,
    target_date: date,
) -> None:
    values = (
        ("minimum_latitude", minimum_latitude, -90.0, 90.0),
        ("maximum_latitude", maximum_latitude, -90.0, 90.0),
        ("minimum_longitude", minimum_longitude, -180.0, 180.0),
        ("maximum_longitude", maximum_longitude, -180.0, 180.0),
    )
    for name, value, lower, upper in values:
        if not _is_number(value) or not (lower <= float(value) <= upper):
            raise ValueError(
                f"{name} inválida: {value!r}. Debe ser un número finito entre "
                f"{lower:g} y {upper:g}."
            )
    if float(minimum_latitude) >= float(maximum_latitude):
        raise ValueError("minimum_latitude debe ser menor que maximum_latitude.")
    if float(minimum_longitude) >= float(maximum_longitude):
        raise ValueError("minimum_longitude debe ser menor que maximum_longitude.")
    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError(  # noqa: TRY004 - contrato público homogéneo para argumentos inválidos
            f"target_date inválida: {target_date!r}. Debe ser datetime.date."
        )


def _utc_query_window(target_date: date) -> tuple[datetime, datetime]:
    """Incluye etiquetas diarias tanto de 00:00 como de 12:00 UTC."""
    start_date = target_date - timedelta(days=MAX_NOMINAL_AGE_DAYS)
    start_utc = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc += timedelta(hours=23, minutes=59, seconds=59)
    return end_utc, start_utc


def _empty_field(
    minimum_latitude: float,
    maximum_latitude: float,
    minimum_longitude: float,
    maximum_longitude: float,
    target_date: date,
) -> OstiaField:
    return OstiaField(
        requested_date=target_date,
        minimum_latitude=float(minimum_latitude),
        maximum_latitude=float(maximum_latitude),
        minimum_longitude=float(minimum_longitude),
        maximum_longitude=float(maximum_longitude),
        nominal_product_date=None,
        time_utc=None,
        time_local=None,
        nominal_age_days=None,
        matches_requested_nominal_date=None,
        latitudes=(),
        longitudes=(),
        sst_kelvin=(),
        sst_celsius=(),
        analysis_error_kelvin=(),
        n_grid_cells=0,
        n_valid_cells=0,
        coverage_fraction=None,
        product_id=PRODUCT_ID,
        dataset_id=DATASET_ID,
        variables=(VARIABLE_SST, VARIABLE_ERROR),
        standard_name=STANDARD_NAME,
        native_units=UNITS_NATIVE,
        converted_units=UNITS_CELSIUS,
        processing_level=PROCESSING_LEVEL,
        nominal_resolution_deg=NOMINAL_RESOLUTION_DEG,
        data_scope=DATA_SCOPE,
        scope_warning=DATA_SCOPE_WARNING,
        status=OstiaStatus.SIN_DATOS,
    )


def _canonicalise(da, variable_name: str):
    """Normaliza solo los NOMBRES de ejes conocidos; nunca remuestrea datos."""
    aliases = {
        "latitude": ("latitude", "lat"),
        "longitude": ("longitude", "lon"),
        "time": ("time",),
    }
    rename: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        found = next((name for name in candidates if name in da.dims), None)
        if found is None:
            raise ValueError(
                f"{variable_name} no contiene el eje requerido {canonical!r}; "
                f"dimensiones recibidas: {tuple(da.dims)}."
            )
        if found != canonical:
            rename[found] = canonical
    if rename:
        da = da.rename(rename)

    required = ("time", "latitude", "longitude")
    extras = [dim for dim in da.dims if dim not in required]
    for dim in extras:
        if da.sizes[dim] != 1:
            raise ValueError(
                f"{variable_name} contiene una dimensión no soportada {dim!r} "
                f"con tamaño {da.sizes[dim]}."
            )
        da = da.isel({dim: 0}, drop=True)
    return da.transpose(*required)


def _assert_same_grid(sst, error) -> None:
    for coord in ("time", "latitude", "longitude"):
        if sst.sizes[coord] != error.sizes[coord] or not np.array_equal(
            sst[coord].values, error[coord].values
        ):
            raise ValueError(
                f"{VARIABLE_SST} y {VARIABLE_ERROR} no comparten exactamente "
                f"el eje {coord!r}. No se alinean ni interpolan silenciosamente."
            )


def _as_utc(value) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.to_pydatetime().replace(tzinfo=timezone.utc)
    return stamp.tz_convert("UTC").to_pydatetime()


def _matrix(values: np.ndarray, valid: np.ndarray, offset: float = 0.0) -> Matrix:
    return tuple(
        tuple(float(values[i, j] + offset) if valid[i, j] else None for j in range(values.shape[1]))
        for i in range(values.shape[0])
    )


def fetch_ostia_field(
    minimum_latitude: float,
    maximum_latitude: float,
    minimum_longitude: float,
    maximum_longitude: float,
    target_date: date,
) -> OstiaField:
    """
    Obtiene el campo OSTIA más reciente para la fecha nominal solicitada.

    ``target_date`` identifica la media diaria UTC del producto, no una hora
    local de observación. La coordenada temporal cruda se conserva, pero su
    conversión a America/Lima no se usa para asignar la fecha del producto. Si
    la fecha nominal solicitada no contiene SST válida, se examinan fechas
    nominales anteriores dentro del límite; nunca se combinan dos fechas.
    """
    _validate_bounds(
        minimum_latitude,
        maximum_latitude,
        minimum_longitude,
        maximum_longitude,
        target_date,
    )
    end_utc, start_utc = _utc_query_window(target_date)

    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE_SST, VARIABLE_ERROR],
            minimum_longitude=float(minimum_longitude),
            maximum_longitude=float(maximum_longitude),
            minimum_latitude=float(minimum_latitude),
            maximum_latitude=float(maximum_latitude),
            start_datetime=start_utc,
            end_datetime=end_utc,
        )
        sst = _canonicalise(ds[VARIABLE_SST], VARIABLE_SST)
        error = _canonicalise(ds[VARIABLE_ERROR], VARIABLE_ERROR)
        _assert_same_grid(sst, error)

        units = str(sst.attrs.get("units", "")).strip().lower()
        if units and units not in {"k", "kelvin"}:
            raise ValueError(
                f"{VARIABLE_SST} declaró unidades inesperadas {units!r}; "
                "no se aplicará una conversión potencialmente incorrecta."
            )

        if sst.sizes.get("time", 0) == 0:
            return _empty_field(
                minimum_latitude,
                maximum_latitude,
                minimum_longitude,
                maximum_longitude,
                target_date,
            )

        candidates = []
        for raw_time in sst.time.values:
            time_utc = _as_utc(raw_time)
            nominal_product_date = time_utc.date()
            if nominal_product_date > target_date:
                continue
            nominal_age_days = (target_date - nominal_product_date).days
            if nominal_age_days <= MAX_NOMINAL_AGE_DAYS:
                candidates.append(
                    (
                        nominal_product_date,
                        time_utc,
                        raw_time,
                        nominal_age_days,
                    )
                )
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

        for (
            nominal_product_date,
            time_utc,
            raw_time,
            nominal_age_days,
        ) in candidates:
            sst_slice = sst.sel(time=raw_time).sortby("latitude").sortby("longitude")
            err_slice = error.sel(time=raw_time).sortby("latitude").sortby("longitude")
            sst_values = np.asarray(sst_slice.values, dtype=float)
            err_values = np.asarray(err_slice.values, dtype=float)
            if sst_values.ndim != 2 or err_values.shape != sst_values.shape:
                raise ValueError("El campo OSTIA seleccionado no es una grilla 2D coherente.")

            valid = np.isfinite(sst_values)
            n_valid = int(valid.sum())
            if n_valid == 0:
                continue

            valid_error = valid & np.isfinite(err_values) & (err_values >= 0.0)
            n_grid = int(sst_values.size)
            time_local = time_utc.astimezone(TZ_PUCUSANA)
            same_nominal_date = nominal_product_date == target_date
            return OstiaField(
                requested_date=target_date,
                minimum_latitude=float(minimum_latitude),
                maximum_latitude=float(maximum_latitude),
                minimum_longitude=float(minimum_longitude),
                maximum_longitude=float(maximum_longitude),
                nominal_product_date=nominal_product_date,
                time_utc=time_utc,
                time_local=time_local,
                nominal_age_days=nominal_age_days,
                matches_requested_nominal_date=same_nominal_date,
                latitudes=tuple(float(v) for v in sst_slice.latitude.values),
                longitudes=tuple(float(v) for v in sst_slice.longitude.values),
                sst_kelvin=_matrix(sst_values, valid),
                sst_celsius=_matrix(sst_values, valid, offset=-273.15),
                analysis_error_kelvin=_matrix(err_values, valid_error),
                n_grid_cells=n_grid,
                n_valid_cells=n_valid,
                coverage_fraction=n_valid / n_grid,
                product_id=PRODUCT_ID,
                dataset_id=DATASET_ID,
                variables=(VARIABLE_SST, VARIABLE_ERROR),
                standard_name=STANDARD_NAME,
                native_units=UNITS_NATIVE,
                converted_units=UNITS_CELSIUS,
                processing_level=PROCESSING_LEVEL,
                nominal_resolution_deg=NOMINAL_RESOLUTION_DEG,
                data_scope=DATA_SCOPE,
                scope_warning=DATA_SCOPE_WARNING,
                status=(
                    OstiaStatus.VALIDA_EN_FECHA_NOMINAL
                    if same_nominal_date
                    else OstiaStatus.VALIDA_RECIENTE
                ),
            )

        logger.warning(
            "Sin campo OSTIA admisible para %s dentro de %d días nominales [%s]",
            target_date,
            MAX_NOMINAL_AGE_DAYS,
            DATASET_ID,
        )
        return _empty_field(
            minimum_latitude,
            maximum_latitude,
            minimum_longitude,
            maximum_longitude,
            target_date,
        )
    except Exception:
        logger.exception(
            "Fallo al obtener el campo OSTIA para %s [%s]",
            target_date,
            DATASET_ID,
        )
        return _empty_field(
            minimum_latitude,
            maximum_latitude,
            minimum_longitude,
            maximum_longitude,
            target_date,
        )
