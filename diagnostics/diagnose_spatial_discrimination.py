"""Diagnóstico multípunto de diferenciación espacial dentro de 0-10 km.

El programa no crea puntos de faena. Exige un YAML aprobado que declare la
distancia mar adentro desde el litoral y consulta el ensamblador en cada punto.
La salida conserva solo conteos y huellas, nunca matrices oceanográficas
crudas ni un score pesquero.

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
NON_RANKING_VARIABLES = REGIONAL_CONTEXT_VARIABLES | {"oleaje"}


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
    distinct_value_signatures: int
    distinct_source_cell_signatures: int
    classification: str
    eligible_to_rank_points: bool


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


def _sample_values(payload: Mapping[str, Any], key: str) -> list[tuple[Any, Any]]:
    return [
        (sample.get("time_utc"), sample.get(key))
        for sample in payload.get("samples", ())
        if isinstance(sample, Mapping) and sample.get(key) is not None
    ]


def _measurement_values(payload: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (
            measurement.get("time_utc"),
            measurement.get("uo_m_s"),
            measurement.get("vo_m_s"),
            measurement.get("speed_m_s"),
            measurement.get("direction_toward_deg"),
        )
        for measurement in payload.get("measurements", ())
        if isinstance(measurement, Mapping)
    ]


def _value_projection(variable_id: str, payload: Mapping[str, Any]) -> Any:
    projections: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "sst": lambda item: _sample_values(item, "value_celsius"),
        "oleaje": lambda item: item.get("significant_wave_height_m"),
        "clorofila": lambda item: item.get("value_mg_m3"),
        "salinidad": lambda item: _sample_values(item, "value_salinity"),
        "sst_observed_ostia": lambda item: item.get("sst_celsius"),
        "thermal_front": lambda item: item.get("gradient_c_per_km"),
        "temperature_10m": lambda item: _sample_values(
            item, "temperature_10m_celsius"
        ),
        "delta_sst_t10": lambda item: _sample_values(
            item, "delta_sst_t10_celsius"
        ),
        "surface_currents": _measurement_values,
        "batimetria": lambda item: (item.get("depth_m"), item.get("slope_deg")),
    }
    return projections[variable_id](payload)


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
    distinct_values: int,
) -> tuple[str, bool]:
    if variable_id == "oleaje":
        return "safety_gate_not_ranking", False
    if variable_id in REGIONAL_CONTEXT_VARIABLES:
        return "regional_context_not_point_discriminator", False
    if available_points < total_points:
        return "insufficient_coverage", False
    if distinct_values >= 2:
        return "observed_point_differentiation", True
    return "no_observed_point_differentiation", False


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
        values: set[str] = set()
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
            values.add(_stable_signature(_value_projection(variable_id, payload)))
            cells.add(_stable_signature(_cell_projection(variable_id, payload)))
        classification, eligible = _classify(
            variable_id, available, len(points), len(values)
        )
        results.append(
            VariableDiscrimination(
                variable_id=variable_id,
                spatial_scope=spatial_scope,
                available_points=available,
                total_points=len(points),
                distinct_value_signatures=len(values),
                distinct_source_cell_signatures=len(cells),
                classification=classification,
                eligible_to_rank_points=eligible,
            )
        )

    return {
        "schema_version": "spatial_discrimination_report_v1",
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
        "ranking_variables_with_observed_differentiation": [
            result.variable_id for result in results if result.eligible_to_rank_points
        ],
        "interpretation": (
            "Diagnóstico técnico de diferenciación; no valida captura, no calcula "
            "favorabilidad y no autoriza navegación."
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
                f"valores={item['distinct_value_signatures']} | "
                f"celdas={item['distinct_source_cell_signatures']}"
            )
        print(report["interpretation"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
