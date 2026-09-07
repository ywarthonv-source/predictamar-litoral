"""Construye un bundle diario consumible por la futura aplicación.

El backend usa exactamente el ensamblador ambiental y puntos operativos
aprobados. No calcula índices por especie: la matriz v1 aún no tiene curvas
calibradas ni validación independiente. El bundle incluye fecha, hora de
generación, contrato operativo, bloqueo de scoring, huella integral y estado
por punto para que la aplicación pueda rechazar datos viejos o incoherentes.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isclose, isfinite
from numbers import Real
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence

from assembly.environmental_assembler import (
    SCHEMA_VERSION as ENVIRONMENTAL_SNAPSHOT_SCHEMA_VERSION,
    AssemblyRequest,
    assemble_environmental_snapshot,
)
from diagnostics.diagnose_spatial_discrimination import (
    CandidatePoint,
    DISTANCE_BASIS,
    MAX_DISTANCE_KM,
    MIN_DISTANCE_KM,
    load_candidate_points,
)


BUNDLE_SCHEMA_VERSION = "daily_environmental_bundle_v1"
DEFAULT_MAX_FUTURE_SKEW = timedelta(minutes=5)
SCORING_REASON = (
    "species_weighting_v1 es una matriz de investigación sin "
    "transformaciones calibradas ni validación independiente"
)
INTEGRITY_FIELDS = (
    "schema_version",
    "generated_at_utc",
    "target_date",
    "operational_contract",
    "status_counts",
    "scoring",
    "points",
    "snapshots",
)
TOP_LEVEL_FIELDS = set(INTEGRITY_FIELDS) | {"run_id", "content_sha256"}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _integrity_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {field: bundle[field] for field in INTEGRITY_FIELDS}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at debe incluir zona horaria")
    return value.astimezone(timezone.utc)


def _scoring_contract() -> dict[str, Any]:
    return {
        "status": "not_generated",
        "reason": SCORING_REASON,
        "is_probability": False,
        "operational_enabled": False,
    }


def _point_documents(points: Sequence[CandidatePoint]) -> list[dict[str, Any]]:
    if len(points) < 2:
        raise ValueError("se requieren al menos dos puntos operativos aprobados")
    documents: list[dict[str, Any]] = []
    ids: set[str] = set()
    coordinates: set[tuple[float, float]] = set()
    for index, point in enumerate(points):
        if not isinstance(point, CandidatePoint):
            raise TypeError(f"points[{index}] debe ser CandidatePoint")
        point_id = point.point_id
        geometry_source = point.geometry_source
        if not isinstance(point_id, str) or not point_id.strip() or point_id != point_id.strip():
            raise ValueError(f"points[{index}].point_id debe ser único y no vacío")
        if point_id in ids:
            raise ValueError(f"points[{index}].point_id está duplicado")
        if not isinstance(geometry_source, str) or not geometry_source.strip():
            raise ValueError(f"points[{index}].geometry_source es obligatorio")
        raw_numbers = (point.lat, point.lon, point.distance_offshore_km)
        if any(isinstance(value, bool) or not isinstance(value, Real) for value in raw_numbers):
            raise TypeError(f"points[{index}] requiere coordenadas y distancia numéricas")
        lat, lon, distance_km = (float(value) for value in raw_numbers)
        if not all(isfinite(value) for value in (lat, lon, distance_km)):
            raise ValueError(f"points[{index}] contiene valores no finitos")
        if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
            raise ValueError(f"points[{index}] tiene coordenadas fuera de rango")
        if not MIN_DISTANCE_KM <= distance_km <= MAX_DISTANCE_KM:
            raise ValueError(f"{point_id}: distancia fuera de 0-10 km")
        coordinate = (lat, lon)
        if coordinate in coordinates:
            raise ValueError("las coordenadas de los puntos deben ser distintas")
        ids.add(point_id)
        coordinates.add(coordinate)
        documents.append(
            {
                "point_id": point_id,
                "lat": lat,
                "lon": lon,
                "distance_offshore_km": distance_km,
                "geometry_source": geometry_source,
            }
        )
    return documents


def build_daily_bundle(
    points: Sequence[CandidatePoint],
    target_date: date,
    *,
    assembler: Callable[..., Any] = assemble_environmental_snapshot,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Ejecuta una instantánea por punto y fija un manifiesto verificable."""

    generated = _as_utc(generated_at or datetime.now(timezone.utc))
    point_documents = _point_documents(points)
    snapshots = []
    for point, point_document in zip(points, point_documents):
        request = AssemblyRequest(
            lat=point_document["lat"],
            lon=point_document["lon"],
            target_date=target_date,
        )
        snapshot = assembler(request)
        document = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        if not isinstance(document, Mapping):
            raise TypeError("el ensamblador debe devolver snapshot o mapping")
        snapshots.append({"point_id": point.point_id, "snapshot": dict(document)})

    status_counts: dict[str, int] = {}
    for item in snapshots:
        status = str(item["snapshot"].get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "target_date": target_date.isoformat(),
        "operational_contract": {
            "distance_basis": DISTANCE_BASIS,
            "range_km": [MIN_DISTANCE_KM, MAX_DISTANCE_KM],
            "point_count": len(points),
        },
        "status_counts": status_counts,
        "scoring": _scoring_contract(),
        "points": point_documents,
        "snapshots": snapshots,
    }
    content_sha256 = _hash(manifest)
    run_id = f"{target_date.isoformat()}-{content_sha256[:16]}"
    return {
        **manifest,
        "run_id": run_id,
        "content_sha256": content_sha256,
    }


def validate_daily_bundle(
    bundle: Mapping[str, Any],
    *,
    expected_target_date: date | None = None,
    checked_at: datetime | None = None,
    max_generation_age: timedelta | None = None,
    max_future_skew: timedelta = DEFAULT_MAX_FUTURE_SKEW,
) -> None:
    """Valida integridad, coherencia y, cuando se pide, frescura del bundle."""

    if not isinstance(bundle, Mapping):
        raise ValueError("bundle debe ser un mapping")
    actual_fields = set(bundle)
    if actual_fields != TOP_LEVEL_FIELDS:
        missing = sorted(TOP_LEVEL_FIELDS - actual_fields)
        extra = sorted(actual_fields - TOP_LEVEL_FIELDS)
        raise ValueError(
            f"campos raíz inválidos; faltan={missing}, sobran={extra}"
        )
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"schema_version debe ser {BUNDLE_SCHEMA_VERSION!r}")
    if not isinstance(bundle.get("target_date"), str) or not isinstance(
        bundle.get("generated_at_utc"), str
    ):
        raise ValueError("fecha objetivo y fecha de generación deben ser texto ISO")
    try:
        target_date = date.fromisoformat(bundle["target_date"])
        generated = datetime.fromisoformat(
            bundle["generated_at_utc"].replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("fecha objetivo o fecha de generación inválida") from exc
    generated_utc = _as_utc(generated)
    if generated.utcoffset() != timedelta(0):
        raise ValueError("generated_at_utc debe estar expresado en UTC")
    if not isinstance(max_future_skew, timedelta) or max_future_skew < timedelta(0):
        raise ValueError("max_future_skew debe ser timedelta no negativo")
    checked_utc = _as_utc(checked_at or datetime.now(timezone.utc))
    if generated_utc > checked_utc + max_future_skew:
        raise ValueError("generated_at_utc está en el futuro")
    if max_generation_age is not None:
        if not isinstance(max_generation_age, timedelta) or max_generation_age < timedelta(0):
            raise ValueError("max_generation_age debe ser timedelta no negativo")
        if checked_utc - generated_utc > max_generation_age:
            raise ValueError("bundle vencido según max_generation_age")
    if expected_target_date is not None and target_date != expected_target_date:
        raise ValueError(
            f"bundle de {target_date.isoformat()}, se esperaba "
            f"{expected_target_date.isoformat()}"
        )

    points = bundle.get("points")
    snapshots = bundle.get("snapshots")
    if not isinstance(points, list) or not isinstance(snapshots, list):
        raise ValueError("points y snapshots deben ser listas")
    if len(points) < 2 or len(points) != len(snapshots):
        raise ValueError("cantidad de puntos/snapshots inválida")
    expected_point_fields = {
        "point_id",
        "lat",
        "lon",
        "distance_offshore_km",
        "geometry_source",
    }
    point_ids: list[str] = []
    coordinates: set[tuple[float, float]] = set()
    for index, item in enumerate(points):
        if not isinstance(item, Mapping) or set(item) != expected_point_fields:
            raise ValueError(f"points[{index}] tiene una estructura inválida")
        point_id = item.get("point_id")
        geometry_source = item.get("geometry_source")
        if not isinstance(point_id, str) or not point_id.strip() or point_id != point_id.strip():
            raise ValueError(f"points[{index}].point_id es inválido")
        if not isinstance(geometry_source, str) or not geometry_source.strip():
            raise ValueError(f"points[{index}].geometry_source es inválido")
        raw_numbers = (item.get("lat"), item.get("lon"), item.get("distance_offshore_km"))
        if any(isinstance(value, bool) or not isinstance(value, Real) for value in raw_numbers):
            raise ValueError(f"points[{index}] contiene valores no numéricos")
        lat, lon, distance_km = (float(value) for value in raw_numbers)
        if not all(isfinite(value) for value in (lat, lon, distance_km)):
            raise ValueError(f"points[{index}] contiene valores no finitos")
        if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
            raise ValueError(f"points[{index}] tiene coordenadas fuera de rango")
        if not MIN_DISTANCE_KM <= distance_km <= MAX_DISTANCE_KM:
            raise ValueError(f"points[{index}] está fuera del alcance 0-10 km")
        if (lat, lon) in coordinates:
            raise ValueError("las coordenadas de los puntos deben ser distintas")
        coordinates.add((lat, lon))
        point_ids.append(point_id)

    snapshot_ids: list[str] = []
    computed_status_counts: dict[str, int] = {}
    for index, (point, item) in enumerate(zip(points, snapshots)):
        if not isinstance(item, Mapping) or set(item) != {"point_id", "snapshot"}:
            raise ValueError(f"snapshots[{index}] tiene una estructura inválida")
        snapshot_id = item.get("point_id")
        snapshot = item.get("snapshot")
        if not isinstance(snapshot_id, str) or not isinstance(snapshot, Mapping):
            raise ValueError(f"snapshots[{index}] debe contener id y snapshot")
        if snapshot.get("schema_version") != ENVIRONMENTAL_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"snapshots[{index}] tiene schema_version inválido")
        request = snapshot.get("request")
        if not isinstance(request, Mapping):
            raise ValueError(f"snapshots[{index}].request debe ser un mapping")
        if request.get("target_date") != target_date.isoformat():
            raise ValueError(f"snapshots[{index}] no coincide con target_date")
        for coordinate_name in ("lat", "lon"):
            raw_value = request.get(coordinate_name)
            if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
                raise ValueError(
                    f"snapshots[{index}].request.{coordinate_name} no es numérico"
                )
            if not isclose(
                float(raw_value),
                float(point[coordinate_name]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    f"snapshots[{index}].request.{coordinate_name} no coincide con el punto"
                )
        status = str(snapshot.get("status", "unknown"))
        computed_status_counts[status] = computed_status_counts.get(status, 0) + 1
        snapshot_ids.append(snapshot_id)

    if len(point_ids) != len(set(point_ids)) or snapshot_ids != point_ids:
        raise ValueError("los ids de puntos y snapshots no coinciden en orden")

    expected_operational_contract = {
        "distance_basis": DISTANCE_BASIS,
        "range_km": [MIN_DISTANCE_KM, MAX_DISTANCE_KM],
        "point_count": len(points),
    }
    if bundle.get("operational_contract") != expected_operational_contract:
        raise ValueError("operational_contract no coincide con el contrato 0-10 km")
    if bundle.get("status_counts") != computed_status_counts:
        raise ValueError("status_counts no coincide con los snapshots")
    if bundle.get("scoring") != _scoring_contract():
        raise ValueError("scoring debe permanecer exactamente en not_generated")

    expected_hash = _hash(_integrity_payload(bundle))
    if bundle.get("content_sha256") != expected_hash:
        raise ValueError("content_sha256 no coincide: bundle alterado o incompleto")
    expected_run_id = f"{target_date.isoformat()}-{expected_hash[:16]}"
    if bundle.get("run_id") != expected_run_id:
        raise ValueError("run_id no coincide con fecha y contenido")


def write_daily_bundle(bundle: Mapping[str, Any], output_directory: str | Path) -> Path:
    """Escritura atómica en un archivo nuevo; nunca sobrescribe una corrida."""

    validate_daily_bundle(bundle)
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"predictamar-litoral-{bundle['run_id']}.json"
    if destination.exists():
        raise FileExistsError(f"la corrida ya existe: {destination}")
    payload = json.dumps(bundle, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=".predictamar-litoral-",
        suffix=".tmp",
        dir=directory,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", required=True, type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    points = load_candidate_points(args.points)
    bundle = build_daily_bundle(points, args.date)
    path = write_daily_bundle(bundle, args.output_directory)
    print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
