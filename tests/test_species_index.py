"""Pruebas del contrato de ponderación por especie.

Estas pruebas no afirman validez pesquera: impiden que reaparezcan la
normalización silenciosa, la imputación y la duplicación taxonómica del modelo
histórico.
"""

from copy import deepcopy
from math import isnan

import pytest
import yaml

from assembly.environmental_assembler import VARIABLE_ORDER
from scoring.species_index import (
    DEFAULT_WEIGHTING_PATH,
    IndexStatus,
    SpeciesWeightingConfigError,
    combine_factor_scores,
    load_weighting_config,
    resolve_species_id,
    validate_weighting_config,
)


ROOT = DEFAULT_WEIGHTING_PATH.parents[1]


@pytest.fixture(scope="module")
def config():
    return load_weighting_config()


def complete_scores(model):
    return {factor_id: 0.5 for factor_id in model["weights_bp"]}


def test_1_configuracion_real_es_valida_y_todas_las_filas_suman_10000(config):
    assert config["schema_version"] == "species_weighting_v1"
    assert len(config["species_models"]) == 9
    assert len(config["ui_order"]) == 10
    for model in config["species_models"].values():
        assert sum(model["weights_bp"].values()) == 10_000
        assert model["operational_enabled"] is False


def test_2_chauchilla_es_alias_exacto_de_bonito(config):
    requested, canonical = resolve_species_id("CHAUCHILLA", config)
    assert (requested, canonical) == ("chauchilla", "bonito")
    assert "weights_bp" not in config["aliases"]["chauchilla"]

    result = combine_factor_scores(
        "chauchilla", complete_scores(config["species_models"]["bonito"]), config=config
    )
    assert result.canonical_species_id == "bonito"
    assert result.ui_label == "CHAUCHILLA"
    assert any("no es un taxón independiente" in item for item in result.warnings)


def test_3_oleaje_no_es_factor_y_su_peso_es_cero(config):
    assert "oleaje" not in config["factor_registry"]
    assert config["index_contract"]["safety"]["oleaje"]["weight_bp"] == 0
    assert all(
        "oleaje" not in model["weights_bp"]
        for model in config["species_models"].values()
    )


def test_4_variables_del_ensamblador_referenciadas_existen(config):
    implemented = set(VARIABLE_ORDER)
    for factor in config["factor_registry"].values():
        assert set(factor["current_assembler_variables"]) <= implemented


def test_5_formula_completa_usa_pesos_fijos_sin_normalizacion(config):
    model = config["species_models"]["anchoveta"]
    scores = {factor_id: 1.0 for factor_id in model["weights_bp"]}

    result = combine_factor_scores("ANCHOVETA", scores, config=config)

    assert result.status is IndexStatus.COMPLETE_RESEARCH_INDEX
    assert result.index_value == pytest.approx(1.0)
    assert result.coverage_weight == pytest.approx(1.0)
    assert result.lower_bound == pytest.approx(1.0)
    assert result.upper_bound == pytest.approx(1.0)
    assert result.is_probability is False
    assert result.operational_enabled is False


def test_6_un_factor_faltante_elimina_indice_y_no_redistribuye(config):
    scores = {"surface_temperature": 1.0, "surface_salinity": 1.0}

    result = combine_factor_scores("anchoveta", scores, config=config)

    assert result.status is IndexStatus.INSUFFICIENT_DATA
    assert result.index_value is None
    assert result.coverage_weight == pytest.approx(0.45)
    assert result.lower_bound == pytest.approx(0.45)
    assert result.upper_bound == pytest.approx(1.0)
    assert "chlorophyll_a" in result.missing_factors
    assert any("no se imputan" in item for item in result.warnings)


def test_7_ceros_explicitos_son_datos_y_no_faltantes(config):
    model = config["species_models"]["pejerrey"]
    scores = {factor_id: 0.0 for factor_id in model["weights_bp"]}

    result = combine_factor_scores("PEJERREY", scores, config=config)

    assert result.status is IndexStatus.COMPLETE_RESEARCH_INDEX
    assert result.index_value == pytest.approx(0.0)
    assert result.missing_factors == ()


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf")])
def test_8_rechaza_factor_fuera_de_rango(value, config):
    with pytest.raises(ValueError, match="entre 0 y 1"):
        combine_factor_scores("anchoveta", {"surface_temperature": value}, config=config)


def test_9_rechaza_nan(config):
    value = float("nan")
    assert isnan(value)
    with pytest.raises(ValueError, match="entre 0 y 1"):
        combine_factor_scores("anchoveta", {"surface_temperature": value}, config=config)


def test_10_rechaza_factor_desconocido(config):
    with pytest.raises(ValueError, match="factores desconocidos"):
        combine_factor_scores("anchoveta", {"luna": 0.5}, config=config)


def test_11_rechaza_uso_operativo(config):
    with pytest.raises(ValueError, match="uso operativo bloqueado"):
        combine_factor_scores("anchoveta", {}, config=config, purpose="operational")


def test_12_rechaza_normalizacion_habilitada(config):
    broken = deepcopy(config)
    broken["index_contract"]["weights"]["runtime_normalization"] = "allowed"
    with pytest.raises(SpeciesWeightingConfigError, match="forbidden"):
        validate_weighting_config(broken)


def test_13_rechaza_fila_que_no_suma_10000(config):
    broken = deepcopy(config)
    broken["species_models"]["merluza"]["weights_bp"]["bathymetry"] -= 1
    with pytest.raises(SpeciesWeightingConfigError, match="suman 9999"):
        validate_weighting_config(broken)


def test_14_rechaza_alias_con_pesos_independientes(config):
    broken = deepcopy(config)
    broken["aliases"]["chauchilla"]["weights_bp"] = {"surface_temperature": 10_000}
    with pytest.raises(SpeciesWeightingConfigError, match="no debe duplicar"):
        validate_weighting_config(broken)


def test_15_no_existen_probabilidad_ni_semaforos_ocultos(config):
    serialized = DEFAULT_WEIGHTING_PATH.read_text(encoding="utf-8").casefold()
    assert "probability: false" in serialized
    assert config["index_contract"]["traffic_light_thresholds"] is None
    assert config["index_contract"]["operational_ranking_enabled"] is False


def test_16_yaml_no_tiene_pesos_flotantes_ambiguos():
    raw = yaml.safe_load(DEFAULT_WEIGHTING_PATH.read_text(encoding="utf-8"))
    for model in raw["species_models"].values():
        assert all(type(value) is int for value in model["weights_bp"].values())


def test_17_area_y_matriz_comparten_las_diez_etiquetas_en_orden(config):
    area = yaml.safe_load((ROOT / "config" / "area.yaml").read_text(encoding="utf-8"))
    labels = []
    for species_id in config["ui_order"]:
        if species_id in config["aliases"]:
            labels.append(config["aliases"][species_id]["ui_label"])
        else:
            labels.append(config["species_models"][species_id]["ui_label"])
    assert area["species"]["lista_interfaz"] == labels
    assert area["species"]["aliases"]["CHAUCHILLA"]["canonical_id"] == "bonito"


def test_18_tabla_historica_queda_congelada_y_fuera_de_runtime():
    legacy = yaml.safe_load(
        (ROOT / "config" / "legacy_species_rules_v0.yaml").read_text(encoding="utf-8")
    )
    assert legacy["status"] == "audit_only_rejected_for_runtime"
    assert legacy["audit_contract"]["runtime_use_forbidden"] is True
    assert len(legacy["rules"]) == 10
    for rule in legacy["rules"].values():
        actual_sum = sum(rule["weights"].values())
        assert actual_sum == pytest.approx(rule["declared_weight_sum"])
        assert actual_sum != pytest.approx(1.0)


def test_19_merluza_historica_duplicaba_sus_pesos_por_normalizacion():
    legacy = yaml.safe_load(
        (ROOT / "config" / "legacy_species_rules_v0.yaml").read_text(encoding="utf-8")
    )
    merluza = legacy["rules"]["MERLUZA"]
    assert merluza["declared_weight_sum"] == pytest.approx(0.5)
    assert merluza["hidden_scale_factor"] == pytest.approx(2.0)
