"""Construye un bundle diario consumible por la futura aplicación.

El backend usa exactamente el ensamblador ambiental y puntos operativos
aprobados. No calcula índices por especie: la matriz v1 aún no tiene curvas
calibradas ni validación independiente. El bundle incluye fecha, hora de
generación, huella de contenido y estado por punto para que la aplicación
pueda rechazar datos viejos o de otro esquema.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence

from assembly.environmental_assembler import (
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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at debe incluir zona horaria")
    return value.astimezone(timezone.utc)


def build_daily_bundle(
    points: Sequence[CandidatePoint],
    target_date: date,
    *,
    assembler: Callable[..., Any] = assemble_environmental_snapshot,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Ejecuta una instantánea por punto y fija un manifiesto verificable."""

    if len(points) < 2:
        raise ValueError("se requieren al menos dos puntos operativos aprobados")
    generated = _as_utc(generated_at or datetime.now(timezone.utc))
    point_documents = []
    snapshots = []
    for point in points:
        if not MIN_DISTANCE_KM <= point.distance_offshore_km <= MAX_DISTANCE_KM:
            raise ValueError(f"{point.point_id}: distancia fuera de 0-10 km")
        point_document = {
            "point_id": point.point_id,
            "lat": point.lat,
            "lon": point.lon,
            "distance_offshore_km": point.distance_offshore_km,
            "geometry_source": point.geometry_source,
        }
        request = AssemblyRequest(
            lat=point.lat,
            lon=point.lon,
            target_date=target_date,
        )
        snapshot = assembler(request)
        document = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        if not isinstance(document, Mapping):
            raise TypeError("el ensamblador debe devolver snapshot o mapping")
        point_documents.append(point_document)
        snapshots.append({"point_id": point.point_id, "snapshot": dict(document)})

    content = {
        "target_date": target_date.isoformat(),
        "points": point_documents,
        "snapshots": snapshots,
    }
    content_sha256 = _hash(content)
    run_id = f"{target_date.isoformat()}-{content_sha256[:16]}"
    status_counts: dict[str, int] = {}
    for item in snapshots:
        status = str(item["snapshot"].get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "target_date": target_date.isoformat(),
        "content_sha256": content_sha256,
        "operational_contract": {
            "distance_basis": DISTANCE_BASIS,
            "range_km": [MIN_DISTANCE_KM, MAX_DISTANCE_KM],
            "point_count": len(points),
        },
        "status_counts": status_counts,
        "scoring": {
            "status": "not_generated",
            "reason": (
                "species_weighting_v1 es una matriz de investigación sin "
                "transformaciones calibradas ni validación independiente"
            ),
            "is_probability": False,
            "operational_enabled": False,
        },
        "points": point_documents,
        "snapshots": snapshots,
    }


def validate_daily_bundle(
    bundle: Mapping[str, Any], *, expected_target_date: date | None = None
) -> None:
    """Contrato mínimo que deberá aplicar la futura interfaz antes de leer."""

    if not isinstance(bundle, Mapping):
        raise ValueError("bundle debe ser un mapping")
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"schema_version debe ser {BUNDLE_SCHEMA_VERSION!r}")
    try:
        target_date = date.fromisoformat(str(bundle["target_date"]))
        generated = datetime.fromisoformat(
            str(bundle["generated_at_utc"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("fecha objetivo o fecha de generación inválida") from exc
    _as_utc(generated)
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
    point_ids = [str(item.get("point_id")) for item in points]
    snapshot_ids = [str(item.get("point_id")) for item in snapshots]
    if len(point_ids) != len(set(point_ids)) or snapshot_ids != point_ids:
        raise ValueError("los ids de puntos y snapshots no coinciden en orden")

    content = {
        "target_date": target_date.isoformat(),
        "points": points,
        "snapshots": snapshots,
    }
    expected_hash = _hash(content)
    if bundle.get("content_sha256") != expected_hash:
        raise ValueError("content_sha256 no coincide: bundle alterado o incompleto")
    expected_run_id = f"{target_date.isoformat()}-{expected_hash[:16]}"
    if bundle.get("run_id") != expected_run_id:
        raise ValueError("run_id no coincide con fecha y contenido")
    scoring = bundle.get("scoring")
    if not isinstance(scoring, Mapping):
        raise ValueError("scoring debe declarar su estado")
    if scoring.get("is_probability") is not False:
        raise ValueError("el bundle no puede declarar probabilidad")
    if scoring.get("operational_enabled") is not False:
        raise ValueError("el scoring operativo debe permanecer bloqueado")


def write_daily_bundle(bundle: Mapping[str, Any], output_directory: str | Path) -> Path:
    """Escritura atómica en un archivo nuevo; nunca sobrescribe una corrida."""

    validate_daily_bundle(bundle)
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"predictamar-litoral-{bundle['run_id']}.json"
    if destination.exists():
        raise FileExistsError(f"la corrida ya existe: {destination}")
    payload = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
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
