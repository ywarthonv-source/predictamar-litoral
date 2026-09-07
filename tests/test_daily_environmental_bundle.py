from copy import deepcopy
from datetime import date, datetime, timezone
import json

import pytest

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
        generated_at=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )


def test_1_bundle_tiene_frescura_huella_y_scoring_bloqueado():
    document = bundle()
    validate_daily_bundle(document, expected_target_date=date(2026, 9, 7))

    assert document["schema_version"] == BUNDLE_SCHEMA_VERSION
    assert document["run_id"].startswith("2026-09-07-")
    assert len(document["content_sha256"]) == 64
    assert document["generated_at_utc"] == "2026-09-07T12:00:00Z"
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
    with pytest.raises(ValueError, match="content_sha256"):
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
