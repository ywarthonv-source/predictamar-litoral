"""
Ingesta de clorofila-a — PredictaMAR Litoral (Pucusana)

FUENTE ÚNICA: cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D
(producto OCEANCOLOUR_GLO_BGC_L4_NRT_009_102, versión 202311, parte default),
variable CHL, unidades nativas 'milligram m-3', cadencia diaria (P1D) con
timestamps nativos a las 00:00 UTC.

POR QUÉ UNA SOLA FUENTE (decidido ago 2026, tras auditoría del catálogo):
el catálogo oficial no ofrece actualmente ninguna fuente global activa de
mayor resolución que cubra Pucusana, de modo que este módulo consulta un
único producto: no hay segunda fuente ni conmutación entre productos. El
diagnóstico real del 7 al 14 de agosto de 2026 sobre el punto de referencia
comparó los tres candidatos activos y dio 50.0% y 16.7% de cobertura
temporal para los dos productos L3, frente al 100.0% de este L4 gap-free.
La elección responde a CONTINUIDAD OPERATIVA, no a validez predictiva: no
existe evidencia de campo de que mejore la predicción.

NATURALEZA DEL PRODUCTO:
L4 gap-free multifuente es un producto PROCESADO por el proveedor, que ya
aplica combinación de sensores y relleno de huecos. NO es una medición
puntual in situ en Pucusana. PredictaMAR no añade ninguna capa adicional de
relleno: cada valor entregado es un valor nativo del producto, en una celda
y un instante concretos y declarados.

SEMÁNTICA TEMPORAL:
Para una fecha local solicitada, la referencia es el final de ese día en
America/Lima (23:59:59). Los timestamps nativos de 00:00 UTC caen a las
19:00 hora local del día ANTERIOR, así que la asociación con una fecha local
se hace siempre después de convertir a Lima, nunca sobre la fecha UTC. Nunca
se usan observaciones posteriores al final local solicitado. Entre los
instantes con alguna celda válida y admisible se prefiere el más reciente;
si su fecha local coincide con la solicitada el estado es
VALIDA_EN_FECHA_LOCAL, y si es anterior pero su antigüedad no supera
MAX_TEMPORAL_AGE_HOURS el estado es VALIDA_RECIENTE. No se interpola en el
tiempo, no se rellenan fechas y no se fabrican valores.

SELECCIÓN ESPACIAL:
De las celdas del recuadro consultado se descartan las NaN y las que estén a
más de MAX_VALID_CELL_DISTANCE_KM; entre las restantes se toma la MÁS
CERCANA, con desempate determinista por menor latitud y luego menor
longitud. No se toma máximo espacial ni promedio: la clorofila es una
lectura ambiental puntual de referencia, no una compuerta de seguridad.

DISEÑO FAIL-SAFE:
Los fallos de red, de datos o de programación se registran con
logger.exception y producen SIN_DATOS, nunca un valor por defecto. Los
errores de USO (argumentos inválidos) se propagan como ValueError y no se
convierten en ausencia de datos. Una lectura SIN_DATOS conserva toda la
procedencia estática: dataset, variable, unidades, alcance y advertencia.

SIN umbrales pesqueros, sin clasificación favorable, sin ranking, sin
kill_switch y sin conversión de unidades. A la fecha esta variable NO está
admitida al scoring (ver config/variables_spec.yaml).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

import copernicusmarine
import pandas as pd

logger = logging.getLogger(__name__)

DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"
VARIABLE = "CHL"
UNITS = "milligram m-3"
STANDARD_NAME = "mass_concentration_of_chlorophyll_a_in_sea_water"

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano

DATA_SCOPE = "clorofila_regional_referencia"

DATA_SCOPE_WARNING = (
    "Clorofila-a regional de referencia, en las unidades nativas del producto "
    "(milligram m-3); no se convierte a otra escala. Procede de un producto L4 "
    "gap-free multifuente PROCESADO por el proveedor, que ya aplica combinación "
    "de sensores y relleno de huecos: NO es una medición puntual ni in situ en "
    "Pucusana. Cuando existe una lectura válida, corresponde al valor nativo de "
    "la celda válida MÁS CERCANA al punto solicitado dentro del recuadro "
    "consultado (grilla ~4.5 km) y dentro de la distancia máxima aceptable, en "
    "un único instante nativo. Si el estado es VALIDA_RECIENTE, la observación "
    "es de una fecha local ANTERIOR a la solicitada y su antigüedad real está "
    "registrada en temporal_age_hours. Si el estado es SIN_DATOS no se tomó "
    "ningún valor ni celda: PredictaMAR no interpola, no rellena fechas y no "
    "fabrica valores."
)

# ---- LÍMITE ESPACIAL (PROVISIONAL, PROPIO DE ESTE PRODUCTO) ----------
# Distancia máxima aceptable entre el punto solicitado y el centro de la
# celda utilizada. NO se hereda del perfil físico PT6H ni de ningún otro
# módulo: la grilla de este producto es distinta (~4.5 km zonales en
# Pucusana). Valor PROVISIONAL, no validado por la asesoría oceanográfica.
MAX_VALID_CELL_DISTANCE_KM = 6.5
# ----------------------------------------------------------------------

# ---- LÍMITE DE ANTIGÜEDAD (PROVISIONAL, PROPIO DE ESTE PRODUCTO) -----
# Antigüedad máxima aceptable de la observación respecto del final del día
# local solicitado. Responde a la cadencia diaria y a la latencia del
# producto NRT. Valor PROVISIONAL, no validado por la asesoría
# oceanográfica, y no comparable con los límites temporales de otros
# módulos.
MAX_TEMPORAL_AGE_HOURS = 72.0
# ----------------------------------------------------------------------

# Margen adicional de la ventana retrospectiva de consulta, por encima de
# MAX_TEMPORAL_AGE_HOURS, para no cortar la rejilla diaria en su borde.
QUERY_MARGIN_HOURS = 24.0


class ChlorophyllStatus(str, Enum):
    VALIDA_EN_FECHA_LOCAL = "valida_en_fecha_local"
    VALIDA_RECIENTE = "valida_reciente"
    SIN_DATOS = "sin_datos"


@dataclass
class ChlorophyllReading:
    lat: float  # solicitada
    lon: float  # solicitada
    date: date  # fecha LOCAL solicitada
    value_mg_m3: float | None
    time_utc: datetime | None
    time_local: datetime | None
    temporal_age_hours: float | None
    inside_requested_local_date: bool | None
    cell_lat: float | None
    cell_lon: float | None
    distance_km: float | None
    dataset_id: str
    variable: str
    units: str
    data_scope: str
    scope_warning: str
    status: ChlorophyllStatus


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia real entre dos puntos geográficos (no solo diferencia de grados)."""
    R_EARTH_KM = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R_EARTH_KM * asin(sqrt(a))


def _validate(lat: float, lon: float, target_date: date) -> None:
    """
    Errores de USO: se propagan como ValueError y nunca se convierten en
    ausencia de datos.
    """
    if not isinstance(lat, (int, float)) or isinstance(lat, bool) or not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitud inválida: {lat!r}. Debe ser un número entre -90 y 90.")
    if not isinstance(lon, (int, float)) or isinstance(lon, bool) or not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitud inválida: {lon!r}. Debe ser un número entre -180 y 180.")
    if not isinstance(target_date, date):
        raise ValueError(f"target_date inválida: {target_date!r}. Debe ser datetime.date.")


def _local_end_and_window(target_date: date) -> tuple[datetime, datetime, datetime]:
    """
    Devuelve (final_local, final_utc, inicio_consulta_utc).

    El final de referencia es 23:59:59 de la fecha LOCAL solicitada. La
    ventana de consulta es retrospectiva: cubre MAX_TEMPORAL_AGE_HOURS más
    QUERY_MARGIN_HOURS, y termina exactamente en el final local para no
    solicitar observaciones posteriores.
    """
    local_end = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ_PUCUSANA)
    local_end += timedelta(hours=23, minutes=59, seconds=59)
    end_utc = local_end.astimezone(timezone.utc)
    start_utc = end_utc - timedelta(hours=MAX_TEMPORAL_AGE_HOURS + QUERY_MARGIN_HOURS)
    return local_end, end_utc, start_utc


def _empty_reading(lat: float, lon: float, target_date: date) -> ChlorophyllReading:
    """SIN_DATOS: sin valores ni celda, pero con toda la procedencia estática."""
    return ChlorophyllReading(
        lat=lat,
        lon=lon,
        date=target_date,
        value_mg_m3=None,
        time_utc=None,
        time_local=None,
        temporal_age_hours=None,
        inside_requested_local_date=None,
        cell_lat=None,
        cell_lon=None,
        distance_km=None,
        dataset_id=DATASET_ID,
        variable=VARIABLE,
        units=UNITS,
        data_scope=DATA_SCOPE,
        scope_warning=DATA_SCOPE_WARNING,
        status=ChlorophyllStatus.SIN_DATOS,
    )


def _nearest_valid_cell(da, t_naive, lat: float, lon: float):
    """
    Celda válida MÁS CERCANA al punto para un instante concreto.

    Descarta NaN y celdas a más de MAX_VALID_CELL_DISTANCE_KM. Desempate
    determinista: menor distancia, luego menor latitud, luego menor
    longitud. Devuelve la tupla (distance_km, cell_lat, cell_lon, valor)
    -- ese es el orden real, el mismo que desempaqueta el consumidor -- o
    None si ninguna celda es admisible.
    """
    candidatos = []
    for lat_val in da.latitude.values:
        for lon_val in da.longitude.values:
            cell_lat, cell_lon = float(lat_val), float(lon_val)
            valor = float(da.sel(time=t_naive, latitude=cell_lat, longitude=cell_lon).values)
            if valor != valor:  # NaN
                continue
            dist = _haversine_km(lat, lon, cell_lat, cell_lon)
            if dist > MAX_VALID_CELL_DISTANCE_KM:
                continue
            candidatos.append((dist, cell_lat, cell_lon, valor))
    if not candidatos:
        return None
    candidatos.sort()
    return candidatos[0]


def fetch_chlorophyll(lat: float, lon: float, target_date: date) -> ChlorophyllReading:
    """
    Devuelve la lectura de clorofila-a de referencia para el punto y la fecha
    LOCAL solicitados.

    Reglas temporales:
      1. La referencia es 23:59:59 de target_date en America/Lima.
      2. Se consulta una ventana retrospectiva que cubre la antigüedad
         permitida y la cadencia diaria.
      3. Cada timestamp nativo UTC se convierte a Lima antes de asociarlo a
         una fecha local.
      4. Nunca se usan observaciones posteriores al final local solicitado.
      5. Entre los instantes con celda válida y admisible se prefiere el más
         reciente: misma fecha local -> VALIDA_EN_FECHA_LOCAL; anterior con
         antigüedad <= MAX_TEMPORAL_AGE_HOURS -> VALIDA_RECIENTE; por encima
         de ese límite -> SIN_DATOS.

    Lanza ValueError si los argumentos son inválidos.
    """
    _validate(lat, lon, target_date)
    local_end, end_utc, start_utc = _local_end_and_window(target_date)

    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=lon - 0.05,
            maximum_longitude=lon + 0.05,
            minimum_latitude=lat - 0.05,
            maximum_latitude=lat + 0.05,
            start_datetime=start_utc,
            end_datetime=end_utc,
            # coordinates_selection_method NO se fija: afectaría también a la
            # dimensión temporal y podría traer instantes fuera de la ventana.
        )
        da = ds[VARIABLE]

        if da.sizes.get("time", 0) == 0:
            logger.warning(
                "Sin instantes devueltos para (%s, %s) %s [%s]",
                lat, lon, target_date, DATASET_ID,
            )
            return _empty_reading(lat, lon, target_date)

        instantes = []
        for t in da.time.values:
            t_naive = pd.Timestamp(t).to_pydatetime()
            t_utc = t_naive.replace(tzinfo=timezone.utc)
            if t_utc > end_utc:  # observación posterior al final local: nunca se usa
                continue
            instantes.append((t_utc, t_naive))
        instantes.sort(key=lambda x: x[0], reverse=True)  # más reciente primero

        for t_utc, t_naive in instantes:
            edad = (end_utc - t_utc).total_seconds() / 3600.0
            if edad > MAX_TEMPORAL_AGE_HOURS:
                break  # ordenados de más reciente a más antiguo: el resto es peor
            celda = _nearest_valid_cell(da, t_naive, lat, lon)
            if celda is None:
                continue
            dist, cell_lat, cell_lon, valor = celda
            t_local = t_utc.astimezone(TZ_PUCUSANA)
            misma_fecha = t_local.date() == target_date
            return ChlorophyllReading(
                lat=lat,
                lon=lon,
                date=target_date,
                value_mg_m3=valor,
                time_utc=t_utc,
                time_local=t_local,
                temporal_age_hours=edad,
                inside_requested_local_date=misma_fecha,
                cell_lat=cell_lat,
                cell_lon=cell_lon,
                distance_km=dist,
                dataset_id=DATASET_ID,
                variable=VARIABLE,
                units=UNITS,
                data_scope=DATA_SCOPE,
                scope_warning=DATA_SCOPE_WARNING,
                status=(
                    ChlorophyllStatus.VALIDA_EN_FECHA_LOCAL
                    if misma_fecha
                    else ChlorophyllStatus.VALIDA_RECIENTE
                ),
            )

        logger.warning(
            "Sin instante admisible para (%s, %s) %s (limite %.1f h, %.1f km)",
            lat, lon, target_date, MAX_TEMPORAL_AGE_HOURS, MAX_VALID_CELL_DISTANCE_KM,
        )
        return _empty_reading(lat, lon, target_date)

    except Exception:
        # Fallo de red, de datos o de programación. Se registra con traza para
        # que no quede indistinguible de una ausencia legítima de datos; no se
        # registran credenciales ni información sensible.
        logger.exception(
            "Fallo al obtener clorofila para (%s, %s) %s [%s]",
            lat, lon, target_date, DATASET_ID,
        )
        return _empty_reading(lat, lon, target_date)