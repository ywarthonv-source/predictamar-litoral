from datetime import date
from pathlib import Path

import pytest

from diagnostics.diagnose_spatial_discrimination import (
    CandidatePoint,
    diagnose_spatial_discrimination,
    load_candidate_points,
)


class FakeSnapshot:
    def __init__(self, document):
        self.document = document

    def to_dict(self):
        return self.document


def points():
    return (
        CandidatePoint("p0", -12.47, -76.80, 0.0, "synthetic"),
        CandidatePoint("p10", -12.47, -76.89, 10.0, "synthetic"),
    )


def payloads(request):
    offset = 0.0 if request.lon > -76.85 else 1.0
    cell_lon = -76.80 if offset == 0 else -76.90
    common = {
        "sst": {
            "samples": [{"time_utc": "2026-09-07T06:00:00Z", "value_celsius": 18.0 + offset}],
            "cell_lat": -12.5,
            "cell_lon": cell_lon,
        },
        "oleaje": {
            "significant_wave_height_m": 1.0 + offset,
            "cell_lat": -12.5,
            "cell_lon": cell_lon,
        },
        "clorofila": {"value_mg_m3": 2.0, "cell_lat": -12.5, "cell_lon": -76.8},
        "salinidad": {
            "samples": [{"time_utc": "2026-09-07T06:00:00Z", "value_salinity": 35.0}],
            "cell_lat": -12.5,
            "cell_lon": -76.8,
        },
        "sst_observed_ostia": {
            "sst_celsius": [[18.0 + offset]],
            "latitudes": [-12.5],
            "longitudes": [cell_lon],
        },
        "thermal_front": {
            "gradient_c_per_km": [[0.1 + offset]],
            "latitudes": [-12.5],
            "longitudes": [cell_lon],
        },
        "temperature_10m": {
            "samples": [{"time_utc": "2026-09-07T06:00:00Z", "temperature_10m_celsius": 17.0}],
            "cell_lat": -12.5,
            "cell_lon": -76.8,
        },
        "delta_sst_t10": {
            "samples": [{"time_utc": "2026-09-07T06:00:00Z", "delta_sst_t10_celsius": 1.0}],
            "cell_lat": -12.5,
            "cell_lon": -76.8,
        },
        "surface_currents": {
            "measurements": [
                {
                    "time_utc": "2026-09-07T06:00:00Z",
                    "uo_m_s": 0.1,
                    "vo_m_s": 0.2,
                    "speed_m_s": 0.2236,
                    "direction_toward_deg": 26.565,
                    "cell_lat": -12.5,
                    "cell_lon": -76.8,
                }
            ]
        },
        "batimetria": {
            "depth_m": 20.0 + 10.0 * offset,
            "slope_deg": 1.0,
            "cell_lat": request.lat,
            "cell_lon": request.lon,
        },
    }
    return common


def fake_assembler(request):
    data = payloads(request)
    scopes = {
        "oleaje": "regional_maximum",
        "sst_observed_ostia": "regional_field",
        "thermal_front": "regional_field",
    }
    return FakeSnapshot(
        {
            "status": "complete",
            "variables": {
                key: {
                    "state": "available",
                    "spatial_scope": scopes.get(key, "point"),
                    "payload": value,
                }
                for key, value in data.items()
            },
        }
    )


def test_1_detecta_diferenciacion_solo_en_variables_puntuales_admisibles():
    report = diagnose_spatial_discrimination(
        points(), date(2026, 9, 7), assembler=fake_assembler
    )
    by_id = {item["variable_id"]: item for item in report["variables"]}

    assert by_id["sst"]["classification"] == "observed_numeric_variation"
    assert by_id["batimetria"]["classification"] == "observed_numeric_variation"
    assert by_id["clorofila"]["classification"] == "no_observed_numeric_variation"
    assert by_id["oleaje"]["classification"] == "safety_gate_not_ranking"
    assert (
        by_id["sst_observed_ostia"]["classification"]
        == "regional_context_not_point_discriminator"
    )
    assert by_id["thermal_front"]["observed_numeric_variation"] is True
    assert by_id["thermal_front"]["eligible_for_spatial_backtest"] is False
    assert by_id["oleaje"]["observed_numeric_variation"] is True
    assert by_id["oleaje"]["eligible_for_spatial_backtest"] is False
    assert report["variables_eligible_for_spatial_backtest"] == ["sst", "batimetria"]


def test_2_cobertura_incompleta_no_se_declara_diferenciacion():
    def one_missing(request):
        snapshot = fake_assembler(request).to_dict()
        if request.lon < -76.85:
            snapshot["variables"]["sst"]["state"] = "no_data"
        return FakeSnapshot(snapshot)

    report = diagnose_spatial_discrimination(
        points(), date(2026, 9, 7), assembler=one_missing
    )
    sst = next(item for item in report["variables"] if item["variable_id"] == "sst")
    assert sst["classification"] == "insufficient_coverage"
    assert sst["eligible_for_spatial_backtest"] is False


def test_3_rechaza_plantilla_no_aprobada(tmp_path: Path):
    path = tmp_path / "points.yaml"
    path.write_text(
        """\
schema_version: operational_points_v1
geometry_status: pending_approval
distance_basis: distance_offshore_from_coastline
points: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="geometry_status"):
        load_candidate_points(path)


def test_4_rechaza_distancia_fuera_de_0_10(tmp_path: Path):
    path = tmp_path / "points.yaml"
    path.write_text(
        """\
schema_version: operational_points_v1
geometry_status: approved
distance_basis: distance_offshore_from_coastline
points:
  - {id: p0, lat: -12.47, lon: -76.80, distance_offshore_km: 0, geometry_source: test}
  - {id: p11, lat: -12.47, lon: -76.90, distance_offshore_km: 11, geometry_source: test}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fuera del alcance"):
        load_candidate_points(path)


def test_5_una_diferencia_solo_de_timestamp_no_es_variacion_espacial():
    def timestamp_only(request):
        snapshot = fake_assembler(request).to_dict()
        sample = snapshot["variables"]["sst"]["payload"]["samples"][0]
        sample["value_celsius"] = 18.0
        sample["time_utc"] = (
            "2026-09-07T06:00:00Z"
            if request.lon > -76.85
            else "2026-09-07T12:00:00Z"
        )
        return FakeSnapshot(snapshot)

    report = diagnose_spatial_discrimination(
        points(), date(2026, 9, 7), assembler=timestamp_only
    )
    sst = next(item for item in report["variables"] if item["variable_id"] == "sst")
    assert sst["classification"] == "insufficient_temporal_alignment"
    assert sst["common_timestamp_count"] == 0
    assert sst["distinct_value_groups"] == 0
    assert sst["observed_numeric_variation"] is False
    assert sst["eligible_for_spatial_backtest"] is False


def test_6_diferencia_menor_que_tolerancia_no_habilita_backtest():
    def numerical_noise(request):
        snapshot = fake_assembler(request).to_dict()
        sample = snapshot["variables"]["sst"]["payload"]["samples"][0]
        sample["value_celsius"] = 18.0 if request.lon > -76.85 else 18.005
        return FakeSnapshot(snapshot)

    report = diagnose_spatial_discrimination(
        points(), date(2026, 9, 7), assembler=numerical_noise
    )
    sst = next(item for item in report["variables"] if item["variable_id"] == "sst")
    assert sst["classification"] == "no_observed_numeric_variation"
    assert sst["comparison_abs_tolerance"] == pytest.approx(0.01)
    assert sst["max_pairwise_abs_difference"] == pytest.approx(0.005)
    assert sst["distinct_value_groups"] == 1
    assert sst["eligible_for_spatial_backtest"] is False


def test_7_diferencia_superior_a_tolerancia_admite_solo_backtest():
    def actual_difference(request):
        snapshot = fake_assembler(request).to_dict()
        sample = snapshot["variables"]["sst"]["payload"]["samples"][0]
        sample["value_celsius"] = 18.0 if request.lon > -76.85 else 18.02
        return FakeSnapshot(snapshot)

    report = diagnose_spatial_discrimination(
        points(), date(2026, 9, 7), assembler=actual_difference
    )
    sst = next(item for item in report["variables"] if item["variable_id"] == "sst")
    assert sst["classification"] == "observed_numeric_variation"
    assert sst["common_timestamp_count"] == 1
    assert sst["distinct_value_groups"] == 2
    assert sst["observed_numeric_variation"] is True
    assert sst["eligible_for_spatial_backtest"] is True
    assert "ranking" not in report
