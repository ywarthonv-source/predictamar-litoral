"""Gradiente MUR: soporte centrado, signos, máscaras y calidad local."""

from dataclasses import replace

import numpy as np
import pytest

import ingestion.fetch_mur as mur
import derivation.mur_gradient as mg
from mur_fixtures import bounds, dataset, parse


def test_campo_constante_gradiente_cero_no_ausente_y_procedencia_identica():
    field = parse(dataset())
    gradient = mg.derive_mur_gradient(field)
    assert gradient.status is mg.MurGradientStatus.VALIDO
    assert gradient.gradient_c_per_km == ((0.,) * 3,) * 3
    assert gradient.n_gradient_cells == 9
    assert gradient.n_gradient_cells_with_complete_dt_1km == 9
    assert gradient.source_time_utc == field.time_utc
    assert gradient.source_provenance is field.provenance
    assert gradient.source_nominal_product_date == field.nominal_product_date
    assert gradient.options is field.options
    assert gradient.method == ((mg.METHOD,) * 3,) * 3
    assert gradient.source_analysis_error_max_kelvin == ((.4,) * 3,) * 3
    assert gradient.source_dt_1km_min_hours == ((-7.,) * 3,) * 3
    assert gradient.source_dt_1km_max_hours == ((-7.,) * 3,) * 3
    assert gradient.analysis_error_support_complete == ((True,) * 3,) * 3
    assert not gradient.field_is_operational_domain


def test_plano_analitico_signos_y_denominador_entre_dos_vecinos():
    coords = -.03 + .01 * np.arange(7)
    ds = dataset(lats=coords, lons=coords)
    ds["analysed_sst"].values[0] += 3 * coords[:, None] - 4 * coords[None, :]
    gradient = mg.derive_mur_gradient(parse(ds))
    km_per_degree = 111.1950802335329
    assert gradient.eastward_gradient_c_per_km[1][1] == pytest.approx(-4 / km_per_degree, abs=1e-12)
    assert gradient.northward_gradient_c_per_km[1][1] == pytest.approx(3 / km_per_degree, abs=1e-12)
    assert gradient.gradient_c_per_km[1][1] == pytest.approx(5 / km_per_degree, abs=1e-12)
    assert gradient.median_meridional_stencil_km == pytest.approx(.02 * km_per_degree)
    assert mur.haversine_km(0, 0, 0, 1) == pytest.approx(km_per_degree)


@pytest.mark.parametrize("i,j", [(3, 3), (2, 3), (4, 3), (3, 2), (3, 4)])
def test_centro_y_cada_vecino_son_obligatorios(i, j):
    ds = dataset()
    ds["analysed_sst"].values[0, i, j] = np.nan
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.gradient_c_per_km[1][1] is None
    assert gradient.method[1][1] is None


def test_tierra_finita_no_fabrica_gradiente_costero():
    ds = dataset()
    ds["mask"].values[0, 3, 2] = 2
    ds["analysed_sst"].values[0, 3, 2] = 310
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.gradient_c_per_km[1][1] is None
    assert gradient.support_adjacent_to_land[1][1] is True


def test_diagonal_ausente_permite_cruz_pero_no_certifica_entorno():
    ds = dataset()
    ds["mask"].values[0, 2, 2] = 2
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.gradient_c_per_km[1][1] == 0
    assert gradient.full_3x3_support[1][1] is False
    assert gradient.data_edge[1][1] is True
    assert gradient.support_adjacent_to_land[1][1] is True


def test_sin_halo_bordes_ausentes_sin_derivadas_unilaterales():
    ds = dataset()
    field = parse(ds, field_bounds=bounds(ds, 0, 6))
    gradient = mg.derive_mur_gradient(field)
    assert not field.halo_complete
    assert gradient.n_gradient_cells == 25
    assert gradient.gradient_c_per_km[0] == (None,) * 7
    assert gradient.gradient_c_per_km[-1] == (None,) * 7
    assert all(row[0] is None and row[-1] is None for row in gradient.gradient_c_per_km)


def test_halo_se_usa_antes_de_recortar():
    ds = dataset()
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.n_gradient_cells == 9
    assert len(gradient.latitudes) == 3
    assert gradient.gradient_coverage_fraction == 1
    assert gradient.full_3x3_support == ((True,) * 3,) * 3
    assert gradient.support_adjacent_to_land == ((False,) * 3,) * 3


def test_calidad_es_del_soporte_local_no_cobertura_de_todo_el_campo():
    ds = dataset()
    ds["dt_1km_data"].values[:] = 0
    ds["dt_1km_data"].values[0, 3, 4] = np.nan
    ds["analysis_error"].values[0, 3, 2] = np.nan
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.n_gradient_cells == 9
    assert gradient.n_dt_1km_support_cells[1][1] == 4
    assert gradient.dt_1km_support_complete[1][1] is False
    assert gradient.source_dt_1km_min_hours[1][1] is None
    assert gradient.source_dt_1km_max_hours[1][1] is None
    assert gradient.analysis_error_support_complete[1][1] is False
    assert gradient.source_analysis_error_max_kelvin[1][1] is None


def test_extremos_dt_conservan_signo_no_abs_ni_regla_de_frescura():
    ds = dataset()
    ds["dt_1km_data"].values[0, 3, 2] = -55
    ds["dt_1km_data"].values[0, 3, 4] = 17
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.source_dt_1km_min_hours[1][1] == -55
    assert gradient.source_dt_1km_max_hours[1][1] == 17
    assert gradient.dt_1km_support_complete[1][1] is True


def test_sin_auxiliares_no_se_confunde_gradiente_ausente_con_calidad_desconocida():
    ds = dataset().drop_vars(["dt_1km_data", "analysis_error"])
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.n_gradient_cells == 9
    assert gradient.n_gradient_cells_with_complete_dt_1km == 0
    assert gradient.n_dt_1km_support_cells == ((0,) * 3,) * 3
    assert gradient.analysis_error_support_complete == ((False,) * 3,) * 3


def test_maximo_error_del_soporte_no_error_del_gradiente():
    ds = dataset()
    ds["analysis_error"].values[0, 3, 2] = .8
    gradient = mg.derive_mur_gradient(parse(ds))
    assert gradient.source_analysis_error_max_kelvin[1][1] == .8
    assert "gradient_uncertainty" not in gradient.__dataclass_fields__


@pytest.mark.parametrize("source_status,expected", [
    (mur.MurStatus.SIN_DATOS, mg.MurGradientStatus.FUENTE_SIN_DATOS),
    (mur.MurStatus.ERROR, mg.MurGradientStatus.FUENTE_ERROR),
])
def test_fuente_ausente_o_error_conserva_procedencia_sin_calcular(source_status, expected):
    field = replace(parse(dataset()), status=source_status, reason="example", error_type="Example")
    gradient = mg.derive_mur_gradient(field)
    assert gradient.status is expected
    assert gradient.n_gradient_cells == 0
    assert gradient.gradient_c_per_km == ((None,) * 3,) * 3
    assert gradient.source_reason == "example"
    assert gradient.source_provenance is field.provenance


def test_archivo_final_conserva_etapa_historica_en_derivada():
    field = parse(dataset(stage="Final"), mode=mur.MurMode.HISTORICAL_DIAGNOSTIC)
    gradient = mg.derive_mur_gradient(field)
    assert gradient.source_status == "historica_final"
    assert gradient.source_provenance.product_stage is mur.MurProductStage.FINAL
    assert not gradient.source_provenance.availability_as_of_verified


@pytest.mark.parametrize("mutation", ["units", "dataset", "shape", "crop", "conversion", "step"])
def test_rechaza_contratos_de_fuente_manipulados(mutation):
    field = parse(dataset())
    if mutation == "units": field = replace(field, units="K")
    elif mutation == "dataset": field = replace(field, provenance=replace(field.provenance, dataset_id="other"))
    elif mutation == "crop": field = replace(field, grid=replace(field.grid, sst_celsius=((0.,),)))
    else:
        support = field.derivation_support
        if mutation == "shape": support = replace(support, mask=((1,),))
        elif mutation == "conversion": support = replace(support, sst_kelvin=((290.,) * 7,) * 7)
        elif mutation == "step": support = replace(support, latitudes=tuple(-12.5 + .02*i for i in range(7)))
        field = replace(field, derivation_support=support)
    with pytest.raises(ValueError):
        mg.derive_mur_gradient(field)


def test_tipo_invalido_no_es_gradiente_vacio():
    with pytest.raises(ValueError):
        mg.derive_mur_gradient(None)
