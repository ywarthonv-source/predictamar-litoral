"""
Suite sintética para ingestion/fetch_salinity.py

Totalmente sintética y determinista: NO consulta Copernicus ni ninguna red.
Sustituye copernicusmarine.open_dataset por un Dataset construido a mano y
registra los argumentos con que se le llama, para poder auditar también la
forma de la consulta (profundidad, ausencia de minimum_depth y de
coordinates_selection_method).

Sigue el patrón de tests/test_fetch_temperature.py, adaptado a salinidad:
el valor se llama `value_salinity` y la unidad nativa es exactamente
"1e-3" -- nunca `value_celsius` ni "PSU".

Punto de referencia: Caleta Pucusana (-12.471, -76.790). Distancias
Haversine conocidas desde ese punto:
  celda lon=-76.75      -> ~5.409 km  (la MÁS CERCANA)
  celda lon=-76.833333  -> ~5.703 km
  celda lon=-76.900     -> ~12.37 km  (FUERA del límite de 6.5 km)

Ejecutar:  python -m pytest tests/test_fetch_salinity.py -v
"""

from dataclasses import fields
from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_salinity as fs

LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 14)

LON_NEAR = -76.75          # ~5.409 km
LON_FAR = -76.833333       # ~5.703 km
LON_TOO_FAR = -76.900      # ~12.37 km, fuera del límite
CELL_LAT = -12.5

# Cuatro niveles bajo la banda de 5 m; el más somero debe elegirse solo.
DEPTHS = [0.494025, 1.541375, 2.645669, 3.819495]
# Marcador para niveles NO superficiales: si una prueba viera este offset
# sumado en el valor, significaría que se usó una profundidad equivocada.
DEEPER_OFFSET = 10.0

# Instantes nativos del día local completo (ventana UTC 08-14 05:00 -> 08-15 04:59:59)
NATIVE_TIMES_FULL_DAY = [
    datetime(2026, 8, 14, 6),   # 01:00 local
    datetime(2026, 8, 14, 12),  # 07:00 local
    datetime(2026, 8, 14, 18),  # 13:00 local
    datetime(2026, 8, 15, 0),   # 19:00 local (cruza fecha UTC)
]


def build_dataset(times, lons, values, depths=DEPTHS):
    """
    values: dict {lon: [v_t0, v_t1, ...]}, np.nan para celda sin dato.
    Los valores se colocan en el nivel MÁS SOMERO; los niveles inferiores
    reciben el mismo valor + DEEPER_OFFSET, para detectar si el módulo
    usara por error una profundidad distinta.
    Dims resultantes: (time, depth, latitude, longitude).
    """
    data = np.empty((len(times), len(depths), 1, len(lons)))
    for j, lon in enumerate(lons):
        col = values[lon]
        for i in range(len(times)):
            base = col[i]
            for k in range(len(depths)):
                data[i, k, 0, j] = base if k == 0 else base + DEEPER_OFFSET
    return xr.Dataset(
        {fs.VARIABLE: (("time", "depth", "latitude", "longitude"), data)},
        coords={
            "time": times,
            "depth": list(depths),
            "latitude": [CELL_LAT],
            "longitude": list(lons),
        },
    )


@pytest.fixture
def patch_open_dataset(monkeypatch):
    """
    Instala un Dataset sintético (o una excepción) y devuelve la lista de
    kwargs con que se llamó a open_dataset, para poder auditar la consulta.
    """
    calls = []

    def _install(ds=None, error=None):
        def fake_open_dataset(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return ds
        monkeypatch.setattr(fs.copernicusmarine, "open_dataset", fake_open_dataset)
        return calls

    return _install


# --------------------------------------------------------------------------
# 1. Conversión de fecha y ventana local America/Lima -> UTC, con cruce al
#    día UTC siguiente.
# --------------------------------------------------------------------------
def test_1_ventana_local_a_utc_cruza_dia_siguiente():
    ini, fin = fs._local_window_to_utc(TARGET_DATE, 0, 23)

    assert ini == datetime(2026, 8, 14, 5, 0, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 8, 15, 4, 59, 59, tzinfo=timezone.utc)
    assert fin.date() == date(2026, 8, 15), "la ventana debe cruzar al día UTC siguiente"
    # La fecha LOCAL solicitada nunca se cruza
    assert ini.astimezone(fs.TZ_PUCUSANA).date() == TARGET_DATE
    assert fin.astimezone(fs.TZ_PUCUSANA).date() == TARGET_DATE


# --------------------------------------------------------------------------
# 2. Día completo: cuatro muestras nativas y cobertura 1.0.
# --------------------------------------------------------------------------
def test_2_dia_completo_cuatro_muestras_cobertura_total(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_NEAR],
        {LON_NEAR: [35.2112, 35.2078, 35.2072, 35.2077]},
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.VALIDA_EN_VENTANA
    assert r.n_native_times_in_window == 4
    assert r.n_samples == 4
    assert r.n_missing_samples == 0
    assert r.coverage_fraction == pytest.approx(1.0)
    assert [s.value_salinity for s in r.samples] == [35.2112, 35.2078, 35.2072, 35.2077]
    assert all(s.inside_requested_window for s in r.samples)
    assert all(s.temporal_offset_hours == 0.0 for s in r.samples)
    # horas locales esperadas, incluida la de las 19:00 (00:00 UTC del día siguiente)
    assert [s.time_local.hour for s in r.samples] == [1, 7, 13, 19]
    assert r.samples[-1].time_utc == datetime(2026, 8, 15, 0, tzinfo=timezone.utc)
    assert r.units == "1e-3"


# --------------------------------------------------------------------------
# 3. Una sola celda: gana la de MAYOR cobertura temporal aunque otra esté
#    más cerca; la serie no salta entre celdas.
# --------------------------------------------------------------------------
def test_3_una_sola_celda_por_mayor_cobertura(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [35.30, np.nan, np.nan, np.nan],       # cercana, 1 válido
            LON_FAR: [35.10, 35.11, 35.12, 35.13],           # lejana, 4 válidos
        },
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.VALIDA_EN_VENTANA
    assert r.cell_lon == pytest.approx(LON_FAR), "debe ganar la celda con MÁS valores válidos"
    assert r.n_samples == 4
    assert r.coverage_fraction == pytest.approx(1.0)
    assert [s.value_salinity for s in r.samples] == [35.10, 35.11, 35.12, 35.13]


# --------------------------------------------------------------------------
# 4. Desempate por menor distancia Haversine a igual cobertura.
# --------------------------------------------------------------------------
def test_4_desempate_por_distancia(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [35.20, 35.21, 35.22, 35.23],
            LON_FAR: [35.10, 35.11, 35.12, 35.13],
        },
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.VALIDA_EN_VENTANA
    assert r.cell_lon == pytest.approx(LON_NEAR), "empate -> gana la más cercana"
    assert r.distance_km == pytest.approx(5.409, abs=0.01)
    assert r.n_samples == 4


# --------------------------------------------------------------------------
# 5. Rechazo de celdas fuera de MAX_VALID_CELL_DISTANCE_KM.
# --------------------------------------------------------------------------
def test_5_rechazo_celda_fuera_de_limite(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_TOO_FAR],
        {LON_TOO_FAR: [35.10, 35.11, 35.12, 35.13]},
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.SIN_DATOS
    assert r.samples == []
    assert r.cell_lat is None and r.cell_lon is None and r.distance_km is None


# --------------------------------------------------------------------------
# 6. Cobertura parcial declarada.
# --------------------------------------------------------------------------
def test_6_cobertura_parcial_declarada(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_NEAR],
        {LON_NEAR: [35.21, np.nan, 35.23, np.nan]},  # 2 de 4
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.VALIDA_EN_VENTANA
    assert r.n_native_times_in_window == 4
    assert r.n_samples == 2
    assert r.n_missing_samples == 2
    assert r.coverage_fraction == pytest.approx(0.5)


# --------------------------------------------------------------------------
# 7. Fallback temporal sin instantes nativos dentro de la ventana:
#    una muestra externa y coverage_fraction=None.
#    Ventana local 02:00-05:59:59 -> UTC 07:00:00-10:59:59.
# --------------------------------------------------------------------------
def test_7_fallback_sin_instantes_internos(patch_open_dataset):
    t = datetime(2026, 8, 14, 6)  # offset 1.0 h antes del inicio
    ds = build_dataset([t], [LON_NEAR], {LON_NEAR: [35.2050]})
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == fs.SalinityStatus.VALIDA_CERCANA_EN_TIEMPO
    assert r.n_native_times_in_window == 0
    assert r.n_samples == 1
    assert r.n_missing_samples == 0
    assert r.coverage_fraction is None, "sin instantes nativos en ventana -> cobertura no aplica"
    s = r.samples[0]
    assert s.inside_requested_window is False
    assert s.temporal_offset_hours == pytest.approx(1.0)
    assert s.value_salinity == 35.2050


# --------------------------------------------------------------------------
# 8. Desempate temporal determinista: a igual desfase gana el instante
#    ANTERIOR, sin depender del orden en que lleguen los tiempos.
# --------------------------------------------------------------------------
def test_8_desempate_temporal_prefiere_anterior(patch_open_dataset):
    antes = datetime(2026, 8, 14, 4)             # offset exacto 3.0 (antes)
    despues = datetime(2026, 8, 14, 13, 59, 59)  # offset exacto 3.0 (después)
    # se listan en orden inverso a propósito
    ds = build_dataset([despues, antes], [LON_NEAR], {LON_NEAR: [36.00, 34.00]})
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == fs.SalinityStatus.VALIDA_CERCANA_EN_TIEMPO
    s = r.samples[0]
    assert s.time_utc == antes.replace(tzinfo=timezone.utc), "a igual desfase, gana el anterior"
    assert s.value_salinity == 34.00
    assert s.temporal_offset_hours == pytest.approx(3.0)


# --------------------------------------------------------------------------
# 9. Fallback con instantes internos presentes pero TODOS inválidos:
#    la muestra externa no cubre ninguno -> coverage_fraction=0.0.
# --------------------------------------------------------------------------
def test_9_fallback_con_internos_invalidos(patch_open_dataset):
    externo = datetime(2026, 8, 14, 3)  # antes de la ventana del día completo; offset 2.0 h
    times = [externo] + NATIVE_TIMES_FULL_DAY
    ds = build_dataset(
        times,
        [LON_NEAR],
        {LON_NEAR: [35.1900, np.nan, np.nan, np.nan, np.nan]},
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.VALIDA_CERCANA_EN_TIEMPO
    assert r.n_native_times_in_window == 4, "los 4 instantes internos sí existían"
    assert r.n_samples == 1
    assert r.n_missing_samples == 4
    assert r.coverage_fraction == 0.0, "la muestra externa no cubre ningún instante interno"
    s = r.samples[0]
    assert s.inside_requested_window is False
    assert s.temporal_offset_hours == pytest.approx(2.0)
    assert s.value_salinity == 35.1900


# --------------------------------------------------------------------------
# 10. Rechazo del fallback cuando supera el límite de 3 horas.
# --------------------------------------------------------------------------
def test_10_fallback_excedido_rechazado(patch_open_dataset):
    t = datetime(2026, 8, 14, 3, 59, 59)  # offset 3.00028 h > 3.0
    ds = build_dataset([t], [LON_NEAR], {LON_NEAR: [35.2050]})
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == fs.SalinityStatus.SIN_DATOS
    assert r.samples == []
    assert r.cell_lon is None


# --------------------------------------------------------------------------
# 11. Nivel más somero elegido dinámicamente, y forma de la consulta:
#     maximum_depth=5.0, SIN minimum_depth y SIN coordinates_selection_method.
# --------------------------------------------------------------------------
def test_11_nivel_mas_somero_y_parametros_de_consulta(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_NEAR],
        {LON_NEAR: [35.2112, 35.2078, 35.2072, 35.2077]},
    )
    calls = patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert len(calls) == 1
    kw = calls[0]
    assert kw["maximum_depth"] == 5.0
    assert "minimum_depth" not in kw, "no debe enviarse minimum_depth"
    assert "coordinates_selection_method" not in kw, "no debe fijarse el método de selección"
    assert kw["dataset_id"] == fs.DATASET_ID
    assert kw["variables"] == [fs.VARIABLE]

    # el nivel usado es el más somero disponible, no otro de la banda
    assert r.depth_m_actual == pytest.approx(min(DEPTHS))
    assert r.depth_m_requested == 0.0
    # ningún valor lleva el marcador de los niveles inferiores
    assert all(s.value_salinity < 36.0 for s in r.samples), "se usó una profundidad equivocada"


# --------------------------------------------------------------------------
# 12. SIN_DATOS conserva procedencia, unidad y alcance, sin fabricar muestras.
# --------------------------------------------------------------------------
def test_12_sin_datos_conserva_procedencia(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_TOO_FAR],
        {LON_TOO_FAR: [35.10, 35.11, 35.12, 35.13]},
    )
    patch_open_dataset(ds)

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.SIN_DATOS
    assert r.samples == [] and r.n_samples == 0
    assert r.depth_m_actual is None
    assert r.dataset_id == "cmems_mod_glo_phy-so_anfc_0.083deg_PT6H-i"
    assert r.variable == "so"
    assert r.units == "1e-3"
    assert r.data_scope == fs.DATA_SCOPE
    assert r.scope_warning == fs.DATA_SCOPE_WARNING
    assert r.scope_warning and "1e-3" in r.scope_warning


# --------------------------------------------------------------------------
# 13. Un error de open_dataset produce SIN_DATOS, no una excepción ni un
#     valor inventado.
# --------------------------------------------------------------------------
def test_13_error_de_open_dataset_produce_sin_datos(patch_open_dataset):
    patch_open_dataset(error=RuntimeError("fallo simulado de red/credenciales"))

    r = fs.fetch_salinity(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fs.SalinityStatus.SIN_DATOS
    assert r.samples == []
    assert r.cell_lat is None and r.cell_lon is None and r.distance_km is None
    assert r.depth_m_actual is None
    assert r.units == "1e-3"


# --------------------------------------------------------------------------
# 14. Rango horario inválido: error de USO -> ValueError propagado.
# --------------------------------------------------------------------------
def test_14_rango_horario_invalido_propaga_valueerror():
    with pytest.raises(ValueError):
        fs.fetch_salinity(LAT, LON, TARGET_DATE, 10, 5)


# --------------------------------------------------------------------------
# 15. Sin residuos OPERATIVOS de temperatura ni oleaje: ni en nombres de
#     clases, ni en campos, ni en miembros de estado, ni en constantes.
#     (El docstring del módulo sí menciona "PSU" para prohibir su uso y cita
#     el módulo de temperatura como patrón; eso es documentación deliberada
#     y queda fuera de esta comprobación, que mira solo los identificadores.)
# --------------------------------------------------------------------------
def test_15_sin_residuos_operativos_de_otros_modulos():
    prohibidos = ("celsius", "psu", "temperat", "thetao", "wave", "oleaje", "vhm0", "kill_switch")

    def limpio(nombre):
        n = nombre.lower()
        return not any(p in n for p in prohibidos)

    campos_sample = [f.name for f in fields(fs.SalinitySample)]
    campos_reading = [f.name for f in fields(fs.SalinityReading)]
    assert "value_salinity" in campos_sample
    assert "value_celsius" not in campos_sample
    assert all(limpio(c) for c in campos_sample), campos_sample
    assert all(limpio(c) for c in campos_reading), campos_reading

    miembros = [(m.name, m.value) for m in fs.SalinityStatus]
    assert all(limpio(n) and limpio(v) for n, v in miembros), miembros

    publicos = [n for n in dir(fs) if not n.startswith("_")]
    assert all(limpio(n) for n in publicos), [n for n in publicos if not limpio(n)]
    assert not hasattr(fs, "kill_switch")

    assert fs.UNITS == "1e-3"
    assert fs.VARIABLE == "so"