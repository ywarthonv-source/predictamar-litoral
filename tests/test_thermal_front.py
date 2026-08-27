"""Pruebas puras y sintéticas del gradiente térmico; sin red."""

from datetime import date, datetime, timezone

import numpy as np
import pytest

import derivation.thermal_front as tf
import ingestion.fetch_ostia as fo


def make_field(values, errors=None, lats=(-12.50, -12.45, -12.40), lons=(-76.85, -76.80, -76.75)):
    rows, cols = len(lats), len(lons)
    if errors is None:
        errors = [[0.2 for _ in range(cols)] for _ in range(rows)]
    valid = sum(value is not None for row in values for value in row)
    return fo.OstiaField(
        requested_date=date(2026, 8, 12),
        minimum_latitude=-12.6,
        maximum_latitude=-12.3,
        minimum_longitude=-76.95,
        maximum_longitude=-76.65,
        time_utc=datetime(2026, 8, 12, 12, tzinfo=timezone.utc),
        time_local=datetime(2026, 8, 12, 7, tzinfo=fo.TZ_PUCUSANA),
        temporal_age_hours=17.0,
        inside_requested_local_date=True,
        latitudes=tuple(lats),
        longitudes=tuple(lons),
        sst_kelvin=tuple(tuple(None if v is None else v + 273.15 for v in row) for row in values),
        sst_celsius=tuple(tuple(v for v in row) for row in values),
        analysis_error_kelvin=tuple(tuple(v for v in row) for row in errors),
        n_grid_cells=rows * cols,
        n_valid_cells=valid,
        coverage_fraction=valid / (rows * cols) if rows * cols else None,
        product_id=fo.PRODUCT_ID,
        dataset_id=fo.DATASET_ID,
        variables=(fo.VARIABLE_SST, fo.VARIABLE_ERROR),
        standard_name=fo.STANDARD_NAME,
        native_units=fo.UNITS_NATIVE,
        converted_units=fo.UNITS_CELSIUS,
        processing_level=fo.PROCESSING_LEVEL,
        nominal_resolution_deg=fo.NOMINAL_RESOLUTION_DEG,
        data_scope=fo.DATA_SCOPE,
        scope_warning=fo.DATA_SCOPE_WARNING,
        status=fo.OstiaStatus.VALIDA_EN_FECHA_LOCAL,
    )


def empty_source():
    return fo._empty_field(-12.6, -12.3, -76.95, -76.65, date(2026, 8, 12))


def test_1_campo_constante_produce_gradiente_cero_valido():
    result = tf.derive_thermal_front(make_field([[20.0] * 3 for _ in range(3)]))
    assert result.status == tf.ThermalFrontStatus.VALIDO
    assert result.n_gradient_cells == 9
    assert all(value == pytest.approx(0.0) for row in result.gradient_c_per_km for value in row)


def test_2_gradiente_zonal_centrado_usa_distancia_haversine():
    values = [[10.0, 11.0, 12.0] for _ in range(3)]
    field = make_field(values)
    result = tf.derive_thermal_front(field)
    distance = tf._haversine_km(field.latitudes[1], field.longitudes[0], field.latitudes[1], field.longitudes[2])
    expected = 2.0 / distance
    assert result.eastward_gradient_c_per_km[1][1] == pytest.approx(expected)
    assert result.northward_gradient_c_per_km[1][1] == pytest.approx(0.0)
    assert result.gradient_c_per_km[1][1] == pytest.approx(expected)
    assert result.method[1][1] == "x:centrada;y:centrada"


def test_3_gradiente_meridional_centrado():
    values = [[10.0] * 3, [11.0] * 3, [12.0] * 3]
    field = make_field(values)
    result = tf.derive_thermal_front(field)
    distance = tf._haversine_km(field.latitudes[0], field.longitudes[1], field.latitudes[2], field.longitudes[1])
    expected = 2.0 / distance
    assert result.northward_gradient_c_per_km[1][1] == pytest.approx(expected)
    assert result.eastward_gradient_c_per_km[1][1] == pytest.approx(0.0)


def test_4_magnitud_combina_las_dos_componentes():
    values = [[10.0, 11.0, 12.0], [11.0, 12.0, 13.0], [12.0, 13.0, 14.0]]
    result = tf.derive_thermal_front(make_field(values))
    dx = result.eastward_gradient_c_per_km[1][1]
    dy = result.northward_gradient_c_per_km[1][1]
    assert result.gradient_c_per_km[1][1] == pytest.approx(np.hypot(dx, dy))


def test_5_bordes_utilizan_diferencias_unilaterales_trazables():
    result = tf.derive_thermal_front(make_field([[10.0, 11.0, 12.0]] * 3))
    assert result.gradient_c_per_km[0][0] is not None
    assert result.method[0][0] == "x:adelante;y:adelante"
    assert result.method[2][2] == "x:atras;y:atras"


def test_6_celda_faltante_no_se_rellena():
    values = [[10.0, 11.0, 12.0], [11.0, None, 13.0], [12.0, 13.0, 14.0]]
    result = tf.derive_thermal_front(make_field(values))
    assert result.gradient_c_per_km[1][1] is None
    assert result.method[1][1] is None
    assert result.n_source_valid_cells == 8


def test_7_sin_vecino_en_un_eje_deja_celda_sin_gradiente():
    values = [[None, 10.0, None], [None, 11.0, None], [None, 12.0, None]]
    result = tf.derive_thermal_front(make_field(values))
    assert result.status == tf.ThermalFrontStatus.SIN_GRADIENTES
    assert result.n_gradient_cells == 0
    assert result.gradient_coverage_fraction == 0.0


def test_8_error_fuente_se_transporta_como_maximo_no_como_incertidumbre_inventada():
    errors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
    result = tf.derive_thermal_front(make_field([[20.0] * 3 for _ in range(3)], errors=errors))
    assert result.source_error_max_c[1][1] == pytest.approx(0.8)
    assert result.source_error_max_c[1][1] != pytest.approx(0.9), "la diagonal no participa"
    assert "uncertainty" not in result.__dataclass_fields__


def test_9_fuente_sin_datos_se_propaga():
    result = tf.derive_thermal_front(empty_source())
    assert result.status == tf.ThermalFrontStatus.FUENTE_SIN_DATOS
    assert result.gradient_c_per_km == ()
    assert result.source_dataset_id == fo.DATASET_ID


def test_10_geometria_inconsistente_lanza_valueerror():
    field = make_field([[20.0] * 3 for _ in range(3)])
    malformed = fo.OstiaField(**{**field.__dict__, "sst_celsius": ((20.0,),)})
    with pytest.raises(ValueError):
        tf.derive_thermal_front(malformed)


def test_11_ejes_no_monotonos_lanzan_valueerror():
    field = make_field([[20.0] * 3 for _ in range(3)], lats=(-12.5, -12.4, -12.45))
    with pytest.raises(ValueError):
        tf.derive_thermal_front(field)


def test_12_reporta_resolucion_efectiva_y_cobertura():
    result = tf.derive_thermal_front(make_field([[20.0] * 3 for _ in range(3)]))
    assert 5.0 < result.median_zonal_resolution_km < 6.0
    assert 5.0 < result.median_meridional_resolution_km < 6.0
    assert result.gradient_coverage_fraction == pytest.approx(1.0)


def test_13_procedencia_derivada_completa_sin_umbral():
    result = tf.derive_thermal_front(make_field([[20.0] * 3 for _ in range(3)]))
    assert result.source_product_id == fo.PRODUCT_ID
    assert result.source_dataset_id == fo.DATASET_ID
    assert result.source_variable == fo.VARIABLE_SST
    assert result.algorithm_version == "finite_difference_haversine_v1"
    assert result.units == "degree_Celsius km-1"
    assert result.source_time_utc == datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
    assert not any("threshold" in name or "score" in name for name in result.__dataclass_fields__)
    assert "no detecta cardúmenes" in result.scope_warning


def test_14_fetch_integrado_usa_un_unico_campo(monkeypatch):
    source = make_field([[20.0] * 3 for _ in range(3)])
    calls = []

    def fake_fetch(*args):
        calls.append(args)
        return source

    monkeypatch.setattr(tf, "fetch_ostia_field", fake_fetch)
    result = tf.fetch_thermal_front(-12.6, -12.3, -76.95, -76.65, date(2026, 8, 12))
    assert calls == [(-12.6, -12.3, -76.95, -76.65, date(2026, 8, 12))]
    assert result.source_time_utc == source.time_utc
    assert result.status == tf.ThermalFrontStatus.VALIDO
