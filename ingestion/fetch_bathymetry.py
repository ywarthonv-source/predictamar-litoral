"""
Ingesta de batimetría — PredictaMAR Litoral (Pucusana)

FUENTE: GEBCO_2026 Grid (publicado el 23 de abril de 2026),
doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa, distribuido por el CEDA del
NERC y accesible vía OPeNDAP. Grilla global de 15 segundos de arco, registrada
al CENTRO del píxel. La elevación es un entero de 2 bytes en metros, NEGATIVO
bajo el mar y POSITIVO en tierra. La acompaña una grilla Type Identifier (TID)
de la misma geometría, en enteros de 1 byte, que describe el TIPO DE FUENTE de
cada celda.

VARIABLE ESTÁTICA DE SOPORTE ESTRUCTURAL:
Este módulo NO recibe fecha ni ventana temporal: el fondo marino no tiene
cadencia. No participa en el scoring y no afirma ninguna capacidad predictiva.
Su función es aportar contexto estructural -- profundidad y pendiente -- que
otras variables dinámicas no transportan.

POR QUÉ ESTA VARIABLE Y NO LA CONVERGENCIA DE CORRIENTES:
La grilla de corrientes (~9.06 km) es casi tan ancha como todo el alcance
operativo de 0-10 km, y una derivada espacial sobre ella describiría un rasgo
de mesoescala mayor que el propio dominio. GEBCO, en cambio, tiene celdas de
unos 450 m en Pucusana: unas veinte veces más finas que el alcance, de modo que
SÍ puede diferenciar puntos dentro de él.

LÍMITE ESPACIAL DERIVADO DE LA GEOMETRÍA, NO HEREDADO:
El límite de 6.5 km de los productos PT6H NO se hereda aquí: sería absurdo
sobre una grilla cuarenta veces más fina. La búsqueda se restringe al VECINDARIO
NATIVO INMEDIATO -- las celdas a distancia de índice 1 de la celda
geométricamente más próxima -- lo que en la latitud de Pucusana acota la
distancia máxima posible a algo menos de 1 km (celda de ~452 m en x y ~463 m
en y, diagonal ~648 m). Cada lectura declara su distancia real en metros.

NUNCA SE CARGA LA GRILLA GLOBAL:
Se solicita únicamente el recuadro mínimo necesario alrededor del punto
(±2.5 celdas), suficiente para buscar la celda oceánica más cercana y sus
cuatro vecinos cardinales. La grilla completa tiene 43200 x 86400 celdas y
jamás se materializa.

DISEÑO FAIL-SAFE:
La validación de argumentos ocurre ANTES de tocar la red y propaga ValueError.
Los fallos de red, de OPeNDAP, de esquema o de datos se registran con
logger.exception y producen SIN_DATOS con una razón explícita. No se registran
credenciales ni información sensible. Tierra NUNCA se trata como profundidad
cero, no se interpola, no se rellena, no se promedia y no se fabrican valores.

CURVATURA: DELIBERADAMENTE NO IMPLEMENTADA.
Todavía no se ha acordado qué curvatura corresponde -- laplaciana, media,
gaussiana, de perfil o de planta -- y esa decisión debe tomarse después de
observar el TID real de Pucusana. Derivar una segunda derivada sobre una
superficie que puede ser interpolada amplificaría el artefacto de interpolación
en vez de describir el fondo. Se registra la limitación de forma explícita en
cada lectura en vez de devolver un cero engañoso.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Procedencia oficial (verificada contra el catálogo de GEBCO/CEDA, ago 2026)
# --------------------------------------------------------------------------
PRODUCT = "GEBCO_2026 Grid"
PRODUCT_VERSION = "2026"
PRODUCT_DOI = "10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa"
PRODUCT_RELEASED = "2026-04-23"

URL_ELEVATION = (
    "https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026/"
    "ice_surface_elevation/netcdf/GEBCO_2026.nc"
)
URL_TID = (
    "https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026/"
    "type_identifier_grid/netcdf/gebco_2026_tid.nc"
)

VARIABLE_ELEVATION = "elevation"
VARIABLE_TID = "tid"
COORD_LAT = "lat"
COORD_LON = "lon"

UNITS_ELEVATION = "m"
UNITS_DEPTH = "m"
UNITS_SLOPE = "degrees"

NOMINAL_RESOLUTION = "15 arc-seconds (1/240 grado), registro al centro del pixel"
CELL_SIZE_DEG = 1.0 / 240.0

OPENDAP_ENGINE = "pydap"

R_EARTH_M = 6371008.8

# --------------------------------------------------------------------------
# Vecindario nativo: derivado de la geometría de la grilla, NO heredado
# --------------------------------------------------------------------------
# Distancia de índice máxima, en celdas, a la que se acepta buscar una celda
# oceánica alrededor de la celda geométricamente más próxima al punto.
NEIGHBOR_SEARCH_CELLS = 1
# La pendiente necesita los cuatro vecinos cardinales de la celda elegida, es
# decir una celda más en cada dirección.
SLOPE_STENCIL_CELLS = 1
# Semiancho del recuadro solicitado al proveedor. El 0.5 adicional cubre el
# registro al centro del píxel para que el recuadro contenga las celdas
# completas y no quede cortado en el borde.
REQUEST_HALF_WIDTH_DEG = (NEIGHBOR_SEARCH_CELLS + SLOPE_STENCIL_CELLS + 0.5) * CELL_SIZE_DEG

# --------------------------------------------------------------------------
# Agrupación de procedencia del TID
# --------------------------------------------------------------------------
# Los RANGOS son política de agrupación declarada por el proyecto; el
# SIGNIFICADO de cada código se lee dinámicamente de flag_values/flag_meanings
# del propio archivo, para no mantener una tabla paralela que pueda divergir
# de la fuente.
TID_LAND_CODE = 0
TID_FILL_VALUE = 127
TID_RANGE_DIRECT = (10, 17)
TID_RANGE_INDIRECT = (40, 48)
TID_RANGE_MIXED = (70, 72)

DATA_SCOPE = "batimetria_regional_referencia_estatica"

DATA_SCOPE_WARNING = (
    "Batimetría regional de referencia, ESTÁTICA. NO es una medición in situ en "
    "Pucusana: procede de un modelo global compilado por GEBCO. NO es apta para "
    "navegación, seguridad marítima ni autorización de faena, y GEBCO lo prohíbe "
    "expresamente. La resolución de la grilla NO equivale a la resolución real "
    "del levantamiento: en muchas zonas costeras la malla es más fina que los "
    "sondajes que la sustentan. El datum vertical puede NO ser homogéneo en "
    "aguas someras, porque GEBCO asimila fuentes heterogéneas asumiendo nivel "
    "medio del mar y en algunas áreas someras incorpora datos con otro datum. El "
    "TID describe la PROCEDENCIA del dato, no garantiza su exactitud. La "
    "pendiente es una cantidad DERIVADA de celdas vecinas, no una observación, y "
    "puede reflejar interpolación en vez de relieve real. Esta variable NO "
    "participa todavía en el scoring y no implica aptitud pesquera."
)

CURVATURE_STATUS = "no_implementada"
CURVATURE_NOTE = (
    "Curvatura deliberadamente NO implementada: falta acordar la definición "
    "(laplaciana, media, gaussiana, de perfil o de planta) y observar antes el "
    "TID real de Pucusana. Una segunda derivada sobre una superficie posiblemente "
    "interpolada amplificaría el artefacto de interpolación. No se devuelve cero: "
    "un cero se leería como fondo plano."
)


class BathymetryStatus(str, Enum):
    VALIDA = "valida"
    SIN_DATOS = "sin_datos"


class TidGroup(str, Enum):
    DIRECTA = "directa"
    INDIRECTA = "indirecta"
    MIXTA_DESCONOCIDA = "mixta_desconocida"
    # Códigos fuera de los rangos declarados (incluidos tierra y relleno). No se
    # fuerzan a "mixta_desconocida": clasificar sin criterio sería inventar una
    # procedencia que la fuente no declara.
    NO_CLASIFICADO = "no_clasificado"


@dataclass(frozen=True)
class BathymetryReading:
    """Lectura estática de batimetría para un punto. Inmutable."""

    status: BathymetryStatus

    # ---- punto solicitado ----
    lat: float
    lon: float

    # ---- dato nativo y derivados ----
    elevation_m: float | None = None
    depth_m: float | None = None          # positiva, solo si elevation_m < 0
    slope_deg: float | None = None
    slope_unavailable_reason: str | None = None
    curvature_status: str = CURVATURE_STATUS
    curvature_note: str = CURVATURE_NOTE

    # ---- procedencia del dato (TID) ----
    tid_code: int | None = None
    tid_meaning: str | None = None
    tid_meaning_source: str | None = None
    tid_group: TidGroup | None = None

    # ---- celda utilizada ----
    cell_lat: float | None = None
    cell_lon: float | None = None
    distance_m: float | None = None
    neighbor_search_cells: int = NEIGHBOR_SEARCH_CELLS

    # ---- procedencia técnica ----
    product: str = PRODUCT
    product_version: str = PRODUCT_VERSION
    product_doi: str = PRODUCT_DOI
    url_elevation: str = URL_ELEVATION
    url_tid: str = URL_TID
    variable_elevation: str = VARIABLE_ELEVATION
    variable_tid: str = VARIABLE_TID
    units_elevation: str = UNITS_ELEVATION
    units_depth: str = UNITS_DEPTH
    units_slope: str = UNITS_SLOPE
    nominal_resolution: str = NOMINAL_RESOLUTION
    data_scope: str = DATA_SCOPE
    scope_warning: str = DATA_SCOPE_WARNING

    # ---- motivo explícito cuando no hay dato ----
    no_data_reason: str | None = None


class _ProviderError(RuntimeError):
    """Fallo al obtener o alinear los subconjuntos del proveedor."""


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia real entre dos puntos geográficos, en metros."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R_EARTH_M * math.asin(math.sqrt(a))


def _validate(lat: float, lon: float) -> None:
    """
    Errores de USO: se comprueban ANTES de cualquier acceso a la red y se
    propagan como ValueError. Nunca se convierten en ausencia de datos.
    """
    for nombre, valor, limite in (("Latitud", lat, 90.0), ("Longitud", lon, 180.0)):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError(f"{nombre} inválida: {valor!r}. Debe ser un número.")
        if not math.isfinite(float(valor)):
            raise ValueError(f"{nombre} inválida: {valor!r}. Debe ser finita.")
        if not (-limite <= float(valor) <= limite):
            raise ValueError(
                f"{nombre} inválida: {valor!r}. Debe estar entre -{limite} y {limite}."
            )


def open_gebco_subsets(lat: float, lon: float):
    """
    CAPA DE ACCESO AL PROVEEDOR -- aislada y sustituible en pruebas.

    Devuelve (subconjunto_elevacion, subconjunto_tid) como DataArray de xarray,
    recortados al recuadro mínimo alrededor del punto. Es la ÚNICA función del
    módulo que toca la red; las pruebas la reemplazan por completo.

    Nunca materializa la grilla global: xarray abre el recurso OPeNDAP de forma
    perezosa, el .sel por rango de coordenadas restringe la lectura al recuadro
    de unas 6x6 celdas, y solo entonces .load() trae valores. La grilla completa
    (43200 x 86400 celdas) jamas se descarga.

    Ambos datasets se abren como context managers y se CIERRAN antes de
    devolver: sin esto quedaria una conexion remota abierta por cada llamada, y
    en un uso repetido el proceso acumularia descriptores hasta agotarlos. Los
    recortes ya estan cargados en memoria, asi que siguen siendo utilizables
    despues del cierre.
    """
    lat_slice = slice(lat - REQUEST_HALF_WIDTH_DEG, lat + REQUEST_HALF_WIDTH_DEG)
    lon_slice = slice(lon - REQUEST_HALF_WIDTH_DEG, lon + REQUEST_HALF_WIDTH_DEG)
    seleccion = {COORD_LAT: lat_slice, COORD_LON: lon_slice}

    with xr.open_dataset(URL_ELEVATION, engine=OPENDAP_ENGINE) as ds_elev, \
         xr.open_dataset(URL_TID, engine=OPENDAP_ENGINE) as ds_tid:
        sub_elev = ds_elev[VARIABLE_ELEVATION].sel(seleccion).load()
        sub_tid = ds_tid[VARIABLE_TID].sel(seleccion).load()

    return sub_elev, sub_tid


def _assert_aligned(sub_elev, sub_tid) -> None:
    """
    Verifica EN EJECUCIÓN que ambos subconjuntos son combinables celda a celda.

    Comprueba tres cosas, y las tres son necesarias:

      1. Que las DIMENSIONES sean exactamente (lat, lon) EN ESE ORDEN en ambos.
         Un TID transpuesto declara las mismas coordenadas lat y lon con los
         mismos valores, de modo que comparar solo los ejes lo dejaria pasar y
         se asignaria la procedencia a la celda equivocada -- silenciosamente y
         sin ningun error.
      2. Que la FORMA de ambos arreglos coincida.
      3. Que los valores de las coordenadas coincidan exactamente.

    Que los dos productos declaren la misma geometria es documentacion; que los
    ejes coincidan valor a valor y en el mismo orden es un hecho que hay que
    comprobar antes de combinar elevacion y TID.
    """
    dims_esperadas = (COORD_LAT, COORD_LON)
    for etiqueta, arr in (("elevacion", sub_elev), ("TID", sub_tid)):
        dims = tuple(getattr(arr, "dims", ()))
        if dims != dims_esperadas:
            raise _ProviderError(
                f"dimensiones_inesperadas: el subconjunto de {etiqueta} tiene "
                f"dimensiones {dims} y se esperaba {dims_esperadas} en ese orden; "
                "combinarlo asignaria la procedencia a la celda equivocada"
            )
    if tuple(sub_elev.shape) != tuple(sub_tid.shape):
        raise _ProviderError(
            "formas_distintas: elevacion tiene forma "
            f"{tuple(sub_elev.shape)} y TID {tuple(sub_tid.shape)}"
        )

    lat_e = np.asarray(sub_elev[COORD_LAT].values)
    lat_t = np.asarray(sub_tid[COORD_LAT].values)
    lon_e = np.asarray(sub_elev[COORD_LON].values)
    lon_t = np.asarray(sub_tid[COORD_LON].values)
    if lat_e.shape != lat_t.shape or lon_e.shape != lon_t.shape:
        raise _ProviderError(
            "desalineacion_de_grilla: los subconjuntos de elevacion y TID tienen "
            f"formas distintas (lat {lat_e.shape} vs {lat_t.shape}, "
            f"lon {lon_e.shape} vs {lon_t.shape})"
        )
    if not (np.array_equal(lat_e, lat_t) and np.array_equal(lon_e, lon_t)):
        raise _ProviderError(
            "desalineacion_de_grilla: las coordenadas de elevacion y TID no "
            "coinciden exactamente; combinarlas asignaria una procedencia a la "
            "celda equivocada"
        )
    if lat_e.size == 0 or lon_e.size == 0:
        raise _ProviderError(
            "recuadro_vacio: el proveedor no devolvio ninguna celda para el punto"
        )


def _tid_lookup(sub_tid) -> tuple[dict, str | None]:
    """Construye dinámicamente la correspondencia TID desde sus atributos."""
    attrs = getattr(sub_tid, "attrs", {}) or {}
    valores = attrs.get("flag_values")
    significados = attrs.get("flag_meanings")

    if valores is None or significados is None:
        return {}, "atributos_tid_ausentes"

    try:
        codigos = [int(v) for v in np.atleast_1d(np.asarray(valores)).tolist()]
        nombres = (
            significados.split()
            if isinstance(significados, str)
            else [
                str(x)
                for x in np.atleast_1d(np.asarray(significados)).tolist()
            ]
        )
    except Exception:
        return {}, "atributos_tid_no_parseables"

    if not codigos or not nombres:
        return {}, "atributos_tid_no_parseables"

    if len(codigos) != len(nombres):
        return {}, (
            "flag_values/flag_meanings_inconsistentes:"
            f"{len(codigos)}_valores_vs_{len(nombres)}_significados"
        )

    return dict(zip(codigos, nombres)), "flag_values/flag_meanings"


def _tid_group(codigo: int | None) -> TidGroup | None:
    """Agrupa el código TID según los rangos de procedencia declarados."""
    if codigo is None:
        return None
    if TID_RANGE_DIRECT[0] <= codigo <= TID_RANGE_DIRECT[1]:
        return TidGroup.DIRECTA
    if TID_RANGE_INDIRECT[0] <= codigo <= TID_RANGE_INDIRECT[1]:
        return TidGroup.INDIRECTA
    if TID_RANGE_MIXED[0] <= codigo <= TID_RANGE_MIXED[1]:
        return TidGroup.MIXTA_DESCONOCIDA
    return TidGroup.NO_CLASIFICADO


def _is_ocean(valor: float | None) -> bool:
    """
    Una celda es OCEÁNICA solo si su elevación es finita y ESTRICTAMENTE
    negativa. Cero no es mar: en GEBCO el cero es la línea de costa o tierra a
    nivel del mar, y tratarlo como profundidad cero convertiría tierra en un
    fondeadero de 0 m. NaN tampoco es mar.
    """
    return valor is not None and valor == valor and float(valor) < 0.0


def _empty_reading(lat: float, lon: float, motivo: str) -> BathymetryReading:
    """SIN_DATOS: sin celda ni valores, pero con toda la procedencia estática."""
    return BathymetryReading(
        status=BathymetryStatus.SIN_DATOS,
        lat=lat,
        lon=lon,
        no_data_reason=motivo,
        slope_unavailable_reason="sin_celda_valida",
    )


def _nearest_ocean_cell(elev: np.ndarray, lats: np.ndarray, lons: np.ndarray,
                        lat: float, lon: float):
    """
    Celda OCEÁNICA válida MÁS CERCANA dentro del vecindario nativo inmediato.

    Primero localiza la celda geométricamente más próxima al punto, y luego
    considera solo las celdas a distancia de índice <= NEIGHBOR_SEARCH_CELLS de
    ella. Desempate determinista: menor distancia, luego menor latitud, luego
    menor longitud. Devuelve (i, j, distancia_m) o None.
    """
    i0 = int(np.argmin(np.abs(lats - lat)))
    j0 = int(np.argmin(np.abs(lons - lon)))
    candidatos = []
    for i in range(max(0, i0 - NEIGHBOR_SEARCH_CELLS), min(len(lats), i0 + NEIGHBOR_SEARCH_CELLS + 1)):
        for j in range(max(0, j0 - NEIGHBOR_SEARCH_CELLS), min(len(lons), j0 + NEIGHBOR_SEARCH_CELLS + 1)):
            if not _is_ocean(elev[i, j]):
                continue
            cell_lat, cell_lon = float(lats[i]), float(lons[j])
            candidatos.append((_haversine_m(lat, lon, cell_lat, cell_lon), cell_lat, cell_lon, i, j))
    if not candidatos:
        return None
    candidatos.sort()
    d, _, _, i, j = candidatos[0]
    return i, j, d


def _slope_deg(elev: np.ndarray, lats: np.ndarray, lons: np.ndarray, i: int, j: int):
    """
    Pendiente por DIFERENCIAS CENTRADAS con los cuatro vecinos cardinales.

    Exige que los cuatro existan dentro del recuadro y sean oceánicos válidos.
    Si falta uno, devuelve (None, motivo): NO se recurre a una diferencia
    lateral, porque desplazaría el punto de cálculo y sesgaría la serie costera
    siempre en la misma dirección, de forma invisible.

    Las distancias son métricas REALES entre los centros de las celdas vecinas,
    no aproximaciones por grados. El signo de la elevación es irrelevante para
    la magnitud, porque las derivadas se elevan al cuadrado.

    Devuelve (slope_deg, None) o (None, motivo).
    """
    if i - 1 < 0 or i + 1 >= len(lats) or j - 1 < 0 or j + 1 >= len(lons):
        return None, "vecindario_incompleto_en_el_recuadro"

    z_sur, z_norte = elev[i - 1, j], elev[i + 1, j]
    z_oeste, z_este = elev[i, j - 1], elev[i, j + 1]
    faltantes = [n for n, z in (("sur", z_sur), ("norte", z_norte),
                                ("oeste", z_oeste), ("este", z_este)) if not _is_ocean(z)]
    if faltantes:
        return None, "vecinos_no_oceanicos_o_invalidos: " + ",".join(faltantes)

    lat_c, lon_c = float(lats[i]), float(lons[j])
    dist_x = _haversine_m(lat_c, float(lons[j - 1]), lat_c, float(lons[j + 1]))
    dist_y = _haversine_m(float(lats[i - 1]), lon_c, float(lats[i + 1]), lon_c)
    if dist_x <= 0.0 or dist_y <= 0.0:
        return None, "distancia_entre_vecinos_nula"

    dz_dx = (float(z_este) - float(z_oeste)) / dist_x
    dz_dy = (float(z_norte) - float(z_sur)) / dist_y
    return math.degrees(math.atan(math.hypot(dz_dx, dz_dy))), None


def fetch_bathymetry(lat: float, lon: float) -> BathymetryReading:
    """
    Devuelve la lectura estática de batimetría para el punto solicitado.

    Reglas:
      1. Variable ESTÁTICA: no recibe fecha ni ventana temporal.
      2. Se solicita al proveedor solo el recuadro mínimo (±2.5 celdas).
      3. Se verifica en ejecución que elevación y TID compartan exactamente las
         mismas dimensiones, forma y coordenadas antes de combinarlas.
      4. Se elige la celda OCEÁNICA válida más cercana dentro del vecindario
         nativo inmediato; tierra nunca cuenta como profundidad cero.
      5. depth_m se deriva solo cuando elevation_m < 0.
      6. slope_deg exige los cuatro vecinos cardinales oceánicos válidos; si
         falta uno, es None con motivo, nunca una diferencia lateral silenciosa.
      7. La curvatura no está implementada y se declara como tal.

    Lanza ValueError si los argumentos son inválidos. Cualquier fallo de red,
    OPeNDAP, esquema o datos se registra con traza y produce SIN_DATOS.
    """
    _validate(lat, lon)
    lat, lon = float(lat), float(lon)

    try:
        sub_elev, sub_tid = open_gebco_subsets(lat, lon)
        _assert_aligned(sub_elev, sub_tid)

        lats = np.asarray(sub_elev[COORD_LAT].values, dtype=float)
        lons = np.asarray(sub_elev[COORD_LON].values, dtype=float)
        elev = np.asarray(sub_elev.values, dtype=float)
        tid = np.asarray(sub_tid.values)

        if elev.shape != (len(lats), len(lons)):
            raise _ProviderError(
                f"esquema_inesperado: la elevacion tiene forma {elev.shape} y se "
                f"esperaba {(len(lats), len(lons))}"
            )

        elegida = _nearest_ocean_cell(elev, lats, lons, lat, lon)
        if elegida is None:
            logger.warning(
                "Sin celda oceanica en el vecindario nativo para (%s, %s) [%s]",
                lat, lon, PRODUCT,
            )
            return _empty_reading(
                lat, lon,
                "sin_celda_oceanica_en_vecindario_nativo: todas las celdas del "
                "vecindario son tierra, cero o invalidas",
            )

        i, j, distancia = elegida
        cell_lat, cell_lon = float(lats[i]), float(lons[j])
        elevation_m = float(elev[i, j])
        depth_m = -elevation_m if elevation_m < 0.0 else None

        pendiente, motivo_pendiente = _slope_deg(elev, lats, lons, i, j)

        tabla, fuente_tabla = _tid_lookup(sub_tid)
        codigo = tid[i, j]
        codigo = None if codigo != codigo else int(codigo)  # NaN -> None
        if codigo == TID_FILL_VALUE:
            significado = None
            grupo = TidGroup.NO_CLASIFICADO
        else:
            significado = tabla.get(codigo) if codigo is not None else None
            grupo = _tid_group(codigo)

        return BathymetryReading(
            status=BathymetryStatus.VALIDA,
            lat=lat,
            lon=lon,
            elevation_m=elevation_m,
            depth_m=depth_m,
            slope_deg=pendiente,
            slope_unavailable_reason=motivo_pendiente,
            tid_code=codigo,
            tid_meaning=significado,
            tid_meaning_source=fuente_tabla,
            tid_group=grupo,
            cell_lat=cell_lat,
            cell_lon=cell_lon,
            distance_m=distancia,
        )

    except Exception:
        # Red, OPeNDAP, esquema o datos. Se registra con traza para que no quede
        # indistinguible de una ausencia legitima; el motivo devuelto es una
        # etiqueta controlada y no incluye credenciales ni informacion sensible.
        logger.exception(
            "Fallo al obtener batimetria para (%s, %s) [%s]", lat, lon, PRODUCT
        )
        return _empty_reading(lat, lon, "fallo_de_proveedor_o_datos")