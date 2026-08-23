"""
Suite sintética para ingestion/fetch_currents.py

Totalmente sintética y determinista: NO consulta Copernicus ni ninguna red.
Sustituye copernicusmarine.open_dataset por un Dataset construido a mano y
registra los kwargs de la llamada.

Corrientes es una variable VECTORIAL: su regla propia es que una celda solo
vale si uo y vo son válidos conjuntamente en el mismo instante, profundidad
y coordenada. No hay máximo espacial (eso es de oleaje), no hay celda única
para toda la serie (eso es del perfil escalar PT6H) y no hay fallback
temporal fuera de ventana (eso es de temperatura y salinidad).

Punto de referencia: Caleta Pucusana (-12.471, -76.790). Distancias
Haversine conocidas:
  lon=-76.75      -> ~5.409 km  (la MAS CERCANA)
  lon=-76.833333  -> ~5.703 km
  lon=-76.900     -> ~12.37 km  (FUERA del limite de 6.5 km)

Fecha local de referencia: 2026-08-16 -> ventana UTC
2026-08-16 05:00:00 a 2026-08-17 04:59:59.

Ejecutar:  python -m pytest tests/test_fetch_currents.py -v
"""

import inspect
import logging
import math
from dataclasses import fields
from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_currents as fcur

LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 16)

INICIO_UTC = datetime(2026, 8, 16, 5, 0, 0, tzinfo=timezone.utc)
FIN_UTC = datetime(2026, 8, 17, 4, 59, 59, tzinfo=timezone.utc)

LON_NEAR = -76.75          # ~5.409 km
LON_FAR = -76.833333       # ~5.703 km
LON_TOO_FAR = -76.900      # ~12.37 km, fuera del limite
CELL_LAT = -12.5
LAT_SUR = -12.500
LAT_NORTE = -12.442

DEPTHS = [0.494025, 1.541375, 2.645669]
DEEPER_OFFSET = 10.0  # marcador para detectar uso de una profundidad equivocada

# Los cuatro instantes nativos del dia local completo
NATIVE_TIMES = [
    datetime(2026, 8, 16, 6),   # 01:00 local
    datetime(2026, 8, 16, 12),  # 07:00 local
    datetime(2026, 8, 16, 18),  # 13:00 local
    datetime(2026, 8, 17, 0),   # 19:00 local (cruza fecha UTC)
]


def build_dataset(times, lons, u_vals, v_vals, lats=(CELL_LAT,), depths=DEPTHS):
    """
    u_vals / v_vals: dict {(lat, lon): [...]} o {lon: [...]} si hay una sola lat.
    np.nan para componente ausente. Los valores se colocan en el nivel MAS
    SOMERO; los niveles inferiores reciben valor + DEEPER_OFFSET.
    Dims: (time, depth, latitude, longitude).
    """
    def llenar(vals):
        arr = np.empty((len(times), len(depths), len(lats), len(lons)))
        for i_lat, la in enumerate(lats):
            for j, lo in enumerate(lons):
                col = vals[(la, lo)] if (la, lo) in vals else vals[lo]
                for i in range(len(times)):
                    base = col[i]
                    for k in range(len(depths)):
                        arr[i, k, i_lat, j] = base if k == 0 else base + DEEPER_OFFSET
        return arr

    dims = ("time", "depth", "latitude", "longitude")
    return xr.Dataset(
        {fcur.VARIABLE_EAST: (dims, llenar(u_vals)),
         fcur.VARIABLE_NORTH: (dims, llenar(v_vals))},
        coords={"time": list(times), "depth": list(depths),
                "latitude": list(lats), "longitude": list(lons)},
    )


@pytest.fixture
def patch_open_dataset(monkeypatch):
    """Instala un Dataset sintetico (o una excepcion) y devuelve los kwargs capturados."""
    calls = []

    def _install(ds=None, error=None):
        def fake_open_dataset(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return ds
        monkeypatch.setattr(fcur.copernicusmarine, "open_dataset", fake_open_dataset)
        return calls

    return _install


# --------------------------------------------------------------------------
# 1. Conversion del dia LOCAL a UTC, con cruce al dia UTC siguiente.
# --------------------------------------------------------------------------
def test_1_ventana_local_a_utc():
    ini, fin = fcur._local_window_to_utc(TARGET_DATE, 0, 23)

    assert ini == INICIO_UTC
    assert fin == FIN_UTC
    assert fin.date() == date(2026, 8, 17), "la ventana debe cruzar al dia UTC siguiente"
    assert ini.astimezone(fcur.TZ_PUCUSANA).date() == TARGET_DATE
    assert fin.astimezone(fcur.TZ_PUCUSANA).date() == TARGET_DATE


# --------------------------------------------------------------------------
# 2. Cuatro instantes validos -> VALIDA_EN_VENTANA, horas locales 1/7/13/19.
# --------------------------------------------------------------------------
def test_2_cuatro_instantes_validos(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.10, 0.11, 0.12, 0.13]},
                       {LON_NEAR: [0.20, 0.21, 0.22, 0.23]})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA
    assert r.n_native_times_in_window == 4
    assert r.n_measurements == 4
    assert r.n_missing_measurements == 0
    assert r.expected_instants == 4
    assert [m.time_local.hour for m in r.measurements] == [1, 7, 13, 19]
    assert r.measurements[-1].time_utc == datetime(2026, 8, 17, 0, tzinfo=timezone.utc)
    assert r.measurements[-1].time_local.date() == TARGET_DATE


# --------------------------------------------------------------------------
# 3. Cobertura parcial: solo dos instantes con par completo.
# --------------------------------------------------------------------------
def test_3_cobertura_parcial(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.10, np.nan, 0.12, np.nan]},
                       {LON_NEAR: [0.20, 0.21, 0.22, np.nan]})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.COBERTURA_PARCIAL
    assert r.n_native_times_in_window == 4
    assert r.n_measurements == 2, "los instantes ausentes NO se completan"
    assert r.n_missing_measurements == 2
    assert [m.time_local.hour for m in r.measurements] == [1, 13]


# --------------------------------------------------------------------------
# 4. Ninguna medicion valida -> SIN_DATOS, jamas cero ni calma.
# --------------------------------------------------------------------------
def test_4_sin_datos(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [np.nan] * 4},
                       {LON_NEAR: [np.nan] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.SIN_DATOS
    assert r.measurements == []
    assert r.n_measurements == 0
    assert r.expected_instants == 4, "los esperados se calculan tambien sin datos"
    assert r.n_missing_measurements == 4
    assert r.depth_m_actual is None
    assert "no significa calma" in r.scope_warning


# --------------------------------------------------------------------------
# 5. uo valido y vo NaN en la celda mas cercana: se usa la siguiente completa.
# --------------------------------------------------------------------------
def test_5_uo_valido_vo_nan(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_FAR, LON_NEAR],
                       {LON_NEAR: [0.90] * 4, LON_FAR: [0.10] * 4},
                       {LON_NEAR: [np.nan] * 4, LON_FAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA
    for m in r.measurements:
        assert m.cell_lon == pytest.approx(LON_FAR), "medio vector no es un vector"
        assert m.uo_m_s == pytest.approx(0.10) and m.vo_m_s == pytest.approx(0.20)


# --------------------------------------------------------------------------
# 6. vo valido y uo NaN en la celda mas cercana: se usa la siguiente completa.
# --------------------------------------------------------------------------
def test_6_vo_valido_uo_nan(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_FAR, LON_NEAR],
                       {LON_NEAR: [np.nan] * 4, LON_FAR: [0.10] * 4},
                       {LON_NEAR: [0.90] * 4, LON_FAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA
    for m in r.measurements:
        assert m.cell_lon == pytest.approx(LON_FAR)
        assert m.uo_m_s == pytest.approx(0.10) and m.vo_m_s == pytest.approx(0.20)


# --------------------------------------------------------------------------
# 7. Ambas componentes NaN en la mas cercana: fallback a la siguiente completa.
# --------------------------------------------------------------------------
def test_7_fallback_a_siguiente_celda_completa(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_FAR, LON_NEAR],
                       {LON_NEAR: [np.nan] * 4, LON_FAR: [-0.12] * 4},
                       {LON_NEAR: [np.nan] * 4, LON_FAR: [0.34] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA
    for m in r.measurements:
        assert m.cell_lon == pytest.approx(LON_FAR)
        assert m.distance_km == pytest.approx(5.703, abs=0.01)


# --------------------------------------------------------------------------
# 8. Unica celda completa fuera de 6.5 km -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_8_rechazo_por_distancia(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_TOO_FAR],
                       {LON_TOO_FAR: [0.10] * 4},
                       {LON_TOO_FAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.SIN_DATOS
    assert r.measurements == []


# --------------------------------------------------------------------------
# 9. Nivel nativo mas somero COMUN elegido dinamicamente.
# --------------------------------------------------------------------------
def test_9_nivel_mas_somero_dinamico(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.10] * 4},
                       {LON_NEAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.depth_m_actual == pytest.approx(min(DEPTHS))
    for m in r.measurements:
        assert m.depth_m == pytest.approx(min(DEPTHS))
        # si se hubiera usado un nivel inferior, el valor traeria DEEPER_OFFSET
        assert m.uo_m_s < 1.0 and m.vo_m_s < 1.0, "se uso una profundidad equivocada"


# --------------------------------------------------------------------------
# 10. Rapidez vectorial: sqrt(uo^2 + vo^2), caso 3-4-5.
# --------------------------------------------------------------------------
def test_10_rapidez_vectorial(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.30] * 4},
                       {LON_NEAR: [0.40] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    for m in r.measurements:
        assert m.speed_m_s == pytest.approx(0.50)
    assert fcur._speed(3.0, 4.0) == pytest.approx(5.0)
    assert fcur._speed(0.0, 0.0) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# 11. Direccion cardinal y normalizacion a [0, 360).
# --------------------------------------------------------------------------
def test_11_direccion_cardinal_y_normalizacion(patch_open_dataset):
    # hacia el norte: uo=0, vo>0 -> 0 grados
    assert fcur._direction_toward(0.0, 1.0) == pytest.approx(0.0)
    # hacia el este: uo>0, vo=0 -> 90
    assert fcur._direction_toward(1.0, 0.0) == pytest.approx(90.0)
    # hacia el sur: uo=0, vo<0 -> 180
    assert fcur._direction_toward(0.0, -1.0) == pytest.approx(180.0)
    # hacia el oeste: uo<0, vo=0 -> 270 (atan2 da -90; el modulo normaliza)
    assert fcur._direction_toward(-1.0, 0.0) == pytest.approx(270.0)
    # noroeste: atan2 negativo -> debe caer en [0,360)
    d = fcur._direction_toward(-1.0, 1.0)
    assert d == pytest.approx(315.0)
    for u, v in ((-0.12, 0.34), (0.5, -0.5), (-0.7, -0.7)):
        assert 0.0 <= fcur._direction_toward(u, v) < 360.0

    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [-1.0] * 4},
                       {LON_NEAR: [0.0] * 4})
    patch_open_dataset(ds)
    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)
    for m in r.measurements:
        assert m.direction_toward_deg == pytest.approx(270.0)


# --------------------------------------------------------------------------
# 12. Desempates deterministas: distancia, luego latitud, luego longitud.
#     El empate EXACTO se fuerza sustituyendo _haversine_km en memoria.
# --------------------------------------------------------------------------
def test_12_desempates_deterministas(patch_open_dataset, monkeypatch):
    # Sin empate: gana la mas cercana entre dos completas.
    ds0 = build_dataset(NATIVE_TIMES, [LON_FAR, LON_NEAR],
                        {LON_NEAR: [0.10] * 4, LON_FAR: [0.90] * 4},
                        {LON_NEAR: [0.20] * 4, LON_FAR: [0.90] * 4})
    patch_open_dataset(ds0)
    r0 = fcur.fetch_currents(LAT, LON, TARGET_DATE)
    assert r0.measurements[0].cell_lon == pytest.approx(LON_NEAR)
    assert r0.measurements[0].distance_km == pytest.approx(5.409, abs=0.01)

    monkeypatch.setattr(fcur, "_haversine_km", lambda a, b, c, d: 1.0)

    # Empate exacto, dos latitudes -> gana la MENOR latitud.
    ds_a = build_dataset(NATIVE_TIMES, [LON],
                         {(LAT_SUR, LON): [0.11] * 4, (LAT_NORTE, LON): [0.99] * 4},
                         {(LAT_SUR, LON): [0.21] * 4, (LAT_NORTE, LON): [0.99] * 4},
                         lats=(LAT_NORTE, LAT_SUR))
    patch_open_dataset(ds_a)
    ra = fcur.fetch_currents(LAT, LON, TARGET_DATE)
    assert ra.measurements[0].distance_km == pytest.approx(1.0)
    assert ra.measurements[0].cell_lat == pytest.approx(LAT_SUR)

    # Empate exacto, misma latitud -> gana la MENOR longitud.
    ds_b = build_dataset(NATIVE_TIMES, [LON_NEAR, LON_FAR],
                         {LON_FAR: [0.12] * 4, LON_NEAR: [0.99] * 4},
                         {LON_FAR: [0.22] * 4, LON_NEAR: [0.99] * 4},
                         lats=(CELL_LAT,))
    patch_open_dataset(ds_b)
    rb = fcur.fetch_currents(LAT, LON, TARGET_DATE)
    assert rb.measurements[0].cell_lon == pytest.approx(LON_FAR)


# --------------------------------------------------------------------------
# 13. Parametros exactos enviados a Copernicus.
# --------------------------------------------------------------------------
def test_13_parametros_de_consulta(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.10] * 4}, {LON_NEAR: [0.20] * 4})
    calls = patch_open_dataset(ds)

    fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert len(calls) == 1
    kw = calls[0]
    assert kw["dataset_id"] == "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
    assert kw["dataset_version"] == "202406"
    assert kw["dataset_part"] == "default"
    assert kw["variables"] == ["uo", "vo"], "ambas componentes se piden juntas"
    assert kw["minimum_longitude"] == pytest.approx(LON - 0.05)
    assert kw["maximum_longitude"] == pytest.approx(LON + 0.05)
    assert kw["minimum_latitude"] == pytest.approx(LAT - 0.05)
    assert kw["maximum_latitude"] == pytest.approx(LAT + 0.05)
    assert kw["maximum_depth"] == 5.0
    assert "minimum_depth" not in kw, "no debe enviarse minimum_depth"
    assert "coordinates_selection_method" not in kw
    assert kw["start_datetime"] == INICIO_UTC
    assert kw["end_datetime"] == FIN_UTC


# --------------------------------------------------------------------------
# 14. Procedencia completa en una lectura con datos.
# --------------------------------------------------------------------------
def test_14_procedencia_con_datos(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.10] * 4}, {LON_NEAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.dataset_id == "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
    assert r.product_id == "GLOBAL_ANALYSISFORECAST_PHY_001_024"
    assert r.dataset_version == "202406"
    assert r.dataset_part == "default"
    assert r.variable_east == "uo" and r.variable_north == "vo"
    assert r.units_components == "m s-1" and r.units_speed == "m s-1"
    assert r.units_direction == "degrees"
    assert r.data_scope == fcur.DATA_SCOPE
    assert r.scope_warning == fcur.DATA_SCOPE_WARNING
    assert "hacia la que fluye" in r.scope_warning.lower()


# --------------------------------------------------------------------------
# 15. Procedencia completa TAMBIEN en SIN_DATOS.
# --------------------------------------------------------------------------
def test_15_procedencia_sin_datos(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_TOO_FAR],
                       {LON_TOO_FAR: [0.10] * 4}, {LON_TOO_FAR: [0.20] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.SIN_DATOS
    assert r.dataset_id == fcur.DATASET_ID
    assert r.product_id == fcur.PRODUCT_ID
    assert r.dataset_version == fcur.DATASET_VERSION
    assert r.dataset_part == fcur.DATASET_PART
    assert r.variable_east == fcur.VARIABLE_EAST and r.variable_north == fcur.VARIABLE_NORTH
    assert r.units_components == fcur.UNITS_COMPONENTS
    assert r.data_scope == fcur.DATA_SCOPE
    assert r.scope_warning == fcur.DATA_SCOPE_WARNING


# --------------------------------------------------------------------------
# 16. Excepcion registrada con traza y convertida en SIN_DATOS.
# --------------------------------------------------------------------------
def test_16_excepcion_registrada(patch_open_dataset, caplog):
    patch_open_dataset(error=RuntimeError("fallo simulado de red/credenciales"))

    with caplog.at_level(logging.ERROR, logger=fcur.logger.name):
        r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.SIN_DATOS
    assert r.measurements == []
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)
    assert any(rec.exc_info for rec in caplog.records), "debe registrarse con traza"


# --------------------------------------------------------------------------
# 17. Argumentos invalidos -> ValueError propagado (fuera del try general).
# --------------------------------------------------------------------------
def test_17_argumentos_invalidos():
    with pytest.raises(ValueError):
        fcur.fetch_currents(100.0, LON, TARGET_DATE)
    with pytest.raises(ValueError):
        fcur.fetch_currents(LAT, 500.0, TARGET_DATE)
    with pytest.raises(ValueError):
        fcur.fetch_currents(LAT, LON, "2026-08-16")
    with pytest.raises(ValueError):
        fcur.fetch_currents(LAT, LON, TARGET_DATE, 10, 5)


# --------------------------------------------------------------------------
# 18. Sin residuos de otra arquitectura ni de otros modulos.
# --------------------------------------------------------------------------
def test_18_sin_residuos_de_otra_arquitectura():
    src = inspect.getsource(fcur)
    prohibidos = (
        "NotImplementedError",
        "value_celsius", "value_salinity", "value_mg_m3",
        "significant_wave_height_m", "WAVE_HEIGHT_THRESHOLD_M",
        "MAX_TEMPORAL_OFFSET_HOURS", "MAX_TEMPORAL_AGE_HOURS",
        "BAJO_UMBRAL_REGIONAL", "SOBRE_UMBRAL_REGIONAL",
        "VALIDA_CERCANA_EN_TIEMPO", "VALIDA_EN_FECHA_LOCAL",
        "coverage_ratio", "low_coverage_alert", "source_age_days",
        ".interp(", "interp_like", "fillna", "ffill", "bfill",
    )
    hallados = [p for p in prohibidos if p in src]
    assert not hallados, "residuos encontrados en el modulo: %s" % hallados

    import ast
    llamadas = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)]
    kwargs_open = [kw.arg for c in llamadas for kw in c.keywords
                   if isinstance(c.func, ast.Attribute) and c.func.attr == "open_dataset"]
    assert "coordinates_selection_method" not in kwargs_open
    assert "minimum_depth" not in kwargs_open

    assert not hasattr(fcur, "kill_switch"), "corrientes no es compuerta de seguridad"

    campos_m = [f.name for f in fields(fcur.CurrentMeasurement)]
    for req in ("time_utc", "time_local", "uo_m_s", "vo_m_s", "speed_m_s",
                "direction_toward_deg", "depth_m", "cell_lat", "cell_lon", "distance_km"):
        assert req in campos_m, "falta %s en CurrentMeasurement" % req

    estados = [(m.name, m.value) for m in fcur.CurrentStatus]
    assert estados == [
        ("VALIDA_EN_VENTANA", "valida_en_ventana"),
        ("COBERTURA_PARCIAL", "cobertura_parcial"),
        ("SIN_DATOS", "sin_datos"),
    ]
    assert fcur.MAX_VALID_CELL_DISTANCE_KM == 6.5
    assert fcur.SURFACE_SEARCH_MAX_DEPTH_M == 5.0
    assert fcur.EXPECTED_LOCAL_HOURS == (1, 7, 13, 19)


# --------------------------------------------------------------------------
# 19. Vector NULO: rapidez 0.0 y direccion None, jamas 0 grados.
# --------------------------------------------------------------------------
def test_19_vector_nulo_sin_direccion(patch_open_dataset):
    assert fcur._direction_toward(0.0, 0.0) is None, "atan2(0,0) daria 0.0: no es el norte"
    assert fcur._speed(0.0, 0.0) == pytest.approx(0.0)

    ds = build_dataset(NATIVE_TIMES, [LON_NEAR],
                       {LON_NEAR: [0.0] * 4}, {LON_NEAR: [0.0] * 4})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA, "cero es un dato valido, no ausencia"
    for m in r.measurements:
        assert m.uo_m_s == pytest.approx(0.0) and m.vo_m_s == pytest.approx(0.0)
        assert m.speed_m_s == pytest.approx(0.0)
        assert m.direction_toward_deg is None, "un vector nulo no apunta al norte"


# --------------------------------------------------------------------------
# 20. El producto devuelve solo dos instantes en un dia completo:
#     los timestamps AUSENTES tambien cuentan como faltantes.
# --------------------------------------------------------------------------
def test_20_timestamps_ausentes_cuentan_como_faltantes(patch_open_dataset):
    dos_instantes = [NATIVE_TIMES[0], NATIVE_TIMES[2]]  # 01:00 y 13:00 local
    ds = build_dataset(dos_instantes, [LON_NEAR],
                       {LON_NEAR: [0.10, 0.12]}, {LON_NEAR: [0.20, 0.22]})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.COBERTURA_PARCIAL
    assert r.n_native_times_in_window == 2, "el producto solo devolvio dos"
    assert r.n_measurements == 2
    assert r.expected_instants == 4, "un dia completo espera cuatro"
    assert r.n_missing_measurements == 2, "los no devueltos tambien faltan"


# --------------------------------------------------------------------------
# 21. Ventana local 00-06: espera UN instante; si existe, es valida.
# --------------------------------------------------------------------------
def test_21_ventana_parcial_espera_un_instante(patch_open_dataset):
    ds = build_dataset([NATIVE_TIMES[0]], [LON_NEAR],
                       {LON_NEAR: [0.10]}, {LON_NEAR: [0.20]})
    patch_open_dataset(ds)

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE, 0, 6)

    assert r.expected_instants == 1, "solo la hora local 01:00 cae en 00-06"
    assert r.n_measurements == 1
    assert r.n_missing_measurements == 0
    assert r.status == fcur.CurrentStatus.VALIDA_EN_VENTANA
    assert r.measurements[0].time_local.hour == 1


# --------------------------------------------------------------------------
# 22. Ejes no identicos entre componentes: solo se conservan los pares
#     comunes, y el desajuste NO convierte el dia entero en SIN_DATOS.
# --------------------------------------------------------------------------
def test_22_ejes_no_identicos_entre_componentes(patch_open_dataset):
    depth = [min(DEPTHS)]

    # uo: 4 instantes y 2 longitudes (incluida la mas cercana)
    da_e = xr.DataArray(
        np.full((4, 1, 1, 2), 0.10),
        dims=("time", "depth", "latitude", "longitude"),
        coords={"time": NATIVE_TIMES, "depth": depth,
                "latitude": [CELL_LAT], "longitude": [LON_FAR, LON_NEAR]},
    )
    # vo: solo 3 instantes y solo la longitud LEJANA
    da_n = xr.DataArray(
        np.full((3, 1, 1, 1), 0.20),
        dims=("time", "depth", "latitude", "longitude"),
        coords={"time": NATIVE_TIMES[:3], "depth": depth,
                "latitude": [CELL_LAT], "longitude": [LON_FAR]},
    )

    class DosComponentes:
        """Doble de prueba: cada componente declara sus propios ejes."""

        def __init__(self, e, n):
            self._d = {fcur.VARIABLE_EAST: e, fcur.VARIABLE_NORTH: n}

        def __getitem__(self, k):
            return self._d[k]

    patch_open_dataset(DosComponentes(da_e, da_n))

    r = fcur.fetch_currents(LAT, LON, TARGET_DATE)

    assert r.status == fcur.CurrentStatus.COBERTURA_PARCIAL, "el desajuste no anula el dia"
    assert r.n_native_times_in_window == 3, "solo los instantes comunes"
    assert r.n_measurements == 3
    assert r.expected_instants == 4
    assert r.n_missing_measurements == 1
    for m in r.measurements:
        assert m.cell_lon == pytest.approx(LON_FAR), "la longitud sin par no es evaluable"
        assert m.uo_m_s == pytest.approx(0.10) and m.vo_m_s == pytest.approx(0.20)