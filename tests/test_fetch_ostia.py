"""Pruebas sintéticas de ingestion.fetch_ostia; nunca consultan la red."""

# xarray representa deliberadamente estos timestamps sintéticos sin zona para
# reproducir el eje temporal nativo del dataset; el módulo los normaliza a UTC.
# ruff: noqa: DTZ001

import ast
import inspect
import logging
from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_ostia as fo

TARGET_DATE = date(2026, 8, 12)
START_UTC = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 8, 12, 23, 59, 59, tzinfo=timezone.utc)
T_TODAY = datetime(2026, 8, 12, 12, 0)
T_YESTERDAY = datetime(2026, 8, 11, 12, 0)
T_FUTURE = datetime(2026, 8, 13, 12, 0)
T_TWO_DAYS_AGO = datetime(2026, 8, 10, 0, 0)
T_TOO_OLD = datetime(2026, 8, 9, 12, 0)

MIN_LAT, MAX_LAT = -12.60, -12.30
MIN_LON, MAX_LON = -76.95, -76.65


def build_dataset(
    times=(T_TODAY,),
    lats=(-12.50, -12.45),
    lons=(-76.85, -76.80, -76.75),
    sst=None,
    error=None,
    coord_style="long",
    units="kelvin",
):
    shape = (len(times), len(lats), len(lons))
    if sst is None:
        sst = np.full(shape, 293.15)
    if error is None:
        error = np.full(shape, 0.30)
    lat_name, lon_name = (
        ("latitude", "longitude") if coord_style == "long" else ("lat", "lon")
    )
    ds = xr.Dataset(
        {
            fo.VARIABLE_SST: (("time", lat_name, lon_name), np.asarray(sst, dtype=float)),
            fo.VARIABLE_ERROR: (("time", lat_name, lon_name), np.asarray(error, dtype=float)),
        },
        coords={"time": list(times), lat_name: list(lats), lon_name: list(lons)},
    )
    ds[fo.VARIABLE_SST].attrs["units"] = units
    ds[fo.VARIABLE_ERROR].attrs["units"] = "kelvin"
    return ds


@pytest.fixture
def install_dataset(monkeypatch):
    calls = []

    def install(ds=None, error=None):
        def fake_open_dataset(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return ds

        monkeypatch.setattr(fo.copernicusmarine, "open_dataset", fake_open_dataset)
        return calls

    return install


def fetch():
    return fo.fetch_ostia_field(MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, TARGET_DATE)


def test_1_contrato_oficial_y_consulta_explicita(install_dataset):
    calls = install_dataset(build_dataset())
    fetch()
    assert fo.PRODUCT_ID == "SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001"
    assert fo.DATASET_ID == "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
    assert fo.VARIABLE_SST == "analysed_sst"
    assert fo.VARIABLE_ERROR == "analysis_error"
    kw = calls[0]
    assert kw["dataset_id"] == fo.DATASET_ID
    assert kw["variables"] == [fo.VARIABLE_SST, fo.VARIABLE_ERROR]
    assert kw["minimum_latitude"] == MIN_LAT
    assert kw["maximum_latitude"] == MAX_LAT
    assert kw["minimum_longitude"] == MIN_LON
    assert kw["maximum_longitude"] == MAX_LON
    assert kw["end_datetime"] == END_UTC
    assert kw["start_datetime"] == START_UTC
    assert "coordinates_selection_method" not in kw


def test_2_conserva_kelvin_y_convierte_celsius(install_dataset):
    sst = np.array([[[273.15, 293.15], [300.15, np.nan]]])
    err = np.array([[[0.2, 0.3], [0.4, 0.5]]])
    install_dataset(build_dataset(lats=(-12.5, -12.4), lons=(-76.8, -76.7), sst=sst, error=err))
    result = fetch()
    assert result.sst_kelvin == ((273.15, 293.15), (300.15, None))
    assert result.sst_celsius[0][0] == pytest.approx(0.0)
    assert result.sst_celsius[0][1] == pytest.approx(20.0)
    assert result.sst_celsius[1][0] == pytest.approx(27.0)
    assert result.sst_celsius[1][1] is None
    assert result.analysis_error_kelvin[1][1] is None


def test_3_timestamp_y_estado_de_fecha_nominal(install_dataset):
    install_dataset(build_dataset())
    result = fetch()
    assert result.nominal_product_date == TARGET_DATE
    assert result.time_utc == datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
    assert result.time_local == datetime(2026, 8, 12, 7, 0, tzinfo=fo.TZ_PUCUSANA)
    assert result.matches_requested_nominal_date is True
    assert result.status == fo.OstiaStatus.VALIDA_EN_FECHA_NOMINAL
    assert result.nominal_age_days == 0


def test_4_campo_anterior_dentro_del_limite(install_dataset):
    install_dataset(build_dataset(times=(T_YESTERDAY,)))
    result = fetch()
    assert result.status == fo.OstiaStatus.VALIDA_RECIENTE
    assert result.matches_requested_nominal_date is False
    assert result.nominal_product_date == date(2026, 8, 11)
    assert result.nominal_age_days == 1
    assert result.time_local.date() == date(2026, 8, 11)


def test_5_limite_nominal_inclusivo(install_dataset):
    install_dataset(build_dataset(times=(T_TWO_DAYS_AGO,)))
    result = fetch()
    assert result.status == fo.OstiaStatus.VALIDA_RECIENTE
    assert result.nominal_age_days == fo.MAX_NOMINAL_AGE_DAYS


def test_6_campo_demasiado_antiguo_es_sin_datos(install_dataset):
    install_dataset(build_dataset(times=(T_TOO_OLD,)))
    result = fetch()
    assert result.status == fo.OstiaStatus.SIN_DATOS
    assert result.sst_kelvin == ()


def test_7_nunca_usa_un_timestamp_futuro(install_dataset):
    install_dataset(build_dataset(times=(T_FUTURE,)))
    assert fetch().status == fo.OstiaStatus.SIN_DATOS


def test_8_salta_el_timestamp_mas_reciente_si_esta_vacio(install_dataset):
    shape = (2, 2, 2)
    sst = np.full(shape, np.nan)
    sst[0, :, :] = 291.15
    err = np.full(shape, 0.2)
    install_dataset(
        build_dataset(
            times=(T_YESTERDAY, T_TODAY),
            lats=(-12.5, -12.4),
            lons=(-76.8, -76.7),
            sst=sst,
            error=err,
        )
    )
    result = fetch()
    assert result.time_utc == datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    assert result.sst_celsius[0][0] == pytest.approx(18.0)


def test_9_faltantes_y_cobertura_permanecen_explicitos(install_dataset):
    sst = np.array([[[293.15, np.nan], [294.15, np.nan]]])
    install_dataset(build_dataset(lats=(-12.5, -12.4), lons=(-76.8, -76.7), sst=sst))
    result = fetch()
    assert result.n_grid_cells == 4
    assert result.n_valid_cells == 2
    assert result.coverage_fraction == pytest.approx(0.5)
    assert result.sst_celsius == ((20.0, None), (21.0, None))


def test_10_error_negativo_o_nan_no_se_convierte_en_cero(install_dataset):
    err = np.array([[[0.2, -1.0], [np.nan, 0.4]]])
    install_dataset(build_dataset(lats=(-12.5, -12.4), lons=(-76.8, -76.7), error=err))
    result = fetch()
    assert result.analysis_error_kelvin == ((0.2, None), (None, 0.4))
    assert result.n_valid_cells == 4, "el error ausente no fabrica ni elimina la SST válida"


def test_11_ordena_ejes_y_reordena_los_valores(install_dataset):
    sst = np.array([[[301.15, 300.15], [291.15, 290.15]]])
    install_dataset(
        build_dataset(
            lats=(-12.4, -12.5),
            lons=(-76.7, -76.8),
            sst=sst,
            error=np.full((1, 2, 2), 0.2),
        )
    )
    result = fetch()
    assert result.latitudes == (-12.5, -12.4)
    assert result.longitudes == (-76.8, -76.7)
    assert result.sst_celsius == ((17.0, 18.0), (27.0, 28.0))


def test_12_acepta_aliases_lat_lon_sin_remuestrear(install_dataset):
    install_dataset(build_dataset(coord_style="short"))
    result = fetch()
    assert result.status == fo.OstiaStatus.VALIDA_EN_FECHA_NOMINAL
    assert len(result.latitudes) == 2 and len(result.longitudes) == 3


def test_13_unidades_inesperadas_fallan_cerrado(install_dataset, caplog):
    install_dataset(build_dataset(units="degree_Celsius"))
    with caplog.at_level(logging.ERROR, logger=fo.logger.name):
        result = fetch()
    assert result.status == fo.OstiaStatus.SIN_DATOS
    assert any(record.exc_info for record in caplog.records)


def test_14_sin_timestamps(install_dataset):
    install_dataset(build_dataset(times=(), sst=np.empty((0, 2, 3)), error=np.empty((0, 2, 3))))
    result = fetch()
    assert result.status == fo.OstiaStatus.SIN_DATOS
    assert result.time_utc is None and result.coverage_fraction is None


def test_15_excepcion_de_fuente_se_registra_y_conserva_procedencia(install_dataset, caplog):
    install_dataset(error=RuntimeError("fallo sintético"))
    with caplog.at_level(logging.ERROR, logger=fo.logger.name):
        result = fetch()
    assert result.status == fo.OstiaStatus.SIN_DATOS
    assert result.dataset_id == fo.DATASET_ID
    assert result.variables == (fo.VARIABLE_SST, fo.VARIABLE_ERROR)
    assert result.data_scope == fo.DATA_SCOPE
    assert any(record.exc_info for record in caplog.records)


def test_16_argumentos_invalidos_se_propagan():
    invalid = (
        (MIN_LAT, MIN_LAT, MIN_LON, MAX_LON, TARGET_DATE),
        (-91.0, MAX_LAT, MIN_LON, MAX_LON, TARGET_DATE),
        (MIN_LAT, MAX_LAT, MAX_LON, MIN_LON, TARGET_DATE),
        (MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, "2026-08-12"),
        (MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, datetime(2026, 8, 12)),
    )
    for args in invalid:
        with pytest.raises(ValueError):
            fo.fetch_ostia_field(*args)


def test_17_procedencia_y_limitacion_en_todos_los_estados(install_dataset, monkeypatch):
    install_dataset(build_dataset())
    valid = fetch()
    empty_ds = build_dataset(times=(), sst=np.empty((0, 2, 3)), error=np.empty((0, 2, 3)))
    monkeypatch.setattr(fo.copernicusmarine, "open_dataset", lambda **kwargs: empty_ds)
    empty = fetch()
    for result in (valid, empty):
        assert result.product_id == fo.PRODUCT_ID
        assert result.dataset_id == fo.DATASET_ID
        assert result.processing_level == "L4"
        assert result.nominal_resolution_deg == 0.05
        assert "no detecta cardúmenes" in result.scope_warning
        assert "espacialmente suavizado" in result.scope_warning
        assert "contexto regional" in result.scope_warning


def test_18_sin_interpolacion_scoring_ni_umbral_pesquero():
    source = inspect.getsource(fo)
    forbidden = (".interp(", "interp_like", "fillna", "ffill", "bfill", "kill_switch", "scoring")
    # "scoring" aparece solo en la explicación de que NO existe. La estructura
    # comprobable es que no haya funciones o campos con ese nombre.
    structural_forbidden = forbidden[:-1]
    assert not [token for token in structural_forbidden if token in source]
    tree = ast.parse(source)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not {"score", "rank", "classify_front"} & names


def test_19_etiqueta_00utc_conserva_fecha_nominal_sin_desplazarla_a_lima(
    install_dataset,
):
    midnight_label = datetime(2026, 8, 12, 0, 0)
    install_dataset(build_dataset(times=(midnight_label,)))
    result = fetch()

    assert result.time_local.date() == date(2026, 8, 11)
    assert result.nominal_product_date == date(2026, 8, 12)
    assert result.matches_requested_nominal_date is True
    assert result.nominal_age_days == 0
    assert result.status == fo.OstiaStatus.VALIDA_EN_FECHA_NOMINAL
