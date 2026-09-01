"""Pruebas sintéticas del diagnóstico ambiental; nunca consultan red."""

import inspect
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

import assembly.environmental_assembler as ea
import diagnostics.diagnose_environmental_30d_pucusana as diag
from ingestion.fetch_mur import MurMode

GENERATED = datetime(2026, 8, 13, 12, tzinfo=timezone.utc)


def governance(variable_id):
    return ea.VariableGovernance(
        description=variable_id,
        intended_role="A",
        implementation_status="implementada_validada_sinteticamente",
        scoring_status="inactiva",
        predictively_valid=None,
        profile="synthetic_profile",
        module="synthetic.py",
    )


def valid_status(variable_id):
    return {
        "sst": "valida_en_ventana",
        "oleaje": "bajo_umbral_regional",
        "clorofila": "valida_en_fecha_local",
        "salinidad": "valida_en_ventana",
        "sst_observed_ostia": "valida_en_fecha_nominal",
        "thermal_front": "valido",
        "temperature_10m": "valida_en_ventana",
        "delta_sst_t10": "valida_en_ventana",
        "surface_currents": "valida_en_ventana",
        "batimetria": "valida",
        "chlorophyll_olci": "valida_en_fecha_nominal",
        "chlorophyll_front": "valido",
        "sst_mur": "historica_final",
        "thermal_gradient_mur": "valido",
    }[variable_id]


def payload(variable_id, target_date):
    stamp = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    value = float(target_date.day)
    common = {
        "dataset_id": f"dataset-{ea.SHARED_OPERATION[variable_id]}",
        "product_id": f"product-{ea.SHARED_OPERATION[variable_id]}",
    }
    if variable_id == "sst":
        return {
            **common,
            "samples": [
                {"time_utc": stamp.isoformat(), "value_celsius": 18.0 + value / 10},
                {
                    "time_utc": (stamp + timedelta(hours=6)).isoformat(),
                    "value_celsius": 19.0 + value / 10,
                },
            ],
            "coverage_fraction": 1.0,
            "cell_lat": -12.5,
            "cell_lon": -76.75,
        }
    if variable_id == "oleaje":
        return {
            **common,
            "significant_wave_height_m": 1.0 + value / 100,
            "max_time_utc": (stamp + timedelta(hours=18)).isoformat(),
            "cell_lat": -12.5,
            "cell_lon": -76.75,
        }
    if variable_id == "clorofila":
        return {
            **common,
            "value_mg_m3": 2.0 + value / 100,
            "time_utc": stamp.isoformat(),
            "inside_requested_local_date": True,
            "cell_lat": -12.5,
            "cell_lon": -76.75,
        }
    if variable_id == "salinidad":
        return {
            **common,
            "samples": [
                {"time_utc": stamp.isoformat(), "value_salinity": 34.0 + value / 100}
            ],
            "coverage_fraction": 0.75,
            "cell_lat": -12.5,
            "cell_lon": -76.75,
        }
    if variable_id == "sst_observed_ostia":
        source = (
            stamp
            if target_date.day == 10
            else datetime(2026, 8, 10, tzinfo=timezone.utc)
        )
        return {
            **common,
            "time_utc": source.isoformat(),
            "nominal_product_date": source.date().isoformat(),
            "matches_requested_nominal_date": target_date.day == 10,
            "sst_celsius": [[18.0 + value / 10, 19.0 + value / 10]],
            "analysis_error_kelvin": [[0.2, 0.3]],
            "coverage_fraction": 1.0,
        }
    if variable_id == "thermal_front":
        source = (
            stamp
            if target_date.day == 10
            else datetime(2026, 8, 10, tzinfo=timezone.utc)
        )
        return {
            **common,
            "source_time_utc": source.isoformat(),
            "source_nominal_product_date": source.date().isoformat(),
            "gradient_c_per_km": [[0.1, 0.2]],
            "eastward_gradient_c_per_km": [[0.08, 0.16]],
            "northward_gradient_c_per_km": [[0.06, 0.12]],
            "gradient_coverage_fraction": 1.0,
        }
    if variable_id in {"temperature_10m", "delta_sst_t10"}:
        return {
            **common,
            "samples": [
                {
                    "time_utc": stamp.isoformat(),
                    "temperature_10m_celsius": 17.0 + value / 10,
                    "delta_sst_t10_celsius": 1.0 + value / 100,
                }
            ],
            "coverage_fraction": 1.0,
            "cell_lat": -12.5,
            "cell_lon": -76.75,
        }
    if variable_id == "surface_currents":
        return {
            **common,
            "measurements": [
                {
                    "time_utc": stamp.isoformat(),
                    "uo_m_s": -0.1,
                    "vo_m_s": 0.2,
                    "speed_m_s": 0.2236,
                    "direction_toward_deg": 350.0,
                    "cell_lat": -12.5,
                    "cell_lon": -76.75,
                },
                {
                    "time_utc": (stamp + timedelta(hours=6)).isoformat(),
                    "uo_m_s": 0.1,
                    "vo_m_s": 0.2,
                    "speed_m_s": 0.2236,
                    "direction_toward_deg": 10.0,
                    "cell_lat": -12.5,
                    "cell_lon": -76.75,
                },
            ],
            "n_measurements": 2,
            "expected_instants": 4,
        }
    if variable_id == "batimetria":
        return {
            **common,
            "depth_m": 42.0,
            "slope_deg": 3.5,
            "tid_code": 10,
            "cell_lat": -12.471,
            "cell_lon": -76.790,
            "product_version": "2026",
        }
    if variable_id == "chlorophyll_olci":
        source = (
            datetime(2026, 8, 10, tzinfo=timezone.utc)
            if target_date.day == 12
            else stamp
        )
        return {
            **common,
            "time_utc": source.isoformat(),
            "nominal_product_date": source.date().isoformat(),
            "matches_requested_nominal_date": source.date() == target_date,
            "coverage_fraction": 0.25,
            "availability_as_of_verified": False,
            "grid": {
                "chlorophyll_mg_m3": [[1.1, None], [1.2, 1.3]],
                "uncertainty_pct": [[20.0, None], [22.0, 24.0]],
            },
        }
    if variable_id == "chlorophyll_front":
        source = (
            datetime(2026, 8, 10, tzinfo=timezone.utc)
            if target_date.day == 12
            else stamp
        )
        return {
            **common,
            "source_time_utc": source.isoformat(),
            "source_nominal_product_date": source.date().isoformat(),
            "source_status": (
                "valida_reciente"
                if source.date() != target_date
                else "valida_en_fecha_nominal"
            ),
            "availability_as_of_verified": False,
            "gradient_coverage_fraction": 0.1,
            "gradient_mg_m3_per_km": [[0.02]],
            "eastward_gradient_mg_m3_per_km": [[0.01]],
            "northward_gradient_mg_m3_per_km": [[0.017]],
        }
    if variable_id == "sst_mur":
        source = datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
        return {
            **common,
            "time_utc": source.isoformat(),
            "nominal_product_date": source.date().isoformat(),
            "matches_requested_nominal_date": target_date.day == 10,
            "coverage_fraction": 1.0,
            "availability_as_of_verified": False,
            "operational_use_verified": False,
            "grid": {
                "sst_celsius": [[18.5, 18.6]],
                "analysis_error_kelvin": [[0.3, 0.3]],
                "dt_1km_hours": [[-7, -6]],
            },
            "provenance": {
                "dataset_id": "MUR-JPL-L4-GLOB-v4.1",
                "collection_id": "C1996881146-POCLOUD",
                "product_version": "04.1",
                "source_file_name": "mur-20260810.nc4",
                "source_file_sha256": "a" * 64,
                "operational_use_verified": False,
            },
        }
    if variable_id == "thermal_gradient_mur":
        source = datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
        return {
            **common,
            "source_status": "historica_final",
            "source_time_utc": source.isoformat(),
            "source_nominal_product_date": source.date().isoformat(),
            "gradient_coverage_fraction": 0.8,
            "gradient_c_per_km": [[0.03]],
            "eastward_gradient_c_per_km": [[0.02]],
            "northward_gradient_c_per_km": [[0.01]],
            "source_provenance": {
                "dataset_id": "MUR-JPL-L4-GLOB-v4.1",
                "collection_id": "C1996881146-POCLOUD",
                "product_version": "04.1",
                "source_file_name": "mur-20260810.nc4",
                "source_file_sha256": "a" * 64,
                "availability_as_of_verified": False,
                "operational_use_verified": False,
            },
        }
    raise AssertionError(variable_id)


def make_snapshot(request, *, chlorophyll_options, mur_options):
    variable_order = ea.VARIABLE_ORDER
    if chlorophyll_options is not None:
        variable_order += ea.OPTIONAL_VARIABLE_ORDER
    if mur_options is not None:
        variable_order += ea.MUR_VARIABLE_ORDER
    results = []
    for variable_id in variable_order:
        state = ea.AssemblyState.AVAILABLE
        source_status = valid_status(variable_id)
        body = payload(variable_id, request.target_date)
        error_code = None
        if request.target_date.day == 11 and variable_id in ea.OPTIONAL_VARIABLE_ORDER:
            state = ea.AssemblyState.NO_DATA
            source_status = (
                "sin_datos" if variable_id == "chlorophyll_olci" else "fuente_sin_datos"
            )
            body = {
                "reason": "no_admissible_time",
                "source_reason": "no_admissible_time",
            }
        if request.target_date.day == 12 and variable_id == "chlorophyll_olci":
            source_status = "valida_reciente"
        if request.target_date.day == 11 and variable_id == "salinidad":
            source_status = "valida_cercana_en_tiempo"
        if request.target_date.day == 12 and variable_id == "surface_currents":
            state = ea.AssemblyState.ERROR
            source_status = None
            body = None
            error_code = "provider_exception"
        results.append(
            ea.VariableResult(
                variable_id=variable_id,
                state=state,
                source_status=source_status,
                source_type="SyntheticReading",
                shared_operation=ea.SHARED_OPERATION[variable_id],
                spatial_scope=ea.SPATIAL_SCOPE_BY_VARIABLE[variable_id],
                value_paths=ea.VALUE_PATHS[variable_id],
                governance=governance(variable_id),
                payload=body,
                error_code=error_code,
                error_type="RuntimeError" if error_code else None,
            )
        )
    available = sum(result.state is ea.AssemblyState.AVAILABLE for result in results)
    no_data = sum(result.state is ea.AssemblyState.NO_DATA for result in results)
    errors = sum(result.state is ea.AssemblyState.ERROR for result in results)
    return ea.EnvironmentalSnapshot(
        schema_version=(
            ea.OLCI_MUR_SCHEMA_VERSION
            if chlorophyll_options and mur_options
            else ea.OLCI_SCHEMA_VERSION
            if chlorophyll_options
            else ea.MUR_SCHEMA_VERSION
            if mur_options
            else ea.SCHEMA_VERSION
        ),
        request=request,
        spatial_context=ea.SpatialContext(
            operational_range_min_km=0.0,
            operational_range_max_km=10.0,
            operational_range_basis="distance_offshore_from_coastline",
            operational_range_is_radius_from_request_point=False,
            operational_bounding_box_defined=False,
            field_half_width_deg=request.field_half_width_deg,
            field_is_operational_domain=False,
            field_scope_relation="regional_context_not_operational_domain",
            field_purpose="synthetic",
        ),
        status=(
            ea.OverallAssemblyStatus.COMPLETE
            if not no_data and not errors
            else ea.OverallAssemblyStatus.PARTIAL
        ),
        variables=tuple(results),
        available_count=available,
        no_data_count=no_data,
        error_count=errors,
        safety=ea.SafetySummary(
            blocked=False,
            source_variable="oleaje",
            source_status="bajo_umbral_regional",
            reason="below_provisional_regional_threshold",
        ),
        chlorophyll_options=chlorophyll_options,
        mur_options=mur_options,
    )


def run_report(*, include_olci=True, include_mur=True):
    calls = []

    def assembler(request, **kwargs):
        calls.append((request, kwargs))
        return make_snapshot(
            request,
            chlorophyll_options=kwargs["chlorophyll_options"],
            mur_options=kwargs["mur_options"],
        )

    report = diag.run_diagnostic(
        date(2026, 8, 12),
        days=3,
        include_olci=include_olci,
        include_mur=include_mur,
        generated_at_utc=GENERATED,
        assembler=assembler,
    )
    return report, calls


def by_id(report, variable_id):
    return next(item for item in report.variables if item.variable_id == variable_id)


def test_1_fecha_default_usa_ultimo_dia_local_completo():
    assert diag.default_end_date(datetime(2026, 9, 1, 1, tzinfo=timezone.utc)) == date(
        2026, 8, 30
    )
    with pytest.raises(ValueError):
        diag.default_end_date(datetime(2026, 9, 1, 1))


def test_2_recorrido_ordenado_activa_14_variables_y_diez_operaciones():
    report, calls = run_report()

    assert [call[0].target_date for call in calls] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert (
        report.variables_expected
        == ea.VARIABLE_ORDER + ea.OPTIONAL_VARIABLE_ORDER + ea.MUR_VARIABLE_ORDER
    )
    assert len(report.variables) == 14
    assert report.n_independent_source_operations == 10
    assert report.requested_start_date == date(2026, 8, 10)
    assert report.requested_end_date == date(2026, 8, 12)
    assert all(call[0].lat == -12.471 and call[0].lon == -76.790 for call in calls)


def test_3_as_of_historico_es_explicito_acotado_y_mur_no_se_disfraza_de_nrt():
    report, calls = run_report()

    assert calls[0][1]["chlorophyll_options"].as_of_utc == datetime(
        2026, 8, 12, tzinfo=timezone.utc
    )
    assert calls[-1][1]["chlorophyll_options"].as_of_utc == GENERATED
    assert all(
        isinstance(call[1]["chlorophyll_options"], diag.HistoricalChlorophyllOptions)
        for call in calls
    )
    assert all(
        call[1]["chlorophyll_mode"] is diag.OpticalMode.HISTORICAL_DIAGNOSTIC
        for call in calls
    )
    assert all(
        call[1]["mur_options"].mode is MurMode.HISTORICAL_DIAGNOSTIC for call in calls
    )
    assert report.mur_mode == "historical_diagnostic"
    assert report.optical_mode == "historical_diagnostic"
    mur = by_id(report, "sst_mur")
    mur_gradient = by_id(report, "thermal_gradient_mur")
    assert mur.days_historical_final == 3
    assert mur_gradient.days_historical_final == 3
    assert mur.availability_verification_declared_days == 3
    assert mur.availability_verified_days == 0
    assert mur.operational_verified_days == 0


def test_4_agrega_disponibilidad_huecos_errores_y_fallback_sin_clasificar():
    report, _ = run_report()

    olci = by_id(report, "chlorophyll_olci")
    salinity = by_id(report, "salinidad")
    currents = by_id(report, "surface_currents")
    assert (olci.days_available, olci.days_no_data, olci.days_error) == (2, 1, 0)
    assert olci.no_data_dates == (date(2026, 8, 11),)
    assert salinity.days_using_fallback == 1
    assert olci.days_using_fallback == 1
    assert by_id(report, "chlorophyll_front").days_using_fallback == 1
    assert olci.source_reason_counts == (diag.StatusCount("no_admissible_time", 1),)
    assert currents.days_error == 1
    assert currents.error_dates == (date(2026, 8, 12),)
    assert all(
        item.technical_classification == "pending_human_review"
        for item in report.variables
    )
    assert all(item.scoring_status == "inactiva" for item in report.variables)
    assert all(item.predictively_valid is None for item in report.variables)


def test_5_resume_valores_declarados_y_no_suma_derivadas_como_fuentes():
    report, _ = run_report()

    sst = by_id(report, "sst")
    ostia = by_id(report, "sst_observed_ostia")
    front = by_id(report, "thermal_front")
    assert sst.metrics[0].count == 6
    assert sst.metrics[0].minimum == pytest.approx(19.0)
    assert sst.metrics[0].maximum == pytest.approx(20.2)
    assert sst.days_with_primary_values == 3
    assert ostia.shared_operation == front.shared_operation == "ostia_field"
    operation = next(
        item
        for item in report.independent_source_operations
        if item.shared_operation == "ostia_field"
    )
    assert operation.variables == ("sst_observed_ostia", "thermal_front")


def test_6_direccion_se_resume_circularmente_y_tid_no_se_promedia():
    report, _ = run_report()
    currents = by_id(report, "surface_currents")
    direction = next(
        metric
        for metric in currents.metrics
        if metric.path == "measurements[].direction_toward_deg"
    )
    tid = next(
        metric
        for metric in by_id(report, "batimetria").metrics
        if metric.path == "tid_code"
    )

    assert direction.aggregation == "circular_degrees"
    assert direction.circular_mean_degrees == pytest.approx(0.0, abs=1e-10)
    assert direction.circular_resultant_length > 0.98
    assert direction.mean is None and direction.span is None
    assert tid.aggregation == "categorical_values_not_averaged"
    assert tid.distinct_values == (10,)
    assert tid.count == 1, "la fuente estática no debe ponderarse treinta veces"
    assert tid.mean is None


def test_7_detecta_reutilizacion_temporal_y_estabilidad_de_celda():
    report, _ = run_report()
    mur = by_id(report, "sst_mur")
    sst = by_id(report, "sst")

    assert mur.reused_source_records > 0
    assert mur.unique_source_records < mur.source_records_total
    assert mur.metric_source_records == 1
    assert mur.metrics[0].count == 2
    assert sst.reused_source_records == 0
    assert sst.selected_cells_stable is True
    assert by_id(report, "chlorophyll_olci").metric_source_records == 1
    assert by_id(report, "chlorophyll_front").metric_source_records == 1
    assert by_id(report, "batimetria").unique_source_records == 1
    assert by_id(report, "batimetria").reused_source_records == 2


def test_8_json_solo_contiene_resumen_y_no_payloads_o_matrices_crudas():
    report, _ = run_report()
    text = diag.report_to_json(report)
    document = json.loads(text)

    assert document["schema_version"] == "environmental_30d_diagnostic_v2"
    assert document["days_requested"] == 3
    assert "payload" not in text
    assert "sst_kelvin" not in text
    assert "scope_warning" not in text
    daily_variable = document["days"][0]["variables"][0]
    assert set(daily_variable) == {
        "requested_date",
        "variable_id",
        "state",
        "source_status",
        "shared_operation",
        "spatial_scope",
        "primary_value_count",
        "coverage_fraction",
        "fallback_used",
        "historical_final_used",
        "source_time_keys",
        "source_record_key",
        "selected_cell_keys",
        "source_reasons",
        "source_error_types",
        "availability_as_of_verified",
        "operational_use_verified",
        "metrics",
        "error_code",
        "error_type",
    }
    assert document["provenance"]["implementation_version"] == (
        "environmental_30d_diagnostic_v2"
    )
    assert len(document["provenance"]["variables_spec_sha256"]) == 64
    mur_files = next(
        item["source_identity"]["source_files"]
        for item in document["variables"]
        if item["variable_id"] == "sst_mur"
    )
    assert mur_files == [{"file_name": "mur-20260810.nc4", "sha256": "a" * 64}]


def test_9_formato_humano_declara_limites_y_fechas_problematicas():
    report, _ = run_report()
    output = diag.format_report(report)

    assert "DIAGNÓSTICO AMBIENTAL CONSOLIDADO" in output
    assert "chlorophyll_olci: disponible=2/3" in output
    assert "fechas_sin_dato: 2026-08-11" in output
    assert "fechas_error: 2026-08-12" in output
    assert "no demuestra utilidad pesquera" in output
    assert "No se activa scoring" in output
    assert "DECISIÓN: clasificación técnica pendiente" in output
    assert "[[18.5" not in output


def test_10_sin_capas_opcionales_conserva_contrato_base_y_no_crea_opciones():
    report, calls = run_report(include_olci=False, include_mur=False)

    assert report.variables_expected == ea.VARIABLE_ORDER
    assert len(report.variables) == 10
    assert report.n_independent_source_operations == 8
    assert report.mur_mode is None
    assert all(call[1]["chlorophyll_options"] is None for call in calls)
    assert all(call[1]["mur_options"] is None for call in calls)


def test_11_batimetria_estatica_se_consulta_una_sola_vez_por_punto():
    calls = []
    providers = replace(
        ea.AssemblerProviders(),
        fetch_bathymetry=lambda lat, lon: calls.append((lat, lon)) or object(),
    )
    cached = diag._cached_bathymetry(providers)

    first = cached.fetch_bathymetry(-12.471, -76.790)
    second = cached.fetch_bathymetry(-12.471, -76.790)
    third = cached.fetch_bathymetry(-12.470, -76.790)
    assert first is second
    assert third is not first
    assert calls == [(-12.471, -76.79), (-12.47, -76.79)]


@pytest.mark.parametrize(
    ("end_date", "days", "hours", "generated"),
    [
        (datetime(2026, 8, 12), 1, (0, 23), GENERATED),
        (date(2026, 8, 12), 0, (0, 23), GENERATED),
        (date(2026, 8, 12), 32, (0, 23), GENERATED),
        (date(2026, 8, 12), 1, (20, 10), GENERATED),
        (date(2026, 8, 13), 1, (0, 23), GENERATED),
        (date(2026, 8, 12), 1, (0, 23), datetime(2026, 8, 13, 12)),
    ],
)
def test_12_argumentos_invalidos_fallan_antes_de_ensamblar(
    end_date, days, hours, generated
):
    touched = False

    def assembler(*_args, **_kwargs):
        nonlocal touched
        touched = True

    with pytest.raises((ValueError, TypeError)):
        diag.run_diagnostic(
            end_date,
            days=days,
            hour_start=hours[0],
            hour_end=hours[1],
            generated_at_utc=generated,
            assembler=assembler,
        )
    assert touched is False


def test_13_cli_distingue_completo_parcial_y_error(monkeypatch, capsys):
    report, _ = run_report()
    complete = replace(
        report,
        variables=tuple(
            replace(item, days_available=3, days_no_data=0, days_error=0)
            for item in report.variables
        ),
    )
    partial = replace(
        complete,
        variables=(
            replace(complete.variables[0], days_available=2, days_no_data=1),
            *complete.variables[1:],
        ),
    )

    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: complete)
    assert diag.main(["--end-date", "2026-08-12", "--days", "3"]) == 0
    assert "RESUMEN POR VARIABLE" in capsys.readouterr().out
    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: partial)
    assert diag.main(["--end-date", "2026-08-12", "--days", "3", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["days_requested"] == 3
    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: report)
    assert diag.main(["--end-date", "2026-08-12", "--days", "3"]) == 4
    capsys.readouterr()


def test_14_modulo_no_abre_imarpe_no_guarda_archivos_y_no_implementa_scoring():
    source = inspect.getsource(diag)
    assert "inspect_imarpe" not in source
    assert "PREDICTAMAR_IMARPE" not in source
    assert "write_text" not in source
    assert "to_netcdf" not in source
    assert "score(" not in source
    assert "predictively_valid=True" not in source
    assert diag.STATIC_VARIABLES == {"batimetria"}
