"""
Suite sintética para ingestion/fetch_waves.py

Totalmente sintética y determinista: NO consulta Copernicus ni ninguna red.
Sustituye copernicusmarine.open_dataset por un Dataset construido a mano y
registra los kwargs de la llamada, para auditar también la forma de la
consulta.

Oleaje es una COMPUERTA DE SEGURIDAD, no una variable de ranking pesquero.
Su criterio espacial es distinto al de los fetchers PT6H: aquí no hay
cobertura temporal ni fallback; se elige la celda válida con MAYOR máximo de
VHM0 dentro del límite de distancia.

Punto de referencia: Caleta Pucusana (-12.471, -76.790). Distancias
Haversine conocidas:
  lon=-76.75      -> ~5.409 km
  lon=-76.833333  -> ~5.703 km
  lon=-76.900     -> ~12.37 km  (FUERA del límite de 6.5 km)
  lat=-12.5 y lat=-12.442 sobre lon=-76.790 -> equidistantes (~3.22 km)

Ejecutar:  python -m pytest tests/test_fetch_waves.py -v
"""

import logging
from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_waves as fw

LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 14)

LON_NEAR = -76.75          # ~5.409 km
LON_FAR = -76.833333       # ~5.703 km
LON_TOO_FAR = -76.900      # ~12.37 km, fuera del límite
CELL_LAT = -12.5

# Latitudes simétricas respecto al punto: equidistantes sobre la misma
# longitud, para forzar el desempate por latitud.
LAT_SUR = -12.500
LAT_NORTE = -12.442

# Instantes nativos PT3H dentro de la ventana local completa
# (ventana UTC 2026-08-14 05:00 -> 2026-08-15 04:59:59)
NATIVE_TIMES = [
    datetime(2026, 8, 14, 6),
    datetime(2026, 8, 14, 12),
    datetime(2026, 8, 14, 18),
    datetime(2026, 8, 15, 0),
]


def build_dataset(times, lons, values, lats=(CELL_LAT,)):
    """
    values: dict {(lat, lon): [v_t0, ...]} o {lon: [...]} si hay una sola lat.
    np.nan para instantes sin dato. Dims: (time, latitude, longitude).
    """
    data = np.empty((len(times), len(lats), len(lons)))
    for i_lat, la in enumerate(lats):
        for j, lo in enumerate(lons):
            col = values[(la, lo)] if (la, lo) in values else values[lo]
            for i in range(len(times)):
                data[i, i_lat, j] = col[i]
    return xr.Dataset(
        {fw.VARIABLE: (("time", "latitude", "longitude"), data)},
        coords={"time": times, "latitude": list(lats), "longitude": list(lons)},
    )


@pytest.fixture
def patch_open_dataset(monkeypatch):
    """Instala un Dataset sintético (o una excepción) y devuelve los kwargs capturados."""
    calls = []

    def _install(ds=None, error=None):
        def fake_open_dataset(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return ds
        monkeypatch.setattr(fw.copernicusmarine, "open_dataset", fake_open_dataset)
        return calls

    return _install


# --------------------------------------------------------------------------
# 1. Conversión de la ventana local America/Lima a UTC, con cruce de día UTC.
# --------------------------------------------------------------------------
def test_1_ventana_local_a_utc():
    ini, fin = fw._local_window_to_utc(TARGET_DATE, 0, 23)

    assert ini == datetime(2026, 8, 14, 5, 0, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 8, 15, 4, 59, 59, tzinfo=timezone.utc)
    assert fin.date() == date(2026, 8, 15), "la ventana debe cruzar al día UTC siguiente"
    assert ini.astimezone(fw.TZ_PUCUSANA).date() == TARGET_DATE
    assert fin.astimezone(fw.TZ_PUCUSANA).date() == TARGET_DATE


# --------------------------------------------------------------------------
# 2. Parámetros exactos de la consulta; sin coordinates_selection_method.
# --------------------------------------------------------------------------
def test_2_parametros_de_consulta(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR], {LON_NEAR: [1.0, 1.1, 1.2, 1.3]})
    calls = patch_open_dataset(ds)

    fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert len(calls) == 1
    kw = calls[0]
    assert kw["dataset_id"] == fw.DATASET_ID
    assert kw["variables"] == [fw.VARIABLE]
    assert kw["minimum_longitude"] == pytest.approx(LON - 0.05)
    assert kw["maximum_longitude"] == pytest.approx(LON + 0.05)
    assert kw["minimum_latitude"] == pytest.approx(LAT - 0.05)
    assert kw["maximum_latitude"] == pytest.approx(LAT + 0.05)
    assert kw["start_datetime"] == datetime(2026, 8, 14, 5, 0, 0, tzinfo=timezone.utc)
    assert kw["end_datetime"] == datetime(2026, 8, 15, 4, 59, 59, tzinfo=timezone.utc)
    assert "coordinates_selection_method" not in kw, "no debe fijarse el método de selección"
    assert "minimum_depth" not in kw and "maximum_depth" not in kw, "el producto de oleaje no tiene profundidad"


# --------------------------------------------------------------------------
# 3. Selección CONSERVADORA: gana la celda con MAYOR máximo aunque esté más
#    lejos (dentro del límite), no la más cercana.
# --------------------------------------------------------------------------
def test_3_seleccion_conservadora_gana_mayor_maximo(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [0.8, 0.9, 1.0, 0.7],   # cercana, máximo 1.0
            LON_FAR: [1.2, 1.9, 1.4, 1.1],    # lejana, máximo 1.9
        },
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.cell_lon == pytest.approx(LON_FAR), "debe ganar la celda de MAYOR máximo"
    assert r.significant_wave_height_m == pytest.approx(1.9)
    assert r.distance_km == pytest.approx(5.703, abs=0.01)
    assert r.status == fw.WaveStatus.SOBRE_UMBRAL_REGIONAL
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 4. Descarte de NaN: la celda más cercana es toda NaN -> se usa la otra.
# --------------------------------------------------------------------------
def test_4_descarte_de_nan(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [np.nan] * 4,
            LON_FAR: [1.6, 1.7, 1.72, 1.6],
        },
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.cell_lon == pytest.approx(LON_FAR)
    assert r.significant_wave_height_m == pytest.approx(1.72)
    assert r.status == fw.WaveStatus.SOBRE_UMBRAL_REGIONAL


# --------------------------------------------------------------------------
# 5. Desempate por distancia cuando los máximos son iguales.
# --------------------------------------------------------------------------
def test_5_desempate_por_distancia(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES,
        [LON_FAR, LON_NEAR],
        {
            LON_NEAR: [0.5, 1.4, 0.6, 0.7],
            LON_FAR: [0.9, 1.4, 0.8, 0.6],
        },
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.significant_wave_height_m == pytest.approx(1.4)
    assert r.cell_lon == pytest.approx(LON_NEAR), "a igual máximo, gana la más cercana"
    assert r.distance_km == pytest.approx(5.409, abs=0.01)
    assert r.status == fw.WaveStatus.BAJO_UMBRAL_REGIONAL


# --------------------------------------------------------------------------
# 6. Desempate determinista por latitud cuando máximo y distancia empatan.
# --------------------------------------------------------------------------
def test_6_desempate_por_latitud(patch_open_dataset):
    d_sur = fw._haversine_km(LAT, LON, LAT_SUR, LON)
    d_norte = fw._haversine_km(LAT, LON, LAT_NORTE, LON)
    assert d_sur == pytest.approx(d_norte, abs=1e-9), "las dos celdas deben ser equidistantes"

    ds = build_dataset(
        NATIVE_TIMES,
        [LON],
        {(LAT_SUR, LON): [1.0, 1.3, 0.9, 0.8], (LAT_NORTE, LON): [0.7, 1.3, 1.0, 0.9]},
        lats=(LAT_SUR, LAT_NORTE),
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.significant_wave_height_m == pytest.approx(1.3)
    assert r.cell_lat == pytest.approx(LAT_SUR), "empate total -> menor latitud"


# --------------------------------------------------------------------------
# 7. Límite de distancia: única celda válida fuera de 6.5 km -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_7_limite_de_distancia(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_TOO_FAR], {LON_TOO_FAR: [2.5, 2.6, 2.7, 2.4]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fw.WaveStatus.SIN_DATOS
    assert r.significant_wave_height_m is None
    assert r.cell_lat is None and r.cell_lon is None and r.distance_km is None
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 8. Dimensión temporal vacía -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_8_tiempo_vacio(patch_open_dataset):
    ds = build_dataset([], [LON_NEAR], {LON_NEAR: []})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fw.WaveStatus.SIN_DATOS
    assert r.max_time_utc is None and r.max_time_local is None
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 9. Todas las celdas NaN -> SIN_DATOS, sin fabricar ningún valor.
# --------------------------------------------------------------------------
def test_9_todas_las_celdas_nan(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES,
        [LON_FAR, LON_NEAR],
        {LON_NEAR: [np.nan] * 4, LON_FAR: [np.nan] * 4},
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fw.WaveStatus.SIN_DATOS
    assert r.significant_wave_height_m is None
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 10. Valor claramente bajo el umbral.
# --------------------------------------------------------------------------
def test_10_bajo_umbral(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR], {LON_NEAR: [0.8, 0.9, 1.0, 0.7]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.significant_wave_height_m == pytest.approx(1.0)
    assert r.status == fw.WaveStatus.BAJO_UMBRAL_REGIONAL
    assert fw.kill_switch(r) is False


# --------------------------------------------------------------------------
# 11. Valor EXACTAMENTE en el umbral: la comparación es >=, luego bloquea.
# --------------------------------------------------------------------------
def test_11_exactamente_en_el_umbral(patch_open_dataset):
    ds = build_dataset(
        NATIVE_TIMES,
        [LON_NEAR],
        {LON_NEAR: [0.9, fw.WAVE_HEIGHT_THRESHOLD_M, 1.1, 0.8]},
    )
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.significant_wave_height_m == pytest.approx(fw.WAVE_HEIGHT_THRESHOLD_M)
    assert r.status == fw.WaveStatus.SOBRE_UMBRAL_REGIONAL, "el umbral es inclusivo (>=)"
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 12. Valor sobre el umbral.
# --------------------------------------------------------------------------
def test_12_sobre_umbral(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR], {LON_NEAR: [1.6, 1.7, 2.1, 1.5]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.significant_wave_height_m == pytest.approx(2.1)
    assert r.status == fw.WaveStatus.SOBRE_UMBRAL_REGIONAL
    assert fw.kill_switch(r) is True


# --------------------------------------------------------------------------
# 13. Hora del máximo en UTC y su conversión a hora local de Pucusana.
# --------------------------------------------------------------------------
def test_13_hora_del_maximo_utc_y_local(patch_open_dataset):
    # el máximo cae en el último instante: 2026-08-15 00:00 UTC = 19:00 local del 14
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR], {LON_NEAR: [1.0, 1.1, 1.2, 1.9]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.max_time_utc == datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    assert r.max_time_local.hour == 19
    assert r.max_time_local.date() == TARGET_DATE, "en hora local sigue siendo el día solicitado"
    assert str(r.max_time_local.tzinfo) == "America/Lima"


# --------------------------------------------------------------------------
# 14. Procedencia completa en una lectura válida.
# --------------------------------------------------------------------------
def test_14_procedencia_en_lectura_valida(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_NEAR], {LON_NEAR: [1.0, 1.1, 1.2, 0.9]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.dataset_id == "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
    assert r.variable == "VHM0"
    assert r.data_scope == fw.DATA_SCOPE
    assert r.scope_warning == fw.DATA_SCOPE_WARNING
    assert "autorización" in r.scope_warning


# --------------------------------------------------------------------------
# 15. Procedencia completa TAMBIÉN en SIN_DATOS.
# --------------------------------------------------------------------------
def test_15_procedencia_en_sin_datos(patch_open_dataset):
    ds = build_dataset(NATIVE_TIMES, [LON_TOO_FAR], {LON_TOO_FAR: [2.0, 2.1, 2.2, 1.9]})
    patch_open_dataset(ds)

    r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fw.WaveStatus.SIN_DATOS
    assert r.dataset_id == fw.DATASET_ID
    assert r.variable == fw.VARIABLE
    assert r.data_scope == fw.DATA_SCOPE
    assert r.scope_warning == fw.DATA_SCOPE_WARNING


# --------------------------------------------------------------------------
# 16. Una excepción de descarga se registra con traza y se convierte en
#     SIN_DATOS, sin propagarse ni fabricar valores.
# --------------------------------------------------------------------------
def test_16_excepcion_registrada_y_convertida_en_sin_datos(patch_open_dataset, caplog):
    patch_open_dataset(error=RuntimeError("fallo simulado de red/credenciales"))

    with caplog.at_level(logging.ERROR, logger=fw.logger.name):
        r = fw.get_wave_status(LAT, LON, TARGET_DATE, 0, 23)

    assert r.status == fw.WaveStatus.SIN_DATOS
    assert r.significant_wave_height_m is None
    assert fw.kill_switch(r) is True
    assert any(rec.levelno == logging.ERROR for rec in caplog.records), "debe registrarse el fallo"
    assert any(rec.exc_info for rec in caplog.records), "debe registrarse con traza (logger.exception)"


# --------------------------------------------------------------------------
# 17. Rango horario inválido: error de USO -> ValueError propagado.
# --------------------------------------------------------------------------
def test_17_rango_horario_invalido_propaga_valueerror():
    with pytest.raises(ValueError):
        fw.get_wave_status(LAT, LON, TARGET_DATE, 10, 5)


# --------------------------------------------------------------------------
# 18. Semántica completa de kill_switch sobre los tres estados.
# --------------------------------------------------------------------------
def test_18_kill_switch_completo():
    def reading(status, valor):
        return fw.WaveReading(
            lat=LAT, lon=LON, date=TARGET_DATE,
            significant_wave_height_m=valor,
            max_time_utc=None, max_time_local=None,
            cell_lat=None, cell_lon=None, distance_km=None,
            dataset_id=fw.DATASET_ID, variable=fw.VARIABLE,
            data_scope=fw.DATA_SCOPE, scope_warning=fw.DATA_SCOPE_WARNING,
            status=status,
        )

    assert fw.kill_switch(reading(fw.WaveStatus.SOBRE_UMBRAL_REGIONAL, 2.0)) is True
    assert fw.kill_switch(reading(fw.WaveStatus.SIN_DATOS, None)) is True
    assert fw.kill_switch(reading(fw.WaveStatus.BAJO_UMBRAL_REGIONAL, 0.9)) is False