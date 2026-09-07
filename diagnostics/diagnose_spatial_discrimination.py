"""Diagnóstico multípunto de diferenciación espacial dentro de 0-10 km.

El programa no crea puntos de faena. Exige un YAML aprobado que declare la
distancia mar adentro desde el litoral y consulta el ensamblador en cada punto.
La salida conserva solo conteos, tolerancias y diferencias máximas, nunca
matrices oceanográficas crudas ni un score pesquero. Las series se comparan
solo sobre timestamps comunes; una diferencia horaria no es una diferencia
espacial.

Ejemplo:

    python -m diagnostics.diagnose_spatial_discrimination \
        --points ruta/a/operational_points.yaml --date 2026-09-07 --json
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from math import isfinite
from numbers import Real
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from assembly.environmental_assembler import (
    VARIABLE_ORDER,
    AssemblyRequest,
    assemble_environmental_snapshot,
)


POINTS_SCHEMA_VERSION = "operational_points_v1"
DISTANCE_BASIS = "distance_offshore_from_coastline"
MIN_DISTANCE_KM = 0.0
MAX_DISTANCE_KM = 10.0

REGIONAL_CONTEXT_VARIABLES = {"sst_observed_ostia", "thermal_front"}
TEMPORAL_VALUE_KEYS = {
    "sst": "value_celsius",
    "salinidad": "value_salinity",
    "temperature_10m": "temperature_10m_celsius",
    "delta_sst_t10": "delta_sst_t10_celsius",
}
COMPARISON_ABS_TOLERANCE = {
    "sst": 0.01,
    "oleaje": 0.01,
    "clorofila": 0.001,
    "salinidad": 0.001,
    "sst_observed_ostia": 0.01,
    "thermal_front": 0.001,
    "temperature_10m": 0.01,
    "delta_sst_t10": 0.01,
    "surface_currents": 0.001,
    "batimetria": 0.01,
}
_INVALID = object()


@dataclass(frozen=True)
class CandidatePoint:
    point_id: str
    lat: float
    lon: float
    distance_offshore_km: float
    geometry_source: str


@dataclass(frozen=True)
class VariableDiscrimination:
    variable_id: str
    spatial_scope: str
    available_points: int
    total_points: int
    comparable_points: int
    distinct_value_groups: int
    distinct_source_cell_signatures: int
    temporal_alignment_status: str
    common_timestamp_count: int | None
    comparison_abs_tolerance: float
    max_pairwise_abs_difference: float | None
    classification: str
    observed_numeric_variation: bool
    eligible_for_spatial_backtest: bool


def load_candidate_points(path: str | Path) -> tuple[CandidatePoint, ...]:
    """Carga geometría aprobada; no infiere costa, rumbo ni sectores."""

    with Path(path).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, Mapping):
        raise ValueError("el archivo de puntos debe ser un mapping YAML")
    if document.get("schema_version") != POINTS_SCHEMA_VERSION:
        raise ValueError(f"schema_version debe ser {POINTS_SCHEMA_VERSION!r}")
    if document.get("geometry_status") != "approved":
        raise ValueError("geometry_status debe ser 'approved'")
    if document.get("distance_basis") != DISTANCE_BASIS:
        raise ValueError(f"distance_basis debe ser {DISTANCE_BASIS!r}")
    rows = document.get("points")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("se requieren al menos dos puntos operativos aprobados")

    points: list[CandidatePoint] = []
    ids: set[str] = set()
    coordinates: set[tuple[float, float]] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise ValueError(f"points[{index}] debe ser un mapping")
        point_id = str(raw.get("id", "")).strip()
        if not point_id or point_id in ids:
            raise ValueError(f"points[{index}].id debe ser único y no vacío")
        geometry_source = str(raw.get("geometry_source", "")).strip()
        if not geometry_source:
            raise ValueError(f"points[{index}].geometry_source es obligatorio")
        try:
            lat = float(raw["lat"])
            lon = float(raw["lon"])
            distance_km = float(raw["distance_offshore_km"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"points[{index}] requiere lat, lon y distance_offshore_km numéricos"
            ) from exc
        if not all(isfinite(value) for value in (lat, lon, distance_km)):
            raise ValueError(f"points[{index}] contiene valores no finitos")
        if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
            raise ValueError(f"points[{index}] tiene coordenadas fuera de rango")
        if not MIN_DISTANCE_KM <= distance_km <= MAX_DISTANCE_KM:
            raise ValueError(f"points[{index}] está fuera del alcance 0-10 km")
        coordinate = (lat, lon)
        if coordinate in coordinates:
            raise ValueError("las coordenadas de los puntos deben ser distintas")
        ids.add(point_id)
        coordinates.add(coordinate)
        points.append(
            CandidatePoint(
                point_id=point_id,
                lat=lat,
                lon=lon,
                distance_offshore_km=distance_km,
                geometry_source=geometry_source,
            )
        )
    return tuple(points)


def _stable_signature(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()[:16]


def _numeric_projection(value: Any) -> Any:
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        return numeric if isfinite(numeric) else _INVALID
    if isinstance(value, (list, tuple)):
        converted = tuple(_numeric_projection(item) for item in value)
        return _INVALID if any(item is _INVALID for item in converted) else converted
    return _INVALID


def _sample_series(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    series: dict[str, Any] = {}
    for sample in payload.get("samples", ()):
        if not isinstance(sample, Mapping):
            continue
        timestamp = sample.get("time_utc")
        value = _numeric_projection(sample.get(key))
        if isinstance(timestamp, str) and timestamp and value is not _INVALID:
            series[timestamp] = value
    return series


def _measurement_series(payload: Mapping[str, Any]) -> dict[str, Any]:
    series: dict[str, Any] = {}
    for measurement in payload.get("measurements", ()):
        if not isinstance(measurement, Mapping):
            continue
        timestamp = measurement.get("time_utc")
        value = _numeric_projection(
            (measurement.get("uo_m_s"), measurement.get("vo_m_s"))
        )
        if isinstance(timestamp, str) and timestamp and value is not _INVALID:
            series[timestamp] = value
    return series


def _temporal_projection(
    variable_id: str, payload: Mapping[str, Any]
) -> dict[str, Any] | None:
    if variable_id in TEMPORAL_VALUE_KEYS:
        return _sample_series(payload, TEMPORAL_VALUE_KEYS[variable_id])
    if variable_id == "surface_currents":
        return _measurement_series(payload)
    return None


def _static_projection(variable_id: str, payload: Mapping[str, Any]) -> Any:
    raw_projections: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "oleaje": lambda item: item.get("significant_wave_height_m"),
        "clorofila": lambda item: item.get("value_mg_m3"),
        "sst_observed_ostia": lambda item: item.get("sst_celsius"),
        "thermal_front": lambda item: item.get("gradient_c_per_km"),
        "batimetria": lambda item: (item.get("depth_m"), item.get("slope_deg")),
    }
    if variable_id not in raw_projections:
        return _INVALID
    return _numeric_projection(raw_projections[variable_id](payload))


def _projections_close(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        return abs(left - right) <= tolerance
    if isinstance(left, tuple) and isinstance(right, tuple):
        return len(left) == len(right) and all(
            _projections_close(a, b, tolerance) for a, b in zip(left, right)
        )
    return False


def _projection_abs_difference(left: Any, right: Any) -> float | None:
    if isinstance(left, float) and isinstance(right, float):
        return abs(left - right)
    if isinstance(left, tuple) and isinstance(right, tuple) and len(left) == len(right):
        differences = [
            _projection_abs_difference(a, b) for a, b in zip(left, right)
        ]
        if any(value is None for value in differences):
            return None
        return max((value for value in differences if value is not None), default=0.0)
    return None


def _distinct_groups(projections: Sequence[Any], tolerance: float) -> int:
    representatives: list[Any] = []
    for projection in projections:
        if not any(
            _projections_close(projection, representative, tolerance)
            for representative in representatives
        ):
            representatives.append(projection)
    return len(representatives)


def _max_pairwise_difference(projections: Sequence[Any]) -> float | None:
    if len(projections) < 2:
        return None
    differences = [
        _projection_abs_difference(projections[left], projections[right])
        for left in range(len(projections))
        for right in range(left + 1, len(projections))
    ]
    finite_differences = [value for value in differences if value is not None]
    return max(finite_differences) if finite_differences else None


def _cell_projection(variable_id: str, payload: Mapping[str, Any]) -> Any:
    if variable_id in REGIONAL_CONTEXT_VARIABLES:
        return (payload.get("latitudes"), payload.get("longitudes"))
    if variable_id == "surface_currents":
        return sorted(
            {
                (item.get("cell_lat"), item.get("cell_lon"))
                for item in payload.get("measurements", ())
                if isinstance(item, Mapping)
            }
        )
    return (payload.get("cell_lat"), payload.get("cell_lon"))


def _classify(
    variable_id: str,
    available_points: int,
    total_points: int,
    comparable_points: int,
    distinct_values: int,
    temporal_alignment_status: str,
) -> tuple[str, bool]:
    if variable_id == "oleaje":
        return "safety_gate_not_ranking", False
    if variable_id in REGIONAL_CONTEXT_VARIABLES:
        return "regional_context_not_point_discriminator", False
    if available_points < total_points:
        return "insufficient_coverage", False
    if temporal_alignment_status == "no_common_timestamps":
        return "insufficient_temporal_alignment", False
    if comparable_points < total_points:
        return "insufficient_comparable_values", False
    if distinct_values >= 2:
        return "observed_numeric_variation", True
    return "no_observed_numeric_variation", False


def diagnose_spatial_discrimination(
    points: Sequence[CandidatePoint],
    target_date: date,
    *,
    assembler: Callable[..., Any] = assemble_environmental_snapshot,
) -> dict[str, Any]:
    """Ejecuta ensamblado por punto y resume diferenciación sin puntuar."""

    if len(points) < 2:
        raise ValueError("se requieren al menos dos puntos")
    snapshots: list[tuple[CandidatePoint, Mapping[str, Any]]] = []
    for point in points:
        request = AssemblyRequest(
            lat=point.lat,
            lon=point.lon,
            target_date=target_date,
        )
        snapshot = assembler(request)
        document = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        if not isinstance(document, Mapping):
            raise TypeError("el ensamblador debe devolver snapshot o mapping")
        snapshots.append((point, document))

    results: list[VariableDiscrimination] = []
    for variable_id in VARIABLE_ORDER:
        static_projections: list[Any] = []
        temporal_series: list[dict[str, Any]] = []
        cells: set[str] = set()
        available = 0
        spatial_scope = "unknown"
        for _, snapshot in snapshots:
            raw_result = snapshot.get("variables", {}).get(variable_id, {})
            if not isinstance(raw_result, Mapping):
                continue
            spatial_scope = str(raw_result.get("spatial_scope", spatial_scope))
            if raw_result.get("state") != "available":
                continue
            payload = raw_result.get("payload")
            if not isinstance(payload, Mapping):
                continue
            available += 1
            temporal = _temporal_projection(variable_id, payload)
            if temporal is not None:
                if temporal:
                    temporal_series.append(temporal)
            else:
                projection = _static_projection(variable_id, payload)
                if projection is not _INVALID:
                    static_projections.append(projection)
            cells.add(_stable_signature(_cell_projection(variable_id, payload)))

        common_timestamp_count: int | None = None
        temporal_alignment_status = "not_applicable"
        projections = static_projections
        if variable_id in TEMPORAL_VALUE_KEYS or variable_id == "surface_currents":
            common_timestamps: set[str] = set()
            if temporal_series and len(temporal_series) == available:
                common_timestamps = set(temporal_series[0])
                for series in temporal_series[1:]:
                    common_timestamps &= set(series)
            common_timestamp_count = len(common_timestamps)
            if common_timestamps:
                ordered_timestamps = sorted(common_timestamps)
                projections = [
                    tuple(series[timestamp] for timestamp in ordered_timestamps)
                    for series in temporal_series
                ]
                temporal_alignment_status = "aligned_on_common_timestamps"
            else:
                projections = []
                temporal_alignment_status = "no_common_timestamps"

        tolerance = COMPARISON_ABS_TOLERANCE[variable_id]
        distinct_values = _distinct_groups(projections, tolerance)
        comparable_points = len(projections)
        observed_variation = comparable_points >= 2 and distinct_values >= 2
        classification, eligible = _classify(
            variable_id,
            available,
            len(points),
            comparable_points,
            distinct_values,
            temporal_alignment_status,
        )
        results.append(
            VariableDiscrimination(
                variable_id=variable_id,
                spatial_scope=spatial_scope,
                available_points=available,
                total_points=len(points),
                comparable_points=comparable_points,
                distinct_value_groups=distinct_values,
                distinct_source_cell_signatures=len(cells),
                temporal_alignment_status=temporal_alignment_status,
                common_timestamp_count=common_timestamp_count,
                comparison_abs_tolerance=tolerance,
                max_pairwise_abs_difference=_max_pairwise_difference(projections),
                classification=classification,
                observed_numeric_variation=observed_variation,
                eligible_for_spatial_backtest=eligible,
            )
        )

    return {
        "schema_version": "spatial_discrimination_report_v2",
        "target_date": target_date.isoformat(),
        "operational_range_km": [MIN_DISTANCE_KM, MAX_DISTANCE_KM],
        "distance_basis": DISTANCE_BASIS,
        "n_points": len(points),
        "points": [asdict(point) for point in points],
        "snapshot_statuses": [
            {
                "point_id": point.point_id,
                "status": snapshot.get("status"),
            }
            for point, snapshot in snapshots
        ],
        "variables": [asdict(result) for result in results],
        "variables_eligible_for_spatial_backtest": [
            result.variable_id
            for result in results
            if result.eligible_for_spatial_backtest
        ],
        "interpretation": (
            "Diagnóstico técnico con alineación temporal y tolerancias; solo admite "
            "variables a backtesting espacial. No ordena puntos, no valida captura, "
            "no calcula favorabilidad y no autoriza navegación."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", required=True, type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    points = load_candidate_points(args.points)
    report = diagnose_spatial_discrimination(points, args.date)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Fecha: {report['target_date']} | puntos: {report['n_points']}")
        for item in report["variables"]:
            print(
                f"{item['variable_id']}: {item['classification']} | "
                f"grupos={item['distinct_value_groups']} | "
                f"celdas={item['distinct_source_cell_signatures']}"
            )
        print(report["interpretation"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
