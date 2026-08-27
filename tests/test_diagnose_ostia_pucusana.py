"""Pruebas sintéticas del diagnosticador OSTIA; nunca consultan Copernicus."""

import inspect
import json
from datetime import date, datetime, timezone

import pytest

import derivation.thermal_front as tf
import diagnostics.diagnose_ostia_pucusana as diag
import ingestion.fetch_ostia as fo


def make_field(
    target_date: date,
    values=((19.0, 20.0, 21.0), (20.0, 21.0, 22.0), (21.0, 22.0, 23.0)),
    errors=None,
    source_time: datetime | None = None,
    status: fo.OstiaStatus = fo.OstiaStatus.VALIDA_EN_FECHA_LOCAL,
):
    rows = len(values)
    cols = len(values[0]) if rows else 0
    errors = errors or tuple(tuple(0.2 for _ in range(cols)) for _ in range(rows))
    source_time = source_time or datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        12,
        tzinfo=timezone.utc,
    )
    valid = sum(value is not None for row in values for value in row)
    return fo.OstiaField(
        requested_date=target_date,
        minimum_latitude=diag.DEFAULT_BBOX.minimum_latitude,
        maximum_latitude=diag.DEFAULT_BBOX.maximum_latitude,
        minimum_longitude=diag.DEFAULT_BBOX.minimum_longitude,
        maximum_longitude=diag.DEFAULT_BBOX.maximum_longitude,
        time_utc=source_time,
        time_local=source_time.astimezone(fo.TZ_PUCUSANA),
        temporal_age_hours=17.0,
        inside_requested_local_date=status == fo.OstiaStatus.VALIDA_EN_FECHA_LOCAL,
        latitudes=tuple(-12.50 + 0.05 * i for i in range(rows)),
        longitudes=tuple(-76.85 + 0.05 * j for j in range(cols)),
        sst_kelvin=tuple(
            tuple(None if value is None else value + 273.15 for value in row)
            for row in values
        ),
        sst_celsius=tuple(tuple(value for value in row) for row in values),
        analysis_error_kelvin=tuple(tuple(value for value in row) for row in errors),
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
        status=status,
    )


def empty_field(target_date: date):
    return fo._empty_field(
        diag.DEFAULT_BBOX.minimum_latitude,
        diag.DEFAULT_BBOX.maximum_latitude,
        diag.DEFAULT_BBOX.minimum_longitude,
        diag.DEFAULT_BBOX.maximum_longitude,
        target_date,
    )


def build_report(fields, generated_at=None):
    by_date = {field.requested_date: field for field in fields}

    def fetcher(_min_lat, _max_lat, _min_lon, _max_lon, target_date):
        return by_date[target_date]

    return diag.run_diagnostic(
        end_date=max(by_date),
        days=len(by_date),
        fetcher=fetcher,
        generated_at_utc=generated_at
        or datetime(2026, 8, 27, 15, tzinfo=timezone.utc),
    )


def test_1_fecha_default_es_ayer_en_pucusana():
    now = datetime(2026, 8, 27, 15, tzinfo=timezone.utc)
    assert diag.default_end_date(now) == date(2026, 8, 26)
    with pytest.raises(ValueError):
        diag.default_end_date(datetime(2026, 8, 27, 15))  # noqa: DTZ001


def test_2_recuadro_es_tecnico_y_no_redefine_el_alcance_operativo():
    assert diag.DEFAULT_BBOX == diag.BoundingBox(-12.60, -12.30, -76.95, -76.65)
    assert "técnico" in diag.TECHNICAL_BBOX_NOTE.lower()
    assert "no equivale" in diag.TECHNICAL_BBOX_NOTE.lower()
    assert "0–10 km" in diag.TECHNICAL_BBOX_NOTE


def test_3_consulta_fechas_en_orden_y_con_limites_explicitos():
    calls = []

    def fetcher(min_lat, max_lat, min_lon, max_lon, target_date):
        calls.append((min_lat, max_lat, min_lon, max_lon, target_date))
        return make_field(target_date)

    report = diag.run_diagnostic(
        date(2026, 8, 12),
        days=3,
        fetcher=fetcher,
        generated_at_utc=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )
    assert [call[-1] for call in calls] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert all(call[:4] == (-12.60, -12.30, -76.95, -76.65) for call in calls)
    assert report.requested_start_date == date(2026, 8, 10)
    assert report.requested_end_date == date(2026, 8, 12)


def test_4_resume_sst_sin_rellenar_faltantes():
    values = ((19.0, None, 21.0), (20.0, 22.0, None), (21.0, 23.0, 24.0))
    report = build_report([make_field(date(2026, 8, 12), values=values)])
    summary = report.days[0].sst_celsius
    assert summary.count == 7
    assert summary.minimum == pytest.approx(19.0)
    assert summary.maximum == pytest.approx(24.0)
    assert summary.span == pytest.approx(5.0)
    assert report.days[0].n_valid_sst_cells == 7
    assert report.days[0].sst_coverage_fraction == pytest.approx(7 / 9)


def test_5_resume_error_y_gradiente_sin_inventar_umbral():
    report = build_report([make_field(date(2026, 8, 12))])
    day = report.days[0]
    assert day.analysis_error_kelvin.count == 9
    assert day.analysis_error_kelvin.mean == pytest.approx(0.2)
    assert day.gradient_status == tf.ThermalFrontStatus.VALIDO.value
    assert day.gradient_c_per_km.count == 9
    assert day.gradient_c_per_km.maximum > 0
    assert report.n_days_with_gradient == 1
    assert "no activa scoring" in report.interpretation_warning


def test_6_detecta_reutilizacion_de_timestamp_por_fallback():
    shared = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    fields = [
        make_field(date(2026, 8, 11), source_time=shared),
        make_field(
            date(2026, 8, 12),
            source_time=shared,
            status=fo.OstiaStatus.VALIDA_RECIENTE,
        ),
    ]
    report = build_report(fields)
    assert report.n_days_with_source == 2
    assert report.n_unique_source_fields == 1
    assert report.n_reused_source_fields == 1
    assert report.n_days_using_recent_fallback == 1


def test_7_dia_sin_fuente_permanece_sin_datos():
    report = build_report([empty_field(date(2026, 8, 12))])
    day = report.days[0]
    assert report.n_days_with_source == 0
    assert report.n_days_without_source == 1
    assert day.sst_celsius.count == 0
    assert day.gradient_status == tf.ThermalFrontStatus.FUENTE_SIN_DATOS.value
    assert report.grid_axes_stable is None


def test_8_fuente_sin_vecinos_suficientes_no_fabrica_gradiente():
    field = make_field(date(2026, 8, 12), values=((19.0, 20.0, 21.0),))
    report = build_report([field])
    assert report.n_days_with_source == 1
    assert report.n_days_with_gradient == 0
    assert report.days[0].gradient_c_per_km.count == 0
    assert report.days[0].gradient_status == tf.ThermalFrontStatus.SIN_GRADIENTES.value


def test_9_detecta_cambio_real_de_ejes_entre_fechas():
    first = make_field(date(2026, 8, 11))
    second = make_field(date(2026, 8, 12))
    second = fo.OstiaField(
        **{
            **second.__dict__,
            "longitudes": tuple(value + 0.01 for value in second.longitudes),
        }
    )
    assert build_report([first, second]).grid_axes_stable is False


def test_10_formato_humano_es_agregado_y_declara_limitaciones():
    report = build_report([make_field(date(2026, 8, 12))])
    output = diag.format_report(report)
    assert "DIAGNÓSTICO REAL OSTIA" in output
    assert "sst_validas=9/9" in output
    assert "DECISIÓN: pendiente de revisión humana" in output
    assert "no detecta cardúmenes" in output
    assert "sst_celsius=((" not in output
    assert str(report.days[0].sst_celsius) not in output


def test_11_json_contiene_resumen_y_no_matrices():
    report = build_report([make_field(date(2026, 8, 12))])
    payload = json.loads(diag.report_to_json(report))
    assert payload["requested_end_date"] == "2026-08-12"
    assert payload["days"][0]["sst_celsius"]["count"] == 9
    assert "gradient_c_per_km" in payload["days"][0]
    text = json.dumps(payload)
    assert "sst_kelvin" not in text
    assert '"latitudes"' not in text
    assert '"longitudes"' not in text


def test_12_cli_humano_y_json_no_consultan_red(monkeypatch, capsys):
    report = build_report([make_field(date(2026, 8, 12))])
    calls = []

    def fake_run(end_date, days, bbox):
        calls.append((end_date, days, bbox))
        return report

    monkeypatch.setattr(diag, "run_diagnostic", fake_run)
    assert diag.main(["--end-date", "2026-08-12", "--days", "1"]) == 0
    assert "RESUMEN TÉCNICO" in capsys.readouterr().out
    assert diag.main(["--end-date", "2026-08-12", "--days", "1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["days_requested"] == 1
    assert len(calls) == 2


def test_13_cli_distingue_sin_fuente_y_sin_gradiente(monkeypatch, capsys):
    no_source = build_report([empty_field(date(2026, 8, 12))])
    no_gradient = build_report(
        [make_field(date(2026, 8, 12), values=((19.0, 20.0, 21.0),))]
    )
    monkeypatch.setattr(diag, "run_diagnostic", lambda *_args: no_source)
    assert diag.main(["--end-date", "2026-08-12", "--days", "1"]) == 2
    capsys.readouterr()
    monkeypatch.setattr(diag, "run_diagnostic", lambda *_args: no_gradient)
    assert diag.main(["--end-date", "2026-08-12", "--days", "1"]) == 3


def test_14_argumentos_invalidos_fallan_antes_de_consultar():
    with pytest.raises(ValueError):
        diag.run_diagnostic(date(2026, 8, 12), days=0, fetcher=lambda *_: None)
    with pytest.raises(ValueError):
        diag.run_diagnostic(date(2026, 8, 12), days=32, fetcher=lambda *_: None)
    invalid_bbox = diag.BoundingBox(-12.3, -12.6, -76.95, -76.65)
    with pytest.raises(ValueError):
        diag.run_diagnostic(
            date(2026, 8, 12),
            days=1,
            bbox=invalid_bbox,
            fetcher=lambda *_: None,
        )


def test_15_modulo_no_toca_imarpe_ni_implementa_scoring_directo():
    source = inspect.getsource(diag)
    assert "inspect_imarpe" not in source
    assert "PREDICTAMAR_IMARPE" not in source
    assert "copernicusmarine" not in source
    assert "score(" not in source
    assert "threshold" not in source.lower()
