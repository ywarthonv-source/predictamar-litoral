"""Ensamblador ambiental v1, sin scoring ni interpretación pesquera.

El ensamblador coordina los ocho trabajos necesarios para exponer las diez
variables implementadas. Conserva las salidas completas de cada módulo y no
promedia, interpola, clasifica ni reduce sus valores. Dos dependencias se
comparten de forma explícita:

* un único campo OSTIA alimenta ``sst_observed_ostia`` y ``thermal_front``;
* un único par térmico alimenta ``temperature_10m`` y ``delta_sst_t10``.

Opcionalmente, ``ChlorophyllOptions`` añade el campo OLCI y el gradiente
centrado derivado del mismo objeto. ``MurOptions`` añade independientemente
SST MUR y su gradiente, desde recortes NetCDF configurados. Sin ninguna opción,
el contrato base de diez variables y su JSON permanecen sin cambios; sin
``MurOptions`` no se leen archivos MUR ni cambia el contrato base/OLCI.

Los fallos de una fuente no impiden recuperar las demás. Un error de uso en la
solicitud se rechaza antes de invocar proveedores; un fallo posterior queda
trazado como ``error`` en las variables afectadas. La compuerta de oleaje se
informa por separado y nunca se convierte en autorización de navegación.

La salida base distingue siete variables puntuales, el máximo regional
conservador de oleaje y los dos campos regionales OSTIA. El recuadro de
+/-0.15 grados sirve para construir SST y gradiente térmico; no es el dominio
operativo. Los 0-10 km operativos describen distancia mar adentro desde el
litoral y no un radio alrededor del punto pedido.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite
from numbers import Real
from pathlib import Path
from typing import Callable

import yaml

from derivation.chlorophyll_gradient import derive_chlorophyll_gradient
from derivation.mur_gradient import derive_mur_gradient
from derivation.thermal_front import derive_thermal_front
from ingestion.fetch_bathymetry import fetch_bathymetry
from ingestion.fetch_chlorophyll import fetch_chlorophyll
from ingestion.fetch_chlorophyll_field import (
    ChlorophyllOptions,
    fetch_chlorophyll_field,
)
from ingestion.fetch_currents import fetch_currents
from ingestion.fetch_mur import MurOptions, fetch_mur_field
from ingestion.fetch_ostia import fetch_ostia_field
from ingestion.fetch_salinity import fetch_salinity
from ingestion.fetch_temperature import fetch_sst
from ingestion.fetch_vertical_temperature import fetch_vertical_thermal_pair
from ingestion.fetch_waves import NOT_AN_AUTHORIZATION_NOTICE, get_wave_status
from ingestion.optical_sources import OpticalMode

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "environmental_snapshot_v1"
OLCI_SCHEMA_VERSION = "environmental_snapshot_v1_olci_v1"
MUR_SCHEMA_VERSION = "environmental_snapshot_v1_mur_v1"
OLCI_MUR_SCHEMA_VERSION = "environmental_snapshot_v1_olci_v1_mur_v1"
DEFAULT_FIELD_HALF_WIDTH_DEG = 0.15
DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[1] / "config" / "variables_spec.yaml"
DEFAULT_AREA_PATH = Path(__file__).resolve().parents[1] / "config" / "area.yaml"

OPERATIONAL_RANGE_MIN_KM = 0.0
OPERATIONAL_RANGE_MAX_KM = 10.0
OPERATIONAL_RANGE_BASIS = "distance_offshore_from_coastline"
REGIONAL_FIELD_PURPOSE = "regional_context_for_ostia_and_thermal_front"
OLCI_REGIONAL_FIELD_PURPOSE = (
    "regional_context_for_ostia_thermal_front_and_chlorophyll_olci"
)
REGIONAL_FIELD_RELATION = "regional_context_not_operational_domain"

VARIABLE_ORDER = (
    "sst",
    "oleaje",
    "clorofila",
    "salinidad",
    "sst_observed_ostia",
    "thermal_front",
    "temperature_10m",
    "delta_sst_t10",
    "surface_currents",
    "batimetria",
)

OPTIONAL_VARIABLE_ORDER = ("chlorophyll_olci", "chlorophyll_front")
MUR_VARIABLE_ORDER = ("sst_mur", "thermal_gradient_mur")

VALUE_PATHS = {
    "sst": ("samples[].value_celsius",),
    "oleaje": ("significant_wave_height_m",),
    "clorofila": ("value_mg_m3",),
    "salinidad": ("samples[].value_salinity",),
    "sst_observed_ostia": ("sst_celsius[][]", "analysis_error_kelvin[][]"),
    "thermal_front": (
        "gradient_c_per_km[][]",
        "eastward_gradient_c_per_km[][]",
        "northward_gradient_c_per_km[][]",
    ),
    "temperature_10m": ("samples[].temperature_10m_celsius",),
    "delta_sst_t10": ("samples[].delta_sst_t10_celsius",),
    "surface_currents": (
        "measurements[].uo_m_s",
        "measurements[].vo_m_s",
        "measurements[].speed_m_s",
        "measurements[].direction_toward_deg",
    ),
    "batimetria": ("depth_m", "slope_deg", "tid_code"),
    "chlorophyll_olci": (
        "grid.chlorophyll_mg_m3[][]",
        "grid.uncertainty_pct[][]",
    ),
    "chlorophyll_front": (
        "gradient_mg_m3_per_km[][]",
        "eastward_gradient_mg_m3_per_km[][]",
        "northward_gradient_mg_m3_per_km[][]",
    ),
    "sst_mur": ("grid.sst_celsius[][]", "grid.analysis_error_kelvin[][]", "grid.dt_1km_hours[][]"),
    "thermal_gradient_mur": (
        "gradient_c_per_km[][]",
        "eastward_gradient_c_per_km[][]",
        "northward_gradient_c_per_km[][]",
    ),
}

SHARED_OPERATION = {
    "sst": "sst_model",
    "oleaje": "waves",
    "clorofila": "chlorophyll",
    "salinidad": "salinity",
    "sst_observed_ostia": "ostia_field",
    "thermal_front": "ostia_field",
    "temperature_10m": "vertical_thermal_pair",
    "delta_sst_t10": "vertical_thermal_pair",
    "surface_currents": "surface_currents",
    "batimetria": "bathymetry",
    "chlorophyll_olci": "chlorophyll_olci_field",
    "chlorophyll_front": "chlorophyll_olci_field",
    "sst_mur": "mur_field",
    "thermal_gradient_mur": "mur_field",
}

AVAILABLE_SOURCE_STATUSES = {
    "sst": {"valida_en_ventana", "valida_cercana_en_tiempo"},
    "oleaje": {"bajo_umbral_regional", "sobre_umbral_regional"},
    "clorofila": {"valida_en_fecha_local", "valida_reciente"},
    "salinidad": {"valida_en_ventana", "valida_cercana_en_tiempo"},
    "sst_observed_ostia": {"valida_en_fecha_nominal", "valida_reciente"},
    "thermal_front": {"valido"},
    "temperature_10m": {"valida_en_ventana", "valida_cercana_en_tiempo"},
    "delta_sst_t10": {"valida_en_ventana", "valida_cercana_en_tiempo"},
    "surface_currents": {"valida_en_ventana", "cobertura_parcial"},
    "batimetria": {"valida"},
    "chlorophyll_olci": {"valida_en_fecha_nominal", "valida_reciente"},
    "chlorophyll_front": {"valido"},
    "sst_mur": {"valida_en_fecha_nominal", "valida_reciente", "historica_final"},
    "thermal_gradient_mur": {"valido"},
}

NO_DATA_SOURCE_STATUSES = {
    "sst": {"sin_datos"},
    "oleaje": {"sin_datos"},
    "clorofila": {"sin_datos"},
    "salinidad": {"sin_datos"},
    "sst_observed_ostia": {"sin_datos"},
    "thermal_front": {"sin_gradientes", "fuente_sin_datos"},
    "temperature_10m": {"sin_datos"},
    "delta_sst_t10": {"sin_datos"},
    "surface_currents": {"sin_datos"},
    "batimetria": {"sin_datos"},
    "chlorophyll_olci": {"sin_datos"},
    "chlorophyll_front": {"sin_gradientes", "fuente_sin_datos"},
    "sst_mur": {"sin_datos"},
    "thermal_gradient_mur": {"sin_gradientes", "fuente_sin_datos"},
}

ERROR_SOURCE_STATUSES = {
    "clorofila": {"error"},
    "chlorophyll_olci": {"error"},
    "chlorophyll_front": {"fuente_error"},
    "sst_mur": {"error"},
    "thermal_gradient_mur": {"fuente_error"},
}


class AssemblyState(str, Enum):
    AVAILABLE = "available"
    NO_DATA = "no_data"
    ERROR = "error"


class OverallAssemblyStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    FAILED = "failed"


class SpatialScope(str, Enum):
    POINT = "point"
    REGIONAL_MAXIMUM = "regional_maximum"
    REGIONAL_FIELD = "regional_field"


REGIONAL_FIELD_VARIABLES = frozenset(
    {"sst_observed_ostia", "thermal_front", *OPTIONAL_VARIABLE_ORDER, *MUR_VARIABLE_ORDER}
)
SPATIAL_SCOPE_BY_VARIABLE = {
    variable_id: (
        SpatialScope.REGIONAL_FIELD
        if variable_id in REGIONAL_FIELD_VARIABLES
        else SpatialScope.REGIONAL_MAXIMUM
        if variable_id == "oleaje"
        else SpatialScope.POINT
    )
    for variable_id in (*VARIABLE_ORDER, *OPTIONAL_VARIABLE_ORDER, *MUR_VARIABLE_ORDER)
}


@dataclass(frozen=True)
class FieldBounds:
    minimum_latitude: float
    maximum_latitude: float
    minimum_longitude: float
    maximum_longitude: float


@dataclass(frozen=True)
class SpatialContext:
    operational_range_min_km: float
    operational_range_max_km: float
    operational_range_basis: str
    operational_range_is_radius_from_request_point: bool
    operational_bounding_box_defined: bool
    field_half_width_deg: float
    field_is_operational_domain: bool
    field_scope_relation: str
    field_purpose: str


@dataclass(frozen=True)
class AssemblyRequest:
    lat: float
    lon: float
    target_date: date
    hour_start_local: int = 0
    hour_end_local: int = 23
    field_half_width_deg: float = DEFAULT_FIELD_HALF_WIDTH_DEG

    def __post_init__(self) -> None:
        for name, value, lower, upper in (
            ("lat", self.lat, -90.0, 90.0),
            ("lon", self.lon, -180.0, 180.0),
        ):
            if (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not isfinite(float(value))
                or not lower <= float(value) <= upper
            ):
                raise ValueError(f"{name} debe ser un número finito entre {lower:g} y {upper:g}.")
        if not isinstance(self.target_date, date) or isinstance(self.target_date, datetime):
            raise ValueError("target_date debe ser datetime.date, no datetime ni texto.")
        for name, value in (
            ("hour_start_local", self.hour_start_local),
            ("hour_end_local", self.hour_end_local),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 23:
                raise ValueError(f"{name} debe ser un entero entre 0 y 23.")
        if self.hour_start_local > self.hour_end_local:
            raise ValueError("hour_start_local no puede ser mayor que hour_end_local.")
        if (
            not isinstance(self.field_half_width_deg, Real)
            or isinstance(self.field_half_width_deg, bool)
            or not isfinite(float(self.field_half_width_deg))
            or not 0.0 < float(self.field_half_width_deg) <= 1.0
        ):
            raise ValueError("field_half_width_deg debe ser finito, mayor que 0 y menor o igual que 1.")
        bounds = self.field_bounds
        if not (-90.0 <= bounds.minimum_latitude < bounds.maximum_latitude <= 90.0):
            raise ValueError("El campo regional solicitado excede los límites de latitud.")
        if not (-180.0 <= bounds.minimum_longitude < bounds.maximum_longitude <= 180.0):
            raise ValueError("El campo regional solicitado excede los límites de longitud.")

    @property
    def field_bounds(self) -> FieldBounds:
        half_width = float(self.field_half_width_deg)
        return FieldBounds(
            minimum_latitude=float(self.lat) - half_width,
            maximum_latitude=float(self.lat) + half_width,
            minimum_longitude=float(self.lon) - half_width,
            maximum_longitude=float(self.lon) + half_width,
        )


@dataclass(frozen=True)
class VariableGovernance:
    description: str
    intended_role: str
    implementation_status: str
    scoring_status: str
    predictively_valid: bool | str | None
    profile: str
    module: str


@dataclass(frozen=True)
class VariableResult:
    variable_id: str
    state: AssemblyState
    source_status: str | None
    source_type: str | None
    shared_operation: str
    spatial_scope: SpatialScope
    value_paths: tuple[str, ...]
    governance: VariableGovernance
    payload: dict[str, object] | None
    error_code: str | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class SafetySummary:
    blocked: bool
    source_variable: str
    source_status: str | None
    reason: str
    not_authorization_notice: str = NOT_AN_AUTHORIZATION_NOTICE


@dataclass(frozen=True)
class EnvironmentalSnapshot:
    schema_version: str
    request: AssemblyRequest
    spatial_context: SpatialContext
    status: OverallAssemblyStatus
    variables: tuple[VariableResult, ...]
    available_count: int
    no_data_count: int
    error_count: int
    safety: SafetySummary
    chlorophyll_options: ChlorophyllOptions | None = None
    mur_options: MurOptions | None = None

    def get(self, variable_id: str) -> VariableResult:
        for result in self.variables:
            if result.variable_id == variable_id:
                return result
        raise KeyError(variable_id)

    def to_dict(self) -> dict[str, object]:
        request_document = _to_primitive(self.request)
        request_document["field_bounds"] = _to_primitive(self.request.field_bounds)
        document = {
            "schema_version": self.schema_version,
            "request": request_document,
            "spatial_context": _to_primitive(self.spatial_context),
            "status": self.status.value,
            "counts": {
                "available": self.available_count,
                "no_data": self.no_data_count,
                "error": self.error_count,
                "total": len(self.variables),
            },
            "safety": _to_primitive(self.safety),
            "variables": {
                result.variable_id: _to_primitive(result) for result in self.variables
            },
        }
        optional_layers = {}
        if self.chlorophyll_options is not None:
            optional_layers["chlorophyll_olci"] = _to_primitive(self.chlorophyll_options)
        if self.mur_options is not None:
            optional_layers["sst_mur"] = _to_primitive(self.mur_options)
        if optional_layers:
            document["optional_layers"] = optional_layers
        return document

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
        )


@dataclass(frozen=True)
class AssemblerProviders:
    fetch_sst: Callable[..., object] = fetch_sst
    get_wave_status: Callable[..., object] = get_wave_status
    fetch_chlorophyll: Callable[..., object] = fetch_chlorophyll
    fetch_salinity: Callable[..., object] = fetch_salinity
    fetch_ostia_field: Callable[..., object] = fetch_ostia_field
    derive_thermal_front: Callable[[object], object] = derive_thermal_front
    fetch_vertical_thermal_pair: Callable[..., object] = fetch_vertical_thermal_pair
    fetch_currents: Callable[..., object] = fetch_currents
    fetch_bathymetry: Callable[..., object] = fetch_bathymetry
    fetch_chlorophyll_field: Callable[..., object] = fetch_chlorophyll_field
    derive_chlorophyll_gradient: Callable[[object], object] = derive_chlorophyll_gradient
    fetch_mur_field: Callable[..., object] = fetch_mur_field
    derive_mur_gradient: Callable[[object], object] = derive_mur_gradient


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader que rechaza claves duplicadas en el contrato YAML."""


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


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_governance(
    spec_path: Path,
    variable_order: tuple[str, ...] = VARIABLE_ORDER,
) -> dict[str, VariableGovernance]:
    try:
        document = yaml.load(spec_path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except OSError as exc:
        raise ValueError(f"No se pudo leer el contrato de variables: {spec_path}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("variables"), dict):
        raise ValueError("variables_spec.yaml debe contener un mapping 'variables'.")

    governance = {}
    required = (
        "descripcion",
        "intended_role",
        "implementation_status",
        "scoring_status",
        "predictively_valid",
        "profile",
        "modulo",
    )
    for variable_id in variable_order:
        config = document["variables"].get(variable_id)
        if not isinstance(config, dict):
            raise ValueError(f"Falta la variable ensamblada {variable_id!r} en variables_spec.yaml.")
        missing = [name for name in required if name not in config]
        if missing:
            raise ValueError(f"{variable_id!r} no declara campos de gobernanza: {missing}.")
        implementation_status = str(config["implementation_status"])
        if not implementation_status.startswith("implementada_"):
            raise ValueError(
                f"{variable_id!r} está registrada en el ensamblador pero no implementada: "
                f"{implementation_status!r}."
            )
        governance[variable_id] = VariableGovernance(
            description=str(config["descripcion"]),
            intended_role=str(config["intended_role"]),
            implementation_status=implementation_status,
            scoring_status=str(config["scoring_status"]),
            predictively_valid=config["predictively_valid"],
            profile=str(config["profile"]),
            module=str(config["modulo"]),
        )
    return governance


def _to_primitive(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return _to_primitive(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_primitive(item) for item in value]
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError("La salida de un proveedor contiene un número no finito.")
        return int(value) if isinstance(value, int) else numeric
    if value is None or isinstance(value, (str, bool)):
        return value
    raise TypeError(f"Tipo no serializable en salida del proveedor: {type(value).__name__}")


def _source_status(reading: object) -> str:
    if not is_dataclass(reading) or isinstance(reading, type):
        raise TypeError("El proveedor debe devolver una instancia dataclass trazable.")
    status = getattr(reading, "status", None)
    if isinstance(status, Enum):
        status = status.value
    if not isinstance(status, str) or not status:
        raise TypeError("La salida del proveedor debe declarar un status serializable.")
    return status


def _validate_value_paths(payload: dict[str, object], variable_id: str) -> None:
    for path in VALUE_PATHS[variable_id]:
        root = path.split(".", 1)[0].split("[", 1)[0]
        if root not in payload:
            raise TypeError(
                f"La salida de {variable_id!r} no contiene la raíz declarada {root!r}."
            )


def _variable_result(
    variable_id: str,
    reading: object,
    governance: VariableGovernance,
) -> VariableResult:
    try:
        source_status = _source_status(reading)
        payload = _to_primitive(reading)
        if not isinstance(payload, dict):
            raise TypeError("La salida serializada del proveedor debe ser un mapping.")
        _validate_value_paths(payload, variable_id)
        if source_status in AVAILABLE_SOURCE_STATUSES[variable_id]:
            state = AssemblyState.AVAILABLE
            error_code = None
        elif source_status in NO_DATA_SOURCE_STATUSES[variable_id]:
            state = AssemblyState.NO_DATA
            error_code = None
        elif source_status in ERROR_SOURCE_STATUSES.get(variable_id, set()):
            state = AssemblyState.ERROR
            error_code = "source_error"
        else:
            state = AssemblyState.ERROR
            error_code = "unknown_source_status"
        return VariableResult(
            variable_id=variable_id,
            state=state,
            source_status=source_status,
            source_type=type(reading).__name__,
            shared_operation=SHARED_OPERATION[variable_id],
            spatial_scope=SPATIAL_SCOPE_BY_VARIABLE[variable_id],
            value_paths=VALUE_PATHS[variable_id],
            governance=governance,
            payload=payload,
            error_code=error_code,
            error_type=None,
        )
    except Exception as exc:
        logger.exception("Contrato de salida inválido para la variable %s", variable_id)
        return _error_result(variable_id, governance, "invalid_provider_result", exc)


def _error_result(
    variable_id: str,
    governance: VariableGovernance,
    error_code: str,
    exc: Exception,
) -> VariableResult:
    return VariableResult(
        variable_id=variable_id,
        state=AssemblyState.ERROR,
        source_status=None,
        source_type=None,
        shared_operation=SHARED_OPERATION[variable_id],
        spatial_scope=SPATIAL_SCOPE_BY_VARIABLE[variable_id],
        value_paths=VALUE_PATHS[variable_id],
        governance=governance,
        payload=None,
        error_code=error_code,
        error_type=type(exc).__name__,
    )


def _call_provider(
    operation: str,
    variable_ids: tuple[str, ...],
    call: Callable[[], object],
    governance: dict[str, VariableGovernance],
    *,
    redact_exception: bool = False,
) -> tuple[object | None, list[VariableResult]]:
    try:
        return call(), []
    except Exception as exc:
        if redact_exception:
            logger.error("Fallo aislado en la operación ambiental %s (%s)", operation, type(exc).__name__)
        else:
            logger.exception("Fallo aislado en la operación ambiental %s", operation)
        return None, [
            _error_result(variable_id, governance[variable_id], "provider_exception", exc)
            for variable_id in variable_ids
        ]


def _overall_status(results: tuple[VariableResult, ...]) -> OverallAssemblyStatus:
    available = sum(result.state is AssemblyState.AVAILABLE for result in results)
    errors = sum(result.state is AssemblyState.ERROR for result in results)
    if available == len(results):
        return OverallAssemblyStatus.COMPLETE
    if errors == len(results):
        return OverallAssemblyStatus.FAILED
    if available == 0 and errors == 0:
        return OverallAssemblyStatus.NO_DATA
    return OverallAssemblyStatus.PARTIAL


def _spatial_context(
    request: AssemblyRequest,
    chlorophyll_enabled: bool = False,
    mur_enabled: bool = False,
) -> SpatialContext:
    """Declara la relación semántica entre el recuadro y el alcance operativo."""
    purpose = OLCI_REGIONAL_FIELD_PURPOSE if chlorophyll_enabled else REGIONAL_FIELD_PURPOSE
    if mur_enabled:
        purpose += "_and_mur_sst_gradient"
    return SpatialContext(
        operational_range_min_km=OPERATIONAL_RANGE_MIN_KM,
        operational_range_max_km=OPERATIONAL_RANGE_MAX_KM,
        operational_range_basis=OPERATIONAL_RANGE_BASIS,
        operational_range_is_radius_from_request_point=False,
        operational_bounding_box_defined=False,
        field_half_width_deg=float(request.field_half_width_deg),
        field_is_operational_domain=False,
        field_scope_relation=REGIONAL_FIELD_RELATION,
        field_purpose=purpose,
    )


def _safety_summary(wave: VariableResult) -> SafetySummary:
    if wave.state is AssemblyState.ERROR:
        return SafetySummary(
            blocked=True,
            source_variable="oleaje",
            source_status=None,
            reason="provider_error",
        )
    if wave.source_status == "bajo_umbral_regional":
        return SafetySummary(
            blocked=False,
            source_variable="oleaje",
            source_status=wave.source_status,
            reason="below_provisional_regional_threshold",
        )
    if wave.source_status == "sobre_umbral_regional":
        return SafetySummary(
            blocked=True,
            source_variable="oleaje",
            source_status=wave.source_status,
            reason="at_or_above_provisional_regional_threshold",
        )
    return SafetySummary(
        blocked=True,
        source_variable="oleaje",
        source_status=wave.source_status,
        reason="no_wave_data",
    )


def assemble_environmental_snapshot(
    request: AssemblyRequest,
    *,
    providers: AssemblerProviders | None = None,
    spec_path: Path | str = DEFAULT_SPEC_PATH,
    chlorophyll_options: ChlorophyllOptions | None = None,
    mur_options: MurOptions | None = None,
    chlorophyll_mode: OpticalMode = OpticalMode.NRT_OPERATIONAL,
) -> EnvironmentalSnapshot:
    """Construye una instantánea ambiental trazable para punto, fecha y ventana.

    ``request`` se valida al construir ``AssemblyRequest``. No se calcula
    ningún promedio diario, favorabilidad, peso, score o ranking. La caja
    regional soporta OSTIA y, si se activan, OLCI, MUR y sus gradientes; la caja
    viaja explícita en la salida.
    Por defecto usa +/-0.15 grados y puede abarcar una extensión mayor que los
    0-10 km operativos. Esos 0-10 km se miden mar adentro desde el litoral, no
    como radio desde ``request.lat``/``request.lon``; ``spatial_context`` evita
    presentar el campo regional como si fuera el dominio de faena.
    """
    if not isinstance(request, AssemblyRequest):
        raise TypeError("request debe ser una instancia de AssemblyRequest.")
    providers = AssemblerProviders() if providers is None else providers
    if not isinstance(providers, AssemblerProviders):
        raise TypeError("providers debe ser una instancia de AssemblerProviders.")
    if chlorophyll_options is not None and not isinstance(
        chlorophyll_options, ChlorophyllOptions
    ):
        raise TypeError("chlorophyll_options debe ser ChlorophyllOptions o None.")
    if mur_options is not None and not isinstance(mur_options, MurOptions):
        raise TypeError("mur_options debe ser MurOptions o None.")
    if not isinstance(chlorophyll_mode, OpticalMode):
        raise TypeError("chlorophyll_mode debe ser OpticalMode.")
    result_order = VARIABLE_ORDER
    if chlorophyll_options is not None:
        result_order += OPTIONAL_VARIABLE_ORDER
    if mur_options is not None:
        result_order += MUR_VARIABLE_ORDER
    governance = _load_governance(Path(spec_path), result_order)

    results_by_id: dict[str, VariableResult] = {}
    point_args = (
        float(request.lat),
        float(request.lon),
        request.target_date,
        request.hour_start_local,
        request.hour_end_local,
    )

    def fetch_chlorophyll_reference():
        if chlorophyll_mode is OpticalMode.NRT_OPERATIONAL:
            return providers.fetch_chlorophyll(*point_args[:3])
        return providers.fetch_chlorophyll(
            *point_args[:3], mode=chlorophyll_mode
        )

    point_operations = (
        ("sst_model", "sst", lambda: providers.fetch_sst(*point_args)),
        ("waves", "oleaje", lambda: providers.get_wave_status(*point_args)),
        (
            "chlorophyll",
            "clorofila",
            fetch_chlorophyll_reference,
        ),
        ("salinity", "salinidad", lambda: providers.fetch_salinity(*point_args)),
    )
    for operation, variable_id, call in point_operations:
        reading, errors = _call_provider(operation, (variable_id,), call, governance)
        if errors:
            results_by_id[variable_id] = errors[0]
        else:
            results_by_id[variable_id] = _variable_result(
                variable_id, reading, governance[variable_id]
            )

    bounds = request.field_bounds
    ostia, errors = _call_provider(
        "ostia_field",
        ("sst_observed_ostia", "thermal_front"),
        lambda: providers.fetch_ostia_field(
            bounds.minimum_latitude,
            bounds.maximum_latitude,
            bounds.minimum_longitude,
            bounds.maximum_longitude,
            request.target_date,
        ),
        governance,
    )
    if errors:
        for result in errors:
            results_by_id[result.variable_id] = result
    else:
        results_by_id["sst_observed_ostia"] = _variable_result(
            "sst_observed_ostia", ostia, governance["sst_observed_ostia"]
        )
        front, front_errors = _call_provider(
            "thermal_front_derivation",
            ("thermal_front",),
            lambda: providers.derive_thermal_front(ostia),
            governance,
        )
        results_by_id["thermal_front"] = (
            front_errors[0]
            if front_errors
            else _variable_result("thermal_front", front, governance["thermal_front"])
        )

    vertical, errors = _call_provider(
        "vertical_thermal_pair",
        ("temperature_10m", "delta_sst_t10"),
        lambda: providers.fetch_vertical_thermal_pair(*point_args),
        governance,
    )
    if errors:
        for result in errors:
            results_by_id[result.variable_id] = result
    else:
        for variable_id in ("temperature_10m", "delta_sst_t10"):
            results_by_id[variable_id] = _variable_result(
                variable_id, vertical, governance[variable_id]
            )

    final_operations = (
        ("surface_currents", "surface_currents", lambda: providers.fetch_currents(*point_args)),
        ("bathymetry", "batimetria", lambda: providers.fetch_bathymetry(*point_args[:2])),
    )
    for operation, variable_id, call in final_operations:
        reading, errors = _call_provider(operation, (variable_id,), call, governance)
        results_by_id[variable_id] = (
            errors[0]
            if errors
            else _variable_result(variable_id, reading, governance[variable_id])
        )

    if chlorophyll_options is not None:
        chlorophyll_field, errors = _call_provider(
            "chlorophyll_olci_field",
            OPTIONAL_VARIABLE_ORDER,
            lambda: providers.fetch_chlorophyll_field(
                bounds.minimum_latitude,
                bounds.maximum_latitude,
                bounds.minimum_longitude,
                bounds.maximum_longitude,
                request.target_date,
                options=chlorophyll_options,
            ),
            governance,
        )
        if errors:
            for result in errors:
                results_by_id[result.variable_id] = result
        else:
            source_result = _variable_result(
                "chlorophyll_olci",
                chlorophyll_field,
                governance["chlorophyll_olci"],
            )
            results_by_id["chlorophyll_olci"] = source_result
            if source_result.error_code == "invalid_provider_result":
                results_by_id["chlorophyll_front"] = _error_result(
                    "chlorophyll_front",
                    governance["chlorophyll_front"],
                    "invalid_shared_source",
                    TypeError("La fuente OLCI no cumple el contrato."),
                )
            else:
                chlorophyll_front, front_errors = _call_provider(
                    "chlorophyll_front_derivation",
                    ("chlorophyll_front",),
                    lambda: providers.derive_chlorophyll_gradient(chlorophyll_field),
                    governance,
                )
                results_by_id["chlorophyll_front"] = (
                    front_errors[0]
                    if front_errors
                    else _variable_result(
                        "chlorophyll_front",
                        chlorophyll_front,
                        governance["chlorophyll_front"],
                    )
                )

    if mur_options is not None:
        mur_field, errors = _call_provider(
            "mur_field", MUR_VARIABLE_ORDER,
            lambda: providers.fetch_mur_field(
                bounds.minimum_latitude, bounds.maximum_latitude,
                bounds.minimum_longitude, bounds.maximum_longitude,
                request.target_date, options=mur_options,
            ),
            governance, redact_exception=True,
        )
        if errors:
            for result in errors:
                results_by_id[result.variable_id] = result
        else:
            source_result = _variable_result("sst_mur", mur_field, governance["sst_mur"])
            results_by_id["sst_mur"] = source_result
            if source_result.error_code in {"invalid_provider_result", "unknown_source_status"}:
                results_by_id["thermal_gradient_mur"] = _error_result(
                    "thermal_gradient_mur", governance["thermal_gradient_mur"],
                    "invalid_shared_source", TypeError("La fuente MUR no cumple el contrato."),
                )
            else:
                mur_gradient, gradient_errors = _call_provider(
                    "mur_gradient_derivation", ("thermal_gradient_mur",),
                    lambda: providers.derive_mur_gradient(mur_field),
                    governance, redact_exception=True,
                )
                results_by_id["thermal_gradient_mur"] = (
                    gradient_errors[0] if gradient_errors
                    else _variable_result("thermal_gradient_mur", mur_gradient, governance["thermal_gradient_mur"])
                )

    results = tuple(results_by_id[variable_id] for variable_id in result_order)
    available_count = sum(result.state is AssemblyState.AVAILABLE for result in results)
    no_data_count = sum(result.state is AssemblyState.NO_DATA for result in results)
    error_count = sum(result.state is AssemblyState.ERROR for result in results)
    return EnvironmentalSnapshot(
        schema_version=(
            OLCI_MUR_SCHEMA_VERSION if mur_options and chlorophyll_options
            else MUR_SCHEMA_VERSION if mur_options
            else OLCI_SCHEMA_VERSION if chlorophyll_options else SCHEMA_VERSION
        ),
        request=request,
        spatial_context=_spatial_context(request, chlorophyll_options is not None, mur_options is not None),
        status=_overall_status(results),
        variables=results,
        available_count=available_count,
        no_data_count=no_data_count,
        error_count=error_count,
        safety=_safety_summary(results_by_id["oleaje"]),
        chlorophyll_options=chlorophyll_options,
        mur_options=mur_options,
    )
