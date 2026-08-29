"""Suite sintética del par temperature_10m + delta_sst_t10.

No consulta Copernicus. Cada caso verifica que ambos niveles permanezcan
unidos por dataset, timestamp y celda, y que no aparezca interpolación.
"""

from datetime import date, datetime, timezone

import numpy as np
import pytest
import xarray as xr

import ingestion.fetch_vertical_temperature as fvt

LAT = -12.471
LON = -76.790
CELL_LAT = -12.5
LON_NEAR = -76.75
LON_FAR = -76.833333
LON_TOO_FAR = -76.900
TARGET_DATE = date(2026, 8, 12)

SURFACE = fvt.OFFICIAL_SURFACE_DEPTH_M
TARGET_10M = fvt.OFFICIAL_NEAREST_10M_DEPTH_M
DEEPER = 11.404999732971191

NATIVE_TIMES = [
    datetime(2026, 8, 12, 6),
    datetime(2026, 8, 12, 12),
    datetime(2026, 8, 12, 18),
    datetime(2026, 8, 13, 0),
]


def build_dataset(times, lons, values, depths=(SURFACE, TARGET_10M, DEEPER)):
    """values usa claves (depth, lon) con una lista por timestamp."""
    data = np.full((len(times), len(depths), 1, len(lons)), np.nan, dtype=float)
    for depth_index, depth in enumerate(depths):
        for lon_index, lon in enumerate(lons):
            series = values.get((depth, lon), [np.nan] * len(times))
            data[:, depth_index, 0, lon_index] = series
    return xr.Dataset(
        {
            fvt.VARIABLE: (
                ("time", "depth", "latitude", "longitude"),
                data,
            )
        },
        coords={
            "time": list(times),
            "depth": list(depths),
            "latitude": [CELL_LAT],
            "longitude": list(lons),
        },
    )


@pytest.fixture
def patch_open_dataset(monkeypatch):
    calls = []

    def install(ds=None, error=None):
        def fake_open(**kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error
            return ds

        monkeypatch.setattr(fvt.copernicusmarine, "open_dataset", fake_open)
        return calls

    return install


def complete_values(lon=LON_NEAR):
    return {
        (SURFACE, lon): [21.0, 21.2, 21.4, 21.6],
        (TARGET_10M, lon): [19.0, 19.1, 19.2, 19.3],
        (DEEPER, lon): [5.0, 5.0, 5.0, 5.0],
    }


def test_1_par_valido_misma_celda_instante_y_formula(patch_open_dataset):
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values()))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.VALIDA_EN_VENTANA
    assert reading.n_native_times_in_window == 4
    assert reading.n_pairs == 4
    assert reading.n_missing_pairs == 0
    assert reading.coverage_fraction == pytest.approx(1.0)
    assert reading.cell_lon == pytest.approx(LON_NEAR)
    assert [sample.delta_sst_t10_celsius for sample in reading.samples] == pytest.approx(
        [2.0, 2.1, 2.2, 2.3]
    )
    assert all(sample.inside_requested_window for sample in reading.samples)


def test_2_gana_celda_con_mas_pares_completos(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [30.0, np.nan, np.nan, np.nan],
        (TARGET_10M, LON_NEAR): [20.0, np.nan, np.nan, np.nan],
        (SURFACE, LON_FAR): [21.0, 21.1, 21.2, 21.3],
        (TARGET_10M, LON_FAR): [19.0, 19.1, 19.2, 19.3],
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR, LON_FAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.cell_lon == pytest.approx(LON_FAR)
    assert reading.n_pairs == 4
    assert [sample.surface_temperature_celsius for sample in reading.samples] == pytest.approx(
        [21.0, 21.1, 21.2, 21.3]
    )


def test_3_empate_de_cobertura_gana_celda_mas_cercana(patch_open_dataset):
    values = {}
    for lon, offset in ((LON_NEAR, 1.0), (LON_FAR, 2.0)):
        values[(SURFACE, lon)] = [21.0 + offset] * 4
        values[(TARGET_10M, lon)] = [19.0 + offset] * 4
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_FAR, LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.cell_lon == pytest.approx(LON_NEAR)
    assert reading.distance_km == pytest.approx(5.409, abs=0.01)


def test_4_no_construye_par_cruzando_celdas(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [21.0] * 4,
        (TARGET_10M, LON_NEAR): [np.nan] * 4,
        (SURFACE, LON_FAR): [np.nan] * 4,
        (TARGET_10M, LON_FAR): [19.0] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR, LON_FAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.samples == ()
    assert reading.cell_lon is None


def test_5_no_construye_par_cruzando_timestamps(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [21.0, np.nan, 21.2, np.nan],
        (TARGET_10M, LON_NEAR): [np.nan, 19.0, np.nan, 19.2],
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.n_native_times_in_window == 4
    assert reading.n_pairs == 0
    assert reading.n_missing_pairs == 4
    assert reading.coverage_fraction == 0.0


def test_6_cobertura_parcial_cuenta_pares_no_valores_sueltos(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [21.0, 21.1, 21.2, 21.3],
        (TARGET_10M, LON_NEAR): [19.0, np.nan, 19.2, np.nan],
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.n_pairs == 2
    assert reading.n_missing_pairs == 2
    assert reading.coverage_fraction == pytest.approx(0.5)
    assert [sample.time_utc.hour for sample in reading.samples] == [6, 18]


def test_7_elige_nivel_nativo_mas_cercano_y_declara_profundidades(patch_open_dataset):
    depths = (DEEPER, SURFACE, TARGET_10M)
    patch_open_dataset(
        build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values(), depths=depths)
    )

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.surface_depth_actual_m == pytest.approx(SURFACE)
    assert reading.temperature_10m_depth_requested_m == 10.0
    assert reading.temperature_10m_depth_actual_m == pytest.approx(TARGET_10M)
    assert reading.temperature_10m_depth_actual_m != 10.0
    assert reading.vertical_separation_m == pytest.approx(TARGET_10M - SURFACE)


def test_8_rechaza_esquema_sin_nivel_cercano_a_10m(patch_open_dataset):
    shallow = 7.92956018447876
    depths = (SURFACE, shallow)
    values = {
        (SURFACE, LON_NEAR): [21.0] * 4,
        (shallow, LON_NEAR): [19.0] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values, depths=depths))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.temperature_10m_depth_actual_m is None


def test_9_nivel_10m_nan_no_se_convierte_en_cero(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [21.0] * 4,
        (TARGET_10M, LON_NEAR): [np.nan] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.samples == ()
    assert reading.n_pairs == 0


def test_10_fallback_temporal_exacto_usa_ambos_niveles_juntos(patch_open_dataset):
    before = datetime(2026, 8, 12, 4)
    values = {
        (SURFACE, LON_NEAR): [22.0],
        (TARGET_10M, LON_NEAR): [20.0],
    }
    patch_open_dataset(build_dataset([before], [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE, 2, 5)

    assert reading.status == fvt.VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO
    assert reading.n_native_times_in_window == 0
    assert reading.coverage_fraction is None
    assert reading.n_pairs == 1
    sample = reading.samples[0]
    assert sample.temporal_offset_hours == pytest.approx(3.0)
    assert sample.delta_sst_t10_celsius == pytest.approx(2.0)
    assert sample.inside_requested_window is False


def test_11_fallback_no_acepta_medio_par(patch_open_dataset):
    before = datetime(2026, 8, 12, 4)
    values = {
        (SURFACE, LON_NEAR): [22.0],
        (TARGET_10M, LON_NEAR): [np.nan],
    }
    patch_open_dataset(build_dataset([before], [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE, 2, 5)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.samples == ()


def test_12_fallback_equivalente_prefiere_timestamp_anterior(patch_open_dataset):
    before = datetime(2026, 8, 12, 4)
    after = datetime(2026, 8, 12, 13, 59, 59)
    values = {
        (SURFACE, LON_NEAR): [30.0, 20.0],
        (TARGET_10M, LON_NEAR): [25.0, 19.0],
    }
    patch_open_dataset(build_dataset([after, before], [LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE, 2, 5)

    assert reading.samples[0].time_utc == before.replace(tzinfo=timezone.utc)
    assert reading.samples[0].surface_temperature_celsius == pytest.approx(20.0)
    assert reading.samples[0].delta_sst_t10_celsius == pytest.approx(1.0)


def test_13_rechazo_espacial_no_expone_celda(patch_open_dataset):
    patch_open_dataset(
        build_dataset(NATIVE_TIMES, [LON_TOO_FAR], complete_values(LON_TOO_FAR))
    )

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.cell_lat is None and reading.cell_lon is None
    assert reading.distance_km is None


def test_14_consulta_unica_versionada_y_sin_nearest(patch_open_dataset):
    calls = patch_open_dataset(
        build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values())
    )

    fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["dataset_id"] == fvt.DATASET_ID
    assert kwargs["dataset_version"] == fvt.DATASET_VERSION
    assert kwargs["dataset_part"] == fvt.DATASET_PART
    assert kwargs["variables"] == [fvt.VARIABLE]
    assert kwargs["maximum_depth"] == fvt.DEPTH_QUERY_MAX_M
    assert "minimum_depth" not in kwargs
    assert "coordinates_selection_method" not in kwargs


@pytest.mark.parametrize(
    ("lat", "lon", "target_date", "hours"),
    [
        (float("nan"), LON, TARGET_DATE, (0, 23)),
        (LAT, 181.0, TARGET_DATE, (0, 23)),
        (LAT, LON, datetime(2026, 8, 12), (0, 23)),
        (LAT, LON, TARGET_DATE, (10, 5)),
    ],
)
def test_15_argumentos_invalidos_fallan_antes_de_red(
    monkeypatch, lat, lon, target_date, hours
):
    touched = False

    def unexpected_open(**_kwargs):
        nonlocal touched
        touched = True

    monkeypatch.setattr(fvt.copernicusmarine, "open_dataset", unexpected_open)
    with pytest.raises(ValueError):
        fvt.fetch_vertical_thermal_pair(lat, lon, target_date, *hours)
    assert touched is False


def test_16_fallo_de_fuente_es_sin_datos_trazable(patch_open_dataset):
    patch_open_dataset(error=RuntimeError("fallo sintético sin credenciales"))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.samples == ()
    assert reading.dataset_id == fvt.DATASET_ID
    assert reading.dataset_version == fvt.DATASET_VERSION
    assert reading.scope_warning == fvt.DATA_SCOPE_WARNING


def test_17_procedencia_distingue_delta_de_gradiente(patch_open_dataset):
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values()))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.delta_formula == "thetao_surface - thetao_nearest_native_10m"
    assert reading.surface_source == "thetao_model_surface"
    assert reading.uses_ostia is False
    assert reading.units_temperature == "degree_Celsius"
    assert reading.algorithm_version == "vertical_thermal_pair_v1"
    assert "diferencia, no un gradiente" in reading.scope_warning
    assert not hasattr(reading.samples[0], "vertical_gradient_c_per_m")
    assert "no detecta cardúmenes" in reading.scope_warning
    assert "no usa sst_observed_ostia" in reading.scope_warning


def test_18_cruce_utc_conserva_fecha_y_hora_local(patch_open_dataset):
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values()))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    last = reading.samples[-1]
    assert last.time_utc == datetime(2026, 8, 13, 0, tzinfo=timezone.utc)
    assert last.time_local.date() == TARGET_DATE
    assert last.time_local.hour == 19


def test_19_alias_publico_devuelve_mismo_contrato(patch_open_dataset):
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], complete_values()))

    reading = fvt.fetch_temperature_10m_pair(LAT, LON, TARGET_DATE)

    assert isinstance(reading, fvt.VerticalThermalReading)
    assert reading.n_pairs == 4


def test_20_delta_usa_valores_nativos_sin_interpolacion(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [20.123456] * 4,
        (TARGET_10M, LON_NEAR): [19.987654] * 4,
        (DEEPER, LON_NEAR): [-999.0] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values))

    sample = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE).samples[0]

    assert sample.temperature_10m_celsius == pytest.approx(19.987654)
    assert sample.delta_sst_t10_celsius == pytest.approx(20.123456 - 19.987654)
    assert sample.temperature_10m_celsius != -999.0


def test_21_rechaza_falsa_superficie_si_cambia_el_esquema(patch_open_dataset):
    shifted_surface = (
        SURFACE + fvt.MAX_SURFACE_DEPTH_DEVIATION_M + 0.01
    )
    depths = (shifted_surface, TARGET_10M, DEEPER)
    values = {
        (shifted_surface, LON_NEAR): [21.0] * 4,
        (TARGET_10M, LON_NEAR): [19.0] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values, depths=depths))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE)

    assert reading.status == fvt.VerticalThermalStatus.SIN_DATOS
    assert reading.surface_depth_actual_m is None
    assert reading.temperature_10m_depth_actual_m is None


def test_22_delta_conserva_signo_en_inversion_termica(patch_open_dataset):
    values = {
        (SURFACE, LON_NEAR): [18.5] * 4,
        (TARGET_10M, LON_NEAR): [19.2] * 4,
    }
    patch_open_dataset(build_dataset(NATIVE_TIMES, [LON_NEAR], values))

    sample = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE).samples[0]

    assert sample.delta_sst_t10_celsius == pytest.approx(-0.7)


def test_23_fallback_elige_la_celda_completa_mas_cercana(patch_open_dataset):
    before = datetime(2026, 8, 12, 4)
    values = {
        (SURFACE, LON_NEAR): [22.0],
        (TARGET_10M, LON_NEAR): [20.0],
        (SURFACE, LON_FAR): [30.0],
        (TARGET_10M, LON_FAR): [25.0],
    }
    patch_open_dataset(build_dataset([before], [LON_FAR, LON_NEAR], values))

    reading = fvt.fetch_vertical_thermal_pair(LAT, LON, TARGET_DATE, 2, 5)

    assert reading.status == fvt.VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO
    assert reading.cell_lon == pytest.approx(LON_NEAR)
    assert reading.samples[0].surface_temperature_celsius == pytest.approx(22.0)
    assert reading.samples[0].delta_sst_t10_celsius == pytest.approx(2.0)
