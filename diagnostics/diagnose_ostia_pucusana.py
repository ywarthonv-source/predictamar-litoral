"""Diagnóstico resumido de OSTIA y gradiente térmico alrededor de Pucusana.

Este ejecutable consulta el producto real de Copernicus mediante el fetcher
OSTIA del proyecto. No abre archivos IMARPE, no guarda matrices, no calcula
favorabilidad pesquera y no afirma presencia de cardúmenes.

El recuadro por defecto es TÉCNICO: aporta vecinos suficientes para calcular
un gradiente sobre la grilla de 0.05 grados. No representa ni redefine el
alcance artesanal de 0–10 km desde el litoral.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from numbers import Real

import numpy as np

from derivation.thermal_front import (
    ThermalFrontField,
    ThermalFrontStatus,
    derive_thermal_front,
)
from ingestion.fetch_ostia import (
    DATASET_ID,
    PRODUCT_ID,
    TZ_PUCUSANA,
    OstiaField,
    OstiaStatus,
    fetch_ostia_field,
)

DEFAULT_DAYS = 7
MAX_DAYS = 31
DEFAULT_END_DATE_LAG_DAYS = 1

REFERENCE_NAME = "Caleta Pucusana"
REFERENCE_LATITUDE = -12.471
REFERENCE_LONGITUDE = -76.790

TECHNICAL_BBOX_NOTE = (
    "Recuadro técnico para inspeccionar la grilla OSTIA y disponer de vecinos "
    "para el gradiente. No equivale al alcance operativo de 0–10 km desde el "
    "litoral y no define zonas de pesca."
)
INTERPRETATION_WARNING = (
    "Este diagnóstico verifica disponibilidad y variación ambiental del "
    "producto. No valida pesca, no detecta cardúmenes y no activa scoring."
)


@dataclass(frozen=True)
class BoundingBox:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float

    def validate(self) -> None:
        values = (
            ("minimum_latitude", self.minimum_latitude, -90.0, 90.0),
            ("maximum_latitude", self.maximum_latitude, -90.0, 90.0),
            ("minimum_longitude", self.minimum_longitude, -180.0, 180.0),
            ("maximum_longitude", self.maximum_longitude, -180.0, 180.0),
        )
        for name, value, lower, upper in values:
            if (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not np.isfinite(value)
            ):
                raise ValueError(f"{name} debe ser un número finito.")
            if not lower <= float(value) <= upper:
                raise ValueError(f"{name} debe estar entre {lower:g} y {upper:g}.")
        if self.minimum_latitude >= self.maximum_latitude:
            raise ValueError("minimum_latitude debe ser menor que maximum_latitude.")
        if self.minimum_longitude >= self.maximum_longitude:
            raise ValueError("minimum_longitude debe ser menor que maximum_longitude.")


DEFAULT_BBOX = BoundingBox(
    minimum_latitude=-12.60,
    maximum_latitude=-12.30,
    minimum_longitude=-76.95,
    maximum_longitude=-76.65,
)


@dataclass(frozen=True)
class NumericSummary:
    count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    standard_deviation: float | None
    span: float | None


@dataclass(frozen=True)
class DiagnosticDay:
    requested_date: date
    source_status: str
    source_time_utc: datetime | None
    temporal_age_hours: float | None
    n_latitudes: int
    n_longitudes: int
    n_grid_cells: int
    n_valid_sst_cells: int
    sst_coverage_fraction: float | None
    sst_celsius: NumericSummary
    analysis_error_kelvin: NumericSummary
    gradient_status: str
    n_gradient_cells: int
    gradient_coverage_fraction: float | None
    gradient_c_per_km: NumericSummary
    median_zonal_resolution_km: float | None
    median_meridional_resolution_km: float | None


@dataclass(frozen=True)
class OstiaDiagnosticReport:
    generated_at_utc: datetime
    reference_name: str
    reference_latitude: float
    reference_longitude: float
    technical_bbox: BoundingBox
    technical_bbox_note: str
    requested_start_date: date
    requested_end_date: date
    days_requested: int
    product_id: str
    dataset_id: str
    days: tuple[DiagnosticDay, ...]
    n_days_with_source: int
    n_days_without_source: int
    n_days_with_gradient: int
    n_days_same_local_date: int
    n_days_using_recent_fallback: int
    n_unique_source_fields: int
    n_reused_source_fields: int
    grid_axes_stable: bool | None
    interpretation_warning: str


Fetcher = Callable[[float, float, float, float, date], OstiaField]
Deriver = Callable[[OstiaField], ThermalFrontField]


def default_end_date(now_utc: datetime | None = None) -> date:
    """Usa ayer en Pucusana para reducir consultas al día todavía incompleto."""
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now_utc debe incluir zona horaria.")
    return current.astimezone(TZ_PUCUSANA).date() - timedelta(
        days=DEFAULT_END_DATE_LAG_DAYS
    )


def _numeric_summary(matrix: Sequence[Sequence[float | None]]) -> NumericSummary:
    values = np.asarray(
        [
            float(value)
            for row in matrix
            for value in row
            if value is not None and np.isfinite(value)
        ],
        dtype=float,
    )
    if values.size == 0:
        return NumericSummary(0, None, None, None, None, None, None)
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    return NumericSummary(
        count=int(values.size),
        minimum=minimum,
        maximum=maximum,
        mean=float(np.mean(values)),
        median=float(np.median(values)),
        standard_deviation=float(np.std(values)),
        span=maximum - minimum,
    )


def _requested_dates(end_date: date, days: int) -> tuple[date, ...]:
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days debe ser un entero entre 1 y {MAX_DAYS}.")
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise TypeError("end_date debe ser datetime.date.")
    start_date = end_date - timedelta(days=days - 1)
    return tuple(start_date + timedelta(days=offset) for offset in range(days))


def _diagnose_day(field: OstiaField, front: ThermalFrontField) -> DiagnosticDay:
    return DiagnosticDay(
        requested_date=field.requested_date,
        source_status=field.status.value,
        source_time_utc=field.time_utc,
        temporal_age_hours=field.temporal_age_hours,
        n_latitudes=len(field.latitudes),
        n_longitudes=len(field.longitudes),
        n_grid_cells=field.n_grid_cells,
        n_valid_sst_cells=field.n_valid_cells,
        sst_coverage_fraction=field.coverage_fraction,
        sst_celsius=_numeric_summary(field.sst_celsius),
        analysis_error_kelvin=_numeric_summary(field.analysis_error_kelvin),
        gradient_status=front.status.value,
        n_gradient_cells=front.n_gradient_cells,
        gradient_coverage_fraction=front.gradient_coverage_fraction,
        gradient_c_per_km=_numeric_summary(front.gradient_c_per_km),
        median_zonal_resolution_km=front.median_zonal_resolution_km,
        median_meridional_resolution_km=front.median_meridional_resolution_km,
    )


def run_diagnostic(
    end_date: date,
    days: int = DEFAULT_DAYS,
    bbox: BoundingBox = DEFAULT_BBOX,
    fetcher: Fetcher = fetch_ostia_field,
    deriver: Deriver = derive_thermal_front,
    generated_at_utc: datetime | None = None,
) -> OstiaDiagnosticReport:
    """Consulta cada fecha y resume campos reales sin conservar matrices."""
    bbox.validate()
    dates = _requested_dates(end_date, days)
    generated = generated_at_utc or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        raise ValueError("generated_at_utc debe incluir zona horaria.")
    generated = generated.astimezone(timezone.utc)

    daily: list[DiagnosticDay] = []
    source_times: list[datetime] = []
    source_axes: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    source_statuses: list[OstiaStatus] = []

    for target_date in dates:
        field = fetcher(
            bbox.minimum_latitude,
            bbox.maximum_latitude,
            bbox.minimum_longitude,
            bbox.maximum_longitude,
            target_date,
        )
        front = deriver(field)
        daily.append(_diagnose_day(field, front))
        source_statuses.append(field.status)
        if field.time_utc is not None and field.n_valid_cells:
            source_times.append(field.time_utc)
            source_axes.append((field.latitudes, field.longitudes))

    n_with_source = sum(status != OstiaStatus.SIN_DATOS for status in source_statuses)
    n_with_gradient = sum(
        item.gradient_status == ThermalFrontStatus.VALIDO.value
        and item.n_gradient_cells > 0
        for item in daily
    )
    n_same_date = sum(
        status == OstiaStatus.VALIDA_EN_FECHA_LOCAL for status in source_statuses
    )
    n_recent = sum(status == OstiaStatus.VALIDA_RECIENTE for status in source_statuses)
    unique_source_times = len(set(source_times))
    grid_stable = len(set(source_axes)) <= 1 if source_axes else None

    return OstiaDiagnosticReport(
        generated_at_utc=generated,
        reference_name=REFERENCE_NAME,
        reference_latitude=REFERENCE_LATITUDE,
        reference_longitude=REFERENCE_LONGITUDE,
        technical_bbox=bbox,
        technical_bbox_note=TECHNICAL_BBOX_NOTE,
        requested_start_date=dates[0],
        requested_end_date=dates[-1],
        days_requested=len(dates),
        product_id=PRODUCT_ID,
        dataset_id=DATASET_ID,
        days=tuple(daily),
        n_days_with_source=n_with_source,
        n_days_without_source=len(dates) - n_with_source,
        n_days_with_gradient=n_with_gradient,
        n_days_same_local_date=n_same_date,
        n_days_using_recent_fallback=n_recent,
        n_unique_source_fields=unique_source_times,
        n_reused_source_fields=max(0, len(source_times) - unique_source_times),
        grid_axes_stable=grid_stable,
        interpretation_warning=INTERPRETATION_WARNING,
    )


def _format_optional(value: float | None, decimals: int = 4) -> str:
    return "sin_dato" if value is None else f"{value:.{decimals}f}"


def _format_percentage(value: float | None) -> str:
    return "sin_dato" if value is None else f"{value * 100:.1f}%"


def _format_stats(summary: NumericSummary, unit: str) -> str:
    if summary.count == 0:
        return "sin_dato"
    return (
        f"min={summary.minimum:.4f}, mediana={summary.median:.4f}, "
        f"max={summary.maximum:.4f}, rango={summary.span:.4f} {unit}"
    )


def format_report(report: OstiaDiagnosticReport) -> str:
    """Genera una salida humana agregada; nunca imprime las matrices crudas."""
    bbox = report.technical_bbox
    lines = [
        "=== DIAGNÓSTICO REAL OSTIA + GRADIENTE | PUCUSANA ===",
        f"generado_utc: {report.generated_at_utc.isoformat()}",
        (
            f"referencia: {report.reference_name} "
            f"({report.reference_latitude:.3f}, {report.reference_longitude:.3f})"
        ),
        (
            "recuadro_tecnico: "
            f"lat[{bbox.minimum_latitude:.2f}, {bbox.maximum_latitude:.2f}] "
            f"lon[{bbox.minimum_longitude:.2f}, {bbox.maximum_longitude:.2f}]"
        ),
        f"nota_recuadro: {report.technical_bbox_note}",
        (
            f"periodo_solicitado: {report.requested_start_date.isoformat()} a "
            f"{report.requested_end_date.isoformat()} "
            f"({report.days_requested} fechas)"
        ),
        f"producto: {report.product_id}",
        f"dataset: {report.dataset_id}",
        "",
        "--- RESULTADOS POR FECHA ---",
    ]
    for item in report.days:
        source_time = (
            item.source_time_utc.isoformat() if item.source_time_utc else "sin_dato"
        )
        lines.extend(
            [
                f"fecha_solicitada: {item.requested_date.isoformat()}",
                (
                    f"  fuente: status={item.source_status}, timestamp_utc={source_time}, "
                    f"antiguedad_h={_format_optional(item.temporal_age_hours, 2)}"
                ),
                (
                    f"  grilla: {item.n_latitudes}x{item.n_longitudes}, "
                    f"sst_validas={item.n_valid_sst_cells}/{item.n_grid_cells}, "
                    f"cobertura={_format_percentage(item.sst_coverage_fraction)}"
                ),
                f"  sst: {_format_stats(item.sst_celsius, '°C')}",
                (
                    "  analysis_error: "
                    f"{_format_stats(item.analysis_error_kelvin, 'K')}"
                ),
                (
                    f"  gradiente: status={item.gradient_status}, "
                    f"celdas={item.n_gradient_cells}, "
                    f"cobertura={_format_percentage(item.gradient_coverage_fraction)}"
                ),
                (
                    "  magnitud_gradiente: "
                    f"{_format_stats(item.gradient_c_per_km, '°C/km')}"
                ),
                (
                    "  resolucion_mediana_km: "
                    f"zonal={_format_optional(item.median_zonal_resolution_km, 3)}, "
                    "meridional="
                    f"{_format_optional(item.median_meridional_resolution_km, 3)}"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "--- RESUMEN TÉCNICO ---",
            f"fechas_con_ostia: {report.n_days_with_source}/{report.days_requested}",
            f"fechas_sin_ostia: {report.n_days_without_source}",
            f"fechas_con_gradiente: {report.n_days_with_gradient}",
            f"campos_en_fecha_local: {report.n_days_same_local_date}",
            f"campos_por_fallback_reciente: {report.n_days_using_recent_fallback}",
            f"timestamps_fuente_unicos: {report.n_unique_source_fields}",
            f"campos_fuente_reutilizados: {report.n_reused_source_fields}",
            (
                "ejes_de_grilla_estables: "
                + (
                    "sin_dato"
                    if report.grid_axes_stable is None
                    else str(report.grid_axes_stable).lower()
                )
            ),
            f"ADVERTENCIA: {report.interpretation_warning}",
            (
                "DECISIÓN: pendiente de revisión humana; este programa no aplica "
                "umbrales automáticos de utilidad ni favorabilidad."
            ),
        ]
    )
    return "\n".join(lines)


def _json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def report_to_json(report: OstiaDiagnosticReport) -> str:
    """Serializa el mismo resumen sin añadir matrices ni coordenadas de celda."""
    return json.dumps(
        _json_safe(asdict(report)),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "La fecha debe tener formato YYYY-MM-DD."
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Consulta OSTIA real alrededor de Pucusana y resume SST, cobertura "
            "y gradiente térmico sin calcular scoring."
        )
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=default_end_date(),
        help="Última fecha local a consultar (YYYY-MM-DD); por defecto, ayer.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Número de fechas consecutivas, entre 1 y {MAX_DAYS} (default: 7).",
    )
    parser.add_argument(
        "--minimum-latitude",
        type=float,
        default=DEFAULT_BBOX.minimum_latitude,
    )
    parser.add_argument(
        "--maximum-latitude",
        type=float,
        default=DEFAULT_BBOX.maximum_latitude,
    )
    parser.add_argument(
        "--minimum-longitude",
        type=float,
        default=DEFAULT_BBOX.minimum_longitude,
    )
    parser.add_argument(
        "--maximum-longitude",
        type=float,
        default=DEFAULT_BBOX.maximum_longitude,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el resumen como JSON en lugar del formato humano.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    bbox = BoundingBox(
        minimum_latitude=args.minimum_latitude,
        maximum_latitude=args.maximum_latitude,
        minimum_longitude=args.minimum_longitude,
        maximum_longitude=args.maximum_longitude,
    )
    try:
        report = run_diagnostic(args.end_date, args.days, bbox)
    except ValueError as exc:
        parser.error(str(exc))
    print(report_to_json(report) if args.json else format_report(report))
    if report.n_days_with_source == 0:
        return 2
    if report.n_days_with_gradient == 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
