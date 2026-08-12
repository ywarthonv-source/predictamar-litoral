"""
Ingesta de oleaje — PredictaMAR Litoral (Pucusana)

ALCANCE DE ESTA FUENTE (decidido ago 2026, tras diagnóstico en campo):
Esta fuente es OLEAJE REGIONAL DE REFERENCIA, no una medición puntual de
Pucusana. La grilla de CMEMS (~9km) no resuelve la costa: la celda válida
más cercana al punto solicitado puede estar a varios km mar adentro (en
las pruebas reales, ~5.7km). El oleaje cerca de la costa cambia por
asomeramiento, refracción y batimetría local -- puede ser mayor o menor
que lo que indica esta fuente. Por eso cada WaveReading lleva su propio
`data_scope` y `scope_warning`: la limitación viaja con el dato, no solo
en este docstring.

Pendiente: incorporar una fuente costera más fina u observación local para
la validación de seguridad exacta.

DISEÑO FAIL-SAFE OBLIGATORIO (bug crítico encontrado en Costero v1.2, ago 2026):
En Costero, cuando no había oleaje y cuando fallaba la descarga, ambos casos
producían la misma salida ("tranquilo") porque el kill-switch se quedaba en
False y se usaba un valor ficticio de 0.8m. Es un diseño fail-open: ante duda,
el sistema asumía la condición más favorable. Aquí se prohíbe ese patrón.

Estado de salida: SIEMPRE uno de estos tres, nunca un cuarto estado implícito:
  - "bajo_umbral_regional"  -> hubo dato regional válido, dentro de distancia
                                aceptable, y bajo el umbral
  - "sobre_umbral_regional" -> hubo dato regional válido, dentro de distancia
                                aceptable, y en o sobre el umbral
  - "sin_datos"             -> ninguna celda del recuadro tuvo dato válido
                                DENTRO de la distancia máxima aceptable

IMPORTANTE -- ESTO NO ES UNA AUTORIZACIÓN OPERATIVA:
BAJO_UMBRAL_REGIONAL (y por lo tanto kill_switch()=False) NO significa que
esté autorizado salir a faenar. Es una referencia regional bajo un umbral
todavía PROVISIONAL (WAVE_HEIGHT_THRESHOLD_M), no validado por la asesoría
oceanográfica del proyecto. Ver NOT_AN_AUTHORIZATION_NOTICE.

Selección espacial: entre las celdas del recuadro consultado, se descartan
las que no tengan dato válido (NaN) y, de las restantes, se elige la
geográficamente MÁS CERCANA al punto solicitado por distancia Haversine
real. Si esa celda más cercana está más lejos que MAX_VALID_CELL_DISTANCE_KM,
también se descarta -- no se amplía el recuadro de búsqueda, y no se acepta
una celda "más cercana disponible" si igual está demasiado lejos para servir
de referencia. Si no queda ninguna celda válida y dentro de distancia
aceptable, el resultado es SIN_DATOS.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

import copernicusmarine
import pandas as pd

DATASET_ID = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
VARIABLE = "VHM0"  # altura de ola significativa, espectro total (m)

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano

DATA_SCOPE = "oleaje_regional_referencia"

DATA_SCOPE_WARNING = (
    "Oleaje regional de referencia (grilla ~9km, celda válida más cercana "
    "dentro del recuadro consultado y dentro de la distancia máxima "
    "aceptable, sin ampliar el área de búsqueda). NO es medición exacta de "
    "Pucusana ni autorización de salida para pesca artesanal costera. "
    "Pendiente: fuente costera fina u observación local."
)

WAVE_HEIGHT_THRESHOLD_M = 1.5  # TODO: PROVISIONAL -- ajustar con criterio de la asesoría oceanográfica

# ---- LÍMITE DE DISTANCIA (añadido, revisión técnica ago 2026) ----------
# PROVISIONAL -- pendiente de validación oceanográfica. El recuadro
# consultado es ±0.05° (~5.5km por eje a esta latitud); la distancia
# máxima teórica centro-esquina dentro de ese recuadro es ~7.8km, así que
# cualquier límite >= 7.8km nunca filtraría nada. Se usa en su lugar la
# mitad de la diagonal de una celda de la grilla nativa (~9.2km de
# resolución) como criterio: una celda a más de esa distancia ya está más
# cerca de la SIGUIENTE celda que de la solicitada, y no debería tratarse
# como "la referencia" de este punto.
MAX_VALID_CELL_DISTANCE_KM = 6.5  # TODO: PROVISIONAL -- ajustar con criterio de la asesoría oceanográfica
# --------------------------------------------------------------------------

NOT_AN_AUTHORIZATION_NOTICE = (
    "BAJO_UMBRAL_REGIONAL y kill_switch()=False NO constituyen autorización "
    "operativa de salida a faenar. WAVE_HEIGHT_THRESHOLD_M y "
    "MAX_VALID_CELL_DISTANCE_KM son valores provisionales, todavía no "
    "validados por la asesoría oceanográfica del proyecto. Esta fuente es "
    "oleaje regional de referencia, no medición puntual costera (ver "
    "DATA_SCOPE_WARNING)."
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
    significant_wave_height_m: float | None  # MÁXIMO de la celda seleccionada, ventana del día
    max_time_utc: datetime | None
    max_time_local: datetime | None
    cell_lat: float | None  # coordenada real de la celda usada (None si se rechazó por distancia o SIN_DATOS)
    cell_lon: float | None
    distance_km: float | None  # distancia real de la celda ACEPTADA (dentro del límite)
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


def _select_nearest_valid_cell(
    da, lat: float, lon: float
) -> tuple[float, float, float] | None:
    """
    Entre todas las celdas (latitude, longitude) del recuadro ya consultado,
    descarta las que no tengan ningún valor válido en toda la ventana
    temporal, y de las restantes elige la geográficamente MÁS CERCANA al
    punto solicitado.

    NO amplía el recuadro. Si la celda válida más cercana está más lejos
    que MAX_VALID_CELL_DISTANCE_KM, TAMBIÉN se descarta -- ver bloque
    "LÍMITE DE DISTANCIA" más abajo.

    Devuelve None si no queda ninguna celda válida y dentro del límite.
    """
    cell_max = da.max(dim="time", skipna=True)  # dims: (latitude, longitude)

    best = None  # (distance_km, cell_lat, cell_lon)
    for lat_val in cell_max.latitude.values:
        for lon_val in cell_max.longitude.values:
            val = float(cell_max.sel(latitude=lat_val, longitude=lon_val).values)
            if val != val:  # NaN -> celda sin dato válido, se descarta
                continue
            dist = _haversine_km(lat, lon, float(lat_val), float(lon_val))
            if best is None or dist < best[0]:
                best = (dist, float(lat_val), float(lon_val))

    if best is None:
        return None

    dist, cell_lat, cell_lon = best

    # ---- LÍMITE DE DISTANCIA (añadido, revisión técnica ago 2026) -------
    # Aunque sea la celda válida MÁS CERCANA disponible, si sigue estando
    # más lejos que MAX_VALID_CELL_DISTANCE_KM se rechaza igual -- "más
    # cercana disponible" no es lo mismo que "suficientemente cercana".
    if dist > MAX_VALID_CELL_DISTANCE_KM:
        return None
    # -----------------------------------------------------------------------

    return cell_lat, cell_lon, dist


def fetch_wave_height(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> WaveMeasurement:
    """
    Obtiene el MÁXIMO de VHM0, dentro de la ventana horaria LOCAL dada, de
    la celda válida geográficamente más cercana al punto solicitado dentro
    del recuadro consultado y dentro de MAX_VALID_CELL_DISTANCE_KM (sin
    ampliar el recuadro).

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
            # el tiempo se queda "inside" (comportamiento por defecto);
            # la selección espacial la hace _select_nearest_valid_cell,
            # que excluye celdas NaN Y celdas fuera del límite de
            # distancia antes de aceptar una.
        )
        da = ds[VARIABLE]

        if da.sizes.get("time", 0) == 0:
            return WaveMeasurement(None, None, None, None, None)

        selection = _select_nearest_valid_cell(da, lat, lon)
        if selection is None:
            return WaveMeasurement(None, None, None, None, None)
        cell_lat, cell_lon, distance_km = selection

        series = da.sel(latitude=cell_lat, longitude=cell_lon, method="nearest")
        value = float(series.max(dim="time", skipna=True).values)
        if value != value:  # no debería pasar, ya se filtró arriba, pero por seguridad
            return WaveMeasurement(None, None, None, None, None)

        max_time_raw = series.idxmax(dim="time", skipna=True).values
        max_time_utc = pd.Timestamp(max_time_raw).to_pydatetime().replace(tzinfo=timezone.utc)

        return WaveMeasurement(value, max_time_utc, cell_lat, cell_lon, distance_km)
    except Exception:
        # Cualquier fallo de datos/red (no de uso -- ver ValueError arriba)
        # se trata igual: sin dato. La decisión de qué hacer con eso vive
        # en get_wave_status / kill_switch, no aquí.
        return WaveMeasurement(None, None, None, None, None)


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
            lat, lon, target_date,
            None, None, None,
            None, None, None,
            DATA_SCOPE, DATA_SCOPE_WARNING,
            WaveStatus.SIN_DATOS,
        )

    max_time_local = m.time_utc.astimezone(TZ_PUCUSANA)

    status = (
        WaveStatus.SOBRE_UMBRAL_REGIONAL
        if m.value_m >= WAVE_HEIGHT_THRESHOLD_M
        else WaveStatus.BAJO_UMBRAL_REGIONAL
    )
    return WaveReading(
        lat, lon, target_date,
        m.value_m, m.time_utc, max_time_local,
        m.cell_lat, m.cell_lon, m.distance_km,
        DATA_SCOPE, DATA_SCOPE_WARNING,
        status,
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