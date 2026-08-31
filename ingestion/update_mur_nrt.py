"""Actualización autenticada y atómica del recorte MUR NRT.

Este proceso está separado del ensamblador. Busca un único granulo reciente en
CMR, solicita a Harmony solo el recuadro técnico, valida los bytes con
``fetch_mur_field`` y recién entonces sustituye el archivo activo. Nunca recibe
usuario, contraseña o token por argumentos y nunca incluye secretos en su
resultado o en los logs.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import fcntl
import hashlib
import json
import logging
from numbers import Real
import os
from pathlib import Path
import re
import time
from typing import Protocol

from ingestion.fetch_mur import (
    ACQUISITION_MANIFEST_SUFFIX,
    ACQUISITION_SCHEMA_VERSION,
    COLLECTION_ID,
    DATASET_ID,
    GRANULE_CONCEPT_PATTERN,
    GRANULE_UR_PATTERN,
    MAX_FILE_BYTES,
    MAX_MANIFEST_BYTES,
    MurBounds,
    MurMode,
    MurOptions,
    MurProductStage,
    MurStatus,
    NRT_PRODUCT_VERSION,
    fetch_mur_field,
    validate_request,
)


logger = logging.getLogger(__name__)
PROVIDER = "POCLOUD"
SEARCH_LIMIT = 20
DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_POLL_SECONDS = 3.0
MANAGED_DIRECTORY_MARKER = ".predictamar-mur-nrt-v1"
LOCK_FILE_NAME = ".update.lock"
ARCHIVE_DIRECTORY_NAME = "archive"
ACTIVE_FILE_PATTERN = re.compile(
    r"^mur_nrt_(?P<stamp>\d{8}T\d{6}Z)_(?P<sha>[0-9a-f]{12})\.nc4$"
)


class MurUpdateStatus(str, Enum):
    UPDATED = "updated"
    ALREADY_CURRENT = "already_current"
    NO_RECENT_GRANULE = "no_recent_granule"
    ERROR = "error"


class MurSourceError(RuntimeError):
    pass


class MurDownloadValidationError(RuntimeError):
    pass


class MurPublishError(RuntimeError):
    pass


def _aware_utc(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe ser un datetime con zona horaria explícita.")
    return value.astimezone(timezone.utc)


def _finite(value, name, minimum, maximum):
    if (not isinstance(value, Real) or isinstance(value, bool)
            or not minimum <= float(value) <= maximum):
        raise ValueError(f"{name} debe estar entre {minimum:g} y {maximum:g}.")
    return float(value)


@dataclass(frozen=True)
class MurUpdateRequest:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float
    data_directory: Path
    as_of_utc: datetime
    max_nominal_age_hours: float = 72.0
    lookback_hours: float = 72.0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    poll_seconds: float = DEFAULT_POLL_SECONDS

    def __post_init__(self):
        options = MurOptions(self.as_of_utc, self.max_nominal_age_hours, MurMode.NRT_ONLY)
        object.__setattr__(self, "as_of_utc", options.as_of_utc)
        object.__setattr__(self, "max_nominal_age_hours", options.max_nominal_age_hours)
        lookback = _finite(self.lookback_hours, "lookback_hours", 0.01, 168.0)
        if lookback < options.max_nominal_age_hours:
            raise ValueError("lookback_hours no puede ser menor que max_nominal_age_hours.")
        object.__setattr__(self, "lookback_hours", lookback)
        object.__setattr__(
            self, "timeout_seconds",
            _finite(self.timeout_seconds, "timeout_seconds", 1.0, 3600.0),
        )
        object.__setattr__(
            self, "poll_seconds", _finite(self.poll_seconds, "poll_seconds", 0.1, 60.0),
        )
        path = Path(self.data_directory)
        if not str(path).strip():
            raise ValueError("data_directory no puede estar vacío.")
        path = path.resolve(strict=False)
        if path == Path(path.anchor):
            raise ValueError("data_directory debe ser un directorio dedicado, no la raíz.")
        object.__setattr__(self, "data_directory", path)
        validate_request(
            self.minimum_latitude, self.maximum_latitude,
            self.minimum_longitude, self.maximum_longitude,
            options.as_of_utc.date(), options,
        )

    @property
    def options(self):
        return MurOptions(
            self.as_of_utc, self.max_nominal_age_hours, MurMode.NRT_ONLY)

    @property
    def query_bounds(self):
        return validate_request(
            self.minimum_latitude, self.maximum_latitude,
            self.minimum_longitude, self.maximum_longitude,
            self.as_of_utc.date(), self.options,
        )[1]


@dataclass(frozen=True)
class MurGranule:
    concept_id: str
    granule_ur: str
    collection_id: str
    native_time_utc: datetime
    end_time_utc: datetime


@dataclass(frozen=True)
class MurUpdateResult:
    status: MurUpdateStatus
    checked_at_utc: datetime
    reason: str | None = None
    granule_concept_id: str | None = None
    granule_ur: str | None = None
    native_time_utc: datetime | None = None
    product_created_at_utc: datetime | None = None
    retrieved_at_utc: datetime | None = None
    source_file_name: str | None = None
    source_file_sha256: str | None = None
    n_valid_cells: int = 0
    availability_as_of_verified: bool = False
    archived_file_names: tuple[str, ...] = ()
    error_type: str | None = None

    def to_dict(self):
        def stamp(value):
            return value.isoformat().replace("+00:00", "Z") if value else None
        return {
            "status": self.status.value,
            "checked_at_utc": stamp(self.checked_at_utc),
            "reason": self.reason,
            "granule_concept_id": self.granule_concept_id,
            "granule_ur": self.granule_ur,
            "native_time_utc": stamp(self.native_time_utc),
            "product_created_at_utc": stamp(self.product_created_at_utc),
            "retrieved_at_utc": stamp(self.retrieved_at_utc),
            "source_file_name": self.source_file_name,
            "source_file_sha256": self.source_file_sha256,
            "n_valid_cells": self.n_valid_cells,
            "availability_as_of_verified": self.availability_as_of_verified,
            "archived_file_names": list(self.archived_file_names),
            "error_type": self.error_type,
        }


class MurNrtSource(Protocol):
    def search(
        self, *, start_utc: datetime, end_utc: datetime,
        query_bounds: MurBounds, count: int,
    ) -> Sequence[Mapping]: ...

    def download(
        self, granule: MurGranule, *, query_bounds: MurBounds,
        directory: Path, timeout_seconds: float, poll_seconds: float,
    ) -> Sequence[Path]: ...


def _parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp ausente")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    stamp = datetime.fromisoformat(text)
    return _aware_utc(stamp, "timestamp")


def _granule_from_result(result):
    if not isinstance(result, Mapping):
        raise ValueError("resultado CMR inválido")
    meta, umm = result.get("meta"), result.get("umm")
    if not isinstance(meta, Mapping) or not isinstance(umm, Mapping):
        raise ValueError("metadatos CMR ausentes")
    concept_id = meta.get("concept-id")
    collection_id = meta.get("collection-concept-id")
    granule_ur = umm.get("GranuleUR")
    if (not isinstance(concept_id, str)
            or not GRANULE_CONCEPT_PATTERN.fullmatch(concept_id)
            or collection_id != COLLECTION_ID
            or not isinstance(granule_ur, str)):
        raise ValueError("identidad CMR incompatible")
    match = GRANULE_UR_PATTERN.fullmatch(granule_ur)
    if not match:
        raise ValueError("GranuleUR MUR incompatible")
    temporal = umm.get("TemporalExtent")
    if not isinstance(temporal, Mapping):
        raise ValueError("tiempo CMR ausente")
    interval = temporal.get("RangeDateTime")
    if isinstance(interval, Mapping):
        start = _parse_utc(interval.get("BeginningDateTime"))
        end = _parse_utc(interval.get("EndingDateTime"))
    else:
        start = end = _parse_utc(temporal.get("SingleDateTime"))
    name_time = datetime.strptime(match.group("stamp"), "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc)
    if start != name_time or end < start:
        raise ValueError("tiempo CMR no coincide con GranuleUR")
    return MurGranule(concept_id, granule_ur, collection_id, start, end)


def select_latest_mur_granule(results, *, as_of_utc, max_age_hours):
    as_of = _aware_utc(as_of_utc, "as_of_utc")
    candidates = []
    for result in results:
        try:
            granule = _granule_from_result(result)
        except (TypeError, ValueError):
            continue
        age = (as_of - granule.native_time_utc).total_seconds() / 3600
        if 0 <= age <= max_age_hours:
            candidates.append(granule)
    return max(candidates, key=lambda item: (item.native_time_utc, item.granule_ur),
               default=None)


class EarthdataHarmonySource:
    """Adaptador real. El token se mantiene privado y nunca se serializa."""

    def __init__(self, token):
        if not isinstance(token, str) or not token:
            raise MurSourceError("earthdata_token_unavailable")
        self._token = token

    @classmethod
    def authenticate(cls, strategy="environment"):
        if strategy not in {"environment", "interactive"}:
            raise ValueError("La estrategia debe ser environment o interactive.")
        import earthaccess
        auth = earthaccess.login(strategy=strategy, persist=False)
        if not getattr(auth, "authenticated", False):
            raise MurSourceError("earthdata_authentication_failed")
        token = earthaccess.get_edl_token()
        if isinstance(token, Mapping):
            token = token.get("access_token")
        return cls(token)

    def search(self, *, start_utc, end_utc, query_bounds, count):
        import earthaccess
        return earthaccess.search_data(
            short_name=DATASET_ID,
            provider=PROVIDER,
            temporal=(start_utc.isoformat(), end_utc.isoformat()),
            bounding_box=(
                query_bounds.minimum_longitude, query_bounds.minimum_latitude,
                query_bounds.maximum_longitude, query_bounds.maximum_latitude,
            ),
            count=count,
        )

    def download(
        self, granule, *, query_bounds, directory,
        timeout_seconds, poll_seconds,
    ):
        from harmony import BBox, Client, Collection, Request
        client = Client(token=self._token, check_interval=poll_seconds)
        deadline = time.monotonic() + timeout_seconds
        try:
            request = Request(
                collection=Collection(id=COLLECTION_ID),
                spatial=BBox(
                    query_bounds.minimum_longitude, query_bounds.minimum_latitude,
                    query_bounds.maximum_longitude, query_bounds.maximum_latitude,
                ),
                granule_id=[granule.concept_id],
                format="application/netcdf",
                max_results=1,
                ignore_errors=False,
            )
            job_id = client.submit(request)
            while True:
                progress, state, _message = client.progress(job_id)
                state = str(state).casefold()
                if progress == 100 and state == "successful":
                    break
                if state in {"failed", "canceled", "cancelled"}:
                    raise MurSourceError("harmony_job_failed")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MurSourceError("harmony_job_timeout")
                time.sleep(min(poll_seconds, remaining))
            futures = list(client.download_all(
                job_id, directory=str(directory), overwrite=False))
            if len(futures) != 1:
                raise MurSourceError("harmony_result_count_invalid")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MurSourceError("harmony_download_timeout")
            return (Path(futures[0].result(timeout=remaining)),)
        except MurSourceError:
            raise
        except Exception as exc:
            raise MurSourceError("earthdata_harmony_failure") from exc
        finally:
            executor = getattr(client, "executor", None)
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)


def _active_netcdf_files(directory):
    if not directory.exists():
        return ()
    if directory.is_symlink() or not directory.is_dir():
        raise MurPublishError("data_directory_invalid")
    marker = directory / MANAGED_DIRECTORY_MARKER
    paths = tuple(sorted(
        path for path in directory.iterdir() if path.suffix.casefold() in {".nc", ".nc4"}
    ))
    if marker.exists():
        if (marker.is_symlink() or not marker.is_file()
                or marker.stat().st_size != len(DATASET_ID) + 1
                or marker.read_text() != DATASET_ID + "\n"):
            raise MurPublishError("managed_directory_marker_invalid")
    elif paths:
        raise MurPublishError("unmanaged_directory_has_netcdf")
    if len(paths) > 1:
        raise MurPublishError("managed_directory_has_multiple_products")
    for path in paths:
        if (path.is_symlink() or not path.is_file()
                or not ACTIVE_FILE_PATTERN.fullmatch(path.name)
                or not 0 < path.stat().st_size <= MAX_FILE_BYTES):
            raise MurPublishError("active_netcdf_invalid")
    return paths


def _active_native_time(path):
    match = ACTIVE_FILE_PATTERN.fullmatch(path.name)
    if not match:
        raise MurPublishError("active_netcdf_name_invalid")
    return datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc)


def _existing_current_result(request, path, selected_granule):
    native_time = _active_native_time(path)
    if native_time < selected_granule.native_time_utc:
        return None
    field = fetch_mur_field(
        request.minimum_latitude, request.maximum_latitude,
        request.minimum_longitude, request.maximum_longitude,
        native_time.date(), options=request.options,
        data_directory=request.data_directory,
    )
    manifest_path = Path(f"{path}{ACQUISITION_MANIFEST_SUFFIX}")
    if (field.status not in {
            MurStatus.VALIDA_EN_FECHA_NOMINAL, MurStatus.VALIDA_RECIENTE}
            or field.time_utc != native_time
            or not field.provenance.availability_as_of_verified
            or not manifest_path.is_file() or manifest_path.is_symlink()
            or not 0 < manifest_path.stat().st_size <= MAX_MANIFEST_BYTES):
        if native_time > selected_granule.native_time_utc:
            raise MurPublishError("newer_active_product_is_not_verifiable")
        return None
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("granule_concept_id") != selected_granule.concept_id
            and native_time == selected_granule.native_time_utc):
        raise MurPublishError("active_granule_identity_conflict")
    return MurUpdateResult(
        status=MurUpdateStatus.ALREADY_CURRENT,
        checked_at_utc=request.as_of_utc,
        reason=("active_product_is_newer" if native_time > selected_granule.native_time_utc
                else "same_granule_already_published"),
        granule_concept_id=manifest.get("granule_concept_id"),
        granule_ur=manifest.get("granule_ur"),
        native_time_utc=native_time,
        product_created_at_utc=field.provenance.product_created_at_utc,
        retrieved_at_utc=_parse_utc(manifest.get("retrieved_at_utc")),
        source_file_name=path.name,
        source_file_sha256=field.provenance.source_file_sha256,
        n_valid_cells=field.n_valid_cells,
        availability_as_of_verified=True,
    )


def _single_download(paths, staging_directory):
    paths = tuple(Path(path) for path in paths)
    if len(paths) != 1:
        raise MurDownloadValidationError("download_count_invalid")
    path = paths[0]
    try:
        inside = path.resolve(strict=True).parent == staging_directory.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MurDownloadValidationError("download_path_invalid") from exc
    if (not inside or path.is_symlink() or not path.is_file()
            or path.suffix.casefold() not in {".nc", ".nc4"}
            or not 0 < path.stat().st_size <= MAX_FILE_BYTES):
        raise MurDownloadValidationError("download_file_invalid")
    return path


def _validate_download(path, granule, request):
    field = fetch_mur_field(
        request.minimum_latitude, request.maximum_latitude,
        request.minimum_longitude, request.maximum_longitude,
        granule.native_time_utc.date(), options=request.options,
        data_directory=path.parent,
    )
    if (field.status not in {
            MurStatus.VALIDA_EN_FECHA_NOMINAL, MurStatus.VALIDA_RECIENTE}
            or field.provenance.product_stage is not MurProductStage.NRT
            or field.provenance.product_version != NRT_PRODUCT_VERSION
            or field.time_utc != granule.native_time_utc
            or field.provenance.product_created_at_utc is None
            or field.n_valid_cells <= 0
            or not field.halo_complete
            or not field.provenance.source_file_sha256):
        raise MurDownloadValidationError("downloaded_product_not_admissible")
    return field


def _iso_utc(value):
    return _aware_utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _manifest(field, granule, request, retrieved_at, file_name):
    return {
        "schema_version": ACQUISITION_SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "collection_id": COLLECTION_ID,
        "product_version": NRT_PRODUCT_VERSION,
        "source_access": "nasa_earthdata_harmony",
        "granule_concept_id": granule.concept_id,
        "granule_ur": granule.granule_ur,
        "native_time_utc": _iso_utc(field.time_utc),
        "product_created_at_utc": _iso_utc(field.provenance.product_created_at_utc),
        "retrieved_at_utc": _iso_utc(retrieved_at),
        "source_file_name": file_name,
        "source_file_sha256": field.provenance.source_file_sha256,
        "query_bbox": {
            "west": request.query_bounds.minimum_longitude,
            "south": request.query_bounds.minimum_latitude,
            "east": request.query_bounds.maximum_longitude,
            "north": request.query_bounds.maximum_latitude,
        },
    }


def _write_staged_manifest(staging, manifest):
    path = staging / "acquisition-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


@contextmanager
def _publication_lock(directory):
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory / LOCK_FILE_NAME, flags, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _archive_destination(archive_directory, path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    candidate = archive_directory / f"{path.stem}_{digest}{path.suffix}"
    counter = 2
    while candidate.exists():
        candidate = archive_directory / f"{path.stem}_{digest}_{counter}{path.suffix}"
        counter += 1
    return candidate


def _ensure_archive_directory(directory):
    archive_directory = directory / ARCHIVE_DIRECTORY_NAME
    if archive_directory.exists() and (
            archive_directory.is_symlink() or not archive_directory.is_dir()):
        raise MurPublishError("archive_directory_invalid")
    archive_directory.mkdir(exist_ok=True)
    return archive_directory


def _archive_active(active, archive_directory):
    moved = []
    archived_names = []
    try:
        for path in active:
            destination = _archive_destination(archive_directory, path)
            os.replace(path, destination)
            moved.append((destination, path))
            archived_names.append(destination.name)
            sidecar = Path(f"{path}{ACQUISITION_MANIFEST_SUFFIX}")
            if sidecar.exists():
                if (sidecar.is_symlink() or not sidecar.is_file()
                        or not 0 < sidecar.stat().st_size <= MAX_MANIFEST_BYTES):
                    raise MurPublishError("active_manifest_invalid")
                sidecar_destination = Path(
                    f"{destination}{ACQUISITION_MANIFEST_SUFFIX}")
                os.replace(sidecar, sidecar_destination)
                moved.append((sidecar_destination, sidecar))
        return moved, tuple(archived_names)
    except Exception:
        for archived, original in reversed(moved):
            if archived.exists():
                os.replace(archived, original)
        raise


def _restore_moves(moved):
    for archived, original in reversed(moved):
        if archived.exists():
            os.replace(archived, original)


def _publish_validated(path, field, granule, request, retrieved_at):
    directory = request.data_directory
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise MurPublishError("data_directory_is_symlink")
    sha = field.provenance.source_file_sha256
    file_name = (
        f"mur_nrt_{granule.native_time_utc:%Y%m%dT%H%M%SZ}_{sha[:12]}.nc4"
    )
    destination = directory / file_name
    manifest_data = _manifest(field, granule, request, retrieved_at, file_name)
    staged_manifest = _write_staged_manifest(path.parent, manifest_data)
    archived_names = ()
    with _publication_lock(directory):
        active = _active_netcdf_files(directory)
        for existing in active:
            if _active_native_time(existing) > granule.native_time_utc:
                raise MurPublishError("concurrent_update_is_newer")
            existing_sha = hashlib.sha256(existing.read_bytes()).hexdigest()
            if existing_sha == sha:
                manifest_destination = Path(
                    f"{existing}{ACQUISITION_MANIFEST_SUFFIX}")
                archive_directory = _ensure_archive_directory(directory)
                moved = []
                if manifest_destination.exists():
                    if (manifest_destination.is_symlink()
                            or not manifest_destination.is_file()
                            or not 0 < manifest_destination.stat().st_size
                            <= MAX_MANIFEST_BYTES):
                        raise MurPublishError("active_manifest_invalid")
                    old_manifest = _archive_destination(
                        archive_directory, manifest_destination)
                    os.replace(manifest_destination, old_manifest)
                    moved.append((old_manifest, manifest_destination))
                try:
                    manifest_data["source_file_name"] = existing.name
                    staged_manifest = _write_staged_manifest(path.parent, manifest_data)
                    os.replace(staged_manifest, manifest_destination)
                except Exception:
                    if manifest_destination.exists():
                        os.replace(manifest_destination, staged_manifest)
                    _restore_moves(moved)
                    raise
                return existing, (), MurUpdateStatus.ALREADY_CURRENT
            if _active_native_time(existing) == granule.native_time_utc:
                raise MurPublishError("same_time_has_conflicting_bytes")
        marker = directory / MANAGED_DIRECTORY_MARKER
        if not marker.exists():
            marker.write_text(DATASET_ID + "\n")
        archive_directory = _ensure_archive_directory(directory)
        manifest_destination = Path(f"{destination}{ACQUISITION_MANIFEST_SUFFIX}")
        moved = []
        published_file = published_manifest = False
        try:
            os.replace(staged_manifest, manifest_destination)
            published_manifest = True
            os.replace(path, destination)
            published_file = True
            moved, archived_names = _archive_active(active, archive_directory)
        except Exception as exc:
            _restore_moves(moved)
            if published_file and destination.exists():
                os.replace(destination, path)
            if published_manifest and manifest_destination.exists():
                os.replace(manifest_destination, staged_manifest)
            raise MurPublishError("atomic_publish_failed") from exc
    return destination, archived_names, MurUpdateStatus.UPDATED


def _verified_published_field(path, granule, request, retrieved_at):
    field = fetch_mur_field(
        request.minimum_latitude, request.maximum_latitude,
        request.minimum_longitude, request.maximum_longitude,
        granule.native_time_utc.date(),
        options=MurOptions(
            max(request.as_of_utc, retrieved_at),
            request.max_nominal_age_hours,
            MurMode.NRT_ONLY,
        ),
        data_directory=path.parent,
    )
    if (field.status not in {
            MurStatus.VALIDA_EN_FECHA_NOMINAL, MurStatus.VALIDA_RECIENTE}
            or not field.provenance.availability_as_of_verified
            or field.provenance.source_file_name != path.name):
        raise MurPublishError("published_product_verification_failed")
    return field


def _error_result(request, reason, exc, granule=None):
    logger.error("Fallo de actualización MUR en %s (%s).", reason, type(exc).__name__)
    return MurUpdateResult(
        status=MurUpdateStatus.ERROR,
        checked_at_utc=request.as_of_utc,
        reason=reason,
        granule_concept_id=granule.concept_id if granule else None,
        granule_ur=granule.granule_ur if granule else None,
        native_time_utc=granule.native_time_utc if granule else None,
        error_type=type(exc).__name__,
    )


def update_mur_nrt(
    request: MurUpdateRequest, source: MurNrtSource, *,
    clock=lambda: datetime.now(timezone.utc),
):
    """Ejecuta una actualización; los errores operativos vuelven como resultado."""
    granule = None
    try:
        active = _active_netcdf_files(request.data_directory)
        results = source.search(
            start_utc=request.as_of_utc - timedelta(hours=request.lookback_hours),
            end_utc=request.as_of_utc,
            query_bounds=request.query_bounds,
            count=SEARCH_LIMIT,
        )
        granule = select_latest_mur_granule(
            results, as_of_utc=request.as_of_utc,
            max_age_hours=request.max_nominal_age_hours,
        )
        if granule is None:
            return MurUpdateResult(
                MurUpdateStatus.NO_RECENT_GRANULE, request.as_of_utc,
                reason="no_admissible_cmr_granule",
            )
        if active:
            current = _existing_current_result(request, active[0], granule)
            if current is not None:
                return current
    except MurPublishError as exc:
        return _error_result(request, "directory_validation_failed", exc)
    except Exception as exc:
        return _error_result(request, "source_search_failed", exc)

    try:
        request.data_directory.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        with tempfile.TemporaryDirectory(
                prefix=".mur-nrt-update-", dir=request.data_directory.parent) as temporary:
            staging = Path(temporary)
            try:
                downloaded = source.download(
                    granule, query_bounds=request.query_bounds, directory=staging,
                    timeout_seconds=request.timeout_seconds,
                    poll_seconds=request.poll_seconds,
                )
            except Exception as exc:
                return _error_result(request, "source_download_failed", exc, granule)
            try:
                path = _single_download(downloaded, staging)
                field = _validate_download(path, granule, request)
            except Exception as exc:
                return _error_result(request, "download_validation_failed", exc, granule)
            retrieved_at = _aware_utc(clock(), "clock()")
            if retrieved_at < field.provenance.product_created_at_utc:
                return _error_result(
                    request, "retrieval_clock_precedes_product", ValueError(), granule)
            try:
                destination, archived, status = _publish_validated(
                    path, field, granule, request, retrieved_at)
                verified = _verified_published_field(
                    destination, granule, request, retrieved_at)
            except Exception as exc:
                return _error_result(request, "publication_failed", exc, granule)
            return MurUpdateResult(
                status=status,
                checked_at_utc=request.as_of_utc,
                granule_concept_id=granule.concept_id,
                granule_ur=granule.granule_ur,
                native_time_utc=granule.native_time_utc,
                product_created_at_utc=verified.provenance.product_created_at_utc,
                retrieved_at_utc=retrieved_at,
                source_file_name=destination.name,
                source_file_sha256=verified.provenance.source_file_sha256,
                n_valid_cells=verified.n_valid_cells,
                availability_as_of_verified=(
                    verified.provenance.availability_as_of_verified),
                archived_file_names=archived,
            )
    except Exception as exc:
        return _error_result(request, "temporary_workspace_failed", exc, granule)


def _parser():
    parser = argparse.ArgumentParser(
        description="Actualiza de forma atómica un directorio dedicado MUR NRT.")
    parser.add_argument("--data-directory", required=True, type=Path)
    parser.add_argument("--min-lat", required=True, type=float)
    parser.add_argument("--max-lat", required=True, type=float)
    parser.add_argument("--min-lon", required=True, type=float)
    parser.add_argument("--max-lon", required=True, type=float)
    parser.add_argument(
        "--auth-strategy", choices=("environment", "interactive"),
        default="environment",
        help=("environment usa EARTHDATA_TOKEN o EARTHDATA_USERNAME junto con "
              "EARTHDATA_PASSWORD; interactive es solo para ejecución manual."),
    )
    parser.add_argument("--max-age-hours", type=float, default=72.0)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    request = MurUpdateRequest(
        args.min_lat, args.max_lat, args.min_lon, args.max_lon,
        args.data_directory, now,
        max_nominal_age_hours=args.max_age_hours,
        lookback_hours=args.max_age_hours,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        source = EarthdataHarmonySource.authenticate(args.auth_strategy)
        result = update_mur_nrt(request, source)
    except Exception as exc:
        result = _error_result(request, "authentication_failed", exc)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    if result.status in {MurUpdateStatus.UPDATED, MurUpdateStatus.ALREADY_CURRENT}:
        return 0
    return 2 if result.status is MurUpdateStatus.NO_RECENT_GRANULE else 1


if __name__ == "__main__":
    raise SystemExit(main())
