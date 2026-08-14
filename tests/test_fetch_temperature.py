"""
Suite sintética para ingestion/fetch_temperature.py

No consulta Copernicus: sustituye copernicusmarine.open_dataset por un
Dataset construido a mano, para ejercitar exactamente los casos que los
diagnósticos reales NO cubren (celdas NaN, límites espacial y temporal,
desempates y consistencia de celda).

Punto de referencia usado en todos los casos: Caleta Pucusana
(-12.471, -76.790). Distancias Haversine conocidas desde ese punto:
  celda lon=-76.75      -> ~5.409 km  (la MÁS CERCANA)
  celda lon=-76.833333  -> ~5.703 km
  celda lon=-76.900     -> ~12.37 km  (FUERA del límite de 6.5 km)

Ejecutar:  python -m pytest tests/test_fetch_temperature.py -v
"""

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_temperature as ft

LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 12)

LON_NEAR = -76.75          # ~5.409 km
LON_FAR = -76.833333       # ~5.703 km
LON_TOO_FAR = -76.900      # ~12.37 km, fuera del límite
CELL_LAT = -12.5
DEPTH = 0.494025

# Los cuatro instantes nativos del día local completo (00-23 local)
NATIVE_TIMES_FULL_DAY = [
    datetime(2026, 8, 12, 6),   # 01:00 local
    datetime(2026, 8, 12, 12),  # 07:00 local
    datetime(2026, 8, 12, 18),  # 13:00 local
    datetime(2026, 8, 13, 0),   # 19:00 local (cruza fecha UTC)
]


def build_dataset(times, lons, values):
    """
    values: dict {lon: [v_t0, v_t1, ...]}, usar np.nan para celda sin dato.
    Construye un Dataset con dims (time, depth, latitude, longitude).
    """
    data = np.empty((len(times), 1, 1, len(lons)))
    for j, lon in enumerate(lons):
        col = values[lon]
        for i in range(len(times)):
            data[i, 0, 0, j] = col[i]
    return xr.Dataset(
        {ft.VARIABLE: (("time", "depth", "latitude", "longitude"), data)},
        coords={
            "time": times,
            "depth": [DEPTH],
            "latitude": [CELL_LAT],
            "longitude": list(lons),
        },
    )


@pytest.fixture
def patch_open_dataset(monkeypatch):
    """Devuelve una función que instala un Dataset sintético."""
    def _install(ds):
        monkeypatch.setattr(
            ft.copernicusmarine, "open_dataset", lambda **kwargs: ds
        )
    return _install


# --------------------------------------------------------------------------
# 1. Consistencia de celda: gana la de MÁS valores válidos, aunque esté más
#    lejos; y todas las muestras deben venir de ESA misma celda.
# --------------------------------------------------------------------------
def test_1_consistencia_de_celda(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [21.0, np.nan, np.nan, np.nan],       # cercana, 1 válido
            LON_FAR: [20.0, 20.1, 20.2, 20.3],              # lejana, 4 válidos
        },
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.VALIDA_EN_VENTANA
    assert r.cell_lon == pytest.approx(LON_FAR), "debe ganar la celda con MÁS valores válidos"
    assert r.n_samples == 4
    assert r.n_native_times_in_window == 4
    assert r.n_missing_samples == 0
    assert r.coverage_fraction == pytest.approx(1.0)
    # la serie no salta entre celdas: todos los valores son de LON_FAR
    assert [s.value_celsius for s in r.samples] == [20.0, 20.1, 20.2, 20.3]
    assert all(s.inside_requested_window for s in r.samples)
    assert all(s.temporal_offset_hours == 0.0 for s in r.samples)


# --------------------------------------------------------------------------
# 2. Desempate por distancia: a igual número de valores válidos, gana la
#    celda MÁS CERCANA.
# --------------------------------------------------------------------------
def test_2_desempate_por_distancia(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [22.0, 22.1, 22.2, 22.3],
            LON_FAR: [20.0, 20.1, 20.2, 20.3],
        },
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.VALIDA_EN_VENTANA
    assert r.cell_lon == pytest.approx(LON_NEAR), "empate -> gana la más cercana"
    assert r.distance_km == pytest.approx(5.409, abs=0.01)
    assert r.n_samples == 4


# --------------------------------------------------------------------------
# 3. Descarte por NaN: la celda más cercana es TODA NaN; debe elegirse la
#    lejana válida (caso que los diagnósticos reales no ejercitaron).
# --------------------------------------------------------------------------
def test_3_descarte_por_nan(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [np.nan] * 4,
            LON_FAR: [20.0, 20.1, 20.2, 20.3],
        },
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.VALIDA_EN_VENTANA
    assert r.cell_lon == pytest.approx(LON_FAR)
    assert r.n_samples == 4


# --------------------------------------------------------------------------
# 4. Rechazo espacial: la única celda con datos está fuera del límite de
#    6.5 km -> SIN_DATOS, sin celda ni valores.
# --------------------------------------------------------------------------
def test_4_rechazo_espacial(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_TOO_FAR],
        {LON_TOO_FAR: [20.0, 20.1, 20.2, 20.3]},
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.SIN_DATOS
    assert r.samples == []
    assert r.n_samples == 0
    assert r.cell_lat is None and r.cell_lon is None and r.distance_km is None
    assert r.depth_m_actual is None
    # el alcance y la procedencia viajan igual en SIN_DATOS
    assert r.data_scope == ft.DATA_SCOPE
    assert r.scope_warning == ft.DATA_SCOPE_WARNING
    assert r.dataset_id == ft.DATASET_ID and r.variable == ft.VARIABLE


# --------------------------------------------------------------------------
# 5. Borde del límite temporal: desfase EXACTAMENTE 3.0 h se acepta;
#    3.0003 h (un segundo más) se rechaza.
#    Ventana local 02:00-05:59:59 -> UTC 07:00:00-10:59:59.
# --------------------------------------------------------------------------
def test_5a_borde_temporal_exacto_aceptado(patch_open_dataset):
    t = datetime(2026, 8, 12, 4)  # 07:00 UTC - 3h = offset exacto 3.0
    ds = build_dataset([t], [LON_NEAR], {LON_NEAR: [21.5]})
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == ft.TemperatureStatus.VALIDA_CERCANA_EN_TIEMPO
    assert r.n_samples == 1
    assert r.n_native_times_in_window == 0
    assert r.coverage_fraction is None, "sin instantes nativos en ventana -> cobertura no aplica"
    s = r.samples[0]
    assert s.inside_requested_window is False
    assert s.temporal_offset_hours == pytest.approx(3.0)
    assert s.value_celsius == 21.5


def test_5b_borde_temporal_excedido_rechazado(patch_open_dataset):
    t = datetime(2026, 8, 12, 3, 59, 59)  # offset 3.00028 h > 3.0
    ds = build_dataset([t], [LON_NEAR], {LON_NEAR: [21.5]})
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == ft.TemperatureStatus.SIN_DATOS
    assert r.samples == []
    assert r.cell_lon is None


# --------------------------------------------------------------------------
# 6. ValueError NO silenciado: un rango de horas inválido es un error de
#    uso, no una ausencia de datos -> debe propagarse, no volverse SIN_DATOS.
# --------------------------------------------------------------------------
def test_6_valueerror_no_silenciado():
    with pytest.raises(ValueError):
        ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 10, 5)


# --------------------------------------------------------------------------
# 7. Desempate temporal determinista: a igual desfase, se prefiere el
#    instante ANTERIOR a la ventana, sin depender del orden recibido.
# --------------------------------------------------------------------------
def test_7_desempate_temporal_prefiere_anterior(patch_open_dataset):
    antes = datetime(2026, 8, 12, 4)             # offset exacto 3.0 (antes)
    despues = datetime(2026, 8, 12, 13, 59, 59)  # offset exacto 3.0 (después)
    # se listan en orden inverso a propósito: el resultado no debe depender
    # del orden en que lleguen los tiempos
    ds = build_dataset([despues, antes], [LON_NEAR], {LON_NEAR: [30.0, 10.0]})
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 2, 5)

    assert r.status == ft.TemperatureStatus.VALIDA_CERCANA_EN_TIEMPO
    s = r.samples[0]
    assert s.time_utc == antes.replace(tzinfo=timezone.utc), "a igual desfase, gana el anterior"
    assert s.value_celsius == 10.0
    assert s.temporal_offset_hours == pytest.approx(3.0)


# --------------------------------------------------------------------------
# 8. Cobertura parcial: serie incompleta dentro de la ventana debe quedar
#    distinguible de una completa, aun siendo ambas VALIDA_EN_VENTANA.
# --------------------------------------------------------------------------
def test_8_cobertura_parcial_declarada(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES_FULL_DAY,
        [LON_NEAR],
        {LON_NEAR: [21.0, np.nan, 21.4, np.nan]},  # 2 de 4
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.VALIDA_EN_VENTANA
    assert r.n_native_times_in_window == 4
    assert r.n_samples == 2
    assert r.n_missing_samples == 2
    assert r.coverage_fraction == pytest.approx(0.5)


# --------------------------------------------------------------------------
# 9. Fallback con instantes internos presentes pero TODOS inválidos:
#    la muestra externa se devuelve, pero NO cubre ninguno de los instantes
#    internos solicitados -> coverage_fraction debe ser 0.0, no 1/n.
#    Ventana local 00:00-23:59:59 -> UTC 05:00:00 - 04:59:59 (día siguiente).
# --------------------------------------------------------------------------
def test_9_fallback_con_internos_invalidos_no_cubre_ventana(patch_open_dataset):
    externo = datetime(2026, 8, 12, 3)  # antes de la ventana; offset 2.0 h
    times = [externo] + NATIVE_TIMES_FULL_DAY
    ds = build_dataset(
        times,
        [LON_NEAR],
        # externo válido; los 4 instantes DENTRO de la ventana, todos NaN
        {LON_NEAR: [19.8, np.nan, np.nan, np.nan, np.nan]},
    )
    patch_open_dataset(ds)

    r = ft.fetch_temperature_window(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == ft.TemperatureStatus.VALIDA_CERCANA_EN_TIEMPO
    assert r.n_native_times_in_window == 4, "los 4 instantes internos sí existían"
    assert r.n_samples == 1
    assert r.n_missing_samples == r.n_native_times_in_window
    assert r.coverage_fraction == 0.0, "la muestra externa no cubre ningún instante interno"
    s = r.samples[0]
    assert s.inside_requested_window is False
    assert s.temporal_offset_hours == pytest.approx(2.0)
    assert s.value_celsius == 19.8