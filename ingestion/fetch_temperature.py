"""
Ingesta de temperatura — PredictaMAR Litoral (Pucusana)

FUENTE OPERATIVA: cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i
(CMEMS GLOBAL_ANALYSISFORECAST_PHY_001_024), variable thetao, temperatura
potencial INSTANTÁNEA cada 6 horas.

Por qué PT6H-i y no P1D (decidido ago 2026, tras diagnóstico):
P1D entrega una media diaria por día UTC, centrada al mediodía. El día UTC
no coincide con la jornada local del pescador (en Lima abarca ~19:00 del
día local anterior a ~19:00 del día local seleccionado), y al ser una media
no distingue una salida de madrugada de una de mediodía. Como PredictaMAR
debe permitir seleccionar fecha Y horario, PT6H-i es la fuente coherente.
P1D queda como posible contexto diario complementario, nunca como
sustituto de la temperatura de la ventana de faena.

Los cuatro instantes nativos (00/06/12/18 UTC) caen, en hora local de
Pucusana, en 01:00, 07:00, 13:00 y 19:00. El de las 19:00 local
corresponde a las 00:00 UTC del día siguiente: la conversión local->UTC
debe conservar ese cruce de fecha (verificado en diagnóstico).

ALCANCE DE ESTA FUENTE:
Es TEMPERATURA REGIONAL DE REFERENCIA, no una medición puntual ni
instantánea en Pucusana. La grilla (~9km) no resuelve la costa: la celda
válida más cercana puede estar a varios km. Por eso cada TemperatureReading
lleva su propio `data_scope` y `scope_warning`: la limitación viaja con el
dato, no solo en este docstring.

ESTRATEGIA DE PROFUNDIDAD (verificada en diagnóstico):
El primer nivel vertical real del producto NO es 0.0 m (es ~0.494 m), y
pedir minimum_depth=0.0 genera una advertencia de rango excedido en cada
consulta. Se consulta con `maximum_depth=SURFACE_SEARCH_MAX_DEPTH_M` y SIN
`minimum_depth`, y se toma dinámicamente el nivel más somero que el propio
dataset devuelva -- así no se hardcodea 0.494025 (que podría cambiar en
una versión futura del producto) ni se descargan los 50 niveles.

NO SE USA coordinates_selection_method='nearest' al abrir el dataset:
afectaría también la dimensión temporal e incorporaría timestamps fuera de
la ventana solicitada (verificado en diagnóstico: traía el día siguiente).

DISEÑO FAIL-SAFE: si no hay ninguna combinación temporal y espacial
aceptable, el estado es SIN_DATOS con todos los campos de dato en None.
NUNCA se interpola, ni se fabrica un valor, ni se rellena con un promedio.
La excepción que provoque un SIN_DATOS se registra por logging (sin
credenciales), para que un error de programación no quede indistinguible
de una ausencia legítima de datos.

SIN kill_switch: la temperatura es una variable del futuro motor de puntaje
pesquero, no una autorización de seguridad. Aun así, SIN_DATOS jamás debe
convertirse en un valor favorable inventado.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

import copernicusmarine
import pandas as pd

logger = logging.getLogger(__name__)

DATASET_ID = "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i"
VARIABLE = "thetao"

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano

DATA_SCOPE = "temperatura_regional_referencia"

DATA_SCOPE_WARNING = (
    "Temperatura regional de referencia. Cuando existe una lectura válida, "
    "procede de uno o más valores instantáneos (producto PT6H-i, cadencia "
    "de 6 h) del nivel superficial disponible del modelo (~0.5 m), obtenidos "
    "de una única celda válida dentro del recuadro consultado (grilla ~9 km) "
    "y dentro de la distancia máxima aceptable. Para las muestras dentro de "
    "la ventana, la celda se selecciona primero por mayor cobertura temporal "
    "y, en caso de empate, por menor distancia Haversine. En el fallback "
    "temporal se utiliza la celda válida más cercana al punto solicitado que "
    "tenga dato en el timestamp seleccionado. NO es una medición puntual ni "
    "in situ en Pucusana. Si el estado es VALIDA_CERCANA_EN_TIEMPO, la "
    "muestra procede de un instante FUERA de la ventana horaria solicitada "
    "y el desfase real está registrado en temporal_offset_hours. Si el "
    "estado es SIN_DATOS, no se tomó ningún valor ni celda: nunca se "
    "interpola ni se fabrica una temperatura."
)

# ---- BANDA DE BÚSQUEDA SUPERFICIAL -----------------------------------
# Se usa solo como techo de la consulta; el nivel efectivo es el más
# somero que devuelva el dataset dentro de esta banda.
SURFACE_SEARCH_MAX_DEPTH_M = 5.0
# ----------------------------------------------------------------------

# ---- LÍMITE ESPACIAL (PROVISIONAL) -----------------------------------
# Mismo criterio y misma justificación que en fetch_waves.py: la mitad de
# la diagonal de una celda de la grilla nativa (~9.2 km). Una celda a más
# de esa distancia ya está más cerca de la SIGUIENTE celda que del punto
# solicitado, y no debería tratarse como "la referencia" de este punto.
MAX_VALID_CELL_DISTANCE_KM = 6.5  # TODO: PROVISIONAL -- pendiente de validación oceanográfica
# ----------------------------------------------------------------------

# ---- LÍMITE TEMPORAL DE FALLBACK (PROVISIONAL) -----------------------
# Si la ventana local solicitada es estrecha, puede no contener ningún
# instante nativo (los hay cada 6 h). En ese caso se acepta el instante
# nativo más cercano FUERA de la ventana, siempre que su desfase respecto
# del borde más cercano no supere este límite. 3.0 h = mitad de la
# cadencia del producto. NO se interpola: el valor es siempre nativo.
MAX_TEMPORAL_OFFSET_HOURS = 3.0  # TODO: PROVISIONAL -- pendiente de validación oceanográfica
# ----------------------------------------------------------------------


class TemperatureStatus(str, Enum):
    VALIDA_EN_VENTANA = "valida_en_ventana"
    VALIDA_CERCANA_EN_TIEMPO = "valida_cercana_en_tiempo"
    SIN_DATOS = "sin_datos"


@dataclass
class TemperatureSample:
    time_utc: datetime
    time_local: datetime
    value_celsius: float
    inside_requested_window: bool
    temporal_offset_hours: float  # 0.0 si está dentro de la ventana


@dataclass
class TemperatureReading:
    lat: float  # solicitada
    lon: float  # solicitada
    date: date  # fecha LOCAL solicitada
    hour_start_local: int
    hour_end_local: int
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    samples: list[TemperatureSample] = field(default_factory=list)
    # ---- cobertura temporal ----
    # n_native_times_in_window: cuántos instantes nativos existen DENTRO de
    # la ventana (independiente de si su valor era válido en la celda).
    # coverage_fraction: proporción de esos timestamps nativos DENTRO de la
    # ventana que tienen una muestra válida de la celda seleccionada.
    # NO mide la cobertura de muestras externas: una muestra obtenida por
    # fallback temporal deja coverage_fraction en 0.0 (no cubre ningún
    # instante interno solicitado), o en None si no había ningún instante
    # nativo dentro de la ventana. Permite distinguir una serie COMPLETA de
    # una PARCIAL aunque ambas tengan estado VALIDA_EN_VENTANA.
    n_native_times_in_window: int = 0
    n_samples: int = 0
    n_missing_samples: int = 0
    coverage_fraction: float | None = None
    # ---- profundidad ----
    depth_m_requested: float = 0.0  # superficie conceptual
    depth_m_actual: float | None = None  # nivel real usado (~0.494 m)
    # ---- celda espacial ----
    cell_lat: float | None = None
    cell_lon: float | None = None
    distance_km: float | None = None
    # ---- procedencia técnica ----
    dataset_id: str = DATASET_ID
    variable: str = VARIABLE
    data_scope: str = DATA_SCOPE
    scope_warning: str = DATA_SCOPE_WARNING
    status: TemperatureStatus = TemperatureStatus.SIN_DATOS


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia real entre dos puntos geográficos (no solo diferencia de grados)."""
    R_EARTH_KM = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R_EARTH_KM * asin(sqrt(a))


def _local_window_to_utc(
    target_date: date, hour_start: int, hour_end: int
) -> tuple[datetime, datetime]:
    """
    Construye la ventana horaria en hora LOCAL de Pucusana y la convierte a
    UTC. Nunca cruza la fecha LOCAL solicitada, aunque en UTC sí cruce de
    fecha -- eso es correcto y necesario: la muestra de las 19:00 local
    corresponde a las 00:00 UTC del día siguiente.
    """
    if not (0 <= hour_start <= hour_end <= 23):
        raise ValueError(
            f"Rango de horas inválido: hour_start={hour_start}, hour_end={hour_end}. "
            "Debe cumplir 0 <= hour_start <= hour_end <= 23."
        )

    local_start = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ_PUCUSANA)
    local_start += timedelta(hours=hour_start)

    local_end = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ_PUCUSANA)
    local_end += timedelta(hours=hour_end, minutes=59, seconds=59)

    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _temporal_offset_hours(
    t_utc: datetime, window_start_utc: datetime, window_end_utc: datetime
) -> float:
    """
    Desfase, en horas, respecto del borde MÁS CERCANO de la ventana.
    0.0 si el instante cae dentro de la ventana.
    """
    if window_start_utc <= t_utc <= window_end_utc:
        return 0.0
    if t_utc < window_start_utc:
        return (window_start_utc - t_utc).total_seconds() / 3600.0
    return (t_utc - window_end_utc).total_seconds() / 3600.0


def _empty_reading(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int,
    hour_end: int,
    window_start_utc: datetime | None,
    window_end_utc: datetime | None,
    n_native_times_in_window: int = 0,
) -> TemperatureReading:
    """
    Lectura SIN_DATOS: sin valores ni celda, pero con alcance y procedencia
    declarados igual que las demás. n_native_times_in_window se conserva
    cuando se conoce: permite distinguir "no había instantes nativos" de
    "los había pero ninguno tenía valor válido en una celda aceptable".
    """
    return TemperatureReading(
        lat=lat,
        lon=lon,
        date=target_date,
        hour_start_local=hour_start,
        hour_end_local=hour_end,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        samples=[],
        n_native_times_in_window=n_native_times_in_window,
        n_samples=0,
        n_missing_samples=n_native_times_in_window,
        coverage_fraction=0.0 if n_native_times_in_window > 0 else None,
        depth_m_requested=0.0,
        depth_m_actual=None,
        cell_lat=None,
        cell_lon=None,
        distance_km=None,
        dataset_id=DATASET_ID,
        variable=VARIABLE,
        data_scope=DATA_SCOPE,
        scope_warning=DATA_SCOPE_WARNING,
        status=TemperatureStatus.SIN_DATOS,
    )


def _cell_candidates(slab, lat: float, lon: float) -> list[tuple[float, float, float]]:
    """
    Todas las celdas (cell_lat, cell_lon) del recuadro con su distancia
    Haversine al punto solicitado, filtradas por MAX_VALID_CELL_DISTANCE_KM.
    No evalúa validez de valores aquí -- eso depende del/los timestamp(s).
    Devuelve [(distance_km, cell_lat, cell_lon), ...] ordenado por distancia.
    """
    out = []
    for lat_val in slab.latitude.values:
        for lon_val in slab.longitude.values:
            cell_lat, cell_lon = float(lat_val), float(lon_val)
            dist = _haversine_km(lat, lon, cell_lat, cell_lon)
            if dist <= MAX_VALID_CELL_DISTANCE_KM:
                out.append((dist, cell_lat, cell_lon))
    out.sort(key=lambda x: x[0])
    return out


def _value_at(slab, t_naive, cell_lat: float, cell_lon: float) -> float | None:
    """Valor nativo en un timestamp y celda concretos. None si es NaN."""
    v = float(slab.sel(time=t_naive, latitude=cell_lat, longitude=cell_lon).values)
    return None if v != v else v


def fetch_temperature_window(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> TemperatureReading:
    """
    Devuelve las muestras instantáneas de temperatura del nivel superficial
    disponible, para la ventana horaria LOCAL de Pucusana solicitada.

    Regla de selección espacial (una sola celda para toda la serie):
      1. Se evalúan las celdas usando los timestamps DENTRO de la ventana.
      2. Se elige una única celda: primero la que tenga MAYOR número de
         valores válidos dentro de la ventana; si hay empate, la de MENOR
         distancia Haversine.
      3. La celda debe estar dentro de MAX_VALID_CELL_DISTANCE_KM.
      4. Se devuelven solo las muestras válidas de ESA misma celda -- la
         serie nunca salta entre celdas.

    Fallback temporal (solo si no hay ningún valor válido en la ventana):
      5. Se consideran los timestamps nativos fuera de la ventana hasta
         MAX_TEMPORAL_OFFSET_HOURS, ordenados por MENOR desfase; ante
         desfase EXACTAMENTE igual se prefiere el instante ANTERIOR a la
         ventana (desempate determinista, no dependiente del orden en que
         Copernicus devuelva los tiempos). Se elige el primero que tenga
         una celda válida dentro del límite espacial (la más cercana, si
         hay varias). Devuelve UNA muestra.
      6. Si no hay combinación aceptable -> SIN_DATOS.
      7. Nunca se interpola ni se inventan valores.

    Lanza ValueError si hour_start/hour_end son inválidos (error de uso,
    no de datos -- no se debe silenciar como SIN_DATOS).
    """
    window_start_utc, window_end_utc = _local_window_to_utc(target_date, hour_start, hour_end)

    # La consulta se amplía SOLO lo necesario para tener candidatos de
    # fallback; la ventana original se conserva intacta para clasificar.
    query_start = window_start_utc - timedelta(hours=MAX_TEMPORAL_OFFSET_HOURS)
    query_end = window_end_utc + timedelta(hours=MAX_TEMPORAL_OFFSET_HOURS)

    n_in_window = 0
    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=lon - 0.05,
            maximum_longitude=lon + 0.05,
            minimum_latitude=lat - 0.05,
            maximum_latitude=lat + 0.05,
            maximum_depth=SURFACE_SEARCH_MAX_DEPTH_M,  # sin minimum_depth (evita WARNING)
            start_datetime=query_start,
            end_datetime=query_end,
            # sin coordinates_selection_method: no debe tocar la dimensión tiempo
        )

        if ds.time.size == 0 or ds.depth.size == 0:
            logger.warning(
                "Sin instantes o niveles devueltos para (%s, %s) %s [%s]",
                lat, lon, target_date, DATASET_ID,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, 0,
            )

        depth_actual = float(ds.depth.values.min())  # nivel más somero devuelto
        slab = ds[VARIABLE].sel(depth=depth_actual)  # dims: (time, latitude, longitude)

        # Clasificar timestamps: dentro de la ventana, o fuera con su desfase
        in_window: list[tuple[datetime, object]] = []
        out_window: list[tuple[float, int, datetime, object]] = []
        for t in slab.time.values:
            t_naive = pd.Timestamp(t).to_pydatetime()
            t_utc = t_naive.replace(tzinfo=timezone.utc)
            offset = _temporal_offset_hours(t_utc, window_start_utc, window_end_utc)
            if offset == 0.0:
                in_window.append((t_utc, t_naive))
            elif offset <= MAX_TEMPORAL_OFFSET_HOURS:
                # clave de desempate: 0 = anterior a la ventana (preferido),
                # 1 = posterior. Determinista, no depende del orden recibido.
                before_flag = 0 if t_utc < window_start_utc else 1
                out_window.append((offset, before_flag, t_utc, t_naive))

        n_in_window = len(in_window)

        candidates = _cell_candidates(slab, lat, lon)
        if not candidates:
            logger.warning(
                "Ninguna celda dentro de %.2f km para (%s, %s) %s",
                MAX_VALID_CELL_DISTANCE_KM, lat, lon, target_date,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, n_in_window,
            )

        # ---- Camino 1: muestras DENTRO de la ventana ----------------------
        if in_window:
            best = None  # ((-n_validos, distancia), cell_lat, cell_lon, dist, valores)
            for dist, cell_lat, cell_lon in candidates:
                valores = []
                for t_utc, t_naive in in_window:
                    v = _value_at(slab, t_naive, cell_lat, cell_lon)
                    if v is not None:
                        valores.append((t_utc, v))
                if not valores:
                    continue
                key = (-len(valores), dist)
                if best is None or key < best[0]:
                    best = (key, cell_lat, cell_lon, dist, valores)

            if best is not None:
                _, cell_lat, cell_lon, dist, valores = best
                samples = [
                    TemperatureSample(
                        time_utc=t_utc,
                        time_local=t_utc.astimezone(TZ_PUCUSANA),
                        value_celsius=v,
                        inside_requested_window=True,
                        temporal_offset_hours=0.0,
                    )
                    for t_utc, v in valores
                ]
                samples.sort(key=lambda s: s.time_utc)
                n_samples = len(samples)
                return TemperatureReading(
                    lat=lat,
                    lon=lon,
                    date=target_date,
                    hour_start_local=hour_start,
                    hour_end_local=hour_end,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                    samples=samples,
                    n_native_times_in_window=n_in_window,
                    n_samples=n_samples,
                    n_missing_samples=n_in_window - n_samples,
                    coverage_fraction=n_samples / n_in_window if n_in_window else None,
                    depth_m_requested=0.0,
                    depth_m_actual=depth_actual,
                    cell_lat=cell_lat,
                    cell_lon=cell_lon,
                    distance_km=dist,
                    dataset_id=DATASET_ID,
                    variable=VARIABLE,
                    data_scope=DATA_SCOPE,
                    scope_warning=DATA_SCOPE_WARNING,
                    status=TemperatureStatus.VALIDA_EN_VENTANA,
                )

        # ---- Camino 2: fallback temporal (una sola muestra) ---------------
        # Orden determinista: menor desfase; a igual desfase, el ANTERIOR a
        # la ventana; a igualdad total, el timestamp más temprano.
        out_window.sort(key=lambda x: (x[0], x[1], x[2]))
        for offset, _before_flag, t_utc, t_naive in out_window:
            for dist, cell_lat, cell_lon in candidates:  # ya ordenados por cercanía
                v = _value_at(slab, t_naive, cell_lat, cell_lon)
                if v is None:
                    continue
                sample = TemperatureSample(
                    time_utc=t_utc,
                    time_local=t_utc.astimezone(TZ_PUCUSANA),
                    value_celsius=v,
                    inside_requested_window=False,
                    temporal_offset_hours=offset,
                )
                return TemperatureReading(
                    lat=lat,
                    lon=lon,
                    date=target_date,
                    hour_start_local=hour_start,
                    hour_end_local=hour_end,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                    samples=[sample],
                    n_native_times_in_window=n_in_window,
                    n_samples=1,
                    # La muestra externa NO cubre ninguno de los instantes
                    # internos solicitados: si había timestamps nativos
                    # dentro de la ventana, todos quedaron sin cubrir.
                    n_missing_samples=n_in_window,
                    coverage_fraction=0.0 if n_in_window > 0 else None,
                    depth_m_requested=0.0,
                    depth_m_actual=depth_actual,
                    cell_lat=cell_lat,
                    cell_lon=cell_lon,
                    distance_km=dist,
                    dataset_id=DATASET_ID,
                    variable=VARIABLE,
                    data_scope=DATA_SCOPE,
                    scope_warning=DATA_SCOPE_WARNING,
                    status=TemperatureStatus.VALIDA_CERCANA_EN_TIEMPO,
                )

        # ---- Sin combinación aceptable ------------------------------------
        logger.warning(
            "Sin combinación temporal/espacial aceptable para (%s, %s) %s "
            "(instantes en ventana: %d, celdas candidatas: %d)",
            lat, lon, target_date, n_in_window, len(candidates),
        )
        return _empty_reading(
            lat, lon, target_date, hour_start, hour_end,
            window_start_utc, window_end_utc, n_in_window,
        )

    except Exception:
        # Fallo de datos/red o error de programación (no de uso -- ver
        # ValueError arriba). Se registra con traza para que NO quede
        # indistinguible de una ausencia legítima de datos; no se registran
        # credenciales ni información sensible. Nunca se devuelve un valor
        # por defecto disfrazado de lectura real.
        logger.exception(
            "Fallo al obtener temperatura para (%s, %s) %s [%s]",
            lat, lon, target_date, DATASET_ID,
        )
        return _empty_reading(
            lat, lon, target_date, hour_start, hour_end,
            window_start_utc, window_end_utc, n_in_window,
        )


def fetch_sst(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> TemperatureReading:
    """
    Atajo para temperatura superficial. Compatible con la llamada existente
    fetch_sst(lat, lon, target_date): por defecto cubre el día local
    completo (00:00-23:59:59), que en Pucusana reúne los cuatro instantes
    nativos (01:00, 07:00, 13:00 y 19:00 local).
    """
    return fetch_temperature_window(lat, lon, target_date, hour_start, hour_end)