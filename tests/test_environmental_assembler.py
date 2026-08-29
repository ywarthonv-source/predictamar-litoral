"""Contrato sintético del ensamblador ambiental.

No consulta Copernicus, GEBCO ni datos IMARPE. Los proveedores se inyectan
para comprobar orquestación, trazabilidad, fallos parciales y ausencia de
scoring sin alterar los módulos fuente.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
import json
import pytest
import yaml

import assembly.environmental_assembler as ea


LAT = -12.471
LON = -76.790
TARGET_DATE = date(2026, 8, 26)


@dataclass(frozen=True)
class FakeSample:
    time_utc: datetime
    value_celsius: float = 20.0
    value_salinity: float = 35.0
    temperature_10m_celsius: float = 19.0
    delta_sst_t10_celsius: float = 1.0


@dataclass(frozen=True)
class FakeReading:
    status: str
    dataset_id: str = "synthetic_dataset"
    variable: str = "synthetic_variable"
    data_scope: str = "synthetic_scope"
    scope_warning: str = "Synthetic data; no fishing interpretation."
    samples: tuple[FakeSample, ...] = ()
    significant_wave_height_m: float | None = 1.0
    value_mg_m3: float | None = 2.0
    sst_celsius: tuple[tuple[float | None, ...], ...] = ((20.0,),)
    analysis_error_kelvin: tuple[tuple[float | None, ...], ...] = ((0.2,),)
    gradient_c_per_km: tuple[tuple[float | None, ...], ...] = ((0.1,),)
    eastward_gradient_c_per_km: tuple[tuple[float | None, ...], ...] = ((0.1,),)
    northward_gradient_c_per_km: tuple[tuple[float | None, ...], ...] = ((0.0,),)
    measurements: tuple[dict[str, float], ...] = (
        ({"uo_m_s": 0.1, "vo_m_s": 0.2, "speed_m_s": 0.2236, "direction_toward_deg": 26.565},),
    )
    depth_m: float | None = 30.0
    slope_deg: float | None = 2.0
    tid_code: int | None = 10


@dataclass(frozen=True)
class BadReading:
    status: str


VALID_STATUSES = {
    "sst": "valida_en_ventana",
    "oleaje": "bajo_umbral_regional",
    "clorofila": "valida_en_fecha_local",
    "salinidad": "valida_en_ventana",
    "sst_observed_ostia": "valida_en_fecha_nominal",
    "thermal_front": "valido",
    "vertical": "valida_en_ventana",
    "surface_currents": "valida_en_ventana",
    "batimetria": "valida",
}

NO_DATA_STATUSES = {
    "sst": "sin_datos",
    "oleaje": "sin_datos",
    "clorofila": "sin_datos",
    "salinidad": "sin_datos",
    "sst_observed_ostia": "sin_datos",
    "thermal_front": "fuente_sin_datos",
    "vertical": "sin_datos",
    "surface_currents": "sin_datos",
    "batimetria": "sin_datos",
}


def make_providers(*, statuses=None, raises=(), overrides=None):
    statuses = {**VALID_STATUSES, **(statuses or {})}
    raises = set(raises)
    overrides = overrides or {}
    calls = []
    ostia_holder = {}

    def result(name, *args):
        calls.append((name, args))
        if name in raises:
            raise RuntimeError(f"synthetic failure: {name}")
        if name in overrides:
            return overrides[name]
        reading = FakeReading(
            status=statuses[name],
            samples=(FakeSample(datetime(2026, 8, 26, 6, tzinfo=timezone.utc)),),
        )
        if name == "sst_observed_ostia":
            ostia_holder["source"] = reading
        return reading

    def derive(source):
        calls.append(("thermal_front", (source,)))
        assert source is ostia_holder["source"]
        if "thermal_front" in raises:
            raise RuntimeError("synthetic failure: thermal_front")
        if "thermal_front" in overrides:
            return overrides["thermal_front"]
        return FakeReading(status=statuses["thermal_front"])

    providers = ea.AssemblerProviders(
        fetch_sst=lambda *args: result("sst", *args),
        get_wave_status=lambda *args: result("oleaje", *args),
        fetch_chlorophyll=lambda *args: result("clorofila", *args),
        fetch_salinity=lambda *args: result("salinidad", *args),
        fetch_ostia_field=lambda *args: result("sst_observed_ostia", *args),
        derive_thermal_front=derive,
        fetch_vertical_thermal_pair=lambda *args: result("vertical", *args),
        fetch_currents=lambda *args: result("surface_currents", *args),
        fetch_bathymetry=lambda *args: result("batimetria", *args),
    )
    return providers, calls


def make_request(**changes):
    values = {
        "lat": LAT,
        "lon": LON,
        "target_date": TARGET_DATE,
        "hour_start_local": 0,
        "hour_end_local": 23,
    }
    values.update(changes)
    return ea.AssemblyRequest(**values)


def minimal_spec():
    return {
        "variables": {
            variable_id: {
                "descripcion": variable_id,
                "intended_role": "A",
                "implementation_status": "implementada_validada_sinteticamente",
                "scoring_status": "inactiva",
                "predictively_valid": None,
                "profile": "synthetic_profile",
                "modulo": "synthetic.py",
            }
            for variable_id in ea.VARIABLE_ORDER
        }
    }


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def test_1_ensambla_diez_variables_con_ocho_adquisiciones_y_una_derivacion():
    providers, calls = make_providers()

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.schema_version == "environmental_snapshot_v1"
    assert snapshot.status is ea.OverallAssemblyStatus.COMPLETE
    assert snapshot.available_count == 10
    assert snapshot.no_data_count == 0
    assert snapshot.error_count == 0
    assert tuple(item.variable_id for item in snapshot.variables) == ea.VARIABLE_ORDER
    assert len(calls) == 9  # ocho adquisiciones + una derivación local
    assert [name for name, _ in calls].count("sst_observed_ostia") == 1
    assert [name for name, _ in calls].count("vertical") == 1
    assert [name for name, _ in calls].count("thermal_front") == 1


def test_2_campo_ostia_usa_caja_explicita_y_alimenta_la_derivacion():
    providers, calls = make_providers()

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    ostia_call = next(args for name, args in calls if name == "sst_observed_ostia")
    assert ostia_call[:4] == pytest.approx((-12.621, -12.321, -76.940, -76.640))
    assert ostia_call[4] == TARGET_DATE
    bounds = snapshot.request.field_bounds
    assert (
        bounds.minimum_latitude,
        bounds.maximum_latitude,
        bounds.minimum_longitude,
        bounds.maximum_longitude,
    ) == pytest.approx((-12.621, -12.321, -76.940, -76.640))
    assert snapshot.get("sst_observed_ostia").shared_operation == "ostia_field"
    assert snapshot.get("thermal_front").shared_operation == "ostia_field"


def test_3_par_vertical_se_consulta_una_vez_y_no_se_recalcula():
    providers, calls = make_providers()

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert [name for name, _ in calls].count("vertical") == 1
    temperature = snapshot.get("temperature_10m")
    delta = snapshot.get("delta_sst_t10")
    assert temperature.payload == delta.payload
    assert temperature.value_paths == ("samples[].temperature_10m_celsius",)
    assert delta.value_paths == ("samples[].delta_sst_t10_celsius",)
    assert temperature.payload["samples"][0]["temperature_10m_celsius"] == 19.0
    assert delta.payload["samples"][0]["delta_sst_t10_celsius"] == 1.0


def test_4_no_agrega_series_y_serializa_fechas_en_json():
    providers, _ = make_providers()

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)
    document = json.loads(snapshot.to_json())

    assert document["request"]["target_date"] == "2026-08-26"
    assert document["request"]["field_bounds"]["minimum_latitude"] == pytest.approx(-12.621)
    sample = document["variables"]["sst"]["payload"]["samples"][0]
    assert sample["time_utc"] == "2026-08-26T06:00:00+00:00"
    assert sample["value_celsius"] == 20.0
    assert document["variables"]["sst"]["payload"]["dataset_id"] == "synthetic_dataset"
    assert document["variables"]["sst"]["payload"]["scope_warning"].startswith("Synthetic")
    assert "mean" not in sample and "median" not in sample
    assert "score" not in set(walk_keys(document))
    assert "favorability" not in set(walk_keys(document))
    assert "ranking" not in set(walk_keys(document))


def test_5_gobernanza_proviene_del_yaml_y_no_activa_scoring():
    providers, _ = make_providers()

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.get("sst").governance.implementation_status == "implementada_validada_tecnicamente"
    assert snapshot.get("sst_observed_ostia").governance.implementation_status == "implementada_validada_sinteticamente"
    assert snapshot.get("thermal_front").governance.implementation_status == "implementada_validada_sinteticamente"
    assert snapshot.get("temperature_10m").governance.intended_role == "B"
    assert snapshot.get("oleaje").governance.scoring_status == "fuera_del_ranking"
    assert all(item.governance.predictively_valid is not True for item in snapshot.variables)


def test_6_ausencia_total_queda_explicita_y_bloquea_seguridad():
    providers, _ = make_providers(statuses=NO_DATA_STATUSES)

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.status is ea.OverallAssemblyStatus.NO_DATA
    assert snapshot.available_count == 0
    assert snapshot.no_data_count == 10
    assert snapshot.error_count == 0
    assert all(item.state is ea.AssemblyState.NO_DATA for item in snapshot.variables)
    assert snapshot.safety.blocked is True
    assert snapshot.safety.reason == "no_wave_data"


def test_7_fallos_de_fuente_se_aislan_y_no_borran_variables_sanas():
    providers, _ = make_providers(raises={"salinidad", "vertical"})

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.status is ea.OverallAssemblyStatus.PARTIAL
    assert snapshot.available_count == 7
    assert snapshot.error_count == 3
    assert snapshot.get("salinidad").error_code == "provider_exception"
    assert snapshot.get("temperature_10m").error_type == "RuntimeError"
    assert snapshot.get("delta_sst_t10").error_type == "RuntimeError"
    assert snapshot.get("sst").state is ea.AssemblyState.AVAILABLE
    assert snapshot.safety.blocked is False


@pytest.mark.parametrize(
    ("wave_status", "blocked", "reason"),
    [
        ("bajo_umbral_regional", False, "below_provisional_regional_threshold"),
        ("sobre_umbral_regional", True, "at_or_above_provisional_regional_threshold"),
        ("sin_datos", True, "no_wave_data"),
    ],
)
def test_8_compuerta_de_oleaje_es_independiente_del_estado_general(
    wave_status, blocked, reason
):
    providers, _ = make_providers(statuses={"oleaje": wave_status})

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.safety.blocked is blocked
    assert snapshot.safety.reason == reason
    assert "autorización" in snapshot.safety.not_authorization_notice.lower()


def test_9_excepcion_de_oleaje_bloquea_y_no_se_interpreta_como_mar_seguro():
    providers, _ = make_providers(raises={"oleaje"})

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.get("oleaje").state is ea.AssemblyState.ERROR
    assert snapshot.safety.blocked is True
    assert snapshot.safety.reason == "provider_error"


def test_10_status_desconocido_se_trata_como_deriva_de_contrato():
    providers, _ = make_providers(statuses={"clorofila": "aparentemente_valida"})

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    result = snapshot.get("clorofila")
    assert result.state is ea.AssemblyState.ERROR
    assert result.source_status == "aparentemente_valida"
    assert result.error_code == "unknown_source_status"


def test_11_resultado_sin_dataclass_o_sin_ruta_de_valor_es_error():
    providers, _ = make_providers(
        overrides={
            "surface_currents": {"status": "valida_en_ventana"},
            "clorofila": BadReading(status="valida_en_fecha_local"),
        }
    )

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.get("surface_currents").error_code == "invalid_provider_result"
    assert snapshot.get("surface_currents").error_type == "TypeError"
    assert snapshot.get("clorofila").error_code == "invalid_provider_result"
    assert snapshot.get("clorofila").error_type == "TypeError"


def test_12_numero_no_finito_no_entra_en_json_como_nan():
    providers, _ = make_providers(
        overrides={"oleaje": replace(FakeReading(status="bajo_umbral_regional"), significant_wave_height_m=float("nan"))}
    )

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.get("oleaje").state is ea.AssemblyState.ERROR
    assert snapshot.get("oleaje").error_code == "invalid_provider_result"
    assert snapshot.safety.blocked is True
    assert "NaN" not in snapshot.to_json()


@pytest.mark.parametrize(
    "changes",
    [
        {"lat": True},
        {"lat": -91.0},
        {"lon": 181.0},
        {"target_date": datetime(2026, 8, 26)},
        {"hour_start_local": -1},
        {"hour_end_local": 24},
        {"hour_start_local": 12, "hour_end_local": 6},
        {"field_half_width_deg": 0.0},
        {"field_half_width_deg": 1.1},
        {"lat": 89.9, "field_half_width_deg": 0.2},
    ],
)
def test_13_solicitudes_invalidas_fallan_antes_de_consultar(changes):
    with pytest.raises(ValueError):
        make_request(**changes)


def test_14_tipo_de_solicitud_y_proveedores_se_valida():
    providers, _ = make_providers()

    with pytest.raises(TypeError):
        ea.assemble_environmental_snapshot({"lat": LAT}, providers=providers)
    with pytest.raises(TypeError):
        ea.assemble_environmental_snapshot(make_request(), providers={})


def test_15_spec_sin_variable_ensamblada_falla_antes_de_consultar(tmp_path):
    original = minimal_spec()
    original["variables"].pop("clorofila")
    spec = tmp_path / "variables_spec.yaml"
    spec.write_text(yaml.safe_dump(original, allow_unicode=True), encoding="utf-8")
    providers, calls = make_providers()

    with pytest.raises(ValueError, match="clorofila"):
        ea.assemble_environmental_snapshot(make_request(), providers=providers, spec_path=spec)
    assert calls == []


def test_16_spec_no_puede_registrar_como_ensamblada_una_variable_no_implementada(tmp_path):
    original = minimal_spec()
    original["variables"]["sst"]["implementation_status"] = "no_implementada"
    spec = tmp_path / "variables_spec.yaml"
    spec.write_text(yaml.safe_dump(original, allow_unicode=True), encoding="utf-8")
    providers, calls = make_providers()

    with pytest.raises(ValueError, match="no implementada"):
        ea.assemble_environmental_snapshot(make_request(), providers=providers, spec_path=spec)
    assert calls == []


def test_17_get_rechaza_variable_fuera_del_contrato():
    providers, _ = make_providers()
    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    with pytest.raises(KeyError):
        snapshot.get("captura_pesquera")


def test_18_fallo_de_derivacion_no_borra_el_campo_ostia_fuente():
    providers, _ = make_providers(raises={"thermal_front"})

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.status is ea.OverallAssemblyStatus.PARTIAL
    assert snapshot.get("sst_observed_ostia").state is ea.AssemblyState.AVAILABLE
    assert snapshot.get("thermal_front").state is ea.AssemblyState.ERROR
    assert snapshot.get("thermal_front").error_code == "provider_exception"


def test_19_si_todos_los_proveedores_fallan_el_estado_global_es_failed():
    providers, _ = make_providers(
        raises={
            "sst",
            "oleaje",
            "clorofila",
            "salinidad",
            "sst_observed_ostia",
            "vertical",
            "surface_currents",
            "batimetria",
        }
    )

    snapshot = ea.assemble_environmental_snapshot(make_request(), providers=providers)

    assert snapshot.status is ea.OverallAssemblyStatus.FAILED
    assert snapshot.available_count == 0
    assert snapshot.no_data_count == 0
    assert snapshot.error_count == 10
    assert snapshot.safety.blocked is True
    assert snapshot.safety.reason == "provider_error"


def test_20_proveedores_predeterminados_exponen_nueve_callables():
    providers = ea.AssemblerProviders()

    assert all(
        callable(getattr(providers, name))
        for name in (
            "fetch_sst",
            "get_wave_status",
            "fetch_chlorophyll",
            "fetch_salinity",
            "fetch_ostia_field",
            "derive_thermal_front",
            "fetch_vertical_thermal_pair",
            "fetch_currents",
            "fetch_bathymetry",
        )
    )
