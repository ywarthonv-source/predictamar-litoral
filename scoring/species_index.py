"""Combinador estricto para la matriz objetivo por especie.

El módulo hace una sola operación matemática: combina ``factor_score`` ya
calculados y trazables mediante los pesos fijos del YAML. No transforma datos
oceanográficos crudos, no imputa, no normaliza pesos en ejecución, no crea
semaforización y no presenta el resultado como probabilidad.

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
WEIGHT_DENOMINATOR_BP = 10_000


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


def validate_weighting_config(config: Mapping[str, Any]) -> None:
    """Impide pesos ocultos, alias independientes y señales desconocidas."""

    root = _require_mapping(config, "config")
    if root.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise SpeciesWeightingConfigError(
            f"schema_version debe ser {EXPECTED_SCHEMA_VERSION!r}"
        )

    contract = _require_mapping(root.get("index_contract"), "index_contract")
    weights_contract = _require_mapping(
        contract.get("weights"), "index_contract.weights"
    )
    if weights_contract.get("required_total_bp") != WEIGHT_DENOMINATOR_BP:
        raise SpeciesWeightingConfigError("required_total_bp debe ser 10000")
    if weights_contract.get("runtime_normalization") != "forbidden":
        raise SpeciesWeightingConfigError(
            "runtime_normalization debe permanecer en forbidden"
        )
    if contract.get("probability") is not False:
        raise SpeciesWeightingConfigError("probability debe ser false")
    if contract.get("operational_ranking_enabled") is not False:
        raise SpeciesWeightingConfigError(
            "operational_ranking_enabled debe ser false"
        )
    if contract.get("traffic_light_thresholds") is not None:
        raise SpeciesWeightingConfigError(
            "no se admiten umbrales de semáforo sin validación"
        )

    registry = _require_mapping(root.get("factor_registry"), "factor_registry")
    models = _require_mapping(root.get("species_models"), "species_models")
    aliases = _require_mapping(root.get("aliases"), "aliases")
    evidence = _require_mapping(root.get("evidence_registry"), "evidence_registry")

    if "oleaje" in registry:
        raise SpeciesWeightingConfigError("oleaje no puede ser factor pesquero")

    for species_id, raw_model in models.items():
        model = _require_mapping(raw_model, f"species_models.{species_id}")
        if model.get("operational_enabled") is not False:
            raise SpeciesWeightingConfigError(
                f"{species_id}: operational_enabled debe ser false"
            )
        weights = _require_mapping(
            model.get("weights_bp"), f"species_models.{species_id}.weights_bp"
        )
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
        for evidence_id in model.get("evidence", ()):
            if evidence_id not in evidence:
                raise SpeciesWeightingConfigError(
                    f"{species_id}: evidencia desconocida {evidence_id!r}"
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

    ui_order = root.get("ui_order")
    if not isinstance(ui_order, list) or not ui_order:
        raise SpeciesWeightingConfigError("ui_order debe ser una lista no vacía")
    if len(ui_order) != len(set(ui_order)):
        raise SpeciesWeightingConfigError("ui_order contiene duplicados")
    selectable_ids = set(models) | set(aliases)
    if set(ui_order) != selectable_ids:
        raise SpeciesWeightingConfigError(
            "ui_order debe contener exactamente modelos canónicos y aliases"
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
    factor_scores: Mapping[str, float | int | None], registry: Mapping[str, Any]
) -> dict[str, float | None]:
    if not isinstance(factor_scores, Mapping):
        raise TypeError("factor_scores debe ser un mapping")
    unknown = sorted(set(factor_scores) - set(registry))
    if unknown:
        raise ValueError(f"factores desconocidos: {', '.join(unknown)}")

    validated: dict[str, float | None] = {}
    for factor_id, raw_value in factor_scores.items():
        if raw_value is None:
            validated[factor_id] = None
            continue
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError(f"{factor_id}: factor_score debe ser numérico o null")
        value = float(raw_value)
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{factor_id}: factor_score debe estar entre 0 y 1")
        validated[factor_id] = value
    return validated


def combine_factor_scores(
    species: str,
    factor_scores: Mapping[str, float | int | None],
    *,
    config: Mapping[str, Any] | None = None,
    purpose: str = "research",
) -> IndexResult:
    """Combina scores completos bajo el contrato de investigación.

    ``purpose`` se mantiene explícito para impedir que un consumidor cambie
    accidentalmente el significado. Cualquier valor distinto de ``research``
    se rechaza mientras la configuración no esté validada predictivamente.
    """

    cfg = config if config is not None else load_weighting_config()
    validate_weighting_config(cfg)
    if purpose != "research":
        raise ValueError(
            "la matriz v1 solo admite purpose='research'; uso operativo bloqueado"
        )

    requested_id, canonical_id = resolve_species_id(species, cfg)
    model = cfg["species_models"][canonical_id]
    scores = _validate_factor_scores(factor_scores, cfg["factor_registry"])
    weights: Mapping[str, int] = model["weights_bp"]

    missing = tuple(
        factor_id
        for factor_id in weights
        if factor_id not in scores or scores[factor_id] is None
    )
    contributions = tuple(
        FactorContribution(
            factor_id=factor_id,
            weight_bp=weight_bp,
            factor_score=float(scores[factor_id]),
            contribution=(weight_bp / WEIGHT_DENOMINATOR_BP)
            * float(scores[factor_id]),
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
