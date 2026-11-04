"""Checks for cross-block ambiguity and regressions on local original files."""
import os
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
import xarray as xr

from reconcile_review import date_summary, linking_summary, prepare_events
from audit_cruise_databases import parse_haul_dates


class ReconciliationTests(unittest.TestCase):
    def test_cruise_date_encodings_are_explicit_without_table_name(self):
        dates=parse_haul_dates(pd.Series(['07/26/24 00:00:00','30/07/2025','bad-date']))
        self.assertEqual(dates.iloc[0],pd.Timestamp('2024-07-26'))
        self.assertEqual(dates.iloc[1],pd.Timestamp('2025-07-30'))
        self.assertTrue(pd.isna(dates.iloc[2]))
    def test_same_time_and_position_do_not_certify_a_single_operation(self):
        left=pd.DataFrame({'declared_time':pd.to_datetime(['2021-02-03']*2),
                           'lat':[-33.1]*2,'lon':[-71.7]*2,'valid_link_fields':[True]*2})
        result=linking_summary(left,left.iloc[:1])
        self.assertEqual(result['shared_keys'],1)
        self.assertEqual(result['one_to_one_candidate_keys'],0)
        self.assertEqual(result['shared_keys_with_multiple_left_events'],1)
        self.assertTrue(result['not_certified_operation_counts'])

    def test_different_date_fields_are_preserved_without_choosing_fishing_date(self):
        frame=pd.DataFrame({'id':['ASIPA_15-01__x'],'eventDate':['2/3/2021 10:00:00'],
             'year':['2021'],'month':['2'],'day':['5'],
             'decimalLatitude':['-33.1'],'decimalLongitude':['-71.7']})
        result=prepare_events(frame)
        summary=date_summary(result)
        self.assertEqual(summary['date_disagreements_among_parseable_rows'],1)
        self.assertEqual(result.declared_time.iloc[0].day,3)
        self.assertEqual(result.component_date.iloc[0].day,5)


@unittest.skipUnless(os.environ.get('CHILE_RAW_DIR'),'Set CHILE_RAW_DIR to run original-file regression checks')
class OriginalDataChecks(unittest.TestCase):
    def test_original_linkage_registry_preserves_events_and_blocks_training(self):
        raw=Path(os.environ['CHILE_RAW_DIR'])
        frame=pd.read_csv(raw/'portales_capture_event_linkage_REVIEW_ONLY.csv')
        self.assertEqual(len(frame),16343)
        self.assertEqual(frame.id.nunique(),16343)
        self.assertFalse(frame.training_ready.any())
        self.assertTrue(frame.same_key_capture_event_count.gt(1).any())

    def test_actual_l3_l4_extra_cells_are_not_labelled_as_l3_observations(self):
        raw=Path(os.environ['CHILE_RAW_DIR'])/'copernicus_october_2026'
        with xr.open_dataset(raw/'chlorophyll_l3.nc') as a,xr.open_dataset(raw/'chlorophyll_l4.nc') as b:
            x,y=xr.align(a.CHL,b.CHL,join='inner')
            common=np.isfinite(x)&np.isfinite(y)
            self.assertEqual(int((~np.isfinite(x)&np.isfinite(y)).sum()),312)
            self.assertEqual(float(abs(x-y).where(common).max()),0.)

    def test_actual_l3_date_with_no_measurement_is_not_a_useful_observation_day(self):
        raw=Path(os.environ['CHILE_RAW_DIR'])/'copernicus_october_2026'
        with xr.open_dataset(raw/'chlorophyll_l3.nc') as ds:
            daily=np.isfinite(ds.CHL).sum(['latitude','longitude'])
            self.assertEqual(len(daily),15)
            self.assertEqual(int((daily==0).sum()),1)
            self.assertEqual(int((daily>=.8*128).sum()),10)


if __name__=='__main__': unittest.main()
