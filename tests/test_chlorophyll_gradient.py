"""Pruebas del gradiente OLCI puro, centrado y enmascarado."""

from dataclasses import replace
import numpy as np

from derivation.chlorophyll_gradient import (
    ChlorophyllGradientStatus, METHOD, derive_chlorophyll_gradient,
)
from ingestion.fetch_chlorophyll_field import ChlorophyllFieldStatus
from test_fetch_chlorophyll_field import dataset, parse


def test_campo_constante_produce_ceros_validos_no_faltantes():
    gradient = derive_chlorophyll_gradient(parse(dataset()))
    assert gradient.status is ChlorophyllGradientStatus.VALIDO
    assert gradient.n_gradient_cells == 9
    assert all(value == 0.0 for row in gradient.gradient_mg_m3_per_km for value in row)
    assert all(value == METHOD for row in gradient.method for value in row)
    assert gradient.gradient_coverage_fraction == 1.0


def test_gradiente_lineal_conserva_signo_componentes_y_magnitud():
    values = np.empty((1, 7, 7))
    for i in range(7):
        for j in range(7):
            values[0, i, j] = 1 + 2*j + 3*i
    gradient = derive_chlorophyll_gradient(parse(dataset(values)))
    gx = gradient.eastward_gradient_mg_m3_per_km[1][1]
    gy = gradient.northward_gradient_mg_m3_per_km[1][1]
    assert gx > 0 and gy > 0
    assert np.isclose(gradient.gradient_mg_m3_per_km[1][1], np.hypot(gx, gy))
    assert gradient.median_zonal_stencil_km > 1.18
    assert gradient.median_meridional_stencil_km > 1.22


def test_falta_cardinal_impide_gradiente_sin_diferencia_unilateral():
    values = np.ones((1, 7, 7))
    values[0, 3, 2] = 0
    gradient = derive_chlorophyll_gradient(parse(dataset(values)))
    assert gradient.gradient_mg_m3_per_km[1][1] is None
    assert gradient.method[1][1] is None
    assert gradient.data_edge[1][1] is True


def test_land_diagonal_no_impide_cruz_pero_se_declara_proximidad():
    flags = np.zeros((1, 7, 7))
    flags[0, 2, 2] = 1
    gradient = derive_chlorophyll_gradient(parse(dataset(flags=flags)))
    assert gradient.gradient_mg_m3_per_km[1][1] == 0.0
    assert gradient.full_3x3_support[1][1] is False
    assert gradient.support_adjacent_to_land[1][1] is True


def test_incertidumbre_incompleta_no_elimina_gradiente():
    uncertainty = np.full((1, 7, 7), 50.0)
    uncertainty[0, 3, 2] = np.nan
    gradient = derive_chlorophyll_gradient(parse(dataset(uncertainty=uncertainty)))
    assert gradient.gradient_mg_m3_per_km[1][1] == 0.0
    assert gradient.uncertainty_support_complete[1][1] is False
    assert gradient.source_uncertainty_max_pct[1][1] is None


def test_fuente_sin_datos_y_error_se_propagan_sin_calcular():
    empty = parse(dataset(np.zeros((1, 7, 7))))
    no_data = derive_chlorophyll_gradient(empty)
    assert no_data.status is ChlorophyllGradientStatus.FUENTE_SIN_DATOS
    assert no_data.n_gradient_cells == 0
    failed = replace(empty, status=ChlorophyllFieldStatus.ERROR,
                     reason="source_failure", error_type="RuntimeError")
    error = derive_chlorophyll_gradient(failed)
    assert error.status is ChlorophyllGradientStatus.FUENTE_ERROR
    assert error.source_error_type == "RuntimeError"


def test_inconsistencia_entre_campo_y_halo_se_rechaza():
    field = parse(dataset())
    broken = replace(field, grid=replace(
        field.grid, chlorophyll_mg_m3=((2.0, 2.0, 2.0),)*3))
    try:
        derive_chlorophyll_gradient(broken)
    except ValueError as exc:
        assert "recorte" in str(exc)
    else:
        raise AssertionError("Se aceptó un campo distinto de su soporte")
