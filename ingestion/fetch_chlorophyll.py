"""
Ingesta de clorofila — PredictaMAR Litoral (Pucusana)

REGLA HÍBRIDA (decidida ago 2026, ver config/variables_spec.yaml):
  1. Intentar primero el producto de 300m (OLCI / Sentinel-3).
  2. Si el pixel en un punto viene enmascarado por nubes, caer a 4km gap-free
     PARA ESE PUNTO ESPECÍFICO (no para todo el área).
  3. Declarar explícitamente qué fuente se usó por punto — nunca fallback silencioso.
  4. Si >80% de los puntos del día caen a 4km, emitir alerta de cobertura del día.

Esto NO está resuelto todavía a nivel de implementación real de descarga (falta
conectar con la API de Copernicus Marine / Earth Engine); esto es el ESQUELETO
que fija el contrato de datos y el comportamiento esperado, para que puedas
completarlo con las llamadas reales cuando tengas las credenciales configuradas.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class ChlorophyllReading:
    lat: float
    lon: float
    date: date
    value_mg_m3: float | None
    source: str          # "300m" | "4km_gapfree" | "sin_dato"
    source_age_days: int  # antigüedad real del dato usado, no siempre 0


def fetch_chlorophyll_300m(lat: float, lon: float, target_date: date) -> ChlorophyllReading | None:
    """
    Intenta obtener el valor OLCI 300m para un punto y fecha.
    Devuelve None si el pixel está enmascarado por nubes o no hay dato.

    TODO: reemplazar por la llamada real al catálogo de Copernicus Marine
    (producto OCEANCOLOUR ..._300m) o Google Earth Engine (Sentinel-3 OLCI).
    """
    raise NotImplementedError("Conectar con la fuente real de datos (Copernicus Marine / GEE)")


def fetch_chlorophyll_4km(lat: float, lon: float, target_date: date) -> ChlorophyllReading:
    """
    Obtiene el valor del producto multi-sensor 4km gap-free.
    Este producto está diseñado para no tener huecos, así que se asume que
    SIEMPRE devuelve un valor (si la fuente cae, eso sí debe tratarse como
    error real, no como comportamiento esperado).

    TODO: reemplazar por la llamada real al catálogo de Copernicus Marine.
    """
    raise NotImplementedError("Conectar con la fuente real de datos (Copernicus Marine)")


def get_chlorophyll(lat: float, lon: float, target_date: date) -> ChlorophyllReading:
    """
    Punto de entrada único para el motor de puntaje. Aplica la regla híbrida
    y SIEMPRE devuelve la fuente real usada — el motor de puntaje debe poder
    leer `.source` y decidir si confía menos en un punto que cayó a 4km.
    """
    reading_300m = fetch_chlorophyll_300m(lat, lon, target_date)
    if reading_300m is not None and reading_300m.value_mg_m3 is not None:
        return reading_300m

    # Fallback explícito, no silencioso
    fallback = fetch_chlorophyll_4km(lat, lon, target_date)
    return fallback


def get_chlorophyll_area(points: list[tuple[float, float]], target_date: date) -> dict:
    """
    Ejecuta get_chlorophyll para todos los puntos del día y calcula la métrica
    de cobertura, para poder emitir la alerta si >80% cayó a 4km.
    """
    readings = [get_chlorophyll(lat, lon, target_date) for lat, lon in points]
    n_total = len(readings)
    n_fallback = sum(1 for r in readings if r.source == "4km_gapfree")
    coverage_ratio_300m = 1 - (n_fallback / n_total) if n_total else 0.0

    result = {
        "date": target_date,
        "readings": readings,
        "coverage_ratio_300m": coverage_ratio_300m,
        "low_coverage_alert": coverage_ratio_300m < 0.20,  # >80% cayó a 4km
    }
    return result
