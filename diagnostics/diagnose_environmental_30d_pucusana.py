"""Diagnóstico ambiental consolidado de 30 días para Pucusana.

Recorre el ensamblador ambiental ya auditado y conserva únicamente resúmenes
técnicos. No guarda matrices ni muestras crudas, no mezcla fuentes térmicas,
no calcula favorabilidad, pesos, score o presencia de cardúmenes.

Las capas OLCI y MUR son explícitas. En el diagnóstico histórico se fija para
cada fecha un ``as_of`` de selección acotado; eso permite comprobar archivos
históricos sin afirmar que estuvieran disponibles operacionalmente en aquel
instante. Los indicadores de disponibilidad verificada que entrega cada
fuente se conservan y nunca se promueven por este módulo.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import json
from math import atan2, degrees, hypot, isfinite, radians
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np

from assembly.environmental_assembler import (
    DEFAULT_SPEC_PATH,
    MUR_VARIABLE_ORDER,
    OPTIONAL_VARIABLE_ORDER,
    VARIABLE_ORDER,
    AssemblerProviders,
    AssemblyRequest,
    AssemblyState,
    EnvironmentalSnapshot,
    VariableResult,
    assemble_environmental_snapshot,
)
from ingestion.fetch_chlorophyll_field import ChlorophyllOptions
from ingestion.fetch_mur import MurMode, MurOptions
from ingestion.fetch_temperature import TZ_PUCUSANA


SCHEMA_VERSION = "environmental_30d_diagnostic_v1"
DEFAULT_DAYS = 30
MAX_DAYS = 31
DEFAULT_FIELD_HALF_WIDTH_DEG = 0.15
HISTORICAL_SELECTION_LAG_HOURS = 48.0
REFERENCE_NAME = "Caleta Pucusana"
REFERENCE_LATITUDE = -12.471
REFERENCE_LONGITUDE = -76.790

OPTIONAL_VARIABLES = frozenset((*OPTIONAL_VARIABLE_ORDER, *MUR_VARIABLE_ORDER))
STATIC_VARIABLES = frozenset({"batimetria"})
FALLBACK_STATUSES = frozenset({"valida_reciente", "valida_cercana_en_tiempo"})
CIRCULAR_VALUE_PATHS = frozenset({"measurements[].direction_toward_deg"})
CATEGORICAL_VALUE_PATHS = frozenset({"tid_code"})

SOURCE_TIME_PATH_GROUPS = (
    ("samples[].time_utc", "measurements[].time_utc"),
    ("source_time_utc", "time_utc", "max_time_utc"),
    ("source_nominal_product_date", "nominal_product_date"),
)

INTERPRETATION_WARNING = (
    "Este informe comprueba disponibilidad, cobertura, procedencia y variación "
    "técnica de productos ambientales. Encontrar valores no demuestra utilidad "
    "pesquera, presencia de cardúmenes ni validez predictiva. Las fuentes SST "
    "de modelo, OSTIA y MUR permanecen separadas y sus derivadas no cuentan como "
    "observaciones independientes. OLCI y los archivos MUR finales históricos "
    "no prueban disponibilidad operacional retrospectiva. No se activa scoring."
)


@dataclass(frozen=True)
class MetricSummary:
    path: str
    aggregation: str
    count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    span: float | None = None
    circular_mean_degrees: float | None = None
    circular_resultant_length: float | None = None
    distinct_values: tuple[int | float, ...] = ()


@dataclass(frozen=True)
class StatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class SourceIdentitySummary:
    dataset_ids: tuple[str, ...]
    product_ids: tuple[str, ...]
    collection_ids: tuple[str, ...]
    versions: tuple[str, ...]


@dataclass(frozen=True)
class DailyVariableDiagnostic:
    requested_date: date
    variable_id: str
    state: str
    source_status: str | None
    shared_operation: str
    spatial_scope: str
    primary_value_count: int
    coverage_fraction: float | None
    fallback_used: bool
    source_time_keys: tuple[str, ...]
    selected_cell_keys: tuple[str, ...]
    availability_as_of_verified: bool | None
    operational_use_verified: bool | None
    metrics: tuple[MetricSummary, ...]
    error_code: str | None


@dataclass(frozen=True)
class DailySnapshotDiagnostic:
    requested_date: date
    schema_version: str
    status: str
    available_count: int
    no_data_count: int
    error_count: int
    safety_blocked: bool
    variables: tuple[DailyVariableDiagnostic, ...]


@dataclass(frozen=True)
class OperationMembership:
    shared_operation: str
    variables: tuple[str, ...]


@dataclass(frozen=True)
class VariablePeriodDiagnostic:
    variable_id: str
    layer: str
    shared_operation: str
    spatial_scope: str
    intended_role: str
    implementation_status: str
    scoring_status: str
    predictively_valid: bool | str | None
    days_requested: int
    days_available: int
    days_no_data: int
    days_error: int
    availability_fraction: float
    days_with_primary_values: int
    days_using_fallback: int
    days_historical_final: int
    source_status_counts: tuple[StatusCount, ...]
    source_observations_total: int
    unique_source_observations: int
    reused_source_observations: int
    selected_cells_stable: bool | None
    coverage_fraction: MetricSummary
    metrics: tuple[MetricSummary, ...]
    source_identity: SourceIdentitySummary
    availability_verification_declared_days: int
    availability_verified_days: int
    operational_verification_declared_days: int
    operational_verified_days: int
    no_data_dates: tuple[date, ...]
    error_dates: tuple[date, ...]
    technical_classification: str


@dataclass(frozen=True)
class EnvironmentalDiagnosticReport:
    schema_version: str
    generated_at_utc: datetime
    reference_name: str
    reference_latitude: float
    reference_longitude: float
    requested_start_date: date
    requested_end_date: date
    days_requested: int
    hour_start_local: int
    hour_end_local: int
    field_half_width_deg: float
    includes_olci: bool
    includes_mur: bool
    mur_mode: str | None
    historical_selection_lag_hours: float
    variables_expected: tuple[str, ...]
    independent_source_operations: tuple[OperationMembership, ...]
    n_independent_source_operations: int
    days: tuple[DailySnapshotDiagnostic, ...]
    variables: tuple[VariablePeriodDiagnostic, ...]
    interpretation_warning: str
    classification_status: str


Assembler = Callable[..., EnvironmentalSnapshot]


def default_end_date(now_utc: datetime | None = None) -> date:
    """Devuelve el último día local completo de Pucusana."""
    current = now_utc or datetime.now(timezone.utc)
    if (
        not isinstance(current, datetime)
        or current.tzinfo is None
        or current.utcoffset() is None
    ):
        raise ValueError("now_utc debe ser datetime con zona horaria.")
    return current.astimezone(TZ_PUCUSANA).date() - timedelta(days=1)


def _requested_dates(end_date: date, days: int) -> tuple[date, ...]:
    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise ValueError("end_date debe ser datetime.date.")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days debe ser un entero entre 1 y {MAX_DAYS}.")
    start = end_date - timedelta(days=days - 1)
    return tuple(start + timedelta(days=offset) for offset in range(days))


def _flatten(values: Sequence[object], levels: int) -> list[object]:
    current = list(values)
    for _ in range(levels):
        expanded: list[object] = []
        for value in current:
            if isinstance(value, (list, tuple)):
                expanded.extend(value)
        current = expanded
    return current


def _extract_path(payload: Mapping[str, object], path: str) -> tuple[object, ...]:
    """Extrae rutas declaradas como ``samples[].x`` o ``grid.x[][]``."""
    values: list[object] = [payload]
    for component in path.split("."):
        levels = component.count("[]")
        key = component.replace("[]", "")
        selected = [
            value[key]
            for value in values
            if isinstance(value, Mapping) and key in value
        ]
        values = _flatten(selected, levels)
        if not values:
            break
    return tuple(values)


def _finite_numbers(values: Sequence[object]) -> tuple[float, ...]:
    numbers = []
    for value in values:
        if isinstance(value, Real) and not isinstance(value, bool):
            number = float(value)
            if isfinite(number):
                numbers.append(number)
    return tuple(numbers)


def _metric_summary(path: str, values: Sequence[object]) -> MetricSummary:
    numbers = _finite_numbers(values)
    if path in CATEGORICAL_VALUE_PATHS:
        distinct = tuple(
            int(number) if number.is_integer() else number
            for number in sorted(set(numbers))
        )
        return MetricSummary(
            path=path,
            aggregation="categorical_values_not_averaged",
            count=len(numbers),
            distinct_values=distinct,
        )
    if path in CIRCULAR_VALUE_PATHS:
        if not numbers:
            return MetricSummary(path, "circular_degrees", 0)
        angles = np.asarray(
            [radians(number % 360.0) for number in numbers], dtype=float
        )
        mean_sin = float(np.mean(np.sin(angles)))
        mean_cos = float(np.mean(np.cos(angles)))
        resultant = hypot(mean_sin, mean_cos)
        circular_mean = (
            degrees(atan2(mean_sin, mean_cos)) % 360.0 if resultant > 1e-12 else None
        )
        if circular_mean is not None and (
            circular_mean < 1e-12 or 360.0 - circular_mean < 1e-12
        ):
            circular_mean = 0.0
        return MetricSummary(
            path=path,
            aggregation="circular_degrees",
            count=len(numbers),
            circular_mean_degrees=circular_mean,
            circular_resultant_length=resultant,
        )
    if not numbers:
        return MetricSummary(path, "linear_numeric", 0)
    array = np.asarray(numbers, dtype=float)
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    return MetricSummary(
        path=path,
        aggregation="linear_numeric",
        count=int(array.size),
        minimum=minimum,
        maximum=maximum,
        mean=float(np.mean(array)),
        median=float(np.median(array)),
        standard_deviation=float(np.std(array)),
        span=maximum - minimum,
    )


def _normalise_source_key(value: object) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _source_time_keys(payload: Mapping[str, object]) -> tuple[str, ...]:
    # Prefiere timestamps nativos sobre una fecha nominal del mismo campo para
    # no contar dos veces una sola observación. La fecha es solo el fallback
    # cuando la fuente no conserva una hora.
    for paths in SOURCE_TIME_PATH_GROUPS:
        keys = {
            key
            for path in paths
            for value in _extract_path(payload, path)
            if (key := _normalise_source_key(value)) is not None
        }
        if keys:
            return tuple(sorted(keys))
    return ()


def _selected_cell_keys(payload: Mapping[str, object]) -> tuple[str, ...]:
    cells: set[str] = set()

    def add(lat: object, lon: object) -> None:
        if all(
            isinstance(value, Real)
            and not isinstance(value, bool)
            and isfinite(float(value))
            for value in (lat, lon)
        ):
            cells.add(f"{float(lat):.8f},{float(lon):.8f}")

    add(payload.get("cell_lat"), payload.get("cell_lon"))
    measurements = payload.get("measurements")
    if isinstance(measurements, (list, tuple)):
        for measurement in measurements:
            if isinstance(measurement, Mapping):
                add(measurement.get("cell_lat"), measurement.get("cell_lon"))
    return tuple(sorted(cells))


def _coverage_fraction(payload: Mapping[str, object]) -> float | None:
    for key in ("gradient_coverage_fraction", "coverage_fraction"):
        value = payload.get(key)
        if (
            isinstance(value, Real)
            and not isinstance(value, bool)
            and isfinite(float(value))
            and 0.0 <= float(value) <= 1.0
        ):
            return float(value)
    measured = payload.get("n_measurements")
    expected = payload.get("expected_instants")
    if (
        isinstance(measured, int)
        and not isinstance(measured, bool)
        and isinstance(expected, int)
        and not isinstance(expected, bool)
        and expected > 0
        and 0 <= measured <= expected
    ):
        return measured / expected
    return None


def _recursive_scalar_values(
    payload: Mapping[str, object], keys: set[str]
) -> tuple[object, ...]:
    found: list[object] = []
    for key, value in payload.items():
        if key in keys and not isinstance(value, (Mapping, list, tuple)):
            found.append(value)
        if isinstance(value, Mapping):
            found.extend(_recursive_scalar_values(value, keys))
    return tuple(found)


def _optional_boolean(payload: Mapping[str, object], key: str) -> bool | None:
    values = _recursive_scalar_values(payload, {key})
    booleans = {value for value in values if isinstance(value, bool)}
    if not booleans:
        return None
    return all(booleans)


def _source_identity(payloads: Sequence[Mapping[str, object]]) -> SourceIdentitySummary:
    def values(keys: set[str]) -> tuple[str, ...]:
        found = {
            str(value)
            for payload in payloads
            for value in _recursive_scalar_values(payload, keys)
            if value is not None and str(value).strip()
        }
        return tuple(sorted(found))

    return SourceIdentitySummary(
        dataset_ids=values({"dataset_id", "source_dataset_id"}),
        product_ids=values({"product_id", "source_product_id", "product"}),
        collection_ids=values({"collection_id"}),
        versions=values(
            {
                "dataset_version",
                "requested_dataset_version",
                "source_dataset_version",
                "product_version",
                "expected_product_version",
            }
        ),
    )


def _daily_variable(
    result: VariableResult, requested_date: date
) -> DailyVariableDiagnostic:
    payload = result.payload if isinstance(result.payload, Mapping) else {}
    metrics = tuple(
        _metric_summary(path, _extract_path(payload, path))
        for path in result.value_paths
    )
    return DailyVariableDiagnostic(
        requested_date=requested_date,
        variable_id=result.variable_id,
        state=result.state.value,
        source_status=result.source_status,
        shared_operation=result.shared_operation,
        spatial_scope=result.spatial_scope.value,
        primary_value_count=metrics[0].count if metrics else 0,
        coverage_fraction=_coverage_fraction(payload),
        fallback_used=result.source_status in FALLBACK_STATUSES,
        source_time_keys=_source_time_keys(payload),
        selected_cell_keys=_selected_cell_keys(payload),
        availability_as_of_verified=_optional_boolean(
            payload, "availability_as_of_verified"
        ),
        operational_use_verified=_optional_boolean(payload, "operational_use_verified"),
        metrics=metrics,
        error_code=result.error_code,
    )


def _validate_snapshot(
    snapshot: EnvironmentalSnapshot,
    requested_date: date,
    expected_variables: tuple[str, ...],
) -> None:
    if not isinstance(snapshot, EnvironmentalSnapshot):
        raise TypeError("El ensamblador debe devolver EnvironmentalSnapshot.")
    if snapshot.request.target_date != requested_date:
        raise ValueError(
            "El ensamblador devolvió una fecha diferente de la solicitada."
        )
    variable_ids = tuple(result.variable_id for result in snapshot.variables)
    if variable_ids != expected_variables or len(set(variable_ids)) != len(
        variable_ids
    ):
        raise ValueError(
            "El conjunto u orden de variables cambió durante el diagnóstico."
        )


def _daily_snapshot(snapshot: EnvironmentalSnapshot) -> DailySnapshotDiagnostic:
    return DailySnapshotDiagnostic(
        requested_date=snapshot.request.target_date,
        schema_version=snapshot.schema_version,
        status=snapshot.status.value,
        available_count=snapshot.available_count,
        no_data_count=snapshot.no_data_count,
        error_count=snapshot.error_count,
        safety_blocked=snapshot.safety.blocked,
        variables=tuple(
            _daily_variable(result, snapshot.request.target_date)
            for result in snapshot.variables
        ),
    )


def _period_variable(
    variable_id: str,
    snapshots: Sequence[EnvironmentalSnapshot],
    daily: Sequence[DailySnapshotDiagnostic],
) -> VariablePeriodDiagnostic:
    results = [snapshot.get(variable_id) for snapshot in snapshots]
    daily_results = [
        next(item for item in day.variables if item.variable_id == variable_id)
        for day in daily
    ]
    template = results[0]
    if any(
        result.shared_operation != template.shared_operation
        or result.spatial_scope != template.spatial_scope
        or result.value_paths != template.value_paths
        or result.governance != template.governance
        for result in results[1:]
    ):
        raise ValueError(f"El contrato de {variable_id!r} cambió entre fechas.")

    payloads = [
        result.payload for result in results if isinstance(result.payload, Mapping)
    ]
    metrics = tuple(
        _metric_summary(
            path,
            tuple(
                value for payload in payloads for value in _extract_path(payload, path)
            ),
        )
        for path in template.value_paths
    )
    states = Counter(item.state for item in daily_results)
    statuses = Counter(item.source_status or "none" for item in daily_results)
    source_keys = [key for item in daily_results for key in item.source_time_keys]
    cell_keys = [key for item in daily_results for key in item.selected_cell_keys]
    coverage_values = [
        item.coverage_fraction
        for item in daily_results
        if item.coverage_fraction is not None
    ]
    availability_declared = [
        item.availability_as_of_verified
        for item in daily_results
        if item.availability_as_of_verified is not None
    ]
    operational_declared = [
        item.operational_use_verified
        for item in daily_results
        if item.operational_use_verified is not None
    ]
    available = states[AssemblyState.AVAILABLE.value]
    return VariablePeriodDiagnostic(
        variable_id=variable_id,
        layer="optional" if variable_id in OPTIONAL_VARIABLES else "base",
        shared_operation=template.shared_operation,
        spatial_scope=template.spatial_scope.value,
        intended_role=template.governance.intended_role,
        implementation_status=template.governance.implementation_status,
        scoring_status=template.governance.scoring_status,
        predictively_valid=template.governance.predictively_valid,
        days_requested=len(daily_results),
        days_available=available,
        days_no_data=states[AssemblyState.NO_DATA.value],
        days_error=states[AssemblyState.ERROR.value],
        availability_fraction=available / len(daily_results),
        days_with_primary_values=sum(
            item.primary_value_count > 0 for item in daily_results
        ),
        days_using_fallback=sum(item.fallback_used for item in daily_results),
        days_historical_final=statuses["historica_final"],
        source_status_counts=tuple(
            StatusCount(status, count) for status, count in sorted(statuses.items())
        ),
        source_observations_total=len(source_keys),
        unique_source_observations=len(set(source_keys)),
        reused_source_observations=len(source_keys) - len(set(source_keys)),
        selected_cells_stable=(len(set(cell_keys)) <= 1 if cell_keys else None),
        coverage_fraction=_metric_summary("daily_coverage_fraction", coverage_values),
        metrics=metrics,
        source_identity=_source_identity(payloads),
        availability_verification_declared_days=len(availability_declared),
        availability_verified_days=sum(availability_declared),
        operational_verification_declared_days=len(operational_declared),
        operational_verified_days=sum(operational_declared),
        no_data_dates=tuple(
            item.requested_date
            for item in daily_results
            if item.state == AssemblyState.NO_DATA.value
        ),
        error_dates=tuple(
            item.requested_date
            for item in daily_results
            if item.state == AssemblyState.ERROR.value
        ),
        technical_classification="pending_human_review",
    )


def _operation_membership(
    snapshot: EnvironmentalSnapshot,
) -> tuple[OperationMembership, ...]:
    membership: dict[str, list[str]] = {}
    for result in snapshot.variables:
        membership.setdefault(result.shared_operation, []).append(result.variable_id)
    return tuple(
        OperationMembership(operation, tuple(variable_ids))
        for operation, variable_ids in membership.items()
    )


def _selection_as_of(target_date: date, generated_at_utc: datetime) -> datetime:
    proposed = datetime.combine(target_date, time.min, tzinfo=timezone.utc) + timedelta(
        hours=HISTORICAL_SELECTION_LAG_HOURS
    )
    return min(proposed, generated_at_utc)


def _cached_bathymetry(providers: AssemblerProviders) -> AssemblerProviders:
    cache: dict[tuple[float, float], object] = {}
    original = providers.fetch_bathymetry

    def fetch(lat: float, lon: float):
        key = (float(lat), float(lon))
        if key not in cache:
            cache[key] = original(*key)
        return cache[key]

    return replace(providers, fetch_bathymetry=fetch)


def run_diagnostic(
    end_date: date,
    days: int = DEFAULT_DAYS,
    *,
    hour_start: int = 0,
    hour_end: int = 23,
    field_half_width_deg: float = DEFAULT_FIELD_HALF_WIDTH_DEG,
    include_olci: bool = True,
    include_mur: bool = True,
    mur_mode: MurMode = MurMode.HISTORICAL_DIAGNOSTIC,
    generated_at_utc: datetime | None = None,
    providers: AssemblerProviders | None = None,
    assembler: Assembler = assemble_environmental_snapshot,
    spec_path: Path | str = DEFAULT_SPEC_PATH,
) -> EnvironmentalDiagnosticReport:
    """Ejecuta una instantánea por fecha y agrega evidencia sin matrices."""
    dates = _requested_dates(end_date, days)
    if not (0 <= hour_start <= hour_end <= 23):
        raise ValueError("Debe cumplirse 0 <= hour_start <= hour_end <= 23.")
    if not isinstance(include_olci, bool) or not isinstance(include_mur, bool):
        raise TypeError("include_olci e include_mur deben ser booleanos explícitos.")
    if not isinstance(mur_mode, MurMode):
        raise TypeError("mur_mode debe ser MurMode.")
    generated = generated_at_utc or datetime.now(timezone.utc)
    if (
        not isinstance(generated, datetime)
        or generated.tzinfo is None
        or generated.utcoffset() is None
    ):
        raise ValueError("generated_at_utc debe ser datetime con zona horaria.")
    generated = generated.astimezone(timezone.utc)
    if end_date > default_end_date(generated):
        raise ValueError("end_date debe ser un día local ya completado en Pucusana.")

    base_providers = providers if providers is not None else AssemblerProviders()
    if not isinstance(base_providers, AssemblerProviders):
        raise TypeError("providers debe ser AssemblerProviders o None.")
    cached_providers = _cached_bathymetry(base_providers)
    expected = VARIABLE_ORDER
    if include_olci:
        expected += OPTIONAL_VARIABLE_ORDER
    if include_mur:
        expected += MUR_VARIABLE_ORDER

    snapshots: list[EnvironmentalSnapshot] = []
    daily: list[DailySnapshotDiagnostic] = []
    for target_date in dates:
        as_of = _selection_as_of(target_date, generated)
        chlorophyll_options = ChlorophyllOptions(as_of) if include_olci else None
        mur_options = MurOptions(as_of, mode=mur_mode) if include_mur else None
        request = AssemblyRequest(
            lat=REFERENCE_LATITUDE,
            lon=REFERENCE_LONGITUDE,
            target_date=target_date,
            hour_start_local=hour_start,
            hour_end_local=hour_end,
            field_half_width_deg=field_half_width_deg,
        )
        snapshot = assembler(
            request,
            providers=cached_providers,
            spec_path=spec_path,
            chlorophyll_options=chlorophyll_options,
            mur_options=mur_options,
        )
        _validate_snapshot(snapshot, target_date, expected)
        snapshots.append(snapshot)
        daily.append(_daily_snapshot(snapshot))

    operations = _operation_membership(snapshots[0])
    variables = tuple(
        _period_variable(variable_id, snapshots, daily) for variable_id in expected
    )
    return EnvironmentalDiagnosticReport(
        schema_version=SCHEMA_VERSION,
        generated_at_utc=generated,
        reference_name=REFERENCE_NAME,
        reference_latitude=REFERENCE_LATITUDE,
        reference_longitude=REFERENCE_LONGITUDE,
        requested_start_date=dates[0],
        requested_end_date=dates[-1],
        days_requested=len(dates),
        hour_start_local=hour_start,
        hour_end_local=hour_end,
        field_half_width_deg=float(field_half_width_deg),
        includes_olci=include_olci,
        includes_mur=include_mur,
        mur_mode=mur_mode.value if include_mur else None,
        historical_selection_lag_hours=HISTORICAL_SELECTION_LAG_HOURS,
        variables_expected=expected,
        independent_source_operations=operations,
        n_independent_source_operations=len(operations),
        days=tuple(daily),
        variables=variables,
        interpretation_warning=INTERPRETATION_WARNING,
        classification_status="pending_human_review_after_real_run",
    )


def _format_metric(metric: MetricSummary) -> str:
    if metric.count == 0:
        return "sin_valores"
    if metric.aggregation == "circular_degrees":
        mean = (
            "indefinida"
            if metric.circular_mean_degrees is None
            else f"{metric.circular_mean_degrees:.2f}°"
        )
        return (
            f"n={metric.count}, media_circular={mean}, "
            f"concentración={metric.circular_resultant_length:.3f}"
        )
    if metric.aggregation == "categorical_values_not_averaged":
        return f"n={metric.count}, categorías={list(metric.distinct_values)}"
    return (
        f"n={metric.count}, min={metric.minimum:.4f}, "
        f"mediana={metric.median:.4f}, max={metric.maximum:.4f}, "
        f"rango={metric.span:.4f}"
    )


def format_report(report: EnvironmentalDiagnosticReport) -> str:
    """Salida humana compacta; no expone payloads ni observaciones crudas."""
    lines = [
        "=== DIAGNÓSTICO AMBIENTAL CONSOLIDADO | PUCUSANA ===",
        f"generado_utc: {report.generated_at_utc.isoformat()}",
        (
            f"periodo: {report.requested_start_date.isoformat()} a "
            f"{report.requested_end_date.isoformat()} ({report.days_requested} días)"
        ),
        (
            f"referencia: {report.reference_name} "
            f"({report.reference_latitude:.3f}, {report.reference_longitude:.3f})"
        ),
        (
            f"capas_opcionales: OLCI={'sí' if report.includes_olci else 'no'}, "
            f"MUR={'sí' if report.includes_mur else 'no'}"
        ),
        (
            f"operaciones_fuente_independientes: "
            f"{report.n_independent_source_operations}"
        ),
        "",
        "--- RESUMEN POR VARIABLE ---",
    ]
    for variable in report.variables:
        coverage = (
            "sin_denominador"
            if variable.coverage_fraction.count == 0
            else f"mediana={variable.coverage_fraction.median * 100:.1f}%"
        )
        primary = (
            variable.metrics[0]
            if variable.metrics
            else MetricSummary("none", "linear_numeric", 0)
        )
        lines.extend(
            [
                (
                    f"{variable.variable_id}: disponible={variable.days_available}/"
                    f"{variable.days_requested}, sin_dato={variable.days_no_data}, "
                    f"error={variable.days_error}, fallback={variable.days_using_fallback}, "
                    f"cobertura={coverage}"
                ),
                f"  valor_principal[{primary.path}]: {_format_metric(primary)}",
                (
                    f"  fuente={variable.shared_operation}; observaciones="
                    f"{variable.unique_source_observations} únicas/"
                    f"{variable.reused_source_observations} reutilizadas; "
                    f"clasificación={variable.technical_classification}"
                ),
            ]
        )
        if variable.no_data_dates:
            lines.append(
                "  fechas_sin_dato: "
                + ", ".join(value.isoformat() for value in variable.no_data_dates)
            )
        if variable.error_dates:
            lines.append(
                "  fechas_error: "
                + ", ".join(value.isoformat() for value in variable.error_dates)
            )
    lines.extend(
        [
            "",
            "--- LÍMITES DE INTERPRETACIÓN ---",
            report.interpretation_warning,
            "DECISIÓN: clasificación técnica pendiente de revisión humana del resultado real.",
        ]
    )
    return "\n".join(lines)


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Tipo no serializable: {type(value).__name__}")


def report_to_json(report: EnvironmentalDiagnosticReport) -> str:
    return json.dumps(
        asdict(report),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        default=_json_default,
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La fecha debe usar YYYY-MM-DD.") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resume hasta 31 días de las variables ambientales de Pucusana sin "
            "guardar matrices ni calcular scoring."
        )
    )
    parser.add_argument("--end-date", type=_parse_date, default=None)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--hour-start", type=int, default=0)
    parser.add_argument("--hour-end", type=int, default=23)
    parser.add_argument(
        "--field-half-width-deg", type=float, default=DEFAULT_FIELD_HALF_WIDTH_DEG
    )
    parser.add_argument(
        "--olci",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Incluye OLCI y su gradiente; use --no-olci para omitirlos.",
    )
    parser.add_argument(
        "--mur",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Incluye MUR local y su gradiente; use --no-mur para omitirlos.",
    )
    parser.add_argument(
        "--mur-mode",
        choices=[mode.value for mode in MurMode],
        default=MurMode.HISTORICAL_DIAGNOSTIC.value,
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    end_date = args.end_date or default_end_date()
    report = run_diagnostic(
        end_date=end_date,
        days=args.days,
        hour_start=args.hour_start,
        hour_end=args.hour_end,
        field_half_width_deg=args.field_half_width_deg,
        include_olci=args.olci,
        include_mur=args.mur,
        mur_mode=MurMode(args.mur_mode),
    )
    print(report_to_json(report) if args.json else format_report(report))
    if any(variable.days_error for variable in report.variables):
        return 4
    if not any(variable.days_available for variable in report.variables):
        return 2
    if any(variable.days_no_data for variable in report.variables):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
