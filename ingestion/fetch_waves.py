"""
Ingesta de oleaje — PredictaMAR Litoral (Pucusana)

ALCANCE DE ESTA FUENTE:
Es OLEAJE REGIONAL DE REFERENCIA, no una medición puntual de Pucusana. La
grilla de CMEMS (~9 km) no resuelve la costa: la celda utilizada puede estar
a varios km del punto solicitado, y la máscara de tierra deja sin dato a
celdas geométricamente más cercanas. El oleaje junto a la costa cambia por
asomeramiento, refracción y batimetría local -- puede ser mayor o menor que
lo que indica esta fuente. Por eso cada WaveReading lleva su propio
`data_scope` y `scope_warning`: la limitación viaja con el dato.

Pendiente: incorporar una fuente costera más fina u observación local para
la validación de seguridad exacta.

DISEÑO FAIL-SAFE OBLIGATORIO (bug crítico encontrado en Costero v1.2, ago 2026):
En Costero, cuando no había oleaje y cuando fallaba la descarga, ambos casos
producían la misma salida ("tranquilo") porque el kill-switch se quedaba en
False y se usaba un valor ficticio de 0.8m. Es un diseño fail-open: ante duda,
el sistema asumía la condición más favorable. Aquí se prohíbe ese patrón.

Estado de salida: SIEMPRE uno de estos tres, nunca un cuarto estado implícito:
  - "bajo_umbral_regional"  -> hubo dato regional válido, bajo el umbral
  - "sobre_umbral_regional" -> hubo dato regional válido, en o sobre el umbral
  - "sin_datos"             -> ninguna celda aceptable tuvo dato válido

IMPORTANTE -- ESTO NO ES UNA AUTORIZACIÓN OPERATIVA:
BAJO_UMBRAL_REGIONAL (y por lo tanto kill_switch()=False) NO significa que
esté autorizado salir a faenar. Ver NOT_AN_AUTHORIZATION_NOTICE.

CRITERIO ESPACIAL CONSERVADOR (decidido ago 2026, PROVISIONAL):
Dentro del recuadro consultado (±0.05°), se consideran únicamente las celdas
que tengan algún valor válido de VHM0 en la ventana Y cuyo centro esté a
<= MAX_VALID_CELL_DISTANCE_KM del punto solicitado. De cada una se toma su
MÁXIMO TEMPORAL nativo, y se selecciona la celda con el MAYOR de esos
máximos -- no la más cercana. El desempate es determinista: a igual máximo,
menor distancia; si persiste, menor latitud y luego menor longitud.

Por qué el máximo y no la cercanía: esta es una compuerta de SEGURIDAD. Ante
dos celdas ambas admisibles, quedarse con la que reporta menos oleaje sería
elegir la lectura más favorable, que es precisamente el patrón fail-open que
este módulo existe para evitar. La cercanía sigue acotada por el límite de
distancia; dentro de ese límite manda la condición más adversa.

NO se amplía el recuadro, NO se interpola, NO se promedia y NO se fabrican
valores. Si no hay ninguna celda válida dentro del límite, el resultado es
SIN_DATOS.

CARÁCTER PROVISIONAL: el criterio espacial anterior, el límite
MAX_VALID_CELL_DISTANCE_KM = 6.5 km y el umbral WAVE_HEIGHT_THRESHOLD_M =
1.5 m son PROVISIONALES. Ninguno ha sido validado por la asesoría
oceanográfica del proyecto y ninguno constituye autorización operativa.
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

DATASET_ID = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
VARIABLE = "VHM0"  # altura de ola significativa, espectro total (m)

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano

DATA_SCOPE = "oleaje_regional_referencia"

DATA_SCOPE_WARNING = (
    "Oleaje regional de referencia (grilla ~9km). Cuando existe una lectura "
    "válida, procede del máximo temporal nativo de UNA celda del recuadro "
    "consultado, elegida con criterio conservador: entre las celdas con dato "
    "válido y dentro de la distancia máxima aceptable, se toma la de MAYOR "
    "máximo de oleaje, no la más cercana; a igual máximo se prefiere la más "
    "cercana y, si persiste el empate, el orden determinista por latitud y "
    "longitud. No se amplía el área de búsqueda, no se interpola y no se "
    "promedia. NO es medición exacta de Pucusana ni autorización de salida "
    "para pesca artesanal costera. Si el estado es SIN_DATOS no se tomó "
    "ningún valor ni celda. Pendiente: fuente costera fina u observación "
    "local."
)

WAVE_HEIGHT_THRESHOLD_M = 1.5  # TODO: PROVISIONAL -- pendiente de validación oceanográfica

# ---- LÍMITE DE DISTANCIA (PROVISIONAL) -------------------------------
# El recuadro consultado es ±0.05° (~5.5km por eje a esta latitud); la
# distancia máxima teórica centro-esquina dentro de ese recuadro es ~7.8km,
# así que cualquier límite >= 7.8km nunca filtraría nada. Se usa en su lugar
# la mitad de la diagonal de una celda de la grilla nativa (~9.2km): una
# celda a más de esa distancia ya está más cerca de la SIGUIENTE celda que
# del punto solicitado.
MAX_VALID_CELL_DISTANCE_KM = 6.5  # TODO: PROVISIONAL -- pendiente de validación oceanográfica
# ----------------------------------------------------------------------

NOT_AN_AUTHORIZATION_NOTICE = (
    "BAJO_UMBRAL_REGIONAL y kill_switch()=False NO constituyen autorización "
    "operativa de salida a faenar. El criterio espacial conservador, "
    "WAVE_HEIGHT_THRESHOLD_M y MAX_VALID_CELL_DISTANCE_KM son valores y "
    "reglas provisionales, todavía no validados por la asesoría "
    "oceanográfica del proyecto. Esta fuente es oleaje regional de "
    "referencia, no medición puntual costera (ver DATA_SCOPE_WARNING)."
)


class WaveStatus(str, Enum):
    BAJO_UMBRAL_REGIONAL = "bajo_umbral_regional"
    SOBRE_UMBRAL_REGIONAL = "sobre_umbral_regional"
    SIN_DATOS = "sin_datos"


@dataclass
class WaveMeasurement:
    value_m: float | None
    time_utc: datetime | None
    cell_lat: float | None
    cell_lon: float | None
    distance_km: float | None


@dataclass
class WaveReading:
    lat: float  # solicitada
    lon: float  # solicitada
    date: date
    significant_wave_height_m: float | None  # MÁXIMO de la celda seleccionada
    max_time_utc: datetime | None
    max_time_local: datetime | None
    cell_lat: float | None  # coordenada real de la celda usada
    cell_lon: float | None
    distance_km: float | None
    dataset_id: str
    variable: str
    data_scope: str
    scope_warning: str
    status: WaveStatus


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
    UTC. Nunca cruza la fecha local solicitada, aunque en UTC sí cruce de
    fecha (eso es correcto: UTC-5 significa que el día local empieza a las
    05:00 UTC y termina justo antes de las 05:00 UTC del día siguiente).
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


def _select_conservative_valid_cell(
    da, lat: float, lon: float
) -> tuple[float, float, float] | None:
    """
    Selección espacial CONSERVADORA para la compuerta de seguridad.

    De todas las celdas del recuadro ya consultado:
      1. Se descartan las que no tengan ningún valor válido en la ventana
         (su máximo temporal es NaN).
      2. Se descartan las que estén a más de MAX_VALID_CELL_DISTANCE_KM del
         punto solicitado.
      3. De las restantes se elige la de MAYOR máximo temporal de VHM0.
      4. Desempate determinista: a igual máximo, menor distancia; si persiste,
         menor latitud y luego menor longitud.

    NO amplía el recuadro. Devuelve (cell_lat, cell_lon, distance_km), o None
    si no queda ninguna celda válida y dentro del límite.
    """
    cell_max = da.max(dim="time", skipna=True)  # dims: (latitude, longitude)

    candidatos = []  # (-max, distancia, cell_lat, cell_lon)
    for lat_val in cell_max.latitude.values:
        for lon_val in cell_max.longitude.values:
            v = float(cell_max.sel(latitude=lat_val, longitude=lon_val).values)
            if v != v:  # NaN -> celda sin ningún dato válido en la ventana
                continue
            cell_lat, cell_lon = float(lat_val), float(lon_val)
            dist = _haversine_km(lat, lon, cell_lat, cell_lon)
            if dist > MAX_VALID_CELL_DISTANCE_KM:
                continue
            candidatos.append((-v, dist, cell_lat, cell_lon))

    if not candidatos:
        return None

    # Orden: -max ascendente (= max descendente), luego distancia, lat, lon.
    candidatos.sort()
    _, dist, cell_lat, cell_lon = candidatos[0]
    return cell_lat, cell_lon, dist


def fetch_wave_height(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> WaveMeasurement:
    """
    Obtiene el MÁXIMO de VHM0 dentro de la ventana horaria LOCAL dada, de la
    celda seleccionada con el criterio conservador descrito en
    _select_conservative_valid_cell (sin ampliar el recuadro).

    Devuelve WaveMeasurement con todos los campos en None si no hay ninguna
    celda válida y dentro de distancia aceptable, o si falla la descarga --
    NUNCA un valor por defecto disfrazado de lectura real.

    Lanza ValueError si hour_start/hour_end son inválidos (error de uso,
    no de datos -- no se debe silenciar).
    """
    start_utc, end_utc = _local_window_to_utc(target_date, hour_start, hour_end)

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
            # coordinates_selection_method NO se fija a "nearest" aquí:
            # afectaría también a la dimensión tiempo y podría traer
            # timestamps fuera de la ventana solicitada.
        )
        da = ds[VARIABLE]

        if da.sizes.get("time", 0) == 0:
            logger.warning(
                "Sin instantes devueltos para (%s, %s) %s [%s]",
                lat, lon, target_date, DATASET_ID,
            )
            return WaveMeasurement(
                value_m=None, time_utc=None, cell_lat=None, cell_lon=None, distance_km=None
            )

        seleccion = _select_conservative_valid_cell(da, lat, lon)
        if seleccion is None:
            logger.warning(
                "Ninguna celda válida dentro de %.2f km para (%s, %s) %s",
                MAX_VALID_CELL_DISTANCE_KM, lat, lon, target_date,
            )
            return WaveMeasurement(
                value_m=None, time_utc=None, cell_lat=None, cell_lon=None, distance_km=None
            )
        cell_lat, cell_lon, distance_km = seleccion

        series = da.sel(latitude=cell_lat, longitude=cell_lon, method="nearest")
        value = float(series.max(dim="time", skipna=True).values)
        if value != value:  # defensivo: ya se filtró arriba, pero por seguridad
            return WaveMeasurement(
                value_m=None, time_utc=None, cell_lat=None, cell_lon=None, distance_km=None
            )

        max_time_raw = series.idxmax(dim="time", skipna=True).values
        max_time_utc = pd.Timestamp(max_time_raw).to_pydatetime().replace(tzinfo=timezone.utc)

        return WaveMeasurement(
            value_m=value,
            time_utc=max_time_utc,
            cell_lat=cell_lat,
            cell_lon=cell_lon,
            distance_km=distance_km,
        )
    except Exception:
        # Fallo de datos/red o error de programación (no de uso -- ver
        # ValueError arriba). Se registra con traza para que NO quede
        # indistinguible de una ausencia legítima de datos; no se registran
        # credenciales ni información sensible.
        logger.exception(
            "Fallo al obtener oleaje para (%s, %s) %s [%s]",
            lat, lon, target_date, DATASET_ID,
        )
        return WaveMeasurement(
            value_m=None, time_utc=None, cell_lat=None, cell_lon=None, distance_km=None
        )


def get_wave_status(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> WaveReading:
    m = fetch_wave_height(lat, lon, target_date, hour_start, hour_end)

    if m.value_m is None or m.time_utc is None:
        return WaveReading(
            lat=lat,
            lon=lon,
            date=target_date,
            significant_wave_height_m=None,
            max_time_utc=None,
            max_time_local=None,
            cell_lat=None,
            cell_lon=None,
            distance_km=None,
            dataset_id=DATASET_ID,
            variable=VARIABLE,
            data_scope=DATA_SCOPE,
            scope_warning=DATA_SCOPE_WARNING,
            status=WaveStatus.SIN_DATOS,
        )

    max_time_local = m.time_utc.astimezone(TZ_PUCUSANA)

    status = (
        WaveStatus.SOBRE_UMBRAL_REGIONAL
        if m.value_m >= WAVE_HEIGHT_THRESHOLD_M
        else WaveStatus.BAJO_UMBRAL_REGIONAL
    )
    return WaveReading(
        lat=lat,
        lon=lon,
        date=target_date,
        significant_wave_height_m=m.value_m,
        max_time_utc=m.time_utc,
        max_time_local=max_time_local,
        cell_lat=m.cell_lat,
        cell_lon=m.cell_lon,
        distance_km=m.distance_km,
        dataset_id=DATASET_ID,
        variable=VARIABLE,
        data_scope=DATA_SCOPE,
        scope_warning=DATA_SCOPE_WARNING,
        status=status,
    )


def kill_switch(reading: WaveReading) -> bool:
    """
    True = bloquear/advertir. SIN_DATOS bloquea igual que SOBRE_UMBRAL_REGIONAL.
    Esta es la corrección directa al bug de Costero: ante duda, no se asume
    la condición favorable.

    RECORDATORIO: kill_switch()=False NO es una autorización operativa.
    Ver NOT_AN_AUTHORIZATION_NOTICE.
    """
    return reading.status in (WaveStatus.SOBRE_UMBRAL_REGIONAL, WaveStatus.SIN_DATOS)