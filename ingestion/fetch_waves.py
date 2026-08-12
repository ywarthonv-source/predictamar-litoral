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
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

import copernicusmarine

DATASET_ID = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
VARIABLE = "VHM0"  # altura de ola significativa, espectro total (m)


class WaveStatus(str, Enum):
    CALMA_CONFIRMADA = "calma_confirmada"
    RIESGO_CONFIRMADO = "riesgo_confirmado"
    SIN_DATOS = "sin_datos"


WAVE_HEIGHT_THRESHOLD_M = 1.5  # TODO: ajustar con criterio de la asesoría oceanográfica


@dataclass
class WaveReading:
    lat: float
    lon: float
    date: date
    significant_wave_height_m: float | None
    status: WaveStatus


def fetch_wave_height(lat: float, lon: float, target_date: date) -> float | None:
    """
    Obtiene la altura de ola significativa (VHM0) desde Copernicus Marine
    (GLOBAL_ANALYSISFORECAST_WAV_001_027, resolución 0.083° / ~9km).

    Requiere credenciales configuradas vía `copernicusmarine login` (local)
    o las variables de entorno COPERNICUSMARINE_SERVICE_USERNAME /
    _PASSWORD (para GitHub Actions más adelante).

    Devuelve None explícitamente si algo falla — NUNCA un valor por defecto
    disfrazado de lectura real (ver docstring del módulo).
    """
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)

    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=lon - 0.05,
            maximum_longitude=lon + 0.05,
            minimum_latitude=lat - 0.05,
            maximum_latitude=lat + 0.05,
            start_datetime=start,
            end_datetime=end,
        )
        # Punto más cercano dentro de la pequeña ventana, promedio del día
        point = ds[VARIABLE].sel(latitude=lat, longitude=lon, method="nearest")
        value = float(point.mean(dim="time", skipna=True).values)
        if value != value:  # NaN check sin depender de numpy aquí
            return None
        return value
    except Exception:
        # Cualquier fallo (red, credenciales, dataset caído, punto sin dato)
        # se trata igual: None. La decisión de qué hacer con eso vive en
        # get_wave_status / kill_switch, no aquí.
        return None


def get_wave_status(lat: float, lon: float, target_date: date) -> WaveReading:
    try:
        height = fetch_wave_height(lat, lon, target_date)
    except Exception:
        height = None

    if height is None:
        return WaveReading(lat, lon, target_date, None, WaveStatus.SIN_DATOS)

    status = (
        WaveStatus.RIESGO_CONFIRMADO
        if height >= WAVE_HEIGHT_THRESHOLD_M
        else WaveStatus.CALMA_CONFIRMADA
    )
    return WaveReading(lat, lon, target_date, height, status)


def kill_switch(reading: WaveReading) -> bool:
    """
    True = bloquear/advertir. SIN_DATOS bloquea igual que RIESGO_CONFIRMADO.
    Esta es la corrección directa al bug de Costero: ante duda, no se asume
    la condición favorable.
    """
    return reading.status in (WaveStatus.RIESGO_CONFIRMADO, WaveStatus.SIN_DATOS)
