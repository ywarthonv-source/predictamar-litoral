"""Diagnóstico real resumido del par térmico vertical en Pucusana.

Consulta ``temperature_10m`` y ``delta_sst_t10`` mediante el fetcher estricto
del proyecto. No abre datos IMARPE, no guarda matrices ni muestras crudas, no
calcula favorabilidad pesquera y no activa scoring.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np

from ingestion.fetch_temperature import TZ_PUCUSANA
from ingestion.fetch_vertical_temperature import (
    ALGORITHM_VERSION,
    DATASET_ID,
    DATASET_PART,
    DATASET_VERSION,
    PRODUCT_ID,
    VARIABLE,
    VerticalThermalReading,
    VerticalThermalStatus,
    fetch_vertical_thermal_pair,
)

DEFAULT_DAYS = 7
MAX_DAYS = 31
REFERENCE_NAME = "Caleta Pucusana"
REFERENCE_LATITUDE = -12.471
REFERENCE_LONGITUDE = -76.790

INTERPRETATION_WARNING = (
    "Este diagnóstico comprueba disponibilidad, coherencia y variación del "
    "par térmico vertical del modelo en una referencia regional. No valida "
    "pesca, no detecta cardúmenes, no demuestra una termoclina y no activa "
    "scoring. delta_sst_t10 resta dos niveles thetao del mismo modelo; no usa "
    "sst_observed_ostia. Es una diferencia en degree_Celsius, no un gradiente "
    "en degree_Celsius/m."
)


@dataclass(frozen=True)
class NumericSummary:
    count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    span: float | None


@dataclass(frozen=True)
class DiagnosticDay:
    requested_date: date
    status: str
    n_native_times_in_window: int
    n_pairs: int
    n_missing_pairs: int
    coverage_fraction: float | None
    surface_depth_actual_m: float | None
    temperature_10m_depth_actual_m: float | None
    vertical_separation_m: float | None
    cell_lat: float | None
    cell_lon: float | None
    distance_km: float | None
    temperature_10m_celsius: NumericSummary
    delta_sst_t10_celsius: NumericSummary


@dataclass(frozen=True)
class VerticalThermalDiagnosticReport:
    generated_at_utc: datetime
    reference_name: str
    reference_latitude: float
    reference_longitude: float
    requested_start_date: date
    requested_end_date: date
    hour_start_local: int
    hour_end_local: int
    days_requested: int
    product_id: str
    dataset_id: str
    dataset_version: str
    dataset_part: str
    variable: str
    algorithm_version: str
    days: tuple[DiagnosticDay, ...]
    n_days_with_pairs: int
    n_days_without_pairs: int
    n_days_with_full_coverage: int
    n_days_using_temporal_fallback: int
    n_pairs_total: int
    n_unique_native_pairs: int
    n_reused_native_pairs: int
    native_depths_stable: bool | None
    selected_cell_stable: bool | None
    interpretation_warning: str


Fetcher = Callable[[float, float, date, int, int], VerticalThermalReading]


def default_end_date(now_local: datetime | None = None) -> date:
    """Usa el día local completo anterior para no diagnosticar un día parcial."""
    current = now_local or datetime.now(TZ_PUCUSANA)
    if current.tzinfo is None:
        raise ValueError("now_local debe incluir zona horaria.")
    return current.astimezone(TZ_PUCUSANA).date() - timedelta(days=1)


def _requested_dates(end_date: date, days: int) -> tuple[date, ...]:
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise ValueError("end_date debe ser datetime.date.")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days debe ser un entero entre 1 y {MAX_DAYS}.")
    start = end_date - timedelta(days=days - 1)
    return tuple(start + timedelta(days=offset) for offset in range(days))


def _summary(values: Sequence[float]) -> NumericSummary:
    array = np.asarray([float(value) for value in values if np.isfinite(value)])
    if array.size == 0:
        return NumericSummary(0, None, None, None, None, None)
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    return NumericSummary(
        count=int(array.size),
        minimum=minimum,
        maximum=maximum,
        mean=float(np.mean(array)),
        median=float(np.median(array)),
        span=maximum - minimum,
    )


def _diagnose_day(reading: VerticalThermalReading) -> DiagnosticDay:
    return DiagnosticDay(
        requested_date=reading.date,
        status=reading.status.value,
        n_native_times_in_window=reading.n_native_times_in_window,
        n_pairs=reading.n_pairs,
        n_missing_pairs=reading.n_missing_pairs,
        coverage_fraction=reading.coverage_fraction,
        surface_depth_actual_m=reading.surface_depth_actual_m,
        temperature_10m_depth_actual_m=reading.temperature_10m_depth_actual_m,
        vertical_separation_m=reading.vertical_separation_m,
        cell_lat=reading.cell_lat,
        cell_lon=reading.cell_lon,
        distance_km=reading.distance_km,
        temperature_10m_celsius=_summary(
            [sample.temperature_10m_celsius for sample in reading.samples]
        ),
        delta_sst_t10_celsius=_summary(
            [sample.delta_sst_t10_celsius for sample in reading.samples]
        ),
    )


def run_diagnostic(
    end_date: date,
    days: int = DEFAULT_DAYS,
    hour_start: int = 0,
    hour_end: int = 23,
    fetcher: Fetcher = fetch_vertical_thermal_pair,
    generated_at_utc: datetime | None = None,
) -> VerticalThermalDiagnosticReport:
    dates = _requested_dates(end_date, days)
    # Valida horas antes de la primera consulta. El fetcher también lo hace,
    # pero esta llamada evita un informe parcialmente ejecutado.
    if not (0 <= hour_start <= hour_end <= 23):
        raise ValueError("Debe cumplirse 0 <= hour_start <= hour_end <= 23.")
    generated = generated_at_utc or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        raise ValueError("generated_at_utc debe incluir zona horaria.")
    generated = generated.astimezone(timezone.utc)

    readings: list[VerticalThermalReading] = []
    days_out: list[DiagnosticDay] = []
    native_pair_keys: list[tuple[datetime, float, float, float, float]] = []

    for requested_date in dates:
        reading = fetcher(
            REFERENCE_LATITUDE,
            REFERENCE_LONGITUDE,
            requested_date,
            hour_start,
            hour_end,
        )
        readings.append(reading)
        days_out.append(_diagnose_day(reading))
        if (
            reading.cell_lat is not None
            and reading.cell_lon is not None
            and reading.surface_depth_actual_m is not None
            and reading.temperature_10m_depth_actual_m is not None
        ):
            native_pair_keys.extend(
                (
                    sample.time_utc,
                    reading.cell_lat,
                    reading.cell_lon,
                    reading.surface_depth_actual_m,
                    reading.temperature_10m_depth_actual_m,
                )
                for sample in reading.samples
            )

    valid = [reading for reading in readings if reading.n_pairs > 0]
    full = [
        reading
        for reading in valid
        if reading.coverage_fraction == 1.0
        and reading.status == VerticalThermalStatus.VALIDA_EN_VENTANA
    ]
    fallback = [
        reading
        for reading in valid
        if reading.status == VerticalThermalStatus.VALIDA_CERCANA_EN_TIEMPO
    ]
    depths = {
        (reading.surface_depth_actual_m, reading.temperature_10m_depth_actual_m)
        for reading in valid
    }
    cells = {(reading.cell_lat, reading.cell_lon) for reading in valid}
    n_unique = len(set(native_pair_keys))

    return VerticalThermalDiagnosticReport(
        generated_at_utc=generated,
        reference_name=REFERENCE_NAME,
        reference_latitude=REFERENCE_LATITUDE,
        reference_longitude=REFERENCE_LONGITUDE,
        requested_start_date=dates[0],
        requested_end_date=dates[-1],
        hour_start_local=hour_start,
        hour_end_local=hour_end,
        days_requested=len(dates),
        product_id=PRODUCT_ID,
        dataset_id=DATASET_ID,
        dataset_version=DATASET_VERSION,
        dataset_part=DATASET_PART,
        variable=VARIABLE,
        algorithm_version=ALGORITHM_VERSION,
        days=tuple(days_out),
        n_days_with_pairs=len(valid),
        n_days_without_pairs=len(readings) - len(valid),
        n_days_with_full_coverage=len(full),
        n_days_using_temporal_fallback=len(fallback),
        n_pairs_total=len(native_pair_keys),
        n_unique_native_pairs=n_unique,
        n_reused_native_pairs=len(native_pair_keys) - n_unique,
        native_depths_stable=(len(depths) == 1) if depths else None,
        selected_cell_stable=(len(cells) == 1) if cells else None,
        interpretation_warning=INTERPRETATION_WARNING,
    )


def _number(value: float | None, digits: int = 4) -> str:
    return "null" if value is None else f"{value:.{digits}f}"


def _format_summary(summary: NumericSummary, units: str) -> str:
    if summary.count == 0:
        return f"count=0, min=null, mediana=null, max=null {units}"
    return (
        f"count={summary.count}, min={_number(summary.minimum)}, "
        f"mediana={_number(summary.median)}, max={_number(summary.maximum)}, "
        f"rango={_number(summary.span)} {units}"
    )


def format_report(report: VerticalThermalDiagnosticReport) -> str:
    lines = [
        "--- DIAGNÓSTICO REAL PAR TÉRMICO VERTICAL ---",
        f"referencia: {report.reference_name} "
        f"({report.reference_latitude:.6f}, {report.reference_longitude:.6f})",
        f"periodo_local: {report.requested_start_date.isoformat()} a "
        f"{report.requested_end_date.isoformat()}",
        f"ventana_local: {report.hour_start_local:02d}:00-"
        f"{report.hour_end_local:02d}:59",
        f"fuente: {report.dataset_id} version={report.dataset_version} "
        f"parte={report.dataset_part} variable={report.variable}",
        "",
    ]
    for day in report.days:
        lines.extend(
            [
                f"fecha_solicitada: {day.requested_date.isoformat()}",
                f"  status: {day.status}",
                f"  pares: {day.n_pairs}/{day.n_native_times_in_window}, "
                f"cobertura={_number(day.coverage_fraction)}",
                "  profundidades_m: "
                f"superficie={_number(day.surface_depth_actual_m, 6)}, "
                f"temperature_10m={_number(day.temperature_10m_depth_actual_m, 6)}, "
                f"separacion={_number(day.vertical_separation_m, 6)}",
                f"  celda: lat={_number(day.cell_lat, 6)}, "
                f"lon={_number(day.cell_lon, 6)}, "
                f"distancia_km={_number(day.distance_km, 3)}",
                "  temperature_10m: "
                + _format_summary(day.temperature_10m_celsius, "degree_Celsius"),
                "  delta_sst_t10: "
                + _format_summary(day.delta_sst_t10_celsius, "degree_Celsius"),
            ]
        )
    lines.extend(
        [
            "",
            "--- RESUMEN TÉCNICO ---",
            f"fechas_con_pares: {report.n_days_with_pairs}/{report.days_requested}",
            f"fechas_sin_pares: {report.n_days_without_pairs}",
            f"fechas_cobertura_completa: {report.n_days_with_full_coverage}",
            f"fechas_con_fallback_temporal: {report.n_days_using_temporal_fallback}",
            f"pares_totales: {report.n_pairs_total}",
            f"pares_nativos_unicos: {report.n_unique_native_pairs}",
            f"pares_reutilizados: {report.n_reused_native_pairs}",
            f"profundidades_estables: {str(report.native_depths_stable).lower()}",
            f"celda_seleccionada_estable: {str(report.selected_cell_stable).lower()}",
            f"ADVERTENCIA: {report.interpretation_warning}",
            "DECISIÓN: pendiente de revisión humana; no se aplican umbrales "
            "automáticos de utilidad ni favorabilidad.",
        ]
    )
    return "\n".join(lines)


def report_to_json(report: VerticalThermalDiagnosticReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La fecha debe usar YYYY-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", type=_parse_date, default=None)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--hour-start", type=int, default=0)
    parser.add_argument("--hour-end", type=int, default=23)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_diagnostic(
        end_date=args.end_date or default_end_date(),
        days=args.days,
        hour_start=args.hour_start,
        hour_end=args.hour_end,
    )
    print(report_to_json(report) if args.json else format_report(report))
    if report.n_days_with_pairs == report.days_requested:
        return 0
    return 2 if report.n_days_with_pairs == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
