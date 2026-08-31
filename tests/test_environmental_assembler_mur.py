"""MUR es aditivo: contratos base/OLCI, origen compartido y fallos aislados."""

from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
import yaml

import assembly.environmental_assembler as ea
from ingestion.fetch_mur import MurMode, MurOptions, MurStatus
from derivation.mur_gradient import derive_mur_gradient
from mur_fixtures import AS_OF, TARGET, dataset, parse
from test_environmental_assembler import (
    BadReading, _providers_with_olci, make_providers, make_request, minimal_spec,
)


def request():
    return make_request(lat=-12.47, lon=-76.80, target_date=TARGET, field_half_width_deg=.01)


def with_mur(*, source=None, source_raises=False, gradient_raises=False, olci=False):
    providers, calls = _providers_with_olci() if olci else make_providers()
    source = parse(dataset()) if source is None else source
    def fetch(*args, **kwargs):
        calls.append(("sst_mur", (*args, kwargs)))
        if source_raises:
            raise RuntimeError("SENSITIVE_SOURCE_URL")
        return source
    def derive(field):
        calls.append(("thermal_gradient_mur", (field,)))
        assert field is source
        if gradient_raises:
            raise RuntimeError("SENSITIVE_GRADIENT_ERROR")
        return derive_mur_gradient(field)
    return replace(providers, fetch_mur_field=fetch, derive_mur_gradient=derive), calls


@pytest.mark.parametrize("olci", [False, True])
def test_mur_desactivado_no_invoca_io_y_no_cambia_json_base_ni_olci(olci):
    baseline, _ = _providers_with_olci() if olci else make_providers()
    providers, calls = with_mur(source_raises=True, gradient_raises=True, olci=olci)
    options = ea.ChlorophyllOptions(AS_OF) if olci else None
    previous = ea.assemble_environmental_snapshot(request(), providers=baseline, chlorophyll_options=options)
    result = ea.assemble_environmental_snapshot(request(), providers=providers, chlorophyll_options=options)
    assert result.to_json() == previous.to_json()
    assert result.schema_version == (ea.OLCI_SCHEMA_VERSION if olci else ea.SCHEMA_VERSION)
    assert not any(name in ea.MUR_VARIABLE_ORDER for name, _ in calls)
    assert "sst_mur" not in result.to_dict().get("optional_layers", {})


@pytest.mark.parametrize("olci,expected_sha256", [
    (False, "5c6b2e01a695f6fe40dd0fef7a0a9ba6bb6b4a7bd6e0bf2f3752354b247efc68"),
    (True, "36e303ebafabd0b438703df0ca834d7aa5bb21279f067c818ad85278e431dc60"),
])
def test_json_golden_del_commit_anterior_no_cambia_sin_mur(olci, expected_sha256):
    # Hashes obtenidos ejecutando 3cee21f con estos mismos proveedores sintéticos,
    # solicitud y opciones, antes de incorporar MUR. No requieren git en CI.
    providers, _ = _providers_with_olci() if olci else make_providers()
    snapshot = ea.assemble_environmental_snapshot(
        request(), providers=providers,
        chlorophyll_options=ea.ChlorophyllOptions(AS_OF) if olci else None)
    assert hashlib.sha256(snapshot.to_json().encode("utf-8")).hexdigest() == expected_sha256


def test_activacion_lee_una_vez_y_deriva_del_mismo_objeto():
    providers, calls = with_mur()
    options = MurOptions(AS_OF)
    result = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=options)
    assert result.available_count == 12
    assert result.error_count == result.no_data_count == 0
    assert result.schema_version == ea.MUR_SCHEMA_VERSION
    assert tuple(v.variable_id for v in result.variables) == ea.VARIABLE_ORDER + ea.MUR_VARIABLE_ORDER
    assert [name for name, _ in calls].count("sst_mur") == 1
    assert [name for name, _ in calls].count("thermal_gradient_mur") == 1
    args = next(args for name, args in calls if name == "sst_mur")
    assert args[:4] == pytest.approx((-12.48, -12.46, -76.81, -76.79))
    assert args[4] == TARGET and args[5]["options"] is options
    for name in ea.MUR_VARIABLE_ORDER:
        assert result.get(name).spatial_scope is ea.SpatialScope.REGIONAL_FIELD
        assert result.get(name).shared_operation == "mur_field"
    document = json.loads(result.to_json())
    assert document["optional_layers"]["sst_mur"]["mode"] == "nrt_only"
    assert document["variables"]["sst_mur"]["payload"]["grid"]["dt_1km_hours"][0][0] == -7
    assert "mur" in document["spatial_context"]["field_purpose"]
    assert document["spatial_context"]["field_is_operational_domain"] is False


def test_olci_y_mur_independientes_sin_doble_consulta_ni_reemplazo():
    providers, calls = with_mur(olci=True)
    result = ea.assemble_environmental_snapshot(
        request(), providers=providers, mur_options=MurOptions(AS_OF),
        chlorophyll_options=ea.ChlorophyllOptions(AS_OF))
    assert result.available_count == 14
    assert result.schema_version == ea.OLCI_MUR_SCHEMA_VERSION
    assert set(result.to_dict()["optional_layers"]) == {"chlorophyll_olci", "sst_mur"}
    for name in ("sst_mur", "chlorophyll_olci", "sst_observed_ostia"):
        assert [n for n, _ in calls].count(name) == 1


@pytest.mark.parametrize("failure", ["source", "gradient", "no_data", "error", "valid"])
def test_mur_no_modifica_ninguna_variable_base_ni_seguridad(failure, caplog):
    source = parse(dataset())
    if failure in {"no_data", "error"}:
        source = replace(source, status=MurStatus.SIN_DATOS if failure == "no_data" else MurStatus.ERROR,
                         reason="test_reason", error_type="Example" if failure == "error" else None)
    providers, calls = with_mur(source=source, source_raises=failure == "source", gradient_raises=failure == "gradient")
    baseline = ea.assemble_environmental_snapshot(request(), providers=providers)
    result = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=MurOptions(AS_OF))
    assert result.variables[:10] == baseline.variables
    assert result.safety == baseline.safety
    assert result.get("sst_observed_ostia").payload == baseline.get("sst_observed_ostia").payload
    if failure == "source":
        assert result.error_count == 2
        assert "thermal_gradient_mur" not in [n for n, _ in calls]
    elif failure == "gradient":
        assert result.error_count == 1
        assert result.get("sst_mur").state is ea.AssemblyState.AVAILABLE
    elif failure == "no_data":
        assert result.no_data_count == 2 and result.error_count == 0
        assert result.get("thermal_gradient_mur").payload["source_reason"] == "test_reason"
    elif failure == "error":
        assert result.error_count == 2
        assert all(result.get(v).error_code == "source_error" for v in ea.MUR_VARIABLE_ORDER)
    assert "SENSITIVE" not in result.to_json()
    assert "SENSITIVE" not in caplog.text


def test_final_historico_se_serializa_sin_afirmar_disponibilidad_a_as_of():
    field = parse(dataset(stage="Final"), mode=MurMode.HISTORICAL_DIAGNOSTIC)
    providers, _ = with_mur(source=field)
    snapshot = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=field.options)
    source = snapshot.get("sst_mur")
    gradient = snapshot.get("thermal_gradient_mur")
    assert source.source_status == "historica_final"
    assert gradient.payload["source_status"] == "historica_final"
    assert source.payload["provenance"]["product_stage"] == "final"
    assert gradient.payload["source_provenance"]["operational_use_verified"] is False
    assert source.payload["provenance"]["availability_as_of_verified"] is False
    assert source.governance.predictively_valid is None


def test_opcion_invalida_y_spec_incompleto_fallan_antes_de_proveedores(tmp_path):
    providers, calls = with_mur()
    with pytest.raises(TypeError, match="MurOptions"):
        ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=True)
    spec = tmp_path / "spec.yaml"
    spec.write_text(yaml.safe_dump(minimal_spec()), encoding="utf-8")
    with pytest.raises(ValueError, match="sst_mur"):
        ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=MurOptions(AS_OF), spec_path=spec)
    assert calls == []


@pytest.mark.parametrize("source", [BadReading("valida_reciente"), replace(parse(dataset()), status="unexpected")])
def test_contrato_invalido_no_se_pasa_a_derivada(source):
    providers, calls = with_mur(source=source)
    result = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=MurOptions(AS_OF))
    assert result.error_count == 2
    assert result.get("thermal_gradient_mur").error_code == "invalid_shared_source"
    assert "thermal_gradient_mur" not in [n for n, _ in calls]


def test_json_estricto_no_nan_con_huecos_de_sst_y_calidad():
    ds = dataset()
    ds["analysed_sst"].values[0, 3, 3] = np.nan
    ds["analysis_error"].values[:] = np.nan
    providers, _ = with_mur(source=parse(ds))
    snapshot = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=MurOptions(AS_OF))
    text = snapshot.to_json()
    document = json.loads(text)
    assert "NaN" not in text and "Infinity" not in text
    assert document["variables"]["sst_mur"]["payload"]["grid"]["sst_celsius"][1][1] is None
    assert document["variables"]["thermal_gradient_mur"]["payload"]["gradient_c_per_km"][1][1] is None


def test_sin_directorio_real_error_mur_no_impide_ostia(monkeypatch):
    from ingestion.fetch_mur import DATA_DIRECTORY_ENV
    monkeypatch.delenv(DATA_DIRECTORY_ENV, raising=False)
    providers, _ = make_providers()
    snapshot = ea.assemble_environmental_snapshot(request(), providers=providers, mur_options=MurOptions(AS_OF))
    assert snapshot.available_count == 10 and snapshot.error_count == 2
    assert snapshot.get("sst_mur").payload["reason"] == "mur_directory_not_configured"
    assert snapshot.get("sst_observed_ostia").state is ea.AssemblyState.AVAILABLE
