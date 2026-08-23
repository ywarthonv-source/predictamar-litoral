"""
Ingesta de corrientes superficiales — PredictaMAR Litoral (Pucusana)

FUENTE: cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i
(producto GLOBAL_ANALYSISFORECAST_PHY_001_024, versión 202406, parte default),
componentes horizontales uo (este) y vo (norte), unidades nativas 'm s-1',
campos 3D instantáneos cada 6 horas.

Verificación oficial del producto (ago 2026): dataset activo (retired=None),
paso de 0.083333° en latitud y longitud (~9.06 km zonales en Pucusana),
cadencia de 6 h, y cobertura de Pucusana confirmada. La versión y la parte
se solicitan EXPLÍCITAMENTE a open_dataset, de modo que lo documentado y lo
abierto no puedan divergir.

QUÉ APORTA Y QUÉ NO:
SST y salinidad describen propiedades de la masa de agua y la clorofila
describe productividad; ninguna describe TRANSPORTE. Esta variable aporta
ese eje. Ahora bien, el valor ecológico esperado está en los features
DERIVADOS (convergencia, persistencia, relación con la costa), no en la
velocidad cruda: este módulo es el sustrato necesario para calcularlos, no
el resultado ecológico. No implementa umbrales pesqueros, ni clases de
aptitud, ni ranking, ni kill_switch, y la variable NO está admitida al
scoring (ver config/variables_spec.yaml).

NATURALEZA VECTORIAL — REGLA CENTRAL:
uo y vo son las dos componentes de un mismo vector. Una celda solo se
considera válida si AMBAS componentes lo son en el mismo instante, la misma
profundidad y la misma coordenada. Un uo válido con vo en NaN no es medio
vector: es un vector desconocido, y tratar la componente ausente como cero
fabricaría una dirección que nadie midió. Por eso el emparejamiento es
estricto y no se rellena nunca.

EJES COMUNES DE LAS DOS COMPONENTES:
Los instantes, las latitudes y las longitudes se cruzan EXPLÍCITAMENTE entre
uo y vo. No se presupone que ambas componentes declaren los mismos ejes. Si
una etiqueta existe en una y no en la otra, se descarta ESA celda o ESE
instante -- nunca el día entero, y nunca a través del except general: un
desajuste de ejes es un dato ausente, no un fallo técnico.

DERIVADAS DECLARADAS (no interpolación):
  speed_m_s = sqrt(uo^2 + vo^2)
  direction_toward_deg = degrees(atan2(uo, vo)) mod 360
Ambas son transformaciones algebraicas exactas de dos valores NATIVOS de la
misma celda e instante. La dirección es la dirección HACIA LA QUE FLUYE el
agua, medida en grados desde el norte en sentido horario (convención
oceanográfica). La convención meteorológica es la contraria y confundirlas
invierte el resultado 180 grados.

VECTOR NULO:
Si uo y vo son exactamente cero, la rapidez es 0.0 y la dirección es None,
NO 0 grados. atan2(0, 0) devuelve 0.0 por convención de la biblioteca, pero
un vector de módulo nulo no apunta al norte: no tiene dirección. Declararla
como 0 grados sería fabricar una orientación que el dato no contiene.

SEMÁNTICA TEMPORAL Y COBERTURA:
La ventana se define en fecha y hora LOCAL de Pucusana y se convierte a UTC.
Los cuatro instantes nativos (00/06/12/18 UTC) caen en 01:00, 07:00, 13:00 y
19:00 hora local; el de las 19:00 corresponde a las 00:00 UTC del día
siguiente, así que la conversión conserva ese cruce de fecha. Los instantes
ESPERADOS se calculan desde la ventana pedida, no son un número fijo: un día
completo espera cuatro y una ventana 00-06 espera uno. Así, los timestamps
que el producto NO devuelve también cuentan como ausentes, no solo los que
devuelve con el par incompleto. Nada se fabrica.

PROFUNDIDAD:
Se consulta con maximum_depth=SURFACE_SEARCH_MAX_DEPTH_M y SIN minimum_depth
(pedir 0.0 genera advertencia de rango excedido), y se toma dinámicamente el
nivel más somero COMÚN a ambas componentes. No se hardcodea ningún valor de
profundidad.

DISEÑO FAIL-SAFE:
Sin ninguna medición válida el estado es SIN_DATOS, con todos los campos de
dato en None. SIN_DATOS nunca se convierte en cero, en calma ni en condición
favorable. Los fallos de red, de datos o de programación se registran con
logger.exception antes de convertirse en SIN_DATOS. Los errores de USO
(argumentos inválidos) se propagan como ValueError, fuera del try general.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from zoneinfo import ZoneInfo

import copernicusmarine
import pandas as pd

logger = logging.getLogger(__name__)

DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
PRODUCT_ID = "GLOBAL_ANALYSISFORECAST_PHY_001_024"
DATASET_VERSION = "202406"
DATASET_PART = "default"

VARIABLE_EAST = "uo"
VARIABLE_NORTH = "vo"
STANDARD_NAME_EAST = "eastward_sea_water_velocity"
STANDARD_NAME_NORTH = "northward_sea_water_velocity"

UNITS_COMPONENTS = "m s-1"
UNITS_SPEED = "m s-1"
UNITS_DIRECTION = "degrees"

TZ_PUCUSANA = ZoneInfo("America/Lima")  # UTC-5, sin horario de verano

# Horas LOCALES en las que caen los instantes nativos del producto, dada su
# cadencia de 6 h. Se usan para calcular cuántos instantes ESPERA una ventana
# concreta, NUNCA para fabricar mediciones ausentes.
EXPECTED_LOCAL_HOURS = (1, 7, 13, 19)

DATA_SCOPE = "corrientes_superficiales_regional_referencia"

DATA_SCOPE_WARNING = (
    "Corrientes superficiales regionales de referencia, en las unidades "
    "nativas del producto (m s-1); no se convierten a otra escala. Cuando "
    "existe una medición válida, procede de las DOS componentes nativas (uo, "
    "vo) de una misma celda, instante y profundidad, dentro del recuadro "
    "consultado (grilla ~9.06 km) y dentro de la distancia máxima aceptable. "
    "La rapidez y la dirección son transformaciones algebraicas exactas de "
    "esas dos componentes, no mediciones independientes ni interpolaciones. "
    "La dirección es la dirección HACIA LA QUE FLUYE el agua, en grados desde "
    "el norte y en sentido horario; en un vector nulo la dirección es None, "
    "no 0 grados. NO es medición puntual ni in situ en Pucusana. Los "
    "instantes esperados se calculan desde la ventana solicitada: los que el "
    "producto no devuelve cuentan como ausentes y no se rellenan. Si el "
    "estado es SIN_DATOS no se tomó ningún valor ni celda: SIN_DATOS no "
    "significa calma ni corriente cero."
)

# ---- BANDA DE BÚSQUEDA SUPERFICIAL -----------------------------------
# Techo de la consulta; el nivel efectivo es el más somero COMÚN a ambas
# componentes que devuelva el dataset dentro de esta banda.
SURFACE_SEARCH_MAX_DEPTH_M = 5.0
# ----------------------------------------------------------------------

# ---- LÍMITE ESPACIAL (PROVISIONAL) -----------------------------------
# Distancia máxima aceptable entre el punto solicitado y el centro de la
# celda utilizada. Valor PROVISIONAL, no validado por la asesoría
# oceanográfica del proyecto. Cualquier interpretación pesquera de estas
# lecturas es igualmente provisional.
MAX_VALID_CELL_DISTANCE_KM = 6.5
# ----------------------------------------------------------------------


class CurrentStatus(str, Enum):
    VALIDA_EN_VENTANA = "valida_en_ventana"
    COBERTURA_PARCIAL = "cobertura_parcial"
    SIN_DATOS = "sin_datos"


@dataclass
class CurrentMeasurement:
    time_utc: datetime
    time_local: datetime
    uo_m_s: float
    vo_m_s: float
    speed_m_s: float
    direction_toward_deg: float | None  # None si el vector es nulo
    depth_m: float
    cell_lat: float
    cell_lon: float
    distance_km: float


@dataclass
class CurrentReading:
    lat: float  # solicitada
    lon: float  # solicitada
    date: date  # fecha LOCAL solicitada
    hour_start_local: int
    hour_end_local: int
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    measurements: list[CurrentMeasurement] = field(default_factory=list)
    # ---- cobertura ----
    # expected_instants NO es fijo: se calcula desde la ventana solicitada.
    # n_missing_measurements cuenta también los instantes que el producto no
    # devolvió, no solo los devueltos con el par incompleto.
    n_native_times_in_window: int = 0
    n_measurements: int = 0
    n_missing_measurements: int = 0
    expected_instants: int = 0
    # ---- profundidad ----
    depth_m_actual: float | None = None
    # ---- procedencia técnica ----
    dataset_id: str = DATASET_ID
    product_id: str = PRODUCT_ID
    dataset_version: str = DATASET_VERSION
    dataset_part: str = DATASET_PART
    variable_east: str = VARIABLE_EAST
    variable_north: str = VARIABLE_NORTH
    units_components: str = UNITS_COMPONENTS
    units_speed: str = UNITS_SPEED
    units_direction: str = UNITS_DIRECTION
    data_scope: str = DATA_SCOPE
    scope_warning: str = DATA_SCOPE_WARNING
    status: CurrentStatus = CurrentStatus.SIN_DATOS


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia real entre dos puntos geográficos (no solo diferencia de grados)."""
    R_EARTH_KM = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R_EARTH_KM * asin(sqrt(a))


def _speed(uo: float, vo: float) -> float:
    """Módulo del vector. Derivada exacta de dos componentes nativas."""
    return sqrt(uo * uo + vo * vo)


def _direction_toward(uo: float, vo: float) -> float | None:
    """
    Dirección HACIA LA QUE FLUYE el agua, en grados desde el norte y en
    sentido horario, normalizada al intervalo [0, 360).

    Devuelve None si el vector es NULO (uo y vo exactamente cero): un vector
    de módulo cero no tiene dirección, y atan2(0, 0) devolvería 0.0, que se
    leería como "hacia el norte". Eso sería fabricar una orientación.
    """
    if uo == 0.0 and vo == 0.0:
        return None
    return degrees(atan2(uo, vo)) % 360.0


def _expected_instants(hour_start: int, hour_end: int) -> int:
    """
    Instantes nativos ESPERADOS dentro de la ventana local solicitada.

    No es un número fijo: se calcula desde EXPECTED_LOCAL_HOURS y el rango
    pedido. Un día completo espera cuatro; una ventana 00-06 espera uno.
    Permite contabilizar como ausentes los instantes que el producto no
    devuelve, no solo los que devuelve con el par incompleto.
    """
    return sum(1 for h in EXPECTED_LOCAL_HOURS if hour_start <= h <= hour_end)


def _validate(lat: float, lon: float, target_date: date, hour_start: int, hour_end: int) -> None:
    """
    Errores de USO: se propagan como ValueError y nunca se convierten en
    ausencia de datos. Se comprueban FUERA del try general.
    """
    if not isinstance(lat, (int, float)) or isinstance(lat, bool) or not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitud inválida: {lat!r}. Debe ser un número entre -90 y 90.")
    if not isinstance(lon, (int, float)) or isinstance(lon, bool) or not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitud inválida: {lon!r}. Debe ser un número entre -180 y 180.")
    if not isinstance(target_date, date):
        raise ValueError(f"target_date inválida: {target_date!r}. Debe ser datetime.date.")
    if not isinstance(hour_start, int) or isinstance(hour_start, bool) \
       or not isinstance(hour_end, int) or isinstance(hour_end, bool) \
       or not (0 <= hour_start <= hour_end <= 23):
        raise ValueError(
            f"Rango de horas inválido: hour_start={hour_start!r}, hour_end={hour_end!r}. "
            "Debe cumplir 0 <= hour_start <= hour_end <= 23."
        )


def _local_window_to_utc(
    target_date: date, hour_start: int, hour_end: int
) -> tuple[datetime, datetime]:
    """
    Ventana horaria en hora LOCAL de Pucusana convertida a UTC. Nunca cruza
    la fecha LOCAL solicitada, aunque en UTC sí cruce de fecha: el instante
    de las 19:00 local corresponde a las 00:00 UTC del día siguiente.
    """
    local_start = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ_PUCUSANA)
    local_start += timedelta(hours=hour_start)
    local_end = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ_PUCUSANA)
    local_end += timedelta(hours=hour_end, minutes=59, seconds=59)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _to_utc(t) -> datetime:
    """Normaliza un timestamp a UTC sin sobrescribir una zona ya presente."""
    ts = pd.Timestamp(t)
    ts = ts.tz_convert("UTC") if ts.tzinfo is not None else ts.tz_localize("UTC")
    return ts.to_pydatetime()


def _shallowest_common_depth(da_east, da_north) -> float | None:
    """
    Nivel más somero COMÚN a ambas componentes. Si no comparten ningún nivel
    en la banda consultada, no hay vector posible y se devuelve None.
    """
    niveles_e = {float(x) for x in da_east.depth.values}
    niveles_n = {float(x) for x in da_north.depth.values}
    comunes = niveles_e & niveles_n
    return min(comunes) if comunes else None


def _common_times(da_east, da_north) -> list:
    """
    Instantes presentes en AMBAS componentes, en orden ascendente. Un
    instante que solo exista en una componente no es evaluable y se descarta
    -- solo ese instante.
    """
    del_norte = {pd.Timestamp(t) for t in da_north.time.values}
    comunes = [t for t in da_east.time.values if pd.Timestamp(t) in del_norte]
    comunes.sort(key=lambda t: pd.Timestamp(t))
    return comunes


def _common_coord(vals_east, vals_north) -> list:
    """
    Etiquetas de una coordenada espacial presentes en AMBAS componentes. Una
    etiqueta que solo exista en una componente no es una celda evaluable.
    """
    del_norte = {float(x) for x in vals_north}
    return [float(x) for x in vals_east if float(x) in del_norte]


def _empty_reading(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int,
    hour_end: int,
    window_start_utc: datetime | None,
    window_end_utc: datetime | None,
    n_native_times_in_window: int = 0,
) -> CurrentReading:
    """
    SIN_DATOS: sin mediciones ni celda, pero con unidades, alcance y
    procedencia declarados igual que en una lectura válida. Los instantes
    esperados se calculan igual que en el camino con datos, de modo que la
    cobertura sea comparable incluso sin timestamps, sin profundidad común o
    tras una excepción.
    """
    esperados = _expected_instants(hour_start, hour_end)
    return CurrentReading(
        lat=lat,
        lon=lon,
        date=target_date,
        hour_start_local=hour_start,
        hour_end_local=hour_end,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        measurements=[],
        n_native_times_in_window=n_native_times_in_window,
        n_measurements=0,
        n_missing_measurements=max(0, esperados),
        expected_instants=esperados,
        depth_m_actual=None,
        dataset_id=DATASET_ID,
        product_id=PRODUCT_ID,
        dataset_version=DATASET_VERSION,
        dataset_part=DATASET_PART,
        variable_east=VARIABLE_EAST,
        variable_north=VARIABLE_NORTH,
        units_components=UNITS_COMPONENTS,
        units_speed=UNITS_SPEED,
        units_direction=UNITS_DIRECTION,
        data_scope=DATA_SCOPE,
        scope_warning=DATA_SCOPE_WARNING,
        status=CurrentStatus.SIN_DATOS,
    )


def _nearest_complete_pair(slab_east, slab_north, t_naive, lat: float, lon: float,
                           lats_comunes: list, lons_comunes: list):
    """
    Celda MÁS CERCANA con PAR COMPLETO para un instante concreto.

    Solo recorre las coordenadas COMUNES a ambas componentes: una etiqueta
    presente en una y ausente en la otra no es una celda evaluable. Descarta
    toda celda donde uo o vo sea NaN -- un par incompleto no es medio vector
    -- y toda celda a más de MAX_VALID_CELL_DISTANCE_KM. Entre las restantes
    elige la más cercana, con desempate determinista por menor latitud y
    luego menor longitud. Si la más cercana tiene el par incompleto, la
    siguiente completa ocupa su lugar.

    Devuelve (distance_km, cell_lat, cell_lon, uo, vo) o None.
    """
    candidatos = []
    for cell_lat in lats_comunes:
        for cell_lon in lons_comunes:
            uo = float(slab_east.sel(time=t_naive, latitude=cell_lat, longitude=cell_lon).values)
            vo = float(slab_north.sel(time=t_naive, latitude=cell_lat, longitude=cell_lon).values)
            if uo != uo or vo != vo:  # par incompleto: NaN en alguna componente
                continue
            dist = _haversine_km(lat, lon, cell_lat, cell_lon)
            if dist > MAX_VALID_CELL_DISTANCE_KM:
                continue
            candidatos.append((dist, cell_lat, cell_lon, uo, vo))
    if not candidatos:
        return None
    candidatos.sort()
    return candidatos[0]


def fetch_currents(
    lat: float,
    lon: float,
    target_date: date,
    hour_start: int = 0,
    hour_end: int = 23,
) -> CurrentReading:
    """
    Devuelve las mediciones vectoriales de corriente superficial para el
    punto y la ventana horaria LOCAL de Pucusana solicitados.

    Reglas:
      1. La ventana se define en hora local y se convierte a UTC.
      2. Se consultan uo y vo JUNTOS, con versión y parte explícitas.
      3. El nivel es el más somero COMÚN a ambas componentes dentro de la
         banda superficial, elegido dinámicamente.
      4. Instantes, latitudes y longitudes se cruzan entre ambas componentes:
         una etiqueta ausente en una de ellas descarta solo esa celda o ese
         instante.
      5. Por cada instante común se toma la celda más cercana con par
         completo dentro del límite de distancia; si no hay ninguna, ese
         instante queda SIN medición y no se fabrica.
      6. Los instantes ESPERADOS se calculan desde la ventana solicitada, de
         modo que los timestamps que el producto no devuelve también cuentan
         como ausentes. Estado: mediciones >= esperados -> VALIDA_EN_VENTANA;
         entre 1 y esperados-1 -> COBERTURA_PARCIAL; ninguna -> SIN_DATOS.

    Lanza ValueError si los argumentos son inválidos.
    """
    _validate(lat, lon, target_date, hour_start, hour_end)
    window_start_utc, window_end_utc = _local_window_to_utc(target_date, hour_start, hour_end)

    n_in_window = 0
    try:
        ds = copernicusmarine.open_dataset(
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            dataset_part=DATASET_PART,
            variables=[VARIABLE_EAST, VARIABLE_NORTH],
            minimum_longitude=lon - 0.05,
            maximum_longitude=lon + 0.05,
            minimum_latitude=lat - 0.05,
            maximum_latitude=lat + 0.05,
            maximum_depth=SURFACE_SEARCH_MAX_DEPTH_M,  # sin minimum_depth (evita WARNING)
            start_datetime=window_start_utc,
            end_datetime=window_end_utc,
            # sin coordinates_selection_method: no debe tocar la dimensión tiempo
        )
        da_east = ds[VARIABLE_EAST]
        da_north = ds[VARIABLE_NORTH]

        if da_east.sizes.get("time", 0) == 0 or da_north.sizes.get("time", 0) == 0:
            logger.warning(
                "Sin instantes devueltos para (%s, %s) %s [%s]",
                lat, lon, target_date, DATASET_ID,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, 0,
            )

        depth_actual = _shallowest_common_depth(da_east, da_north)
        if depth_actual is None:
            logger.warning(
                "uo y vo no comparten ningún nivel en la banda superficial para (%s, %s) %s",
                lat, lon, target_date,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, 0,
            )

        slab_east = da_east.sel(depth=depth_actual)
        slab_north = da_north.sel(depth=depth_actual)

        lats_comunes = _common_coord(slab_east.latitude.values, slab_north.latitude.values)
        lons_comunes = _common_coord(slab_east.longitude.values, slab_north.longitude.values)
        if not lats_comunes or not lons_comunes:
            logger.warning(
                "uo y vo no comparten coordenadas espaciales para (%s, %s) %s",
                lat, lon, target_date,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, 0,
            )

        instantes = []
        for t in _common_times(slab_east, slab_north):
            t_utc = _to_utc(t)
            if not (window_start_utc <= t_utc <= window_end_utc):
                continue
            instantes.append((t_utc, pd.Timestamp(t)))
        instantes.sort(key=lambda x: x[0])
        n_in_window = len(instantes)

        mediciones = []
        for t_utc, t_naive in instantes:
            par = _nearest_complete_pair(slab_east, slab_north, t_naive, lat, lon,
                                         lats_comunes, lons_comunes)
            if par is None:
                continue  # instante sin par admisible: NO se fabrica
            dist, cell_lat, cell_lon, uo, vo = par
            mediciones.append(
                CurrentMeasurement(
                    time_utc=t_utc,
                    time_local=t_utc.astimezone(TZ_PUCUSANA),
                    uo_m_s=uo,
                    vo_m_s=vo,
                    speed_m_s=_speed(uo, vo),
                    direction_toward_deg=_direction_toward(uo, vo),
                    depth_m=depth_actual,
                    cell_lat=cell_lat,
                    cell_lon=cell_lon,
                    distance_km=dist,
                )
            )

        if not mediciones:
            logger.warning(
                "Ningún instante con par completo admisible para (%s, %s) %s "
                "(instantes comunes en ventana: %d, límite %.2f km)",
                lat, lon, target_date, n_in_window, MAX_VALID_CELL_DISTANCE_KM,
            )
            return _empty_reading(
                lat, lon, target_date, hour_start, hour_end,
                window_start_utc, window_end_utc, n_in_window,
            )

        n = len(mediciones)
        esperados = _expected_instants(hour_start, hour_end)
        estado = (
            CurrentStatus.VALIDA_EN_VENTANA
            if n >= esperados
            else CurrentStatus.COBERTURA_PARCIAL
        )
        return CurrentReading(
            lat=lat,
            lon=lon,
            date=target_date,
            hour_start_local=hour_start,
            hour_end_local=hour_end,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            measurements=mediciones,
            n_native_times_in_window=n_in_window,
            n_measurements=n,
            n_missing_measurements=max(0, esperados - n),
            expected_instants=esperados,
            depth_m_actual=depth_actual,
            dataset_id=DATASET_ID,
            product_id=PRODUCT_ID,
            dataset_version=DATASET_VERSION,
            dataset_part=DATASET_PART,
            variable_east=VARIABLE_EAST,
            variable_north=VARIABLE_NORTH,
            units_components=UNITS_COMPONENTS,
            units_speed=UNITS_SPEED,
            units_direction=UNITS_DIRECTION,
            data_scope=DATA_SCOPE,
            scope_warning=DATA_SCOPE_WARNING,
            status=estado,
        )

    except Exception:
        # Fallo de red, de datos o de programación (no de uso -- ver
        # ValueError arriba, fuera del try). Se registra con traza para que
        # no quede indistinguible de una ausencia legítima de datos; no se
        # registran credenciales ni información sensible.
        logger.exception(
            "Fallo al obtener corrientes para (%s, %s) %s [%s]",
            lat, lon, target_date, DATASET_ID,
        )
        return _empty_reading(
            lat, lon, target_date, hour_start, hour_end,
            window_start_utc, window_end_utc, n_in_window,
        )