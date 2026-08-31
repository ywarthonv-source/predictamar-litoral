"""Regresión opt-in con el paquete histórico aportado; jamás consulta NASA.

PREDICTAMAR_MUR_BUNDLE debe apuntar a comparacion_mur_ostia_30d_reproducible.zip.
Los datos no se redistribuyen dentro del repositorio. CI sin el paquete omite
esta prueba; no se sustituye por datos sintéticos con la etiqueta 'real'.
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import os
from zipfile import ZipFile

import numpy as np
import pytest
import xarray as xr

from ingestion.fetch_mur import (
    MurMode, MurOptions, MurProductStage, MurStatus,
    fetch_mur_field, mur_field_from_dataset,
)
from derivation.mur_gradient import derive_mur_gradient


@pytest.mark.skipif(not os.environ.get("PREDICTAMAR_MUR_BUNDLE"), reason="paquete histórico no configurado")
def test_treinta_recortes_reales_mascara_fecha_gradiente_y_calidad_local(tmp_path):
    core = (-12.621, -12.321, -76.94, -76.64)
    days, days_with_ir = [], 0
    with ZipFile(os.environ["PREDICTAMAR_MUR_BUNDLE"]) as bundle:
        with ZipFile(BytesIO(bundle.read("upload/mur_20260723_20260821.zip"))) as archive:
            names = sorted(n for n in archive.namelist() if n.endswith(".nc4"))
            assert len(names) == 30
            for index, name in enumerate(names):
                raw = archive.read(name)
                # Nombres internos no se usan como rutas de extracción.
                (tmp_path / f"mur_{index:02d}.nc4").write_bytes(raw)
                with xr.open_dataset(BytesIO(raw), engine="h5netcdf", decode_timedelta=False) as ds:
                    stamp = datetime.fromisoformat(str(ds.time.values[0])).replace(tzinfo=timezone.utc)
                    options = MurOptions(stamp + timedelta(days=1), mode=MurMode.HISTORICAL_DIAGNOSTIC)
                    field = mur_field_from_dataset(ds, *core, stamp.date(), options=options)
                gradient = derive_mur_gradient(field)
                assert field.status is MurStatus.HISTORICA_FINAL
                assert field.provenance.product_stage is MurProductStage.FINAL
                assert field.provenance.product_created_at_utc > options.as_of_utc
                assert not field.provenance.availability_as_of_verified
                assert field.n_marine_cells == field.n_valid_cells == 527
                assert gradient.n_gradient_cells == 492
                assert field.halo_complete
                days.append(stamp.date().isoformat())
                days_with_ir += field.n_dt_1km_cells > 0
                # Esta celda de TIERRA tiene SST finita en el NetCDF del proveedor.
                i = int(np.argmin(np.abs(np.asarray(field.grid.latitudes) + 12.47)))
                j = int(np.argmin(np.abs(np.asarray(field.grid.longitudes) + 76.80)))
                assert field.grid.mask[i][j] == 2
                assert field.grid.sst_celsius[i][j] is None
                if stamp.date().isoformat() == "2026-07-31":
                    values = np.asarray(gradient.gradient_c_per_km, dtype=float)
                    ij = np.unravel_index(np.nanargmax(values), values.shape)
                    assert float(np.nanmax(values)) == pytest.approx(.23594265, abs=1e-7)
                    assert gradient.n_dt_1km_support_cells[ij[0]][ij[1]] == 1
                    assert gradient.dt_1km_support_complete[ij[0]][ij[1]] is False
    assert min(days) == "2026-07-23" and max(days) == "2026-08-21"
    assert len(set(days)) == 30 and days_with_ir == 13
    options = MurOptions(datetime(2026, 8, 1, 9, tzinfo=timezone.utc), mode=MurMode.HISTORICAL_DIAGNOSTIC)
    reading = fetch_mur_field(*core, date(2026, 7, 31), options=options, data_directory=tmp_path)
    assert reading.status is MurStatus.HISTORICA_FINAL
    assert reading.n_valid_cells == 527
    assert reading.provenance.source_file_sha256 is not None
    assert derive_mur_gradient(reading).n_gradient_cells == 492
