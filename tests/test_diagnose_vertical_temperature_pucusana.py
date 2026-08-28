"""Pruebas sintéticas del diagnóstico térmico vertical; nunca usan red."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

import diagnostics.diagnose_vertical_temperature_pucusana as diag
import ingestion.fetch_vertical_temperature as fvt


def make_reading(
    target_date: date,
    n_pairs: int = 4,
    n_native: int = 4,
    status: fvt.VerticalThermalStatus = fvt.VerticalThermalStatus.VALIDA_EN_VENTANA,
    cell_lon: float = -76.75,
    surface_depth: float = fvt.OFFICIAL_SURFACE_DEPTH_M,
    target_depth: float = fvt.OFFICIAL_NEAREST_10M_DEPTH_M,
    times=None,
):
    if times is None:
        first = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            6,
            tzinfo=timezone.utc,
        )
        times = [first + timedelta(hours=6 * index) for index in range(n_pairs)]
    samples = tuple(
        fvt.VerticalThermalSample(
            time_utc=timestamp,
            time_local=timestamp.astimezone(fvt.TZ_PUCUSANA),
            surface_temperature_celsius=21.0 + index * 0.1,
            temperature_10m_celsius=19.0 + index * 0.05,
            delta_sst_t10_celsius=2.0 + index * 0.05,
            inside_requested_window=(
                status == fvt.VerticalThermalStatus.VALIDA_EN_VENTANA
            ),
            temporal_offset_hours=(
                0.0
                if status == fvt.VerticalThermalStatus.VALIDA_EN_VENTANA
                else 1.0
            ),
        )
        for index, timestamp in enumerate(times)
    )
    coverage = (
        n_pairs / n_native
        if status == fvt.VerticalThermalStatus.VALIDA_EN_VENTANA and n_native
        else None if n_native == 0 else 0.0
    )
    return fvt.VerticalThermalReading(
        lat=diag.REFERENCE_LATITUDE,
        lon=diag.REFERENCE_LONGITUDE,
        date=target_date,
        hour_start_local=0,
        hour_end_local=23,
        window_start_utc=None,
        window_end_utc=None,
        samples=samples,
        n_native_times_in_window=n_native,
        n_pairs=n_pairs,
        n_missing_pairs=n_native - n_pairs if status == fvt.VerticalThermalStatus.VALIDA_EN_VENTANA else n_native,
        coverage_fraction=coverage,
        surface_depth_actual_m=surface_depth,
        temperature_10m_depth_actual_m=target_depth,
        vertical_separation_m=target_depth - surface_depth,
        cell_lat=-12.5,
        cell_lon=cell_lon,
        distance_km=5.409,
        status=status,
    )


def empty_reading(target_date: date):
    return fvt._empty_reading(
        diag.REFERENCE_LATITUDE,
        diag.REFERENCE_LONGITUDE,
        target_date,
        0,
        23,
        None,
        None,
        4,
    )


def run_with(readings):
    by_date = {reading.date: reading for reading in readings}

    def fetcher(_lat, _lon, target_date, _hour_start, _hour_end):
        return by_date[target_date]

    return diag.run_diagnostic(
        end_date=max(by_date),
        days=len(by_date),
        fetcher=fetcher,
        generated_at_utc=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
    )


def test_1_fecha_default_usa_ultimo_dia_local_completo():
    assert diag.default_end_date(
        datetime(2026, 8, 28, 0, 30, tzinfo=timezone.utc)
    ) == date(2026, 8, 26)
    assert diag.default_end_date(
        datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)
    ) == date(2026, 8, 27)
    with pytest.raises(ValueError):
        diag.default_end_date(datetime(2026, 8, 28, 15))


def test_2_consulta_fechas_ordenadas_y_una_referencia_fija():
    calls = []

    def fetcher(lat, lon, target_date, hour_start, hour_end):
        calls.append((lat, lon, target_date, hour_start, hour_end))
        return make_reading(target_date)

    report = diag.run_diagnostic(
        date(2026, 8, 12),
        days=3,
        hour_start=1,
        hour_end=19,
        fetcher=fetcher,
        generated_at_utc=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )

    assert [call[2] for call in calls] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert all(call[:2] == (-12.471, -76.790) for call in calls)
    assert all(call[3:] == (1, 19) for call in calls)
    assert report.requested_start_date == date(2026, 8, 10)


def test_3_resume_temperature_10m_y_delta_sin_muestras_crudas():
    report = run_with([make_reading(date(2026, 8, 12))])
    day = report.days[0]

    assert day.temperature_10m_celsius.count == 4
    assert day.temperature_10m_celsius.minimum == pytest.approx(19.0)
    assert day.temperature_10m_celsius.maximum == pytest.approx(19.15)
    assert day.delta_sst_t10_celsius.median == pytest.approx(2.075)
    assert day.delta_sst_t10_celsius.span == pytest.approx(0.15)
    assert not hasattr(day, "samples")


def test_4_distingue_cobertura_completa_parcial_y_sin_datos():
    readings = [
        make_reading(date(2026, 8, 10)),
        make_reading(date(2026, 8, 11), n_pairs=2),
        empty_reading(date(2026, 8, 12)),
    ]
    report = run_with(readings)

    assert report.n_days_with_pairs == 2
    assert report.n_days_without_pairs == 1
    assert report.n_days_with_full_coverage == 1
    assert report.n_pairs_total == 6
    assert report.days[1].coverage_fraction == pytest.approx(0.5)
    assert report.days[2].delta_sst_t10_celsius.count == 0


def test_5_detecta_fallback_y_reutilizacion_de_par_nativo():
    shared = datetime(2026, 8, 11, 4, tzinfo=timezone.utc)
    readings = [
        make_reading(
            date(2026, 8, 10),
            n_pairs=1,
            n_native=0,
            status=fvt.VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO,
            times=[shared],
        ),
        make_reading(
            date(2026, 8, 11),
            n_pairs=1,
            n_native=0,
            status=fvt.VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO,
            times=[shared],
        ),
    ]
    report = run_with(readings)

    assert report.n_days_using_temporal_fallback == 2
    assert report.n_pairs_total == 2
    assert report.n_unique_native_pairs == 1
    assert report.n_reused_native_pairs == 1


def test_6_declara_estabilidad_de_profundidad_y_celda():
    stable = run_with(
        [make_reading(date(2026, 8, day)) for day in (10, 11, 12)]
    )
    changed = run_with(
        [
            make_reading(date(2026, 8, 11)),
            make_reading(date(2026, 8, 12), cell_lon=-76.833333, target_depth=11.405),
        ]
    )

    assert stable.native_depths_stable is True
    assert stable.selected_cell_stable is True
    assert changed.native_depths_stable is False
    assert changed.selected_cell_stable is False


def test_7_formato_humano_declara_limites_y_no_lista_muestras():
    report = run_with([make_reading(date(2026, 8, 12))])
    output = diag.format_report(report)

    assert "DIAGNÓSTICO REAL PAR TÉRMICO VERTICAL" in output
    assert "temperature_10m" in output
    assert "delta_sst_t10" in output
    assert "no detecta cardúmenes" in output
    assert "no un gradiente" in output
    assert "DECISIÓN: pendiente de revisión humana" in output
    assert "VerticalThermalSample" not in output
    assert "surface_temperature_celsius" not in output


def test_8_json_contiene_solo_resumen_no_muestras():
    payload = json.loads(
        diag.report_to_json(run_with([make_reading(date(2026, 8, 12))]))
    )

    assert payload["dataset_version"] == fvt.DATASET_VERSION
    assert payload["days"][0]["temperature_10m_celsius"]["count"] == 4
    text = json.dumps(payload)
    assert '"samples"' not in text
    assert "surface_temperature_celsius" not in text
    assert "time_utc" not in text


@pytest.mark.parametrize(
    ("end_date", "days", "hours"),
    [
        (datetime(2026, 8, 12), 1, (0, 23)),
        (date(2026, 8, 12), 0, (0, 23)),
        (date(2026, 8, 12), 32, (0, 23)),
        (date(2026, 8, 12), 1, (20, 10)),
    ],
)
def test_9_argumentos_invalidos_fallan_antes_de_consultar(end_date, days, hours):
    touched = False

    def fetcher(*_args):
        nonlocal touched
        touched = True

    with pytest.raises(ValueError):
        diag.run_diagnostic(
            end_date,
            days=days,
            hour_start=hours[0],
            hour_end=hours[1],
            fetcher=fetcher,
        )
    assert touched is False


def test_10_cli_retorna_0_completo_3_parcial_y_2_vacio(monkeypatch, capsys):
    complete = run_with([make_reading(date(2026, 8, 12))])
    partial = run_with(
        [make_reading(date(2026, 8, 11)), empty_reading(date(2026, 8, 12))]
    )
    empty = run_with([empty_reading(date(2026, 8, 12))])

    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: complete)
    assert diag.main(["--end-date", "2026-08-12", "--days", "1"]) == 0
    assert "RESUMEN TÉCNICO" in capsys.readouterr().out
    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: partial)
    assert diag.main(["--end-date", "2026-08-12", "--days", "2"]) == 3
    capsys.readouterr()
    monkeypatch.setattr(diag, "run_diagnostic", lambda **_kwargs: empty)
    assert diag.main(["--end-date", "2026-08-12", "--days", "1", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["n_days_with_pairs"] == 0


def test_11_reporte_fija_fuente_version_y_algoritmo():
    report = run_with([make_reading(date(2026, 8, 12))])

    assert report.product_id == "GLOBAL_ANALYSISFORECAST_PHY_001_024"
    assert report.dataset_id == fvt.DATASET_ID
    assert report.dataset_version == "202406"
    assert report.dataset_part == "default"
    assert report.variable == "thetao"
    assert report.algorithm_version == "vertical_thermal_pair_v1"
