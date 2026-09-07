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


def validated_transform_config(config):
    candidate = deepcopy(config)
    candidate["index_contract"]["factor_scores"][
        "raw_to_score_transform_status"
    ] = "validated_versioned"
    candidate["transform_registry"]["status"] = "validated_versioned"
    transforms = candidate["transform_registry"]["approved_transforms"]
    for species_id, model in candidate["species_models"].items():
        for factor_id in model["weights_bp"]:
            transform_id = f"{species_id}.{factor_id}.test_v1"
            transforms[transform_id] = {
                "species_id": species_id,
                "factor_id": factor_id,
                "status": "validated_for_research_combination",
                "version": "test_v1",
                "calibration_id": f"calibration-{species_id}-test-v1",
                "source_data_version": "synthetic-test-data-v1",
            }
    validate_weighting_config(candidate)
    return candidate


@pytest.fixture(scope="module")
def calibrated_config(config):
    return validated_transform_config(config)


def traceable_score(config, species_id, factor_id, value):
    transform_id = f"{species_id}.{factor_id}.test_v1"
    transform = config["transform_registry"]["approved_transforms"][transform_id]
    return {
        "value": value,
        "transform_id": transform_id,
        "transform_version": transform["version"],
        "calibration_id": transform["calibration_id"],
        "source_data_version": transform["source_data_version"],
    }


def complete_scores(config, species_id, value=0.5):
    return {
        factor_id: traceable_score(config, species_id, factor_id, value)
        for factor_id in config["species_models"][species_id]["weights_bp"]
    }


def test_1_configuracion_real_es_valida_y_todas_las_filas_suman_10000(config):
    assert config["schema_version"] == "species_weighting_v1"
    assert len(config["species_models"]) == 9
    assert len(config["ui_order"]) == 10
    for model in config["species_models"].values():
        assert sum(model["weights_bp"].values()) == 10_000
        assert model["operational_enabled"] is False


def test_2_chauchilla_es_alias_exacto_de_bonito(config, calibrated_config):
    requested, canonical = resolve_species_id("CHAUCHILLA", config)
    assert (requested, canonical) == ("chauchilla", "bonito")
    assert "weights_bp" not in config["aliases"]["chauchilla"]

    result = combine_factor_scores(
        "chauchilla",
        complete_scores(calibrated_config, "bonito"),
        config=calibrated_config,
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


def test_5_formula_completa_usa_pesos_fijos_sin_normalizacion(calibrated_config):
    scores = complete_scores(calibrated_config, "anchoveta", value=1.0)

    result = combine_factor_scores("ANCHOVETA", scores, config=calibrated_config)

    assert result.status is IndexStatus.COMPLETE_RESEARCH_INDEX
    assert result.index_value == pytest.approx(1.0)
    assert result.coverage_weight == pytest.approx(1.0)
    assert result.lower_bound == pytest.approx(1.0)
    assert result.upper_bound == pytest.approx(1.0)
    assert result.is_probability is False
    assert result.operational_enabled is False


def test_6_un_factor_faltante_elimina_indice_y_no_redistribuye(calibrated_config):
    scores = {
        factor_id: traceable_score(
            calibrated_config, "anchoveta", factor_id, 1.0
        )
        for factor_id in ("surface_temperature", "surface_salinity")
    }

    result = combine_factor_scores("anchoveta", scores, config=calibrated_config)

    assert result.status is IndexStatus.INSUFFICIENT_DATA
    assert result.index_value is None
    assert result.coverage_weight == pytest.approx(0.45)
    assert result.lower_bound == pytest.approx(0.45)
    assert result.upper_bound == pytest.approx(1.0)
    assert "chlorophyll_a" in result.missing_factors
    assert any("no se imputan" in item for item in result.warnings)


def test_7_ceros_explicitos_son_datos_y_no_faltantes(calibrated_config):
    scores = complete_scores(calibrated_config, "pejerrey", value=0.0)

    result = combine_factor_scores("PEJERREY", scores, config=calibrated_config)

    assert result.status is IndexStatus.COMPLETE_RESEARCH_INDEX
    assert result.index_value == pytest.approx(0.0)
    assert result.missing_factors == ()


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf")])
def test_8_rechaza_factor_fuera_de_rango(value, calibrated_config):
    score = traceable_score(
        calibrated_config, "anchoveta", "surface_temperature", value
    )
    with pytest.raises(ValueError, match="entre 0 y 1"):
        combine_factor_scores(
            "anchoveta",
            {"surface_temperature": score},
            config=calibrated_config,
        )


def test_9_rechaza_nan(calibrated_config):
    value = float("nan")
    assert isnan(value)
    score = traceable_score(
        calibrated_config, "anchoveta", "surface_temperature", value
    )
    with pytest.raises(ValueError, match="entre 0 y 1"):
        combine_factor_scores(
            "anchoveta",
            {"surface_temperature": score},
            config=calibrated_config,
        )


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


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("status",), "operational", "status debe permanecer"),
        (
            ("index_contract", "catch_prediction"),
            True,
            "catch_prediction debe ser false",
        ),
        (
            ("index_contract", "missing_data", "imputation"),
            "median",
            "imputation debe permanecer en forbidden",
        ),
        (
            (
                "index_contract",
                "factor_scores",
                "raw_to_score_transform_status",
            ),
            "validated",
            "raw_to_score_transform_status",
        ),
        (
            ("index_contract", "safety", "oleaje", "weight_bp"),
            1000,
            "oleaje.weight_bp",
        ),
    ],
)
def test_20_rechaza_mutaciones_que_activarían_un_contrato_prohibido(
    config, path, value, match
):
    broken = deepcopy(config)
    target = broken
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(SpeciesWeightingConfigError, match=match):
        validate_weighting_config(broken)


def test_21_configuracion_real_no_admite_scores_sin_transformacion_registrada(config):
    with pytest.raises(TypeError, match="mapping trazable"):
        combine_factor_scores(
            "anchoveta", {"surface_temperature": 0.5}, config=config
        )

    self_declared = {
        "value": 0.5,
        "transform_id": "inventada",
        "transform_version": "v1",
        "calibration_id": "sin-calibracion",
        "source_data_version": "sin-fuente",
    }
    with pytest.raises(SpeciesWeightingConfigError, match="siguen pendientes"):
        combine_factor_scores(
            "anchoveta", {"surface_temperature": self_declared}, config=config
        )


def test_22_contribucion_conserva_procedencia_y_rechaza_discrepancias(
    calibrated_config,
):
    scores = complete_scores(calibrated_config, "anchoveta")
    result = combine_factor_scores(
        "anchoveta", scores, config=calibrated_config
    )
    contribution = result.contributions[0]
    assert contribution.transform_id.startswith("anchoveta.")
    assert contribution.transform_version == "test_v1"
    assert contribution.calibration_id == "calibration-anchoveta-test-v1"
    assert contribution.source_data_version == "synthetic-test-data-v1"

    broken_scores = deepcopy(scores)
    broken_scores["surface_temperature"]["transform_version"] = "otra-version"
    with pytest.raises(ValueError, match="procedencia no coincide"):
        combine_factor_scores(
            "anchoveta", broken_scores, config=calibrated_config
        )


def test_23_registro_de_transformaciones_pendiente_debe_permanecer_vacio(config):
    broken = deepcopy(config)
    broken["transform_registry"]["approved_transforms"]["inventada"] = {}
    with pytest.raises(SpeciesWeightingConfigError, match="registro esté pendiente"):
        validate_weighting_config(broken)
