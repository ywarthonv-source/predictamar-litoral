"""La selección óptica es explícita y nunca mezcla NRT con MY."""

import pytest

from ingestion.optical_sources import (
    OpticalMode,
    chlorophyll_reference_spec,
    olci_field_spec,
)


@pytest.mark.parametrize(
    ("resolver", "nrt_version", "historical_version"),
    [
        (chlorophyll_reference_spec, "202311", "202603"),
        (olci_field_spec, "202207", "202211"),
    ],
)
def test_productos_nrt_e_historicos_tienen_identidades_distintas(
    resolver, nrt_version, historical_version
):
    nrt = resolver(OpticalMode.NRT_OPERATIONAL)
    historical = resolver(OpticalMode.HISTORICAL_DIAGNOSTIC)

    assert nrt.dataset_id != historical.dataset_id
    assert nrt.product_id != historical.product_id
    assert nrt.dataset_version == nrt_version
    assert historical.dataset_version == historical_version
    assert nrt.dataset_part == historical.dataset_part == "default"
    assert "_nrt_" in nrt.dataset_id
    assert "_my_" in historical.dataset_id


@pytest.mark.parametrize("resolver", [chlorophyll_reference_spec, olci_field_spec])
def test_modo_no_admite_texto_o_booleano_implicito(resolver):
    with pytest.raises(ValueError, match="OpticalMode"):
        resolver("historical_diagnostic")
    with pytest.raises(ValueError, match="OpticalMode"):
        resolver(True)
