"""Combinador estricto para la matriz objetivo por especie.

El módulo hace una sola operación matemática: combina ``factor_score`` ya
calculados y trazables mediante los pesos fijos del YAML. Cada score debe
declarar una transformación versionada, calibración y versión de fuente que
coincidan con el registro aprobado. No transforma datos oceanográficos crudos,
no imputa, no normaliza pesos en ejecución, no crea semaforización y no presenta
el resultado como probabilidad.

Si falta cualquier factor con peso positivo, el índice puntual queda ausente.
Se devuelven únicamente límites diagnósticos: el inferior conserva los aportes
observados y supone cero para lo desconocido; el superior supone uno. Esos
límites no sirven para ordenar puntos y existen para hacer visible cuánto peso
falta, no para rescatar un score incompleto.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_WEIGHTING_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "species_weighting_v1.yaml"
)
EXPECTED_SCHEMA_VERSION = "species_weighting_v1"
EXPECTED_MODEL_ID = "predictamar_litoral_species_prior_v1"
EXPECTED_CONFIG_STATUS = "research_only_not_predictively_validated"
EXPECTED_OUTPUT_NAME = "experimental_habitat_compatibility_index"
WEIGHT_DENOMINATOR_BP = 10_000
PENDING_TRANSFORM_STATUS = "pending_species_calibration"
VALIDATED_TRANSFORM_STATUS = "validated_versioned"
VALIDATED_TRANSFORM_ENTRY_STATUS = "validated_for_research_combination"
REQUIRED_PROVENANCE_FIELDS = (
    "transform_id",
    "transform_version",
    "calibration_id",
    "source_data_version",
)


class SpeciesWeightingConfigError(ValueError):
    """El contrato de ponderación no es internamente consistente."""


class IndexStatus(str, Enum):
    COMPLETE_RESEARCH_INDEX = "complete_research_index"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class FactorContribution:
    factor_id: str
    weight_bp: int
    factor_score: float
    contribution: float
    transform_id: str
    transform_version: str
    calibration_id: str
    source_data_version: str


@dataclass(frozen=True)
class ValidatedFactorScore:
    value: float
    transform_id: str
    transform_version: str
    calibration_id: str
    source_data_version: str


@dataclass(frozen=True)
class IndexResult:
    requested_species_id: str
    canonical_species_id: str
    ui_label: str
    scientific_name: str
    status: IndexStatus
    index_name: str
    index_value: float | None
    is_probability: bool
    operational_enabled: bool
    coverage_weight: float
    lower_bound: float
    upper_bound: float
    missing_factors: tuple[str, ...]
    contributions: tuple[FactorContribution, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        document = asdict(self)
        document["status"] = self.status.value
        return document


def load_weighting_config(
    path: str | Path = DEFAULT_WEIGHTING_PATH,
) -> dict[str, Any]:
    """Carga y valida el contrato YAML antes de devolverlo."""

    with Path(path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    validate_weighting_config(config)
    return config


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpeciesWeightingConfigError(f"{path} debe ser un mapping")
    return value


def _require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpeciesWeightingConfigError(f"{path} debe ser texto no vacío")
    return value


def _require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise SpeciesWeightingConfigError(f"{path} debe ser una lista de textos")
    if len(value) != len(set(value)):
        raise SpeciesWeightingConfigError(f"{path} contiene duplicados")
    return value


def validate_weighting_config(config: Mapping[str, Any]) -> None:
    """Valida en modo cerrado todo el contrato de investigación v1."""

    root = _require_mapping(config, "config")
    if root.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise SpeciesWeightingConfigError(
            f"schema_version debe ser {EXPECTED_SCHEMA_VERSION!r}"
        )
    if root.get("model_id") != EXPECTED_MODEL_ID:
        raise SpeciesWeightingConfigError(f"model_id debe ser {EXPECTED_MODEL_ID!r}")
    if root.get("status") != EXPECTED_CONFIG_STATUS:
        raise SpeciesWeightingConfigError(
            f"status debe permanecer en {EXPECTED_CONFIG_STATUS!r}"
        )

    contract = _require_mapping(root.get("index_contract"), "index_contract")
    if contract.get("output_name") != EXPECTED_OUTPUT_NAME:
        raise SpeciesWeightingConfigError(
            f"index_contract.output_name debe ser {EXPECTED_OUTPUT_NAME!r}"
        )
    if contract.get("probability") is not False:
        raise SpeciesWeightingConfigError("probability debe ser false")
    if contract.get("catch_prediction") is not False:
        raise SpeciesWeightingConfigError("catch_prediction debe ser false")
    if contract.get("operational_ranking_enabled") is not False:
        raise SpeciesWeightingConfigError(
            "operational_ranking_enabled debe ser false"
        )
    if contract.get("traffic_light_thresholds") is not None:
        raise SpeciesWeightingConfigError(
            "no se admiten umbrales de semáforo sin validación"
        )
    value_range = contract.get("value_range")
    if (
        not isinstance(value_range, list)
        or len(value_range) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value_range
        )
        or [float(item) for item in value_range] != [0.0, 1.0]
    ):
        raise SpeciesWeightingConfigError("index_contract.value_range debe ser [0, 1]")

    weights_contract = _require_mapping(
        contract.get("weights"), "index_contract.weights"
    )
    if weights_contract.get("unit") != "basis_points":
        raise SpeciesWeightingConfigError("weights.unit debe ser 'basis_points'")
    if weights_contract.get("required_total_bp") != WEIGHT_DENOMINATOR_BP:
        raise SpeciesWeightingConfigError("required_total_bp debe ser 10000")
    if weights_contract.get("runtime_normalization") != "forbidden":
        raise SpeciesWeightingConfigError(
            "runtime_normalization debe permanecer en forbidden"
        )
    if weights_contract.get("derivation") != "provisional_expert_prior":
        raise SpeciesWeightingConfigError(
            "weights.derivation debe permanecer en 'provisional_expert_prior'"
        )

    factor_score_contract = _require_mapping(
        contract.get("factor_scores"), "index_contract.factor_scores"
    )
    required_range = factor_score_contract.get("required_range")
    if (
        not isinstance(required_range, list)
        or len(required_range) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in required_range
        )
        or [float(item) for item in required_range] != [0.0, 1.0]
    ):
        raise SpeciesWeightingConfigError(
            "factor_scores.required_range debe ser [0, 1]"
        )
    transform_status = factor_score_contract.get("raw_to_score_transform_status")
    if transform_status not in {
        PENDING_TRANSFORM_STATUS,
        VALIDATED_TRANSFORM_STATUS,
    }:
        raise SpeciesWeightingConfigError(
            "raw_to_score_transform_status no es un estado admitido"
        )
    if (
        factor_score_contract.get("complete_index_requires_registry_status")
        != VALIDATED_TRANSFORM_STATUS
    ):
        raise SpeciesWeightingConfigError(
            "complete_index_requires_registry_status debe ser 'validated_versioned'"
        )
    provenance_fields = _require_string_list(
        factor_score_contract.get("required_provenance_fields"),
        "index_contract.factor_scores.required_provenance_fields",
    )
    if provenance_fields != list(REQUIRED_PROVENANCE_FIELDS):
        raise SpeciesWeightingConfigError(
            "required_provenance_fields no coincide con el contrato v1"
        )

    missing_data = _require_mapping(
        contract.get("missing_data"), "index_contract.missing_data"
    )
    for field in (
        "imputation",
        "default_zero",
        "weight_redistribution",
        "point_estimate_when_incomplete",
    ):
        if missing_data.get(field) != "forbidden":
            raise SpeciesWeightingConfigError(
                f"index_contract.missing_data.{field} debe permanecer en forbidden"
            )

    safety = _require_mapping(contract.get("safety"), "index_contract.safety")
    wave = _require_mapping(safety.get("oleaje"), "index_contract.safety.oleaje")
    if type(wave.get("weight_bp")) is not int or wave.get("weight_bp") != 0:
        raise SpeciesWeightingConfigError("oleaje.weight_bp debe ser el entero 0")
    if wave.get("role") != "safety_gate_only":
        raise SpeciesWeightingConfigError("oleaje.role debe ser 'safety_gate_only'")

    registry = _require_mapping(root.get("factor_registry"), "factor_registry")
    models = _require_mapping(root.get("species_models"), "species_models")
    aliases = _require_mapping(root.get("aliases"), "aliases")
    evidence = _require_mapping(root.get("evidence_registry"), "evidence_registry")
    transform_registry = _require_mapping(
        root.get("transform_registry"), "transform_registry"
    )

    if not registry:
        raise SpeciesWeightingConfigError("factor_registry no puede estar vacío")
    if "oleaje" in registry:
        raise SpeciesWeightingConfigError("oleaje no puede ser factor pesquero")
    allowed_availability = {
        "implemented_but_transform_unvalidated",
        "implemented_but_derived_features_missing",
        "missing",
    }
    for factor_id, raw_factor in registry.items():
        factor = _require_mapping(raw_factor, f"factor_registry.{factor_id}")
        _require_non_empty_string(factor.get("label_es"), f"factor_registry.{factor_id}.label_es")
        _require_string_list(
            factor.get("current_assembler_variables"),
            f"factor_registry.{factor_id}.current_assembler_variables",
        )
        if factor.get("availability") not in allowed_availability:
            raise SpeciesWeightingConfigError(
                f"factor_registry.{factor_id}.availability no es admisible"
            )
        _require_non_empty_string(
            factor.get("formula_contract"),
            f"factor_registry.{factor_id}.formula_contract",
        )

    for evidence_id, raw_evidence in evidence.items():
        item = _require_mapping(raw_evidence, f"evidence_registry.{evidence_id}")
        _require_non_empty_string(item.get("type"), f"evidence_registry.{evidence_id}.type")
        _require_non_empty_string(item.get("title"), f"evidence_registry.{evidence_id}.title")
        if not item.get("url") and not item.get("doi"):
            raise SpeciesWeightingConfigError(
                f"evidence_registry.{evidence_id} requiere url o doi"
            )

    for species_id, raw_model in models.items():
        model = _require_mapping(raw_model, f"species_models.{species_id}")
        _require_non_empty_string(model.get("ui_label"), f"species_models.{species_id}.ui_label")
        _require_non_empty_string(
            model.get("scientific_name"), f"species_models.{species_id}.scientific_name"
        )
        _require_non_empty_string(
            model.get("research_status"), f"species_models.{species_id}.research_status"
        )
        _require_non_empty_string(
            model.get("domain_0_10km"), f"species_models.{species_id}.domain_0_10km"
        )
        if model.get("operational_enabled") is not False:
            raise SpeciesWeightingConfigError(
                f"{species_id}: operational_enabled debe ser false"
            )
        weights = _require_mapping(
            model.get("weights_bp"), f"species_models.{species_id}.weights_bp"
        )
        if not weights:
            raise SpeciesWeightingConfigError(f"{species_id}: weights_bp no puede estar vacío")
        total = 0
        for factor_id, weight in weights.items():
            if factor_id not in registry:
                raise SpeciesWeightingConfigError(
                    f"{species_id}: factor desconocido {factor_id!r}"
                )
            if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
                raise SpeciesWeightingConfigError(
                    f"{species_id}.{factor_id}: peso debe ser entero positivo"
                )
            total += weight
        if total != WEIGHT_DENOMINATOR_BP:
            raise SpeciesWeightingConfigError(
                f"{species_id}: pesos suman {total}, deben sumar 10000"
            )
        model_evidence = _require_string_list(
            model.get("evidence"), f"species_models.{species_id}.evidence"
        )
        if not model_evidence:
            raise SpeciesWeightingConfigError(f"{species_id}: evidence no puede estar vacío")
        for evidence_id in model_evidence:
            if evidence_id not in evidence:
                raise SpeciesWeightingConfigError(
                    f"{species_id}: evidencia desconocida {evidence_id!r}"
                )
        for factor_id in _require_string_list(
            model.get("blocking_gaps"), f"species_models.{species_id}.blocking_gaps"
        ):
            if factor_id not in weights:
                raise SpeciesWeightingConfigError(
                    f"{species_id}: blocking_gap desconocido {factor_id!r}"
                )

    for alias_id, raw_alias in aliases.items():
        alias = _require_mapping(raw_alias, f"aliases.{alias_id}")
        target = alias.get("canonical_id")
        if target not in models:
            raise SpeciesWeightingConfigError(
                f"{alias_id}: canonical_id desconocido {target!r}"
            )
        if alias.get("independent_weights") is not False:
            raise SpeciesWeightingConfigError(
                f"{alias_id}: un alias no puede tener pesos independientes"
            )
        if "weights_bp" in alias:
            raise SpeciesWeightingConfigError(
                f"{alias_id}: no debe duplicar la matriz del taxón canónico"
            )
        if alias.get("inheritance") != "exact":
            raise SpeciesWeightingConfigError(
                f"{alias_id}: inheritance debe permanecer en 'exact'"
            )
        _require_non_empty_string(alias.get("ui_label"), f"aliases.{alias_id}.ui_label")
        if alias.get("scientific_name") != models[target].get("scientific_name"):
            raise SpeciesWeightingConfigError(
                f"{alias_id}: scientific_name debe coincidir con {target}"
            )
        for evidence_id in _require_string_list(
            alias.get("evidence"), f"aliases.{alias_id}.evidence"
        ):
            if evidence_id not in evidence:
                raise SpeciesWeightingConfigError(
                    f"{alias_id}: evidencia desconocida {evidence_id!r}"
                )

    ui_order = _require_string_list(root.get("ui_order"), "ui_order")
    if not ui_order:
        raise SpeciesWeightingConfigError("ui_order debe ser una lista no vacía")
    selectable_ids = set(models) | set(aliases)
    if set(ui_order) != selectable_ids:
        raise SpeciesWeightingConfigError(
            "ui_order debe contener exactamente modelos canónicos y aliases"
        )

    registry_status = transform_registry.get("status")
    if registry_status != transform_status:
        raise SpeciesWeightingConfigError(
            "transform_registry.status debe coincidir con raw_to_score_transform_status"
        )
    approved = _require_mapping(
        transform_registry.get("approved_transforms"),
        "transform_registry.approved_transforms",
    )
    if registry_status == PENDING_TRANSFORM_STATUS and approved:
        raise SpeciesWeightingConfigError(
            "no puede haber transformaciones aprobadas mientras el registro esté pendiente"
        )
    if registry_status == VALIDATED_TRANSFORM_STATUS and not approved:
        raise SpeciesWeightingConfigError(
            "un registro validated_versioned no puede estar vacío"
        )
    registered_pairs: set[tuple[str, str]] = set()
    for transform_id, raw_transform in approved.items():
        transform = _require_mapping(
            raw_transform, f"transform_registry.approved_transforms.{transform_id}"
        )
        if transform.get("status") != VALIDATED_TRANSFORM_ENTRY_STATUS:
            raise SpeciesWeightingConfigError(
                f"{transform_id}: status de transformación no validado"
            )
        species_id = transform.get("species_id")
        factor_id = transform.get("factor_id")
        if species_id not in models:
            raise SpeciesWeightingConfigError(
                f"{transform_id}: species_id desconocido {species_id!r}"
            )
        if factor_id not in models[species_id]["weights_bp"]:
            raise SpeciesWeightingConfigError(
                f"{transform_id}: factor_id no pertenece al modelo {species_id}"
            )
        pair = (str(species_id), str(factor_id))
        if pair in registered_pairs:
            raise SpeciesWeightingConfigError(
                f"transformación duplicada para {species_id}.{factor_id}"
            )
        registered_pairs.add(pair)
        for field in ("version", "calibration_id", "source_data_version"):
            _require_non_empty_string(
                transform.get(field),
                f"transform_registry.approved_transforms.{transform_id}.{field}",
            )


def resolve_species_id(
    species: str, config: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    """Devuelve ``(id_solicitado, id_canónico)`` desde id o etiqueta UI."""

    cfg = config if config is not None else load_weighting_config()
    token = str(species).strip().casefold()
    if not token:
        raise KeyError("especie vacía")

    models = cfg["species_models"]
    aliases = cfg["aliases"]
    lookup: dict[str, str] = {}
    for species_id, model in models.items():
        lookup[species_id.casefold()] = species_id
        lookup[str(model["ui_label"]).casefold()] = species_id
    for alias_id, alias in aliases.items():
        lookup[alias_id.casefold()] = alias_id
        lookup[str(alias["ui_label"]).casefold()] = alias_id

    try:
        requested_id = lookup[token]
    except KeyError as exc:
        raise KeyError(f"especie no configurada: {species!r}") from exc
    canonical_id = aliases.get(requested_id, {}).get("canonical_id", requested_id)
    return requested_id, canonical_id


def _validate_factor_scores(
    factor_scores: Mapping[str, Mapping[str, Any] | None],
    factor_registry: Mapping[str, Any],
    transform_registry: Mapping[str, Any],
    canonical_species_id: str,
    weights: Mapping[str, int],
) -> dict[str, ValidatedFactorScore | None]:
    if not isinstance(factor_scores, Mapping):
        raise TypeError("factor_scores debe ser un mapping")
    unknown = sorted(set(factor_scores) - set(factor_registry))
    if unknown:
        raise ValueError(f"factores desconocidos: {', '.join(unknown)}")
    unrelated = sorted(set(factor_scores) - set(weights))
    if unrelated:
        raise ValueError(
            "factores ajenos al modelo de la especie: " + ", ".join(unrelated)
        )

    registry_status = transform_registry["status"]
    approved = transform_registry["approved_transforms"]
    validated: dict[str, ValidatedFactorScore | None] = {}
    for factor_id, raw_score in factor_scores.items():
        if raw_score is None:
            validated[factor_id] = None
            continue
        if not isinstance(raw_score, Mapping):
            raise TypeError(
                f"{factor_id}: factor_score debe ser un mapping trazable o null"
            )
        missing_provenance = [
            field
            for field in ("value", *REQUIRED_PROVENANCE_FIELDS)
            if field not in raw_score
        ]
        if missing_provenance:
            raise ValueError(
                f"{factor_id}: faltan campos trazables: "
                + ", ".join(missing_provenance)
            )
        raw_value = raw_score["value"]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError(f"{factor_id}: value debe ser numérico")
        value = float(raw_value)
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{factor_id}: factor_score debe estar entre 0 y 1")
        provenance: dict[str, str] = {}
        for field in REQUIRED_PROVENANCE_FIELDS:
            raw_field = raw_score[field]
            if not isinstance(raw_field, str) or not raw_field.strip():
                raise ValueError(f"{factor_id}.{field} debe ser texto no vacío")
            provenance[field] = raw_field
        if registry_status != VALIDATED_TRANSFORM_STATUS:
            raise SpeciesWeightingConfigError(
                "las transformaciones crudo-a-score siguen pendientes; "
                "no se admiten factor_scores"
            )
        transform_id = provenance["transform_id"]
        transform = approved.get(transform_id)
        if not isinstance(transform, Mapping):
            raise ValueError(
                f"{factor_id}: transform_id {transform_id!r} no está aprobado"
            )
        expected = {
            "species_id": canonical_species_id,
            "factor_id": factor_id,
            "status": VALIDATED_TRANSFORM_ENTRY_STATUS,
            "version": provenance["transform_version"],
            "calibration_id": provenance["calibration_id"],
            "source_data_version": provenance["source_data_version"],
        }
        mismatches = [
            field for field, expected_value in expected.items()
            if transform.get(field) != expected_value
        ]
        if mismatches:
            raise ValueError(
                f"{factor_id}: procedencia no coincide con el registro aprobado: "
                + ", ".join(mismatches)
            )
        validated[factor_id] = ValidatedFactorScore(
            value=value,
            transform_id=transform_id,
            transform_version=provenance["transform_version"],
            calibration_id=provenance["calibration_id"],
            source_data_version=provenance["source_data_version"],
        )
    return validated


def combine_factor_scores(
    species: str,
    factor_scores: Mapping[str, Mapping[str, Any] | None],
    *,
    config: Mapping[str, Any] | None = None,
    purpose: str = "research",
) -> IndexResult:
    """Combina scores completos bajo el contrato de investigación.

    ``purpose`` se mantiene explícito para impedir que un consumidor cambie
    accidentalmente el significado. Cualquier valor distinto de ``research``
    se rechaza mientras la configuración no esté validada predictivamente. Un
    score no nulo debe ser un mapping con ``value`` y los cuatro campos de
    procedencia fijados por ``REQUIRED_PROVENANCE_FIELDS``.
    """

    cfg = config if config is not None else load_weighting_config()
    validate_weighting_config(cfg)
    if purpose != "research":
        raise ValueError(
            "la matriz v1 solo admite purpose='research'; uso operativo bloqueado"
        )

    requested_id, canonical_id = resolve_species_id(species, cfg)
    model = cfg["species_models"][canonical_id]
    weights: Mapping[str, int] = model["weights_bp"]
    scores = _validate_factor_scores(
        factor_scores,
        cfg["factor_registry"],
        cfg["transform_registry"],
        canonical_id,
        weights,
    )

    missing = tuple(
        factor_id
        for factor_id in weights
        if factor_id not in scores or scores[factor_id] is None
    )
    contributions = tuple(
        FactorContribution(
            factor_id=factor_id,
            weight_bp=weight_bp,
            factor_score=scores[factor_id].value,
            contribution=(weight_bp / WEIGHT_DENOMINATOR_BP)
            * scores[factor_id].value,
            transform_id=scores[factor_id].transform_id,
            transform_version=scores[factor_id].transform_version,
            calibration_id=scores[factor_id].calibration_id,
            source_data_version=scores[factor_id].source_data_version,
        )
        for factor_id, weight_bp in weights.items()
        if factor_id in scores and scores[factor_id] is not None
    )

    observed_weight_bp = sum(item.weight_bp for item in contributions)
    coverage_weight = observed_weight_bp / WEIGHT_DENOMINATOR_BP
    lower_bound = sum(item.contribution for item in contributions)
    missing_weight = 1.0 - coverage_weight
    upper_bound = lower_bound + missing_weight
    status = (
        IndexStatus.INSUFFICIENT_DATA
        if missing
        else IndexStatus.COMPLETE_RESEARCH_INDEX
    )
    index_value = None if missing else lower_bound

    warnings = [
        "Índice de investigación; no es probabilidad de captura.",
        "Pesos provisionales no calibrados con capturas/CPUE independientes.",
        "No usar para navegación, autorización de faena ni ranking operativo.",
    ]
    if requested_id != canonical_id:
        warnings.append(
            f"{requested_id.upper()} hereda exactamente el modelo de "
            f"{canonical_id.upper()}; no es un taxón independiente."
        )
    if missing:
        warnings.append(
            "Índice puntual omitido: no se imputan faltantes ni se redistribuyen pesos."
        )

    return IndexResult(
        requested_species_id=requested_id,
        canonical_species_id=canonical_id,
        ui_label=(
            cfg["aliases"][requested_id]["ui_label"]
            if requested_id in cfg["aliases"]
            else model["ui_label"]
        ),
        scientific_name=model["scientific_name"],
        status=status,
        index_name=cfg["index_contract"]["output_name"],
        index_value=index_value,
        is_probability=False,
        operational_enabled=False,
        coverage_weight=coverage_weight,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        missing_factors=missing,
        contributions=contributions,
        warnings=tuple(warnings),
    )
