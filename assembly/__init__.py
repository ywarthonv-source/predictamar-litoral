"""Ensamblado trazable de las señales ambientales de PredictaMAR Litoral."""

from ingestion.fetch_chlorophyll_field import (
    ChlorophyllOptions,
    HistoricalChlorophyllOptions,
)
from ingestion.fetch_mur import MurMode, MurOptions
from ingestion.optical_sources import OpticalMode

from .environmental_assembler import (
    AssemblerProviders,
    AssemblyRequest,
    AssemblyState,
    EnvironmentalSnapshot,
    FieldBounds,
    OverallAssemblyStatus,
    SafetySummary,
    SpatialContext,
    SpatialScope,
    VariableGovernance,
    VariableResult,
    assemble_environmental_snapshot,
)

__all__ = [
    "AssemblyRequest",
    "AssemblyState",
    "AssemblerProviders",
    "EnvironmentalSnapshot",
    "FieldBounds",
    "OverallAssemblyStatus",
    "SafetySummary",
    "SpatialContext",
    "SpatialScope",
    "VariableGovernance",
    "VariableResult",
    "assemble_environmental_snapshot",
    "ChlorophyllOptions",
    "HistoricalChlorophyllOptions",
    "MurMode",
    "MurOptions",
    "OpticalMode",
]
