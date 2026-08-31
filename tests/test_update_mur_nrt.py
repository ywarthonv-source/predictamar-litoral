"""Actualizador MUR NRT: selección, validación, idempotencia y publicación."""

from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import ingestion.fetch_mur as mur
import ingestion.update_mur_nrt as update
from mur_fixtures import bounds, dataset, write_dataset


AS_OF = datetime(2026, 8, 31, 21, 31, 55, tzinfo=timezone.utc)
NATIVE = datetime(2026, 8, 30, 9, tzinfo=timezone.utc)
CREATED = datetime(2026, 8, 31, 9, 5, 19, tzinfo=timezone.utc)


def cmr_result(native=NATIVE, *, concept_id="G301306982-POCLOUD",
               collection_id=update.COLLECTION_ID):
    name = native.strftime("%Y%m%d%H%M%S") + (
        "-JPL-L4_GHRSST-SSTfnd-MUR-GLOB-v02.0-fv04.1")
    return {
        "meta": {
            "concept-id": concept_id,
            "collection-concept-id": collection_id,
        },
        "umm": {
            "GranuleUR": name,
            "TemporalExtent": {"RangeDateTime": {
                "BeginningDateTime": native.isoformat().replace("+00:00", "Z"),
                "EndingDateTime": native.isoformat().replace("+00:00", "Z"),
            }},
        },
    }


def nrt_dataset(native=NATIVE, created=CREATED, value=295.15):
    return dataset(
        sst=None if value == 295.15 else [[[value] * 7 for _ in range(7)]],
        times=(native.replace(tzinfo=None).isoformat(),),
        title="Daily MUR SST, Interim near-real-time (nrt) product",
        product_version=mur.NRT_PRODUCT_VERSION,
        date_created=created.strftime("%Y%m%dT%H%M%SZ"),
    )


def request(tmp_path, ds=None, as_of=AS_OF):
    ds = ds if ds is not None else nrt_dataset()
    return update.MurUpdateRequest(
        *bounds(ds), tmp_path / "mur-current", as_of,
        timeout_seconds=30, poll_seconds=.1,
    )


class FakeSource:
    def __init__(self, ds, results=None, payload=None):
        self.ds = ds
        self.results = list(results if results is not None else [cmr_result()])
        self.payload = payload
        self.search_calls = []
        self.download_calls = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.results

    def download(self, granule, **kwargs):
        self.download_calls.append((granule, kwargs))
        path = kwargs["directory"] / "harmony-subset.nc4"
        if self.payload is None:
            write_dataset(self.ds, path)
            self.payload = path.read_bytes()
        else:
            path.write_bytes(self.payload)
        return (path,)


def run(req, source, clock=AS_OF):
    return update.update_mur_nrt(req, source, clock=lambda: clock)


def active_files(directory):
    return tuple(path for path in directory.iterdir()
                 if path.suffix.casefold() in {".nc", ".nc4"})


def test_selecciona_ultimo_granulo_admisible_y_rechaza_identidades_ajenas():
    older = NATIVE - timedelta(days=1)
    selected = update.select_latest_mur_granule(
        [cmr_result(older, concept_id="G1-POCLOUD"),
         cmr_result(collection_id="C0000000000-POCLOUD"),
         {"meta": {}, "umm": {}}, cmr_result()],
        as_of_utc=AS_OF, max_age_hours=72,
    )
    assert selected.native_time_utc == NATIVE
    assert selected.collection_id == update.COLLECTION_ID
    assert selected.granule_ur.startswith("20260830090000-")


def test_sin_granulo_reciente_no_descarga_ni_crea_directorio(tmp_path):
    ds = nrt_dataset()
    source = FakeSource(ds, [cmr_result(NATIVE - timedelta(days=8))])
    req = request(tmp_path, ds)
    result = run(req, source)
    assert result.status is update.MurUpdateStatus.NO_RECENT_GRANULE
    assert result.reason == "no_admissible_cmr_granule"
    assert source.download_calls == []
    assert not req.data_directory.exists()


def test_publica_recorte_validado_con_manifiesto_y_hash(tmp_path):
    ds = nrt_dataset()
    source = FakeSource(ds)
    req = request(tmp_path, ds)
    result = run(req, source)
    assert result.status is update.MurUpdateStatus.UPDATED
    assert result.availability_as_of_verified
    assert result.native_time_utc == NATIVE
    assert result.product_created_at_utc == CREATED
    assert result.n_valid_cells == 9
    files = active_files(req.data_directory)
    assert len(files) == 1 and files[0].name == result.source_file_name
    assert result.source_file_sha256 == mur.hashlib.sha256(files[0].read_bytes()).hexdigest()
    manifest_path = Path(f"{files[0]}{mur.ACQUISITION_MANIFEST_SUFFIX}")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema_version"] == mur.ACQUISITION_SCHEMA_VERSION
    assert manifest["granule_concept_id"] == "G301306982-POCLOUD"
    assert manifest["source_file_sha256"] == result.source_file_sha256
    assert "token" not in manifest and "password" not in manifest
    field = mur.fetch_mur_field(
        *bounds(ds), NATIVE.date(), options=mur.MurOptions(AS_OF),
        data_directory=req.data_directory,
    )
    assert field.provenance.availability_as_of_verified
    assert field.provenance.availability_basis == "earthdata_harmony_manifest_sha256"
    search = source.search_calls[0]
    assert search["start_utc"] == AS_OF - timedelta(hours=72)
    assert search["end_utc"] == AS_OF
    assert search["count"] == update.SEARCH_LIMIT
    assert search["query_bounds"].minimum_latitude == pytest.approx(
        bounds(ds)[0] - mur.HALO_CELLS * mur.NATIVE_GRID_STEP_DEG)


def test_repetir_mismos_bytes_es_idempotente(tmp_path):
    ds = nrt_dataset()
    first_source = FakeSource(ds)
    req = request(tmp_path, ds)
    first = run(req, first_source)
    second_source = FakeSource(ds, payload=first_source.payload)
    second = run(req, second_source, AS_OF + timedelta(minutes=5))
    assert first.status is update.MurUpdateStatus.UPDATED
    assert second.status is update.MurUpdateStatus.ALREADY_CURRENT
    assert second.source_file_name == first.source_file_name
    assert second.source_file_sha256 == first.source_file_sha256
    assert len(active_files(req.data_directory)) == 1


def test_descarga_incompatible_no_reemplaza_archivo_vigente(tmp_path):
    ds = nrt_dataset()
    req = request(tmp_path, ds)
    assert run(req, FakeSource(ds)).status is update.MurUpdateStatus.UPDATED
    current = active_files(req.data_directory)[0]
    before = current.read_bytes()
    invalid_native = NATIVE + timedelta(days=1)
    invalid = nrt_dataset(
        invalid_native, datetime(2026, 8, 31, 18, tzinfo=timezone.utc))
    invalid.attrs["product_version"] = "04.1"
    result = run(req, FakeSource(
        invalid, [cmr_result(invalid_native, concept_id="G3-POCLOUD")]))
    assert result.status is update.MurUpdateStatus.ERROR
    assert result.reason == "download_validation_failed"
    assert active_files(req.data_directory) == (current,)
    assert current.read_bytes() == before


def test_producto_nuevo_archiva_el_anterior_sin_borrarlo(tmp_path):
    old_native = NATIVE - timedelta(days=1)
    old_created = CREATED - timedelta(days=1)
    old_ds = nrt_dataset(old_native, old_created)
    req = request(tmp_path, old_ds)
    old_source = FakeSource(old_ds, [cmr_result(old_native, concept_id="G2-POCLOUD")])
    old_result = run(req, old_source)
    assert old_result.status is update.MurUpdateStatus.UPDATED
    new_ds = nrt_dataset(value=296.15)
    new_result = run(req, FakeSource(new_ds))
    assert new_result.status is update.MurUpdateStatus.UPDATED
    assert len(new_result.archived_file_names) == 1
    assert new_result.source_file_sha256 != old_result.source_file_sha256
    assert len(active_files(req.data_directory)) == 1
    archive = req.data_directory / update.ARCHIVE_DIRECTORY_NAME
    assert (archive / new_result.archived_file_names[0]).is_file()


def test_resultado_cmr_mas_antiguo_nunca_degrada_el_activo(tmp_path):
    ds = nrt_dataset()
    req = request(tmp_path, ds)
    current = run(req, FakeSource(ds))
    older_native = NATIVE - timedelta(days=1)
    older = FakeSource(
        nrt_dataset(older_native, CREATED - timedelta(days=1)),
        [cmr_result(older_native, concept_id="G2-POCLOUD")],
    )
    result = run(req, older)
    assert result.status is update.MurUpdateStatus.ALREADY_CURRENT
    assert result.reason == "active_product_is_newer"
    assert result.source_file_name == current.source_file_name
    assert result.native_time_utc == NATIVE
    assert older.download_calls == []


def test_fallo_atomico_restaura_el_producto_anterior(tmp_path, monkeypatch):
    old_native = NATIVE - timedelta(days=1)
    old_ds = nrt_dataset(old_native, CREATED - timedelta(days=1))
    req = request(tmp_path, old_ds)
    old = run(
        req,
        FakeSource(old_ds, [cmr_result(old_native, concept_id="G2-POCLOUD")]),
    )
    old_path = req.data_directory / old.source_file_name
    old_bytes = old_path.read_bytes()
    original_replace = update.os.replace
    failed = False

    def fail_new_publish(source, destination):
        nonlocal failed
        source, destination = Path(source), Path(destination)
        if (not failed and source.parent.name.startswith(".mur-nrt-update-")
                and destination.parent == req.data_directory
                and destination.suffix == ".nc4"):
            failed = True
            raise OSError("simulated atomic failure")
        return original_replace(source, destination)

    monkeypatch.setattr(update.os, "replace", fail_new_publish)
    result = run(req, FakeSource(nrt_dataset(value=296.15)))
    assert result.status is update.MurUpdateStatus.ERROR
    assert result.reason == "publication_failed"
    assert failed
    assert active_files(req.data_directory) == (old_path,)
    assert old_path.read_bytes() == old_bytes


def test_archivo_fuera_del_temporal_se_rechaza_sin_publicar(tmp_path):
    ds = nrt_dataset()
    source = FakeSource(ds)
    req = request(tmp_path, ds)
    outside = tmp_path / "outside.nc4"
    write_dataset(ds, outside)

    def outside_download(*args, **kwargs):
        return (outside,)

    source.download = outside_download
    result = run(req, source)
    assert result.status is update.MurUpdateStatus.ERROR
    assert result.reason == "download_validation_failed"
    assert not req.data_directory.exists()


def test_fallo_de_fuente_no_expone_secreto(tmp_path, caplog):
    ds = nrt_dataset()
    source = FakeSource(ds)

    def failure(**kwargs):
        raise RuntimeError("PASSWORD=super-secret-token")

    source.search = failure
    result = run(request(tmp_path, ds), source)
    assert result.status is update.MurUpdateStatus.ERROR
    assert result.reason == "source_search_failed"
    assert "super-secret-token" not in caplog.text
    assert "super-secret-token" not in json.dumps(result.to_dict())


def test_autenticacion_solo_usa_estrategia_y_token_privado(monkeypatch):
    import earthaccess

    class Auth:
        authenticated = True

    calls = []
    monkeypatch.setattr(
        earthaccess, "login",
        lambda **kwargs: calls.append(kwargs) or Auth(),
    )
    monkeypatch.setattr(
        earthaccess, "get_edl_token", lambda: {"access_token": "private-token"})
    source = update.EarthdataHarmonySource.authenticate("environment")
    assert calls == [{"strategy": "environment", "persist": False}]
    assert "private-token" not in repr(source)
    with pytest.raises(ValueError):
        update.EarthdataHarmonySource.authenticate("all")


def test_adaptador_harmony_solicita_un_granulo_y_un_netcdf(tmp_path, monkeypatch):
    import harmony

    captured = {}

    class Executor:
        def shutdown(self, **kwargs):
            captured["shutdown"] = kwargs

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.executor = Executor()

        def submit(self, request):
            captured["request"] = request
            return "job-id"

        def progress(self, job_id):
            return 100, "successful", "ok"

        def download_all(self, job_id, directory, overwrite):
            path = Path(directory) / "subset.nc4"
            path.write_bytes(b"netcdf-placeholder")
            future = Future()
            future.set_result(str(path))
            return iter((future,))

    monkeypatch.setattr(harmony, "Client", Client)
    source = update.EarthdataHarmonySource("private-token")
    req = request(tmp_path)
    granule = update._granule_from_result(cmr_result())
    paths = source.download(
        granule, query_bounds=req.query_bounds, directory=tmp_path,
        timeout_seconds=30, poll_seconds=.1,
    )
    harmony_request = captured["request"]
    assert captured["client"]["token"] == "private-token"
    assert harmony_request.collection.id == update.COLLECTION_ID
    assert harmony_request.granule_id == [granule.concept_id]
    assert harmony_request.format == "application/netcdf"
    assert harmony_request.max_results == 1
    assert paths == (tmp_path / "subset.nc4",)


def test_manifiesto_modificado_falla_cerrado(tmp_path):
    ds = nrt_dataset()
    req = request(tmp_path, ds)
    result = run(req, FakeSource(ds))
    path = req.data_directory / result.source_file_name
    manifest_path = Path(f"{path}{mur.ACQUISITION_MANIFEST_SUFFIX}")
    manifest = json.loads(manifest_path.read_text())
    manifest["source_file_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    field = mur.fetch_mur_field(
        *bounds(ds), NATIVE.date(), options=mur.MurOptions(AS_OF),
        data_directory=req.data_directory,
    )
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "source_failure"


def test_identidad_de_granulo_modificada_falla_cerrado(tmp_path):
    ds = nrt_dataset()
    req = request(tmp_path, ds)
    result = run(req, FakeSource(ds))
    path = req.data_directory / result.source_file_name
    manifest_path = Path(f"{path}{mur.ACQUISITION_MANIFEST_SUFFIX}")
    manifest = json.loads(manifest_path.read_text())
    manifest["granule_ur"] = "another-product"
    manifest_path.write_text(json.dumps(manifest))
    field = mur.fetch_mur_field(
        *bounds(ds), NATIVE.date(), options=mur.MurOptions(AS_OF),
        data_directory=req.data_directory,
    )
    assert field.status is mur.MurStatus.ERROR
    assert field.reason == "source_failure"


def test_manifiesto_recuperado_despues_del_as_of_no_retroproyecta_disponibilidad(
        tmp_path):
    ds = nrt_dataset()
    req = request(tmp_path, ds)
    result = run(req, FakeSource(ds))
    field = mur.fetch_mur_field(
        *bounds(ds), NATIVE.date(),
        options=mur.MurOptions(AS_OF - timedelta(minutes=1)),
        data_directory=req.data_directory,
    )
    assert field.status is mur.MurStatus.VALIDA_EN_FECHA_NOMINAL
    assert not field.provenance.availability_as_of_verified
    assert field.provenance.availability_basis == "retrieved_after_requested_as_of"
