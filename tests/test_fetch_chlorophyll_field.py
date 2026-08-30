"""Contrato sintético del campo OLCI opcional; nunca consulta la red."""

from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_chlorophyll_field as cf


STEP = cf.NATIVE_GRID_STEP_DEG
TARGET = date(2026, 8, 28)
AS_OF = datetime(2026, 8, 29, tzinfo=timezone.utc)


def dataset(chl=None, *, times=("2026-08-28",), flags=None, uncertainty=None,
            lats=None, lons=None):
    lats = np.asarray(lats if lats is not None else -12.49 + STEP*np.arange(7))
    lons = np.asarray(lons if lons is not None else -76.81 + STEP*np.arange(7))
    shape = (len(times), len(lats), len(lons))
    chl = np.ones(shape) if chl is None else np.asarray(chl, dtype=float)
    flags = np.zeros(shape) if flags is None else np.asarray(flags, dtype=float)
    uncertainty = (np.full(shape, 50.0) if uncertainty is None
                   else np.asarray(uncertainty, dtype=float))
    coords = {"time": np.asarray(times, dtype="datetime64[ns]"),
              "latitude": lats, "longitude": lons}
    ds = xr.Dataset({
        "CHL": (("time", "latitude", "longitude"), chl,
                {"units": cf.UNITS, "standard_name": cf.STANDARD_NAME}),
        "CHL_uncertainty": (("time", "latitude", "longitude"), uncertainty,
                            {"units": "%"}),
        "flags": (("time", "latitude", "longitude"), flags,
                  {"flag_masks": 1, "flag_meanings": "LAND"}),
    }, coords=coords)
    return ds


def bounds(ds, first=2, last=4):
    return (float(ds.latitude[first]), float(ds.latitude[last]),
            float(ds.longitude[first]), float(ds.longitude[last]))


def parse(ds, *, target=TARGET, as_of=AS_OF, max_age=72.0, **kwargs):
    return cf.chlorophyll_field_from_dataset(
        ds, *bounds(ds), target,
        options=cf.ChlorophyllOptions(as_of, max_age), **kwargs)


@pytest.mark.parametrize("bad", [None, datetime(2026, 8, 29), "2026-08-29"])
def test_options_exige_datetime_con_zona(bad):
    with pytest.raises(ValueError):
        cf.ChlorophyllOptions(bad)


@pytest.mark.parametrize("age", [0, -1, 169, float("nan"), True])
def test_options_rechaza_antiguedad_invalida(age):
    with pytest.raises(ValueError):
        cf.ChlorophyllOptions(AS_OF, age)


def test_campo_valido_conserva_valores_halo_cobertura_y_procedencia():
    ds = dataset()
    result = parse(ds)
    assert result.status is cf.ChlorophyllFieldStatus.VALIDA_EN_FECHA_NOMINAL
    assert result.nominal_product_date == TARGET
    assert result.n_grid_cells == result.n_marine_cells == result.n_valid_cells == 9
    assert result.coverage_fraction == 1.0
    assert result.halo_complete is True
    assert len(result.derivation_support.latitudes) == 7
    assert result.grid.chlorophyll_mg_m3 == ((1.0,)*3,)*3
    assert result.dataset_version is None
    assert result.requested_dataset_version == "202207"
    assert result.availability_as_of_verified is False
    assert .59 < result.median_zonal_resolution_km < .62
    assert .61 < result.median_meridional_resolution_km < .63


def test_elige_ultimo_dia_con_chl_valida_y_no_mezcla_fechas():
    values = np.ones((2, 7, 7))
    values[1] = 0
    ds = dataset(values, times=("2026-08-26", "2026-08-28"))
    result = parse(ds)
    assert result.status is cf.ChlorophyllFieldStatus.VALIDA_RECIENTE
    assert result.nominal_product_date == date(2026, 8, 26)
    assert result.nominal_age_hours == 72.0
    assert result.n_valid_cells == 9


def test_dia_no_completado_a_as_of_no_es_admisible():
    ds = dataset(np.ones((2, 7, 7)), times=("2026-08-27", "2026-08-28"))
    noon = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    result = parse(ds, as_of=noon, max_age=48)
    assert result.nominal_product_date == date(2026, 8, 27)


def test_land_y_flag_desconocido_no_son_cero_y_no_entran_al_denominador():
    flags = np.zeros((1, 7, 7))
    flags[0, 2, 2] = 1
    flags[0, 2, 3] = 4
    result = parse(dataset(flags=flags))
    assert result.n_grid_cells == 9
    assert result.n_marine_cells == 7
    assert result.n_valid_cells == 7
    assert result.grid.chlorophyll_mg_m3[0][:2] == (None, None)
    assert result.grid.flags[0][:2] == (1, None)


def test_sin_chl_positiva_es_sin_datos_no_error():
    result = parse(dataset(np.zeros((1, 7, 7))))
    assert result.status is cf.ChlorophyllFieldStatus.SIN_DATOS
    assert result.reason == "no_valid_chlorophyll_in_requested_field"
    assert result.error_type is None


def test_valores_validos_solo_en_halo_no_hacen_disponible_el_campo():
    values = np.ones((1, 7, 7))
    values[0, 2:5, 2:5] = 0
    result = parse(dataset(values))
    assert result.status is cf.ChlorophyllFieldStatus.SIN_DATOS
    assert result.n_valid_cells == 0
    assert any(v is not None for row in result.derivation_support.chlorophyll_mg_m3 for v in row)


def test_campo_enteramente_land_no_inventa_denominador_de_cobertura():
    flags = np.ones((1, 7, 7))
    result = parse(dataset(flags=flags))
    assert result.n_marine_cells == result.n_valid_cells == 0
    assert result.coverage_fraction is None


def test_fecha_fuera_de_antiguedad_no_se_reutiliza_eternamente():
    ds = dataset(times=("2026-08-25",))
    result = parse(ds)
    assert result.status is cf.ChlorophyllFieldStatus.SIN_DATOS
    assert result.nominal_product_date is None
    assert result.reason == "no_admissible_time"


@pytest.mark.parametrize("mutation", ["units", "flags", "step", "scale"])
def test_contrato_rechaza_dataset_incompatible(mutation):
    ds = dataset()
    if mutation == "units":
        ds.CHL.attrs["units"] = "unknown"
    elif mutation == "flags":
        ds.flags.attrs["flag_meanings"] = "LAND CLOUD"
    elif mutation == "step":
        longitude = np.asarray(ds.longitude).copy()
        longitude[3] += STEP * .2
        ds = ds.assign_coords(longitude=longitude)
    else:
        ds.CHL.attrs["scale_factor"] = 0.01
    result = parse(ds)
    assert result.status is cf.ChlorophyllFieldStatus.ERROR
    assert result.reason == "invalid_dataset"


def test_fetch_fija_version_parte_halo_y_cierra_dataset(monkeypatch):
    ds = dataset()
    captured = {}

    class Context:
        closed = False
        def __enter__(self):
            return ds
        def __exit__(self, *args):
            self.closed = True

    context = Context()
    def fake_open(**kwargs):
        captured.update(kwargs)
        return context
    monkeypatch.setattr(cf.copernicusmarine, "open_dataset", fake_open)
    result = cf.fetch_chlorophyll_field(
        *bounds(ds), TARGET, options=cf.ChlorophyllOptions(AS_OF))
    assert result.status is cf.ChlorophyllFieldStatus.VALIDA_EN_FECHA_NOMINAL
    assert captured["dataset_id"] == cf.DATASET_ID
    assert captured["dataset_version"] == "202207"
    assert captured["dataset_part"] == "default"
    assert captured["coordinates_selection_method"] == "inside"
    assert "username" not in captured and "password" not in captured
    assert captured["minimum_latitude"] < bounds(ds)[0]
    assert captured["maximum_longitude"] > bounds(ds)[3]
    assert context.closed is True
    assert result.source_access == "copernicus_query"
    assert result.dataset_version == "202207"


def test_fallo_de_api_produce_error_trazable(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("secret text must not enter payload")
    monkeypatch.setattr(cf.copernicusmarine, "open_dataset", fail)
    ds = dataset()
    result = cf.fetch_chlorophyll_field(
        *bounds(ds), TARGET, options=cf.ChlorophyllOptions(AS_OF))
    assert result.status is cf.ChlorophyllFieldStatus.ERROR
    assert result.reason == "source_failure"
    assert result.error_type == "RuntimeError"
