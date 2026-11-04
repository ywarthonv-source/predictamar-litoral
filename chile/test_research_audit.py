"""Offline checks for the scientific mistakes most harmful to this audit."""
import unittest
import numpy as np
import pandas as pd
import xarray as xr

from audit_public_data import SITE_LAT, SITE_LON, distance_km, target_key
from diagnose_copernicus import summarize_array


class ResearchAuditTests(unittest.TestCase):
    def test_chilean_hake_does_not_accept_peruvian_subspecies(self):
        self.assertEqual(target_key("Merluccius gayi gayi"), "merluza_comun")
        self.assertEqual(target_key("Merluccius gayi peruanus"), "")
        self.assertEqual(target_key("Merluccius australis"), "")

    def test_distance_is_to_reference_point_in_km(self):
        self.assertAlmostEqual(float(distance_km(np.array([SITE_LAT]),np.array([SITE_LON]))[0]), 0)
        self.assertAlmostEqual(float(distance_km(np.array([SITE_LAT+1]),np.array([SITE_LON]))[0]),111.195,places=2)

    def test_missing_cells_are_not_zero_observations(self):
        da=xr.DataArray([[[np.nan,2.]],[[np.nan,3.]]],dims=("time","latitude","longitude"),attrs={"units":"mg m-3"})
        r=summarize_array(da)
        self.assertEqual(r["finite_fraction_box_including_land"],.5)
        self.assertEqual(r["minimum_native_units"],2.)
        self.assertEqual(r["cells_with_any_finite_value"],1)
        self.assertEqual(r["daily_finite_cells"],[1,1])

    def test_uniform_map_does_not_gain_spatial_discrimination(self):
        da=xr.DataArray(np.full((3,2,2),4.),dims=("time","latitude","longitude"))
        self.assertEqual(summarize_array(da)["median_daily_spatial_range_native_units"],0.)

    def test_all_missing_keeps_summary_absent(self):
        da=xr.DataArray(np.full((2,1,2),np.nan),dims=("time","latitude","longitude"))
        r=summarize_array(da)
        self.assertIsNone(r["minimum_native_units"])
        self.assertIsNone(r["median_daily_spatial_range_native_units"])
        self.assertEqual(r["finite_values"],0)


if __name__=="__main__": unittest.main()
