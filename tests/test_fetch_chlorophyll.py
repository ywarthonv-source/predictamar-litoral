"""
Suite sintética para ingestion/fetch_chlorophyll.py

Totalmente sintética y determinista: NO consulta Copernicus ni ninguna red.
Sustituye copernicusmarine.open_dataset por un Dataset construido a mano y
registra los kwargs de la llamada.

Clorofila es una lectura ambiental de referencia, no una compuerta de
seguridad ni un fetcher del perfil PT6H: no hay máximo espacial, no hay
cobertura temporal por ventana y no hay fallback de instante dentro del día.
Su regla es distinta: instante válido más reciente hasta 72 h de antigüedad,
y celda válida más cercana hasta 6.5 km.

Punto de referencia: Caleta Pucusana (-12.471, -76.790). Distancias
Haversine conocidas:
  lon=-76.75      -> ~5.409 km
  lon=-76.833333  -> ~5.703 km
  lon=-76.900     -> ~12.37 km  (FUERA del límite de 6.5 km)
  lat=-12.5 y lat=-12.442 sobre lon=-76.790 -> equidistantes (~3.22 km)

Fecha local de referencia: 2026-08-12 -> final local 23:59:59 -05:00,
equivalente a 2026-08-13 04:59:59 UTC.

Ejecutar:  python -m pytest tests/test_fetch_chlorophyll.py -v
"""

import inspect
import logging
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_chlorophyll as fc

LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 12)

FIN_UTC = datetime(2026, 8, 13, 4, 59, 59, tzinfo=timezone.utc)

LON_NEAR = -76.75          # ~5.409 km
LON_FAR = -76.833333       # ~5.703 km
LON_TOO_FAR = -76.900      # ~12.37 km, fuera del límite
CELL_LAT = -12.5
LAT_SUR = -12.500
LAT_NORTE = -12.442
LON_OESTE = -76.840   # equidistantes entre si respecto del punto solicitado
LON_ESTE = -76.740

# Instantes nativos P1D (00:00 UTC = 19:00 local del día anterior)
T_HOY = datetime(2026, 8, 13, 0, 0)      # 2026-08-12 19:00 local  -> misma fecha local
T_AYER = datetime(2026, 8, 12, 0, 0)     # 2026-08-11 19:00 local  -> ~29 h
T_ANTEAYER = datetime(2026, 8, 11, 0, 0)  # 2026-08-10 19:00 local -> ~53 h
T_72H_EXACTO = datetime(2026, 8, 10, 4, 59, 59)   # antigüedad exactamente 72.0 h
T_72H_EXCEDIDO = datetime(2026, 8, 10, 4, 59, 58)  # 72.0003 h
T_FUTURO = datetime(2026, 8, 14, 0, 0)   # posterior al final local


def build_dataset(times, lons, values, lats=(CELL_LAT,)):
    """
    values: dict {(lat, lon): [v_t0, ...]} o {lon: [...]} si hay una sola lat.
    np.nan para celda sin dato. Dims: (time, latitude, longitude).
    """
    data = np.empty((len(times), len(lats), len(lons)))
    for i_lat, la in enumerate(lats):
        for j, lo in enumerate(lons):
            col = values[(la, lo)] if (la, lo) in values else values[lo]
            for i in range(len(times)):
                data[i, i_lat, j] = col[i]
    return xr.Dataset(
        {fc.VARIABLE: (("time", "latitude", "longitude"), data)},
        coords={"time": list(times), "latitude": list(lats), "longitude": list(lons)},
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
        monkeypatch.setattr(fc.copernicusmarine, "open_dataset", fake_open_dataset)
        return calls

    return _install


# --------------------------------------------------------------------------
# 1. Fecha local convertida a UTC, ventana retrospectiva y forma de la consulta.
# --------------------------------------------------------------------------
def test_1_ventana_retrospectiva_y_parametros_de_consulta(patch_open_dataset):
    ds = build_dataset([T_HOY], [LON_NEAR], {LON_NEAR: [0.9]})
    calls = patch_open_dataset(ds)

    fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert len(calls) == 1
    kw = calls[0]
    assert kw["dataset_id"] == fc.DATASET_ID
    assert kw["variables"] == [fc.VARIABLE]
    assert kw["minimum_longitude"] == pytest.approx(LON - 0.05)
    assert kw["maximum_longitude"] == pytest.approx(LON + 0.05)
    assert kw["minimum_latitude"] == pytest.approx(LAT - 0.05)
    assert kw["maximum_latitude"] == pytest.approx(LAT + 0.05)
    assert kw["end_datetime"] == FIN_UTC, "la ventana termina en el final del día local"
    esperado_inicio = FIN_UTC - timedelta(
        hours=fc.MAX_TEMPORAL_AGE_HOURS + fc.QUERY_MARGIN_HOURS
    )
    assert kw["start_datetime"] == esperado_inicio, "ventana retrospectiva insuficiente"
    assert "coordinates_selection_method" not in kw, "no debe fijarse el método de selección"
    assert fc.VARIABLE == "CHL"
    assert fc.UNITS == "milligram m-3"


# --------------------------------------------------------------------------
# 2. Un timestamp de 00:00 UTC corresponde a las 19:00 del día local anterior.
# --------------------------------------------------------------------------
def test_2_timestamp_00utc_es_19h_local_del_dia_anterior(patch_open_dataset):
    ds = build_dataset([T_HOY], [LON_NEAR], {LON_NEAR: [1.1]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.time_utc == datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)
    assert r.time_local.hour == 19
    assert r.time_local.date() == TARGET_DATE, "00:00 UTC del 13 es el 12 local"
    assert str(r.time_local.tzinfo) == "America/Lima"


# --------------------------------------------------------------------------
# 3. Observación de la misma fecha local -> VALIDA_EN_FECHA_LOCAL.
# --------------------------------------------------------------------------
def test_3_misma_fecha_local(patch_open_dataset):
    ds = build_dataset([T_HOY], [LON_NEAR], {LON_NEAR: [0.75]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.VALIDA_EN_FECHA_LOCAL
    assert r.inside_requested_local_date is True
    assert r.value_mg_m3 == pytest.approx(0.75)
    assert r.temporal_age_hours == pytest.approx(4.99972, abs=0.001)


# --------------------------------------------------------------------------
# 4. Observación anterior dentro de las 72 h -> VALIDA_RECIENTE.
# --------------------------------------------------------------------------
def test_4_anterior_dentro_de_72h(patch_open_dataset):
    ds = build_dataset([T_ANTEAYER], [LON_NEAR], {LON_NEAR: [0.6]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.VALIDA_RECIENTE
    assert r.inside_requested_local_date is False
    assert r.time_local.date() == date(2026, 8, 10)
    assert 52.0 < r.temporal_age_hours < 54.0


# --------------------------------------------------------------------------
# 5. Antigüedad EXACTAMENTE 72 h: aceptada (límite inclusivo).
# --------------------------------------------------------------------------
def test_5_antiguedad_exacta_72h_aceptada(patch_open_dataset):
    ds = build_dataset([T_72H_EXACTO], [LON_NEAR], {LON_NEAR: [0.42]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.VALIDA_RECIENTE
    assert r.temporal_age_hours == pytest.approx(fc.MAX_TEMPORAL_AGE_HOURS)
    assert r.value_mg_m3 == pytest.approx(0.42)


# --------------------------------------------------------------------------
# 6. Antigüedad mayor de 72 h: rechazada.
# --------------------------------------------------------------------------
def test_6_antiguedad_superior_a_72h_rechazada(patch_open_dataset):
    ds = build_dataset([T_72H_EXCEDIDO], [LON_NEAR], {LON_NEAR: [0.42]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.SIN_DATOS
    assert r.value_mg_m3 is None
    assert r.temporal_age_hours is None


# --------------------------------------------------------------------------
# 7. Observación posterior al final local: nunca se usa.
# --------------------------------------------------------------------------
def test_7_observacion_futura_rechazada(patch_open_dataset):
    ds = build_dataset([T_FUTURO], [LON_NEAR], {LON_NEAR: [9.9]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.SIN_DATOS
    assert r.value_mg_m3 is None


# --------------------------------------------------------------------------
# 8. Con varios instantes se prefiere el más reciente CON DATO VÁLIDO.
# --------------------------------------------------------------------------
def test_8_prefiere_el_instante_valido_mas_reciente(patch_open_dataset):
    # El instante MAS NUEVO (T_HOY) esta completamente en NaN: la regla no es
    # "el ultimo timestamp" sino "el ultimo timestamp CON celda valida
    # admisible". Debe elegirse T_AYER, no T_HOY ni T_ANTEAYER.
    ds = build_dataset(
        [T_ANTEAYER, T_AYER, T_HOY],
        [LON_NEAR],
        {LON_NEAR: [0.30, 0.55, np.nan]},
    )
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.value_mg_m3 == pytest.approx(0.55), "debe saltar el instante sin dato, no devolver NaN"
    assert r.time_utc == datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
    assert r.time_local.date() == date(2026, 8, 11)
    assert r.status == fc.ChlorophyllStatus.VALIDA_RECIENTE
    assert r.inside_requested_local_date is False
    assert 28.0 < r.temporal_age_hours < 30.0


# --------------------------------------------------------------------------
# 9. Celda válida MÁS CERCANA (no máximo, no promedio).
# --------------------------------------------------------------------------
def test_9_celda_valida_mas_cercana(patch_open_dataset):
    ds = build_dataset(
        [T_HOY],
        [LON_FAR, LON_NEAR],
        {LON_NEAR: [0.40], LON_FAR: [7.90]},  # la lejana tiene un valor mucho mayor
    )
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.cell_lon == pytest.approx(LON_NEAR), "debe ganar la más cercana, no la de mayor valor"
    assert r.value_mg_m3 == pytest.approx(0.40)
    assert r.distance_km == pytest.approx(5.409, abs=0.01)


# --------------------------------------------------------------------------
# 10. La celda más cercana es NaN: se elige la siguiente válida.
# --------------------------------------------------------------------------
def test_10_celda_mas_cercana_nan(patch_open_dataset):
    ds = build_dataset(
        [T_HOY],
        [LON_FAR, LON_NEAR],
        {LON_NEAR: [np.nan], LON_FAR: [0.63]},
    )
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.cell_lon == pytest.approx(LON_FAR)
    assert r.value_mg_m3 == pytest.approx(0.63)
    assert r.distance_km == pytest.approx(5.703, abs=0.01)


# --------------------------------------------------------------------------
# 11. Única celda válida fuera de 6.5 km -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_11_celda_fuera_del_limite_de_distancia(patch_open_dataset):
    ds = build_dataset([T_HOY], [LON_TOO_FAR], {LON_TOO_FAR: [1.5]})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.SIN_DATOS
    assert r.cell_lat is None and r.cell_lon is None and r.distance_km is None


# --------------------------------------------------------------------------
# 12. Desempate espacial determinista: por latitud y, después, por longitud.
#
#     Las longitudes simetricas no producen un empate EXACTO en coma flotante
#     (difieren ~1e-12 km), asi que el orden real quedaria decidido por esa
#     diferencia minuscula y no por el criterio que queremos probar. Para
#     forzar el empate exacto se sustituye en memoria _haversine_km por una
#     funcion constante admisible; las comprobaciones geometricas previas se
#     hacen con la funcion real.
# --------------------------------------------------------------------------
def test_12_desempate_por_latitud_y_longitud(patch_open_dataset, monkeypatch):
    # Comprobacion geometrica con la funcion REAL: las parejas son simetricas.
    assert fc._haversine_km(LAT, LON, LAT_SUR, LON) == pytest.approx(
        fc._haversine_km(LAT, LON, LAT_NORTE, LON), abs=1e-9
    ), "las dos latitudes deben ser simetricas respecto al punto"
    assert fc._haversine_km(LAT, LON, LAT, LON_OESTE) == pytest.approx(
        fc._haversine_km(LAT, LON, LAT, LON_ESTE), abs=1e-9
    ), "las dos longitudes deben ser simetricas respecto al punto"

    # Empate EXACTO forzado: toda celda queda a la misma distancia admisible.
    monkeypatch.setattr(fc, "_haversine_km", lambda a, b, c, d: 1.0)

    # Caso A: dos latitudes empatadas -> gana la MENOR latitud.
    ds_a = build_dataset(
        [T_HOY],
        [LON],
        {(LAT_SUR, LON): [0.21], (LAT_NORTE, LON): [0.99]},
        lats=(LAT_NORTE, LAT_SUR),  # orden invertido a proposito
    )
    patch_open_dataset(ds_a)
    ra = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert ra.distance_km == pytest.approx(1.0), "el empate exacto debe estar activo"
    assert ra.cell_lat == pytest.approx(LAT_SUR), "empate exacto -> menor latitud"
    assert ra.value_mg_m3 == pytest.approx(0.21)

    # Caso B: misma latitud, dos longitudes empatadas -> gana la MENOR longitud.
    ds_b = build_dataset(
        [T_HOY],
        [LON_ESTE, LON_OESTE],  # orden invertido a proposito
        {LON_OESTE: [0.11], LON_ESTE: [0.99]},
        lats=(LAT,),
    )
    patch_open_dataset(ds_b)
    rb = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert rb.distance_km == pytest.approx(1.0), "el empate exacto debe estar activo"
    assert rb.cell_lat == pytest.approx(LAT)
    assert rb.cell_lon == pytest.approx(LON_OESTE), "empate exacto e igual latitud -> menor longitud"
    assert rb.value_mg_m3 == pytest.approx(0.11)


# --------------------------------------------------------------------------
# 13. Recuadro mixto: NaN terrestres y celdas marinas válidas.
# --------------------------------------------------------------------------
def test_13_recuadro_con_nan_terrestres(patch_open_dataset):
    ds = build_dataset(
        [T_HOY],
        [LON_FAR, LON_NEAR],
        {
            (LAT_SUR, LON_FAR): [0.52],
            (LAT_SUR, LON_NEAR): [np.nan],
            (LAT_NORTE, LON_FAR): [np.nan],
            (LAT_NORTE, LON_NEAR): [np.nan],
        },
        lats=(LAT_SUR, LAT_NORTE),
    )
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.VALIDA_EN_FECHA_LOCAL
    assert (r.cell_lat, r.cell_lon) == (pytest.approx(LAT_SUR), pytest.approx(LON_FAR))
    assert r.value_mg_m3 == pytest.approx(0.52)


# --------------------------------------------------------------------------
# 14. Sin timestamps -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_14_sin_timestamps(patch_open_dataset):
    ds = build_dataset([], [LON_NEAR], {LON_NEAR: []})
    patch_open_dataset(ds)

    r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.SIN_DATOS
    assert r.time_utc is None and r.time_local is None


# --------------------------------------------------------------------------
# 15. Excepción de open_dataset: registrada con traza y convertida en SIN_DATOS.
# --------------------------------------------------------------------------
def test_15_excepcion_registrada_y_sin_datos(patch_open_dataset, caplog):
    patch_open_dataset(error=RuntimeError("fallo simulado de red/credenciales"))

    with caplog.at_level(logging.ERROR, logger=fc.logger.name):
        r = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert r.status == fc.ChlorophyllStatus.SIN_DATOS
    assert r.value_mg_m3 is None
    assert any(rec.levelno == logging.ERROR for rec in caplog.records), "debe registrarse el fallo"
    assert any(rec.exc_info for rec in caplog.records), "debe registrarse con traza (logger.exception)"


# --------------------------------------------------------------------------
# 16. Argumentos inválidos: error de USO -> ValueError propagado.
# --------------------------------------------------------------------------
def test_16_argumentos_invalidos_propagan_valueerror():
    with pytest.raises(ValueError):
        fc.fetch_chlorophyll(100.0, LON, TARGET_DATE)
    with pytest.raises(ValueError):
        fc.fetch_chlorophyll(LAT, 500.0, TARGET_DATE)
    with pytest.raises(ValueError):
        fc.fetch_chlorophyll(LAT, LON, "2026-08-12")


# --------------------------------------------------------------------------
# 17. Procedencia completa en lectura válida Y en SIN_DATOS.
# --------------------------------------------------------------------------
def test_17_procedencia_en_ambos_estados(patch_open_dataset, monkeypatch):
    ds_ok = build_dataset([T_HOY], [LON_NEAR], {LON_NEAR: [0.5]})
    patch_open_dataset(ds_ok)
    valida = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    ds_vacio = build_dataset([], [LON_NEAR], {LON_NEAR: []})
    monkeypatch.setattr(fc.copernicusmarine, "open_dataset", lambda **kw: ds_vacio)
    sin_datos = fc.fetch_chlorophyll(LAT, LON, TARGET_DATE)

    assert valida.status == fc.ChlorophyllStatus.VALIDA_EN_FECHA_LOCAL
    assert sin_datos.status == fc.ChlorophyllStatus.SIN_DATOS
    for r in (valida, sin_datos):
        assert r.dataset_id == "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"
        assert r.variable == "CHL"
        assert r.units == "milligram m-3"
        assert r.data_scope == fc.DATA_SCOPE
        assert r.scope_warning == fc.DATA_SCOPE_WARNING
        assert "no es una medición puntual" in r.scope_warning.lower()


# --------------------------------------------------------------------------
# 18. Sin residuos de la arquitectura descartada ni de otros módulos.
# --------------------------------------------------------------------------
def test_18_sin_residuos_de_arquitectura_hibrida():
    src = inspect.getsource(fc)
    prohibidos = (
        # --- texto historico de la arquitectura descartada ---
        "arquitectura híbrida",
        "arquitectura hibrida",
        "~300 m",
        "300 m",
        "300m",
        "producto de 300m",
        "respaldo de ~4 km",
        "fuente primaria",
        # --- identificadores y campos de la arquitectura descartada ---
        "NotImplementedError",
        "fetch_chlorophyll_300m",
        "fetch_chlorophyll_4km",
        "get_chlorophyll_area",
        "4km_gapfree",
        "coverage_ratio",
        "coverage_ratio_300m",
        "low_coverage_alert",
        "source_age_days",
        ".interp(",
        "interp_like",
        "fillna",
        "ffill",
        "bfill",
        "MAX_TEMPORAL_OFFSET_HOURS",
        "SURFACE_SEARCH_MAX_DEPTH_M",
        "value_celsius",
        "value_salinity",
        "significant_wave_height_m",
    )
    hallados = [p for p in prohibidos if p in src]
    assert not hallados, "residuos encontrados en el modulo: %s" % hallados

    # coordinates_selection_method y kill_switch se comprueban de forma
    # ESTRUCTURAL, no textual: el modulo los nombra en comentarios que
    # explican por que NO se usan, y prohibir el texto castigaria la
    # documentacion correcta. Lo que importa es que no se envien ni existan.
    import ast
    llamadas = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)]
    kwargs_open = [kw.arg for c in llamadas for kw in c.keywords
                   if isinstance(c.func, ast.Attribute) and c.func.attr == "open_dataset"]
    assert "coordinates_selection_method" not in kwargs_open, "no debe enviarse a open_dataset"

    campos = [f.name for f in fields(fc.ChlorophyllReading)]
    assert "value_mg_m3" in campos
    assert "source" not in campos, "el campo 'source' del esquema hibrido debe desaparecer"
    assert not hasattr(fc, "get_chlorophyll")
    assert not hasattr(fc, "kill_switch")

    estados = [(m.name, m.value) for m in fc.ChlorophyllStatus]
    assert estados == [
        ("VALIDA_EN_FECHA_LOCAL", "valida_en_fecha_local"),
        ("VALIDA_RECIENTE", "valida_reciente"),
        ("SIN_DATOS", "sin_datos"),
    ]
    assert fc.MAX_VALID_CELL_DISTANCE_KM == 6.5
    assert fc.MAX_TEMPORAL_AGE_HOURS == 72.0