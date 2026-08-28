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
