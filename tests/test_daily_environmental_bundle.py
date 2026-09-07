from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json

import pytest

import backend.daily_environmental_bundle as daily_bundle
from backend.daily_environmental_bundle import (
    BUNDLE_SCHEMA_VERSION,
    build_daily_bundle,
    validate_daily_bundle,
    write_daily_bundle,
)
from diagnostics.diagnose_spatial_discrimination import CandidatePoint


class FakeSnapshot:
    def __init__(self, request):
        self.request = request

    def to_dict(self):
        return {
            "schema_version": "environmental_snapshot_v1",
            "request": {
                "lat": self.request.lat,
                "lon": self.request.lon,
                "target_date": self.request.target_date.isoformat(),
            },
            "status": "complete",
            "variables": {},
        }


def fake_assembler(request):
    return FakeSnapshot(request)


def points():
    return (
        CandidatePoint("costa", -12.47, -76.80, 0.0, "levantamiento aprobado"),
        CandidatePoint("mar", -12.47, -76.88, 8.0, "levantamiento aprobado"),
    )


def bundle():
    return build_daily_bundle(
        points(),
        date(2026, 9, 7),
        assembler=fake_assembler,
        generated_at=datetime(2026, 9, 7, 0, tzinfo=timezone.utc),
    )


def resign(document):
    document["content_sha256"] = daily_bundle._hash(
        daily_bundle._integrity_payload(document)
    )
    document["run_id"] = (
        f"{document['target_date']}-{document['content_sha256'][:16]}"
    )


def test_1_bundle_tiene_frescura_huella_y_scoring_bloqueado():
    document = bundle()
    validate_daily_bundle(document, expected_target_date=date(2026, 9, 7))

    assert document["schema_version"] == BUNDLE_SCHEMA_VERSION
    assert document["run_id"].startswith("2026-09-07-")
    assert len(document["content_sha256"]) == 64
    assert document["generated_at_utc"] == "2026-09-07T00:00:00Z"
    assert document["status_counts"] == {"complete": 2}
    assert document["scoring"]["status"] == "not_generated"
    assert document["scoring"]["is_probability"] is False
    assert document["scoring"]["operational_enabled"] is False


def test_2_bundle_preserva_un_snapshot_por_punto():
    document = bundle()
    assert [item["point_id"] for item in document["snapshots"]] == ["costa", "mar"]
    assert document["snapshots"][1]["snapshot"]["request"]["lon"] == -76.88


def test_3_detecta_contenido_alterado():
    document = deepcopy(bundle())
    document["snapshots"][0]["snapshot"]["status"] = "error"
    with pytest.raises(ValueError, match="status_counts|content_sha256"):
        validate_daily_bundle(document)


def test_4_rechaza_fecha_distinta():
    with pytest.raises(ValueError, match="se esperaba"):
        validate_daily_bundle(bundle(), expected_target_date=date(2026, 9, 8))


def test_5_escritura_atomica_no_sobrescribe(tmp_path):
    document = bundle()
    path = write_daily_bundle(document, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == document["run_id"]
    with pytest.raises(FileExistsError, match="ya existe"):
        write_daily_bundle(document, tmp_path)


def test_6_rechaza_generated_at_sin_zona():
    with pytest.raises(ValueError, match="zona horaria"):
        build_daily_bundle(
            points(),
            date(2026, 9, 7),
            assembler=fake_assembler,
            generated_at=datetime(2026, 9, 7, 12),
        )


def test_7_huella_cubre_todos_los_metadatos_criticos():
    original = bundle()
    for mutate in (
        lambda item: item.__setitem__("generated_at_utc", "2026-09-07T00:01:00Z"),
        lambda item: item.__setitem__("status_counts", {"error": 999}),
        lambda item: item["operational_contract"].__setitem__("range_km", [0, 999]),
        lambda item: item["scoring"].__setitem__("status", "generated"),
    ):
        changed = deepcopy(original)
        mutate(changed)
        assert daily_bundle._hash(
            daily_bundle._integrity_payload(changed)
        ) != original["content_sha256"]


def test_8_rechaza_fecha_de_generacion_futura_con_huella_valida():
    document = build_daily_bundle(
        points(),
        date(2026, 9, 7),
        assembler=fake_assembler,
        generated_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="está en el futuro"):
        validate_daily_bundle(
            document,
            checked_at=datetime(2026, 9, 7, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda item: item.__setitem__("status_counts", {"error": 999}),
            "status_counts",
        ),
        (
            lambda item: item["operational_contract"].__setitem__(
                "range_km", [0, 999]
            ),
            "operational_contract",
        ),
        (
            lambda item: item["scoring"].__setitem__("status", "generated"),
            "scoring",
        ),
        (
            lambda item: item["snapshots"][0]["snapshot"]["request"].__setitem__(
                "target_date", "1999-01-01"
            ),
            "target_date",
        ),
        (
            lambda item: item["snapshots"][0]["snapshot"]["request"].__setitem__(
                "lat", -1.0
            ),
            "lat no coincide",
        ),
    ],
)
def test_9_rechaza_incoherencias_aunque_se_recalcule_la_huella(mutate, match):
    document = deepcopy(bundle())
    mutate(document)
    resign(document)
    with pytest.raises(ValueError, match=match):
        validate_daily_bundle(document)


def test_10_consumidor_puede_exigir_edad_maxima():
    with pytest.raises(ValueError, match="bundle vencido"):
        validate_daily_bundle(
            bundle(),
            checked_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
            max_generation_age=timedelta(hours=12),
        )


def test_11_api_directa_rechaza_puntos_duplicados_antes_de_consultar():
    duplicated = (points()[0], points()[0])
    with pytest.raises(ValueError, match="duplicado"):
        build_daily_bundle(
            duplicated,
            date(2026, 9, 7),
            assembler=fake_assembler,
            generated_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )
