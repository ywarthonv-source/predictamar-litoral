"""Fuentes ópticas explícitas para operación NRT y diagnóstico histórico.

Los productos NRT y MY de Copernicus Marine tienen ventanas temporales y
versiones diferentes. Elegir uno u otro es una decisión de ejecución, no un
fallback silencioso: la aplicación conserva NRT por defecto y el diagnóstico
retrospectivo debe solicitar MY explícitamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OpticalMode(str, Enum):
    NRT_OPERATIONAL = "nrt_operational"
    HISTORICAL_DIAGNOSTIC = "historical_diagnostic"


@dataclass(frozen=True)
class OpticalDatasetSpec:
    product_id: str
    dataset_id: str
    dataset_version: str
    dataset_part: str = "default"


CHLOROPHYLL_REFERENCE_SPECS = {
    OpticalMode.NRT_OPERATIONAL: OpticalDatasetSpec(
        product_id="OCEANCOLOUR_GLO_BGC_L4_NRT_009_102",
        dataset_id="cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D",
        dataset_version="202311",
    ),
    OpticalMode.HISTORICAL_DIAGNOSTIC: OpticalDatasetSpec(
        product_id="OCEANCOLOUR_GLO_BGC_L4_MY_009_104",
        dataset_id="cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D",
        dataset_version="202603",
    ),
}


OLCI_FIELD_SPECS = {
    OpticalMode.NRT_OPERATIONAL: OpticalDatasetSpec(
        product_id="OCEANCOLOUR_GLO_BGC_L3_NRT_009_101",
        dataset_id="cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D",
        dataset_version="202207",
    ),
    OpticalMode.HISTORICAL_DIAGNOSTIC: OpticalDatasetSpec(
        product_id="OCEANCOLOUR_GLO_BGC_L3_MY_009_103",
        dataset_id="cmems_obs-oc_glo_bgc-plankton_my_l3-olci-300m_P1D",
        dataset_version="202211",
    ),
}


def _spec(
    specs: dict[OpticalMode, OpticalDatasetSpec], mode: OpticalMode
) -> OpticalDatasetSpec:
    if not isinstance(mode, OpticalMode):
        raise ValueError("mode debe ser OpticalMode, no un indicador implícito.")
    return specs[mode]


def chlorophyll_reference_spec(mode: OpticalMode) -> OpticalDatasetSpec:
    return _spec(CHLOROPHYLL_REFERENCE_SPECS, mode)


def olci_field_spec(mode: OpticalMode) -> OpticalDatasetSpec:
    return _spec(OLCI_FIELD_SPECS, mode)
