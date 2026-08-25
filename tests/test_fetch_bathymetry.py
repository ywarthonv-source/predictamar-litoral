"""
Suite sintética para ingestion/fetch_bathymetry.py

Totalmente sintética y determinista: NO consulta GEBCO, CEDA ni ninguna red.
Sustituye la capa de proveedor `open_gebco_subsets` -- que es la única función
del módulo que toca la red -- por recortes construidos a mano.

Batimetría es una variable ESTÁTICA de soporte estructural: no recibe fecha ni
ventana temporal, no participa en el scoring y no afirma capacidad predictiva.
Por eso aquí no hay pruebas de conversión horaria, cobertura temporal ni
fallback de instante: no aplican, y copiarlas de los fetchers dinámicos sería
un residuo.

Grilla GEBCO_2026: 15 segundos de arco = 1/240 grado. En la latitud de
Pucusana (-12.471) eso equivale a ~452.4 m en longitud y ~463.3 m en latitud.

Ejecutar:  python -m pytest tests/test_fetch_bathymetry.py -v
"""

import dataclasses
import inspect
import logging

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_bathymetry as fb

LAT = -12.471
LON = -76.790
C = fb.CELL_SIZE_DEG

# Recuadro nativo de 5x5 celdas centrado en el punto solicitado.
LATS = np.array([LAT + k * C for k in (-2, -1, 0, 1, 2)])
LONS = np.array([LON + k * C for k in (-2, -1, 0, 1, 2)])
CENTRO = 2  # indice de la celda coincidente con el punto

# Metadatos TID consistentes: 7 codigos y 7 significados.
ATTRS_OK = {
    "flag_values": [0, 11, 15, 40, 44, 70, 127],
    "flag_meanings": "land singlebeam multibeam predicted interpolated mixed unknown",
}

# Metadatos TID REALES de GEBCO_2026: 21 valores frente a 19 significados.
ATTRS_REAL = {
    "flag_values": [0, 10, 11, 12, 13, 14, 15, 16, 17,
                    40, 41, 42, 43, 44, 45, 46, 47, 48,
                    70, 71, 72],
    "flag_meanings": " ".join("significado_%d" % k for k in range(19)),
}


def arr(valores, dims=("lat", "lon"), lats=LATS, lons=LONS, attrs=None):
    """DataArray sintetico con las coordenadas de la grilla de prueba."""
    return xr.DataArray(
        np.asarray(valores),
        dims=dims,
        coords={"lat": np.asarray(lats), "lon": np.asarray(lons)},
        attrs=dict(attrs or {}),
    )


def mar(valor=-60.0, forma=(5, 5)):
    """Recuadro enteramente oceanico."""
    return np.full(forma, float(valor))


def tid_uniforme(codigo=11, forma=(5, 5)):
    return np.full(forma, int(codigo), dtype=np.int8)


@pytest.fixture
def proveedor(monkeypatch):
    """
    Sustituye la capa de proveedor y registra las llamadas recibidas.
    Devuelve la lista de llamadas para poder afirmar que NO se invoco.
    """
    llamadas = []

    def _instalar(elev=None, tid=None, error=None):
        def falso(lat, lon):
            llamadas.append((lat, lon))
            if error is not None:
                raise error
            return elev, tid
        monkeypatch.setattr(fb, "open_gebco_subsets", falso)
        return llamadas

    _instalar.llamadas = llamadas
    return _instalar


# --------------------------------------------------------------------------
# 1. Lectura valida: profundidad positiva derivada de elevacion negativa.
# --------------------------------------------------------------------------
def test_1_lectura_valida_profundidad_positiva(proveedor):
    proveedor(arr(mar(-75.0)), arr(tid_uniforme(11), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.VALIDA
    assert r.elevation_m == pytest.approx(-75.0), "la elevacion nativa se conserva con su signo"
    assert r.depth_m == pytest.approx(75.0), "la profundidad es positiva"
    assert r.depth_m == pytest.approx(-r.elevation_m)
    assert r.cell_lat == pytest.approx(LATS[CENTRO])
    assert r.cell_lon == pytest.approx(LONS[CENTRO])
    assert r.distance_m == pytest.approx(0.0, abs=1e-6)
    assert r.no_data_reason is None


# --------------------------------------------------------------------------
# 2. Tierra excluida: elevacion positiva nunca produce profundidad.
# --------------------------------------------------------------------------
def test_2_tierra_excluida(proveedor):
    proveedor(arr(np.full((5, 5), 120.0)), arr(tid_uniforme(0), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS
    assert r.elevation_m is None and r.depth_m is None
    assert "sin_celda_oceanica" in r.no_data_reason


# --------------------------------------------------------------------------
# 3. Elevacion CERO no es oceano: no se convierte en profundidad cero.
# --------------------------------------------------------------------------
def test_3_elevacion_cero_no_es_oceano(proveedor):
    proveedor(arr(np.zeros((5, 5))), arr(tid_uniforme(0), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS, "cero es costa o tierra, no un fondeadero de 0 m"
    assert r.depth_m is None
    assert fb._is_ocean(0.0) is False
    assert fb._is_ocean(-0.1) is True
    assert fb._is_ocean(float("nan")) is False


# --------------------------------------------------------------------------
# 4. Seleccion determinista de la celda oceanica mas cercana.
# --------------------------------------------------------------------------
def test_4_celda_oceanica_mas_cercana(proveedor):
    # Solo la celda del ESTE es mar; el resto es tierra.
    E = np.full((5, 5), 30.0)
    E[CENTRO, CENTRO + 1] = -40.0
    proveedor(arr(E), arr(tid_uniforme(11), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.VALIDA
    assert r.cell_lon == pytest.approx(LONS[CENTRO + 1])
    assert r.cell_lat == pytest.approx(LATS[CENTRO])
    assert r.distance_m == pytest.approx(452.4, abs=1.0), "una celda de longitud en esta latitud"
    assert r.distance_m < 1000.0, "el vecindario nativo acota la distancia muy por debajo de 1 km"


# --------------------------------------------------------------------------
# 5. Desempate determinista: menor latitud y despues menor longitud.
# --------------------------------------------------------------------------
def test_5_desempate_determinista(proveedor, monkeypatch):
    # Empate EXACTO forzado: toda celda queda a la misma distancia.
    monkeypatch.setattr(fb, "_haversine_m", lambda a, b, c, d: 1.0)
    E = np.full((5, 5), -50.0)
    E[CENTRO, CENTRO] = 20.0  # la celda coincidente es tierra
    proveedor(arr(E), arr(tid_uniforme(11), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.distance_m == pytest.approx(1.0), "el empate exacto debe estar activo"
    assert r.cell_lat == pytest.approx(LATS[CENTRO - 1]), "empate -> menor latitud"
    assert r.cell_lon == pytest.approx(LONS[CENTRO - 1]), "y despues menor longitud"


# --------------------------------------------------------------------------
# 6. Pendiente por diferencias centradas con los cuatro vecinos cardinales.
# --------------------------------------------------------------------------
def test_6_pendiente_cuatro_vecinos(proveedor):
    # Gradiente puro norte-sur: 10 m mas profundo por cada celda hacia el norte.
    E = np.array([[-50.0 - 10.0 * i] * 5 for i in range(5)])
    proveedor(arr(E), arr(tid_uniforme(11), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    dist_y = fb._haversine_m(LATS[CENTRO - 1], LONS[CENTRO], LATS[CENTRO + 1], LONS[CENTRO])
    esperado = np.degrees(np.arctan(abs(-20.0 / dist_y)))

    assert r.slope_deg == pytest.approx(esperado, rel=1e-9)
    assert r.slope_unavailable_reason is None
    assert dist_y == pytest.approx(926.6, abs=2.0), "dos celdas de latitud, distancia metrica real"
    assert r.units_slope == "degrees"


# --------------------------------------------------------------------------
# 7. Pendiente None cuando un vecino cardinal no es oceanico.
# --------------------------------------------------------------------------
def test_7_pendiente_none_vecino_no_oceanico(proveedor):
    E = np.full((5, 5), -40.0)
    E[CENTRO, CENTRO + 1] = 5.0  # el vecino ESTE es tierra
    proveedor(arr(E), arr(tid_uniforme(11), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.VALIDA, "la profundidad sigue siendo valida"
    assert r.slope_deg is None, "nunca una diferencia lateral silenciosa"
    assert "este" in r.slope_unavailable_reason
    assert "vecinos_no_oceanicos" in r.slope_unavailable_reason


# --------------------------------------------------------------------------
# 8. Pendiente None cuando el vecindario no cabe en el recuadro.
# --------------------------------------------------------------------------
def test_8_pendiente_none_vecindario_incompleto(proveedor):
    # Recuadro de una sola celda: no hay vecinos cardinales posibles.
    una_lat, una_lon = np.array([LAT]), np.array([LON])
    proveedor(
        arr(np.full((1, 1), -30.0), lats=una_lat, lons=una_lon),
        arr(np.full((1, 1), 11, dtype=np.int8), lats=una_lat, lons=una_lon, attrs=ATTRS_OK),
    )

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.VALIDA
    assert r.depth_m == pytest.approx(30.0)
    assert r.slope_deg is None
    assert r.slope_unavailable_reason == "vecindario_incompleto_en_el_recuadro"


# --------------------------------------------------------------------------
# 9. TID con metadatos consistentes: significado leido del propio archivo.
# --------------------------------------------------------------------------
def test_9_tid_metadatos_consistentes(proveedor):
    proveedor(arr(mar()), arr(tid_uniforme(44), attrs=ATTRS_OK))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.tid_code == 44
    assert r.tid_meaning == "interpolated"
    assert r.tid_meaning_source == "flag_values/flag_meanings"
    assert r.tid_group == fb.TidGroup.INDIRECTA


# --------------------------------------------------------------------------
# 10. TID REAL de GEBCO_2026: 21 valores frente a 19 significados.
#     No se inventa correspondencia; el codigo y el grupo se conservan.
# --------------------------------------------------------------------------
def test_10_tid_inconsistente_21_vs_19(proveedor):
    proveedor(arr(mar()), arr(tid_uniforme(40), attrs=ATTRS_REAL))

    r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.VALIDA
    assert r.tid_code == 40, "el codigo nativo se conserva intacto"
    assert r.tid_group == fb.TidGroup.INDIRECTA, "el grupo se deriva del rango, no de la tabla"
    assert r.tid_meaning is None, "sin correspondencia fiable no se inventa significado"
    assert r.tid_meaning_source == (
        "flag_values/flag_meanings_inconsistentes:21_valores_vs_19_significados"
    ), "la lectura debe declarar POR QUE no hay significado"

    tabla, motivo = fb._tid_lookup(arr(tid_uniforme(40), attrs=ATTRS_REAL))
    assert tabla == {}, "ninguna correspondencia parcial, ni truncada ni rellenada"
    assert str(len(ATTRS_REAL["flag_values"])) in motivo
    assert str(len(ATTRS_REAL["flag_meanings"].split())) in motivo


# --------------------------------------------------------------------------
# 11. Ramas restantes de _tid_lookup: ausentes y no parseables.
# --------------------------------------------------------------------------
def test_11_tid_lookup_ausente_y_no_parseable(proveedor):
    tabla, motivo = fb._tid_lookup(arr(tid_uniforme(11), attrs={}))
    assert (tabla, motivo) == ({}, "atributos_tid_ausentes")

    tabla, motivo = fb._tid_lookup(
        arr(tid_uniforme(11), attrs={"flag_values": "no-numerico", "flag_meanings": "a b"})
    )
    assert (tabla, motivo) == ({}, "atributos_tid_no_parseables")

    proveedor(arr(mar()), arr(tid_uniforme(11), attrs={}))
    r = fb.fetch_bathymetry(LAT, LON)
    assert r.tid_code == 11 and r.tid_meaning is None
    assert r.tid_meaning_source == "atributos_tid_ausentes"
    assert r.tid_group == fb.TidGroup.DIRECTA


# --------------------------------------------------------------------------
# 12. TID de relleno (127) y codigos fuera de los rangos declarados.
# --------------------------------------------------------------------------
def test_12_tid_relleno_y_fuera_de_rango(proveedor):
    proveedor(arr(mar()), arr(tid_uniforme(127), attrs=ATTRS_OK))
    r = fb.fetch_bathymetry(LAT, LON)
    assert r.tid_code == 127
    assert r.tid_meaning is None, "el relleno no describe una procedencia"
    assert r.tid_group == fb.TidGroup.NO_CLASIFICADO

    assert fb._tid_group(0) == fb.TidGroup.NO_CLASIFICADO, "tierra no es una procedencia de sondaje"
    assert fb._tid_group(9) == fb.TidGroup.NO_CLASIFICADO
    assert fb._tid_group(10) == fb.TidGroup.DIRECTA
    assert fb._tid_group(17) == fb.TidGroup.DIRECTA
    assert fb._tid_group(40) == fb.TidGroup.INDIRECTA
    assert fb._tid_group(48) == fb.TidGroup.INDIRECTA
    assert fb._tid_group(70) == fb.TidGroup.MIXTA_DESCONOCIDA
    assert fb._tid_group(72) == fb.TidGroup.MIXTA_DESCONOCIDA
    assert fb._tid_group(99) == fb.TidGroup.NO_CLASIFICADO
    assert fb._tid_group(None) is None


# --------------------------------------------------------------------------
# 13. TID TRANSPUESTO: mismos ejes, dimensiones invertidas -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_13_dimensiones_transpuestas(proveedor, caplog):
    tid_t = xr.DataArray(
        tid_uniforme(11).T,
        dims=("lon", "lat"),
        coords={"lat": LATS, "lon": LONS},
        attrs=ATTRS_OK,
    )
    elev = arr(mar())
    # El agujero que cierra esta comprobacion: los EJES son identicos.
    assert np.array_equal(np.asarray(elev.lat.values), np.asarray(tid_t.lat.values))
    assert np.array_equal(np.asarray(elev.lon.values), np.asarray(tid_t.lon.values))

    proveedor(elev, tid_t)
    with caplog.at_level(logging.ERROR, logger=fb.logger.name):
        r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS
    assert any(rec.exc_info for rec in caplog.records), "debe registrarse con traza"


# --------------------------------------------------------------------------
# 14. Formas distintas entre elevacion y TID -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_14_formas_distintas(proveedor, caplog):
    proveedor(
        arr(mar()),
        arr(tid_uniforme(11, (4, 5)), lats=LATS[:4], attrs=ATTRS_OK),
    )
    with caplog.at_level(logging.ERROR, logger=fb.logger.name):
        r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS
    assert any(rec.exc_info for rec in caplog.records)


# --------------------------------------------------------------------------
# 15. Coordenadas desalineadas con la misma forma -> SIN_DATOS.
# --------------------------------------------------------------------------
def test_15_coordenadas_desalineadas(proveedor, caplog):
    proveedor(
        arr(mar()),
        arr(tid_uniforme(11), lons=LONS + 0.001, attrs=ATTRS_OK),
    )
    with caplog.at_level(logging.ERROR, logger=fb.logger.name):
        r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS
    assert any(rec.exc_info for rec in caplog.records)


# --------------------------------------------------------------------------
# 16. Fallo del proveedor: registrado con traza y convertido en SIN_DATOS.
# --------------------------------------------------------------------------
def test_16_fallo_del_proveedor(proveedor, caplog):
    proveedor(error=RuntimeError("fallo simulado de OPeNDAP"))

    with caplog.at_level(logging.ERROR, logger=fb.logger.name):
        r = fb.fetch_bathymetry(LAT, LON)

    assert r.status == fb.BathymetryStatus.SIN_DATOS
    assert r.no_data_reason == "fallo_de_proveedor_o_datos"
    assert any(rec.exc_info for rec in caplog.records)
    texto = " ".join(rec.getMessage() for rec in caplog.records)
    assert "password" not in texto.lower() and "token" not in texto.lower()


# --------------------------------------------------------------------------
# 17. ValueError ANTES de llamar al proveedor.
# --------------------------------------------------------------------------
def test_17_valueerror_antes_del_proveedor(proveedor):
    llamadas = proveedor(arr(mar()), arr(tid_uniforme(11), attrs=ATTRS_OK))

    for lat, lon in ((100.0, LON), (LAT, 500.0), (float("nan"), LON),
                     (LAT, float("inf")), ("-12.471", LON), (LAT, None), (True, LON)):
        with pytest.raises(ValueError):
            fb.fetch_bathymetry(lat, lon)

    assert llamadas == [], "la validacion debe ocurrir antes de tocar la red"


# --------------------------------------------------------------------------
# 18. Dataclass inmutable y procedencia tecnica completa.
# --------------------------------------------------------------------------
def test_18_inmutable_y_procedencia(proveedor):
    proveedor(arr(mar()), arr(tid_uniforme(11), attrs=ATTRS_OK))
    valida = fb.fetch_bathymetry(LAT, LON)

    proveedor(arr(np.full((5, 5), 50.0)), arr(tid_uniforme(0), attrs=ATTRS_OK))
    sin_datos = fb.fetch_bathymetry(LAT, LON)

    assert dataclasses.is_dataclass(fb.BathymetryReading)
    with pytest.raises(dataclasses.FrozenInstanceError):
        valida.elevation_m = 1.0

    for r in (valida, sin_datos):
        assert r.product == "GEBCO_2026 Grid"
        assert r.product_doi == "10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa"
        assert r.url_elevation.endswith("GEBCO_2026.nc")
        assert r.url_tid.endswith("gebco_2026_tid.nc")
        assert r.variable_elevation == "elevation" and r.variable_tid == "tid"
        assert r.units_elevation == "m" and r.units_depth == "m"
        assert "15 arc-seconds" in r.nominal_resolution
        assert r.data_scope == fb.DATA_SCOPE
        assert r.scope_warning == fb.DATA_SCOPE_WARNING
        assert r.neighbor_search_cells == fb.NEIGHBOR_SEARCH_CELLS

    aviso = valida.scope_warning.lower()
    for exigido in ("no es una medici", "navegaci", "resoluci", "datum",
                    "procedencia", "derivada", "scoring"):
        assert exigido in aviso, "falta declarar %r en scope_warning" % exigido


# --------------------------------------------------------------------------
# 19. Curvatura declarada como NO implementada, nunca como cero.
# --------------------------------------------------------------------------
def test_19_curvatura_no_implementada(proveedor):
    proveedor(arr(mar()), arr(tid_uniforme(11), attrs=ATTRS_OK))
    r = fb.fetch_bathymetry(LAT, LON)

    assert r.curvature_status == "no_implementada"
    assert "no se devuelve cero" in r.curvature_note.lower()
    campos = {f.name for f in dataclasses.fields(fb.BathymetryReading)}
    assert not any(c.startswith("curvature_") and c.endswith(("_m", "_deg", "_value"))
                   for c in campos), "no debe existir un campo numerico de curvatura"


# --------------------------------------------------------------------------
# 20. Variable ESTATICA: sin fecha, sin ventana temporal y fuera del scoring.
# --------------------------------------------------------------------------
def test_20_estatica_sin_tiempo_ni_scoring():
    params = list(inspect.signature(fb.fetch_bathymetry).parameters)
    assert params == ["lat", "lon"], "la API publica no recibe tiempo"

    campos = {f.name for f in dataclasses.fields(fb.BathymetryReading)}
    prohibidos = {"date", "target_date", "time_utc", "time_local", "hour_start_local",
                  "hour_end_local", "window_start_utc", "window_end_utc",
                  "temporal_age_hours", "expected_instants", "score", "scoring_status"}
    assert not (campos & prohibidos), "residuos temporales o de scoring: %s" % (campos & prohibidos)

    fuente = inspect.getsource(fb)
    for residuo in ("MAX_TEMPORAL_AGE_HOURS", "EXPECTED_LOCAL_HOURS", "kill_switch",
                    "start_datetime", "end_datetime", "predictively_valid"):
        assert residuo not in fuente, "residuo de otro fetcher: %s" % residuo
    assert "scoring" in fb.DATA_SCOPE_WARNING.lower()


# --------------------------------------------------------------------------
# 21. Los recortes se cargan ANTES de cerrar, y siguen usables tras el cierre.
# --------------------------------------------------------------------------
def test_21_recortes_cargados_antes_de_cerrar(monkeypatch):
    da = pytest.importorskip("dask.array")

    n = 240
    glat = LAT + (np.arange(-n // 2, n // 2) * C)
    glon = LON + (np.arange(-n // 2, n // 2) * C)
    orden = []

    def perezoso(valor, dtype, attrs=None):
        base = da.full((n, n), valor, dtype=dtype, chunks=(10, 10))

        def marcar(bloque):
            orden.append("carga")
            return bloque

        return xr.DataArray(base.map_blocks(marcar, dtype=dtype), dims=("lat", "lon"),
                            coords={"lat": glat, "lon": glon}, attrs=dict(attrs or {}))

    class Handle:
        def __init__(self, nombre, ds):
            self.nombre, self.ds = nombre, ds

        def __enter__(self):
            return self

        def __exit__(self, *a):
            orden.append("cierre:" + self.nombre)
            self.ds.close()
            return False

        def __getitem__(self, k):
            return self.ds[k]

    def falso_open(url, engine=None):
        assert engine == "pydap", "debe solicitarse el motor pydap"
        if "tid" in url:
            return Handle("tid", xr.Dataset({"tid": perezoso(11, np.int8, ATTRS_OK)}))
        return Handle("elev", xr.Dataset({"elevation": perezoso(-60.0, np.float64)}))

    monkeypatch.setattr(fb.xr, "open_dataset", falso_open)

    sub_elev, sub_tid = fb.open_gebco_subsets(LAT, LON)

    cierres = [i for i, e in enumerate(orden) if e.startswith("cierre:")]
    cargas = [i for i, e in enumerate(orden) if e == "carga"]
    assert cargas and cierres, "deben registrarse cargas y cierres"
    assert max(cargas) < min(cierres), "los recortes se cargan ANTES de cerrar"
    assert sorted(orden[i] for i in cierres) == ["cierre:elev", "cierre:tid"], \
        "ambos datasets deben cerrarse"

    assert sub_elev._in_memory and sub_tid._in_memory, "los recortes quedan en memoria"
    assert float(sub_elev.values[0, 0]) == pytest.approx(-60.0), "usable tras el cierre"
    assert int(sub_tid.values[0, 0]) == 11
    assert sub_tid.attrs.get("flag_meanings"), "los atributos flag_* se conservan"


# --------------------------------------------------------------------------
# 22. Nunca se materializa la grilla global.
# --------------------------------------------------------------------------
def test_22_no_materializa_grilla_global(monkeypatch):
    da = pytest.importorskip("dask.array")

    n = 960  # grilla "global" simulada con el espaciado real de 1/240 grado
    glat = LAT + (np.arange(-n // 2, n // 2) * C)
    glon = LON + (np.arange(-n // 2, n // 2) * C)
    celdas = {"n": 0}

    def perezoso(valor, dtype, attrs=None):
        base = da.full((n, n), valor, dtype=dtype, chunks=(10, 10))

        def contar(bloque):
            celdas["n"] += bloque.size
            return bloque

        return xr.DataArray(base.map_blocks(contar, dtype=dtype), dims=("lat", "lon"),
                            coords={"lat": glat, "lon": glon}, attrs=dict(attrs or {}))

    class Handle:
        def __init__(self, ds):
            self.ds = ds

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.ds.close()
            return False

        def __getitem__(self, k):
            return self.ds[k]

    def falso_open(url, engine=None):
        if "tid" in url:
            return Handle(xr.Dataset({"tid": perezoso(11, np.int8, ATTRS_OK)}))
        return Handle(xr.Dataset({"elevation": perezoso(-60.0, np.float64)}))

    monkeypatch.setattr(fb.xr, "open_dataset", falso_open)

    sub_elev, sub_tid = fb.open_gebco_subsets(LAT, LON)

    total = n * n
    assert sub_elev.shape == (5, 5), "el recuadro pedido son ~5x5 celdas nativas"
    assert sub_elev.size == 25 and sub_tid.size == 25
    # El exceso sobre 25 es granularidad de bloque del simulador, no peticion
    # del modulo: lo que importa es que quede muy por debajo de la grilla entera.
    assert celdas["n"] < total * 0.01, (
        "se materializaron %d de %d celdas" % (celdas["n"], total)
    )
    assert fb.REQUEST_HALF_WIDTH_DEG == pytest.approx(2.5 * C)