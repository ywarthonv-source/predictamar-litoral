"""
Ingesta de temperatura superficial (SST) — PredictaMAR Litoral (Pucusana)

Fuente: CMEMS GLOBAL_ANALYSISFORECAST_PHY_001_024, dataset
cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m, variable thetao
(temperatura potencial del mar).

Es un producto de modelo/reanálisis: no depende de nubosidad, ~100%
disponible (a diferencia de un sensor óptico puro). Ver
config/variables_spec.yaml — rol A, resolución ~8.9 km.

Mismo patrón fail-safe que fetch_waves.py: nunca se inventa un valor por
defecto. Si falla la descarga o el punto no tiene dato, se declara
explícitamente "sin_dato".

Nota para el gradiente vertical (variable futura): este mismo dataset
(thetao) permite pedir profundidad, así que la temperatura a ~10 m debe
salir de AQUÍ, con la MISMA target_date que la superficial — el bug
encontrado en Costero fue justo mezclar fechas distintas entre SST y T10.

Correcciones aplicadas (revisión técnica, ago 2026):
1. El nivel vertical exacto solicitado (p.ej. 0 m) puede no existir como
   nivel nativo del modelo -> se usa coordinates_selection_method="nearest"
   en la apertura del dataset, para que lat/lon/profundidad/tiempo se
   resuelvan por vecino más cercano, no por inclusión estricta.
2. Además, tras seleccionar lat/lon, se hace un .sel(depth=..., method=
   "nearest") explícito sobre el resultado, antes de convertir a float.
3. end_datetime ya NO se extiende a las 00:00 del día siguiente (eso podía
   traer también el primer valor del día siguiente); se acota al final del
   mismo target_date.
4. Se registra la profundidad REAL devuelta por CMEMS (depth_m_actual),
   no solo la solicitada (depth_m_requested) — pueden no coincidir.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import copernicusmarine

DATASET_ID = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"
VARIABLE = "thetao"


@dataclass
class TemperatureReading:
    lat: float
    lon: float
    date: date
    depth_m_requested: float
    depth_m_actual: float | None
    value_celsius: float | None
    source: str  # "cmems_thetao_8km" | "sin_dato"


def fetch_temperature(
    lat: float,
    lon: float,
    target_date: date,
    depth_m: float = 0.0,
) -> TemperatureReading:
    """
    Obtiene thetao en un punto, fecha y profundidad dados.

    depth_m=0.0 -> SST (superficie)
    depth_m=10.0 -> T10, para el cálculo futuro del gradiente vertical
    (usar SIEMPRE la misma target_date para ambas llamadas, para no
    repetir el bug de fechas desalineadas de Costero).
    """
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(hours=23, minutes=59, seconds=59)

    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=lon - 0.05,
            maximum_longitude=lon + 0.05,
            minimum_latitude=lat - 0.05,
            maximum_latitude=lat + 0.05,
            minimum_depth=depth_m,
            maximum_depth=depth_m,
            start_datetime=start,
            end_datetime=end,
            coordinates_selection_method="nearest",
        )
        point = ds[VARIABLE].sel(latitude=lat, longitude=lon, method="nearest")
        point = point.sel(depth=depth_m, method="nearest")

        depth_actual = float(point.depth.values)
        value = float(point.mean(dim="time", skipna=True).values)

        if value != value:  # NaN
            return TemperatureReading(
                lat, lon, target_date, depth_m, depth_actual, None, "sin_dato"
            )
        return TemperatureReading(
            lat, lon, target_date, depth_m, depth_actual, value, "cmems_thetao_8km"
        )
    except Exception:
        return TemperatureReading(lat, lon, target_date, depth_m, None, None, "sin_dato")


def fetch_sst(lat: float, lon: float, target_date: date) -> TemperatureReading:
    """Atajo explícito para SST (profundidad solicitada 0m) — usado por el scoring de superficie."""
    return fetch_temperature(lat, lon, target_date, depth_m=0.0)
