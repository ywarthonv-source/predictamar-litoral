"""Invariantes estructurales de config/variables_spec.yaml."""

from pathlib import Path

import yaml

SPEC = Path(__file__).resolve().parents[1] / "config" / "variables_spec.yaml"


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader que rechaza claves repetidas en cualquier mapping."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_spec():
    return yaml.load(SPEC.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def test_1_especificacion_no_contiene_claves_duplicadas():
    data = load_spec()
    assert len(data["variables"]) == 25
    assert list(data["variables"]).count("surface_currents") == 1


def test_2_bloque_termico_declara_modulos_fuente_y_estado_real():
    variables = load_spec()["variables"]
    ostia = variables["sst_observed_ostia"]
    front = variables["thermal_front"]
    assert ostia["implementation_status"] == "implementada_validada_sinteticamente"
    assert ostia["dataset_id"] == "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
    assert ostia["modulo"] == "ingestion/fetch_ostia.py"
    assert "thetao instantánea PT6H" in ostia["proposito"]
    assert "contexto regional" in ostia["nota"]
    assert front["implementation_status"] == "implementada_validada_sinteticamente"
    assert front["fuente"].startswith("sst_observed_ostia")
    assert front["modulo"] == "derivation/thermal_front.py"
    assert front["umbral_de_frente"] is None
    assert front["etiqueta_visualizacion"] == "Gradiente térmico regional (experimental)"
    assert "no son directamente comparables" in front["comparabilidad_metodos"]


def test_3_ninguna_variable_afirma_validez_predictiva():
    variables = load_spec()["variables"]
    assert not [name for name, cfg in variables.items() if cfg.get("predictively_valid") is True]
    assert all(variables[name]["scoring_status"] == "inactiva" for name in ("sst_observed_ostia", "thermal_front"))


def test_4_par_termico_vertical_declara_coherencia_y_nivel_nativo_real():
    data = load_spec()
    variables = data["variables"]
    profile = data["profiles"]["fetcher_puntual_termico_vertical_phy_0083deg_pt6h"]
    temperature = variables["temperature_10m"]
    delta = variables["delta_sst_t10"]

    assert profile["aplica_a_hoy"] == ["temperature_10m", "delta_sst_t10"]
    assert "misma celda" in profile["reglas"]["emparejamiento_estricto"]
    assert temperature["implementation_status"] == "implementada_validada_sinteticamente"
    assert temperature["modulo"] == "ingestion/fetch_vertical_temperature.py"
    assert temperature["dataset_version"] == "202406"
    assert temperature["profundidad"]["solicitada_m"] == 10.0
    assert temperature["profundidad"]["nivel_nativo_oficial_m"] == 9.572997093200684
    assert delta["implementation_status"] == "implementada_validada_sinteticamente"
    assert delta["formula"] == "thetao_superficie - thetao_nivel_nativo_cercano_a_10m"
    assert delta["unidades"] == "degree_Celsius"
    assert "NO equivale a gradiente vertical" in delta["nota"]
    assert temperature["scoring_status"] == delta["scoring_status"] == "inactiva"
    assert temperature["predictively_valid"] is None
    assert delta["predictively_valid"] is None
