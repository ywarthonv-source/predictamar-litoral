"""Ensamblado trazable de las señales ambientales de PredictaMAR Litoral."""

from .environmental_assembler import (
    AssemblyRequest,
    AssemblyState,
    AssemblerProviders,
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
from ingestion.fetch_chlorophyll_field import ChlorophyllOptions

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
]
