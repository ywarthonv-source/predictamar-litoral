"""Contrato de lectura MUR: máscaras, tiempo, versiones y fallos sin red."""

from datetime import date, datetime, timedelta, timezone
import hashlib

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_mur as mur
from mur_fixtures import AS_OF, TARGET, bounds, dataset, parse, write_dataset


@pytest.mark.parametrize("bad", [None, "2026-08-29", datetime(2026, 8, 29)])
def test_options_requiere_as_of_con_zona(bad):
    with pytest.raises(ValueError):
        mur.MurOptions(bad)


@pytest.mark.parametrize("bad", [0, -1, True, float("nan"), float("inf"), 168.1])
def test_options_limita_antiguedad(bad):
    with pytest.raises(ValueError):
        mur.MurOptions(AS_OF, bad)


def test_defaults_y_modo_explicito():
    assert mur.DEFAULT_MAX_NOMINAL_AGE_HOURS == 72.0
    assert mur.NATIVE_GRID_STEP_DEG == .01
    assert mur.HALO_CELLS == 2
    assert mur.MurOptions(AS_OF).mode is mur.MurMode.NRT_ONLY
    with pytest.raises(ValueError):
        mur.MurOptions(AS_OF, mode="historical_diagnostic")
    local = datetime(2026, 8, 29, 4, tzinfo=timezone(timedelta(hours=-5)))
    assert mur.MurOptions(local).as_of_utc == AS_OF


def test_conserva_unidades_mascara_halo_y_procedencia():
    field = parse(dataset())
    assert field.status is mur.MurStatus.VALIDA_EN_FECHA_NOMINAL
    assert field.grid.sst_celsius == ((22.0,) * 3,) * 3
    assert field.grid.sst_kelvin == ((295.15,) * 3,) * 3
    assert field.grid.analysis_error_kelvin == ((.4,) * 3,) * 3
    assert field.grid.dt_1km_hours == ((-7.0,) * 3,) * 3
    assert field.n_grid_cells == field.n_marine_cells == field.n_valid_cells == 9
    assert field.n_analysis_error_cells == field.n_dt_1km_cells == 9
    assert field.coverage_fraction == 1.0
    assert field.halo_complete
    assert len(field.derivation_support.latitudes) == 7
    assert 1.08 < field.median_zonal_spacing_km < 1.10
    assert 1.11 < field.median_meridional_spacing_km < 1.12
    assert field.time_utc == datetime(2026, 8, 28, 9, tzinfo=timezone.utc)
    assert field.nominal_age_hours == 24.0
    assert field.provenance.product_version == "04.1nrt"
    assert field.provenance.product_stage is mur.MurProductStage.NRT
    assert not field.provenance.availability_as_of_verified
    assert not field.provenance.operational_use_verified
    assert field.provenance.read_at_utc is None  # transformación pura
    assert not field.field_is_operational_domain


def test_contrato_metadatos_nrt_observado_en_descarga_real():
    ds = dataset(
        times=("2026-08-30T09:00:00",),
        title="Daily MUR SST, Interim near-real-time (nrt) product",
        product_version="04.1nrt",
        date_created="20260831T090519Z",
    )
    field = parse(
        ds,
        target=date(2026, 8, 30),
        as_of=datetime(2026, 8, 31, 21, 31, 55, tzinfo=timezone.utc),
    )
    assert field.status is mur.MurStatus.VALIDA_EN_FECHA_NOMINAL
    assert field.time_utc == datetime(2026, 8, 30, 9, tzinfo=timezone.utc)
    assert field.provenance.product_version == mur.NRT_PRODUCT_VERSION
    assert field.provenance.product_stage is mur.MurProductStage.NRT
    assert field.provenance.product_created_at_utc == datetime(
        2026, 8, 31, 9, 5, 19, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "stage,product_version",
    [("nrt", "04.1"), ("Final", "04.1nrt")],
)
def test_no_confunde_version_final_y_nrt(stage, product_version):
    field = parse(dataset(stage=stage, product_version=product_version),
                  mode=mur.MurMode.HISTORICAL_DIAGNOSTIC)
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "invalid_dataset"


def test_tierra_con_sst_finita_y_bits_desconocidos_no_son_mar():
    ds = dataset()
    ds["mask"].values[0, 2, 2:5] = [2, 32, 9]  # tierra, bit desconocido, mar+hielo
    field = parse(ds)
    assert field.grid.sst_celsius[0] == (None, None, None)
    assert field.grid.mask[0] == (2, None, 9)
    assert field.grid.analysis_error_kelvin[0] == (None,) * 3
    assert field.grid.dt_1km_hours[0] == (None,) * 3
    assert field.n_grid_cells == 9
    assert field.n_marine_cells == field.n_valid_cells == 6
    assert field.coverage_fraction == 1.0


def test_huecos_no_son_ceros_ni_se_trasladan_a_otra_celda():
    ds = dataset()
    ds["analysed_sst"].values[0, 3, 3] = np.nan
    field = parse(ds)
    assert field.grid.sst_celsius[1][1] is None
    assert field.grid.mask[1][1] == 1
    assert field.n_marine_cells == 9 and field.n_valid_cells == 8
    assert field.coverage_fraction == pytest.approx(8 / 9)


@pytest.mark.parametrize("kind", ["land", "missing", "halo_only"])
def test_sin_datos_en_campo_no_se_salva_con_halo(kind):
    ds = dataset()
    if kind == "land":
        ds["mask"].values[:] = 2
    elif kind == "missing":
        ds["analysed_sst"].values[:] = np.nan
    else:
        ds["analysed_sst"].values[:, 2:5, 2:5] = np.nan
    field = parse(ds)
    assert field.status is mur.MurStatus.SIN_DATOS
    assert field.n_valid_cells == 0
    assert field.reason == "no_valid_sst_in_requested_field"
    assert field.coverage_fraction == (None if kind == "land" else 0.0)


def test_falta_calidad_no_inventa_error_cero_ni_invalidacion_de_sst():
    ds = dataset().drop_vars(["analysis_error", "dt_1km_data"])
    field = parse(ds)
    assert field.n_valid_cells == 9
    assert field.n_analysis_error_cells == field.n_dt_1km_cells == 0
    assert field.grid.analysis_error_kelvin == ((None,) * 3,) * 3
    assert field.missing_quality_variables == mur.QUALITY_VARIABLES


def test_dt_preserva_signos_cero_y_faltantes_del_int8():
    ds = dataset()
    ds["dt_1km_data"].values[0, 2:5, 2:5] = [[-55, 0, 17], [-128, 128, np.nan], [-127, 127, .5]]
    ds["analysis_error"].values[0, 2, 2:5] = [0, -1, np.nan]
    field = parse(ds)
    assert field.grid.dt_1km_hours == ((-55., 0., 17.), (None,) * 3, (-127., 127., None))
    assert field.grid.analysis_error_kelvin[0] == (0., None, None)
    assert field.n_dt_1km_cells == 5
    assert field.n_valid_cells == 9


def test_final_no_se_disfraza_de_nrt_por_mencionar_nrt_en_history():
    ds = dataset(stage="Final")
    ds.attrs["history"] = "created at nominal 4-day latency; replaced nrt (1-day latency) version."
    field = parse(ds)
    assert field.status is mur.MurStatus.SIN_DATOS
    assert field.provenance.product_stage is mur.MurProductStage.FINAL
    assert field.reason == "final_product_requires_historical_mode"
    assert field.n_valid_cells == 0
    historical = parse(ds, mode=mur.MurMode.HISTORICAL_DIAGNOSTIC)
    assert historical.status is mur.MurStatus.HISTORICA_FINAL
    assert historical.n_valid_cells == 9
    assert historical.provenance.availability_as_of_verified is False


@pytest.mark.parametrize("title,reason", [
    ("Daily MUR SST", "unknown_product_stage"),
    ("Daily MUR SST, Final NRT", "invalid_dataset"),
])
def test_etapa_desconocida_o_ambigua_no_se_admite(title, reason):
    ds = dataset()
    ds.attrs["title"] = title
    field = parse(ds, mode=mur.MurMode.HISTORICAL_DIAGNOSTIC)
    assert field.reason == reason
    assert field.n_valid_cells == 0


@pytest.mark.parametrize("created,reason", [
    (None, "product_creation_time_unknown"),
    ("20260830T050000Z", "product_created_after_as_of"),
])
def test_nrt_no_retroproyecta_producto_creado_despues_de_as_of(created, reason):
    ds = dataset()
    ds.attrs.pop("date_created")
    if created:
        ds.attrs["date_created"] = created
    field = parse(ds)
    assert field.reason == reason
    assert field.status is mur.MurStatus.SIN_DATOS


@pytest.mark.parametrize("stamp", ["2026-08-25T08:59:59", "2026-08-29T09:00:01"])
def test_fuera_de_edad_o_futuro_es_ausente(stamp):
    field = parse(dataset(times=(stamp,)))
    assert field.reason == "outside_nominal_age_window"
    assert field.n_valid_cells == 0


def test_fecha_nominal_utc_no_se_decide_en_lima():
    ds = dataset(times=("2026-08-28T00:00:00",))
    field = parse(ds)
    assert field.nominal_product_date == TARGET
    assert field.nominal_age_hours == 33.0
    assert field.matches_requested_nominal_date


@pytest.mark.parametrize("kind", [
    "units", "identity", "version", "level", "mask_bits", "standard_name", "error_units",
    "dt_units", "unscaled", "raw_time", "two_times", "missing_mask", "step", "duplicate_axis",
])
def test_esquema_incompatible_es_error_trazable(kind):
    ds = dataset()
    if kind == "units": ds["analysed_sst"].attrs["units"] = "degree_Celsius"
    elif kind == "identity": ds.attrs["id"] = "OSTIA"
    elif kind == "version": ds.attrs["product_version"] = "05.0"
    elif kind == "level": ds.attrs["processing_level"] = "L3"
    elif kind == "mask_bits": ds["mask"].attrs["flag_meanings"] = "land open_sea"
    elif kind == "standard_name": ds["analysed_sst"].attrs["standard_name"] = "sea_surface_skin_temperature"
    elif kind == "error_units": ds["analysis_error"].attrs["units"] = "%"
    elif kind == "dt_units": ds["dt_1km_data"].attrs["units"] = "days"
    elif kind == "unscaled": ds["analysed_sst"].attrs["scale_factor"] = .001
    elif kind == "raw_time": ds = ds.assign_coords(time=[0])
    elif kind == "two_times": ds = dataset(times=("2026-08-27T09:00", "2026-08-28T09:00"))
    elif kind == "missing_mask": ds = ds.drop_vars("mask")
    else:
        coords = ds.lon.values.copy()
        coords[3] = coords[2] if kind == "duplicate_axis" else coords[3] + .003
        ds = ds.assign_coords(lon=coords)
    field = parse(ds)
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "invalid_dataset"
    assert field.error_type is not None


def test_orden_descendente_y_float32_conservan_celdas_en_limites():
    ds = dataset(lats=(-12.50 + .01*np.arange(7)).astype("float32"),
                 lons=(-76.83 + .01*np.arange(7)).astype("float32"))
    requested = (-12.48, -12.46, -76.81, -76.79)
    field = parse(ds, field_bounds=requested)
    reversed_field = parse(ds.isel(lat=slice(None, None, -1), lon=slice(None, None, -1)),
                           field_bounds=requested)
    assert field.grid == reversed_field.grid
    assert field.n_grid_cells == 9
    assert field.halo_complete


def test_rechaza_campo_global_antes_de_cargar_matrices():
    ds = dataset(lats=-13 + .01*np.arange(220))
    field = parse(ds)
    assert field.status is mur.MurStatus.ERROR


def test_argumentos_invalidos_fallan_antes_de_abrir_archivos(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("IO no permitido")
    monkeypatch.setattr(mur.xr, "open_dataset", forbidden)
    with pytest.raises(ValueError):
        mur.fetch_mur_field(-12, -13, -77, -76, TARGET, options=mur.MurOptions(AS_OF))
    with pytest.raises(ValueError):
        mur.fetch_mur_field(-13, -12, -77, -74, TARGET, options=mur.MurOptions(AS_OF))


def test_directorio_no_configurado_es_error_sin_red(monkeypatch):
    monkeypatch.delenv(mur.DATA_DIRECTORY_ENV, raising=False)
    field = mur.fetch_mur_field(*bounds(dataset()), TARGET, options=mur.MurOptions(AS_OF))
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "mur_directory_not_configured"


def test_archivo_netcdf_cf_se_decodifica_una_vez_y_se_cierra(tmp_path, monkeypatch):
    ds = dataset()
    ds["analysed_sst"].values[0, 3, 3] = np.nan
    path = tmp_path / "mur.nc4"
    ds.to_netcdf(path, engine="h5netcdf", encoding={
        "analysed_sst": {"dtype": "int16", "scale_factor": .001, "add_offset": 298.15,
                         "_FillValue": -32768},
        "dt_1km_data": {"dtype": "int8", "_FillValue": -128},
    })
    calls, closed = [], []
    original = xr.open_dataset
    class Context:
        def __init__(self, *args, **kwargs):
            calls.append(kwargs)
            self.ds = original(*args, **kwargs)
        def __enter__(self): return self.ds
        def __exit__(self, *args):
            self.ds.close()
            closed.append(True)
    monkeypatch.setattr(mur.xr, "open_dataset", Context)
    field = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.n_valid_cells == 8
    assert field.grid.sst_celsius[0][0] == pytest.approx(22.0)
    assert field.grid.sst_celsius[1][1] is None
    assert field.provenance.source_file_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert field.provenance.source_file_name == "mur.nc4"
    assert field.provenance.read_at_utc.tzinfo is not None
    assert calls[0]["decode_timedelta"] is False and closed == [True]


def test_el_ultimo_campo_valido_es_unico_no_mosaico(tmp_path, monkeypatch):
    old = dataset(times=("2026-08-27T09:00",))
    old["analysed_sst"].values[0, 2, 2] = np.nan
    new = dataset()
    new["analysed_sst"].values[:] = np.nan
    write_dataset(old, tmp_path / "old.nc4")
    write_dataset(new, tmp_path / "new.nc4")
    monkeypatch.setenv(mur.DATA_DIRECTORY_ENV, str(tmp_path))
    field = mur.fetch_mur_field(*bounds(old), TARGET, options=mur.MurOptions(AS_OF))
    assert field.nominal_product_date == date(2026, 8, 27)
    assert field.status is mur.MurStatus.VALIDA_RECIENTE
    assert field.grid.sst_celsius[0][0] is None
    assert field.n_valid_cells == 8
    assert field.provenance.source_file_name == "old.nc4"


def test_dos_archivos_para_un_dia_no_se_eligen_por_orden_de_nombre(tmp_path):
    ds = dataset()
    write_dataset(ds, tmp_path / "a.nc4")
    write_dataset(ds, tmp_path / "b.nc4")
    field = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "source_failure"


def test_error_de_lectura_no_expone_texto_sensible(tmp_path, monkeypatch, caplog):
    write_dataset(dataset(), tmp_path / "mur.nc4")
    def fail(*args, **kwargs):
        raise RuntimeError("SECRET_AUTH_URL")
    monkeypatch.setattr(mur.xr, "open_dataset", fail)
    field = mur.fetch_mur_field(*bounds(dataset()), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.status is mur.MurStatus.ERROR
    assert field.error_type == "RuntimeError"
    assert "SECRET_AUTH_URL" not in caplog.text
    assert "SECRET_AUTH_URL" not in repr(field)


def test_directorio_vacio_es_sin_datos(tmp_path):
    field = mur.fetch_mur_field(*bounds(dataset()), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.status is mur.MurStatus.SIN_DATOS
    assert field.nominal_product_date is None


def test_numero_de_archivos_acotado_y_sin_seguir_enlaces(tmp_path, monkeypatch):
    ds = dataset()
    write_dataset(ds, tmp_path / "a.nc4")
    (tmp_path / "b.nc4").symlink_to(tmp_path / "a.nc4")
    field = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.status is mur.MurStatus.ERROR
    monkeypatch.setattr(mur, "MAX_LOCAL_FILES", 1)
    field = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert field.status is mur.MurStatus.ERROR


def test_hash_y_valores_provienen_de_los_mismos_bytes(tmp_path, monkeypatch):
    ds = dataset()
    path = write_dataset(ds, tmp_path / "mur.nc4")
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    original_open = xr.open_dataset
    def opened_snapshot(*args, **kwargs):
        result = original_open(*args, **kwargs)
        path.write_bytes(b"replaced after taking the read snapshot")
        return result
    monkeypatch.setattr(mur.xr, "open_dataset", opened_snapshot)
    result = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert result.n_valid_cells == 9
    assert result.provenance.source_file_sha256 == original_hash
    assert result.provenance.source_file_sha256 != hashlib.sha256(path.read_bytes()).hexdigest()


def test_rechaza_archivo_demasiado_grande_antes_de_abrir_netcdf(tmp_path, monkeypatch):
    ds = dataset()
    write_dataset(ds, tmp_path / "mur.nc4")
    monkeypatch.setattr(mur, "MAX_FILE_BYTES", 1)
    def forbidden(*args, **kwargs):
        pytest.fail("No se debe abrir un NetCDF por encima del límite")
    monkeypatch.setattr(mur.xr, "open_dataset", forbidden)
    result = mur.fetch_mur_field(*bounds(ds), TARGET, options=mur.MurOptions(AS_OF), data_directory=tmp_path)
    assert result.status is mur.MurStatus.ERROR
    assert result.error_type == "ValueError"
