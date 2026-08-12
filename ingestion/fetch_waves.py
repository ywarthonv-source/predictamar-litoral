"""
Ingesta de oleaje — PredictaMAR Litoral (Pucusana)

DISEÑO FAIL-SAFE OBLIGATORIO (bug crítico encontrado en Costero v1.2, ago 2026):
En Costero, cuando no había oleaje y cuando fallaba la descarga, ambos casos
producían la misma salida ("tranquilo") porque el kill-switch se quedaba en
False y se usaba un valor ficticio de 0.8m. Es un diseño fail-open: ante duda,
el sistema asumía la condición más favorable. Aquí se prohíbe ese patrón.

Estado de salida: SIEMPRE uno de estos tres, nunca un cuarto estado implícito:
  - "calma_confirmada"   -> hubo dato real y el oleaje está por debajo del umbral
  - "riesgo_confirmado"  -> hubo dato real y el oleaje está sobre el umbral
  - "sin_datos"          -> la descarga falló o no hay dato disponible

"sin_datos" DEBE bloquear la recomendación de salida a faenar (o marcarla con
advertencia explícita), nunca tratarse como equivalente a "calma_confirmada".

Correcciones aplicadas (revisión técnica, ago 2026):
1. MÁXIMO en vez de promedio dentro de la ventana -- variable de seguridad,
   importa el peor momento posible, no el típico.
2. Manejo correcto de zona horaria: target_date es la fecha LOCAL de
   Pucusana (America/Lima, UTC-5, sin horario de verano). CMEMS trabaja en
   UTC. La ventana horaria local (hour_start-hour_end) se construye en hora
   local y se convierte a UTC antes de consultar -- para el día completo
   local esto es 05:00 UTC del target_date hasta antes de las 05:00 UTC del
   día siguiente. Cruzar de fecha UTC es correcto y esperado; lo que nunca
   debe cruzarse es la fecha LOCAL solicitada.
3. coordinates_selection_method="nearest" NO se aplica globalmente al abrir
   el dataset, porque también afectaría la dimensión de tiempo y podría
   traer un timestamp fuera de la ventana solicitada. El tiempo se
   mantiene "inside" (comportamiento por defecto de la librería); solo
   latitud/longitud se resuelven por vecino más cercano, después de abrir
   el dataset.
4. Se valida 0 <= hour_start <= hour_end <= 23 (error de programación, no
   de datos -- se deja propagar como ValueError, no se convierte en
   "sin_datos"). Se registra la hora UTC y local exacta en la que ocurrió
   el máximo, para que el valor de seguridad sea trazable y auditable.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

import copernicusmarine
import pandas as pd

DATASET_ID = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
VARIABLE = "VHM0"  # altura de ola significativa, espectro total (m)

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano


class WaveStatus(str, Enum):
    CALMA_CONFIRMADA = "calma_confirmada"
    RIESGO_CONFIRMADO = "riesgo_confirmado"
    SIN_DATOS = "sin_datos"


WAVE_HEIGHT_THRESHOLD_M = 1.5  # TODO: ajustar con criterio de la asesoría oceanográfica


@dataclass
class WaveMeasurement:
    value_m: float | None
    time_utc: datetime | None


@dataclass
class WaveReading:
    lat: float
    lon: float
    date: date
    significant_wave_height_m: float | None  # MÁXIMO de la ventana, no promedio
    max_time_utc: datetime | None
    max_time_local: datetime | None  # hora local Pucusana en que ocurrió el máximo
    status: WaveStatus


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


def fetch_wave_height(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> WaveMeasurement:
    """
    Obtiene el MÁXIMO de VHM0 dentro de la ventana horaria LOCAL dada
    (hour_start-hour_end, hora de Pucusana), para el mismo target_date local.

    Ventana por defecto: día local completo (0-23), porque la ventana real
    de faena del gremio de Pucusana todavía no está confirmada -- acotar
    aquí en cuanto se tenga ese dato.

    Devuelve WaveMeasurement(None, None) explícitamente si algo falla —
    NUNCA un valor por defecto disfrazado de lectura real.

    Lanza ValueError si hour_start/hour_end son inválidos (error de uso,
    no de datos -- no se debe silenciar como "sin_datos").
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
            # el tiempo se queda "inside" (comportamiento por defecto),
            # solo lat/lon se resuelven por vecino más cercano, abajo.
        )
        point = ds[VARIABLE].sel(latitude=lat, longitude=lon, method="nearest")

        if point.sizes.get("time", 0) == 0:
            return WaveMeasurement(None, None)

        value = float(point.max(dim="time", skipna=True).values)
        if value != value:  # NaN
            return WaveMeasurement(None, None)

        max_time_raw = point.idxmax(dim="time", skipna=True).values
        max_time_utc = pd.Timestamp(max_time_raw).to_pydatetime().replace(tzinfo=timezone.utc)

        return WaveMeasurement(value, max_time_utc)
    except Exception:
        # Cualquier fallo de datos/red (no de uso -- ver ValueError arriba)
        # se trata igual: sin dato. La decisión de qué hacer con eso vive
        # en get_wave_status / kill_switch, no aquí.
        return WaveMeasurement(None, None)


def get_wave_status(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> WaveReading:
    measurement = fetch_wave_height(lat, lon, target_date, hour_start, hour_end)

    if measurement.value_m is None or measurement.time_utc is None:
        return WaveReading(lat, lon, target_date, None, None, None, WaveStatus.SIN_DATOS)

    max_time_local = measurement.time_utc.astimezone(TZ_PUCUSANA)

    status = (
        WaveStatus.RIESGO_CONFIRMADO
        if measurement.value_m >= WAVE_HEIGHT_THRESHOLD_M
        else WaveStatus.CALMA_CONFIRMADA
    )
    return WaveReading(
        lat, lon, target_date, measurement.value_m, measurement.time_utc, max_time_local, status
    )


def kill_switch(reading: WaveReading) -> bool:
    """
    True = bloquear/advertir. SIN_DATOS bloquea igual que RIESGO_CONFIRMADO.
    Esta es la corrección directa al bug de Costero: ante duda, no se asume
    la condición favorable.
    """
    return reading.status in (WaveStatus.RIESGO_CONFIRMADO, WaveStatus.SIN_DATOS)
