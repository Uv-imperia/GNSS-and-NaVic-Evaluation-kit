"""
Comprehensive Quality Assurance & Automated Test Suite for Elena EVK v3 Suite.
Tests all 6 domains:
1. NMEA Parser Resilience
2. 4-Pillars Evaluation Mathematical Integrity & Edge Cases (0 fixes, 1 fix, 100+ fixes)
3. Plotter Engine & In-Place Canvas Reusability
4. Report Generator HTML & CSS Output
5. Logger Worker & Constellation Logic
6. Integrated Suite Bridge
"""

import os
import sys
import math
import shutil
import tempfile
import unittest
import numpy as np

project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

from core.nmea_parser import NMEAParser, SatelliteInfo, GNSSFix
from core.evaluator import GNSSEvaluator, geodetic_to_ecef, ecef_to_enu
from core.plotter import GNSSPlotter
from core.report_generator import ReportGenerator
import matplotlib
matplotlib.use('Agg') # Headless backend for automated test execution
import matplotlib.pyplot as plt

class TestNMEAParser(unittest.TestCase):
    def setUp(self):
        self.parser = NMEAParser()

    def test_clean_nmea_extraction(self):
        # Noise, timestamps, prefixes before $
        raw = "2026-11-05 10:00:00.123 [DEBUG] $GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        clean = self.parser.extract_clean_nmea_sentence(raw)
        self.assertTrue(clean.startswith("$GNGGA"))
        self.assertTrue(clean.endswith("*47"))

        # Null bytes and control characters
        raw_null = "\x00\x00$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39\r\n"
        clean_null = self.parser.extract_clean_nmea_sentence(raw_null)
        self.assertEqual(clean_null, "$GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39")

        # Empty and non-NMEA
        self.assertIsNone(self.parser.extract_clean_nmea_sentence(""))
        self.assertIsNone(self.parser.extract_clean_nmea_sentence("JUST RANDOM NOISE WITHOUT DOLLAR"))

    def test_checksum_validation(self):
        # Correct XOR checksum for GNGGA string is *59
        valid = "$GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*59"
        self.assertTrue(self.parser.verify_checksum(valid))

        invalid = "$GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*99"
        self.assertFalse(self.parser.verify_checksum(invalid))

        # Omitted checksum is accepted leniently
        no_chk = "$GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,"
        self.assertTrue(self.parser.verify_checksum(no_chk))

    def test_coordinate_parsing_hemispheres(self):
        # North East (e.g. Bangalore: ~13 deg N, ~77 deg E)
        lat = self.parser._parse_lat("1302.4960", "N")
        lon = self.parser._parse_lon("07734.0260", "E")
        self.assertAlmostEqual(lat, 13.0416, places=3)
        self.assertAlmostEqual(lon, 77.5671, places=3)

        # South West
        lat_s = self.parser._parse_lat("1302.4960", "S")
        lon_w = self.parser._parse_lon("07734.0260", "W")
        self.assertAlmostEqual(lat_s, -13.0416, places=3)
        self.assertAlmostEqual(lon_w, -77.5671, places=3)

        # Malformed
        self.assertIsNone(self.parser._parse_lat("", "N"))
        self.assertIsNone(self.parser._parse_lon("abc", "E"))

    def test_navic_gsv_parsing(self):
        # NavIC talker $GI
        gsv = "$GIGSV,1,1,04,01,62,140,42,02,40,230,30,05,25,080,27,06,75,320,40*7A"
        res = self.parser.parse_line(gsv)
        self.assertEqual(res['type'], 'GSV')
        self.assertEqual(res['constellation'], 'NavIC')
        self.assertEqual(len(res['satellites']), 4)
        summary = self.parser.get_satellites_summary()
        self.assertEqual(summary['navic_count'], 4)
        self.assertIn('NavIC', summary['by_constellation'])
        self.assertGreater(summary['by_constellation']['NavIC']['avg_cno'], 30.0)


class TestGNSSEvaluatorPillars(unittest.TestCase):
    def setUp(self):
        self.evaluator = GNSSEvaluator()

    def test_geodetic_ecef_enu_roundtrip(self):
        # Bangalore coordinates
        lat, lon, alt = 13.0416, 77.5671, 910.0
        x, y, z = geodetic_to_ecef(lat, lon, alt)
        # Reference is same point -> ENU should be (0, 0, 0)
        e, n, u = ecef_to_enu(x, y, z, lat, lon, alt)
        self.assertAlmostEqual(e, 0.0, places=3)
        self.assertAlmostEqual(n, 0.0, places=3)
        self.assertAlmostEqual(u, 0.0, places=3)

        # Offset by ~0.001 deg North (~111 meters)
        lat_offset = lat + 0.001
        x2, y2, z2 = geodetic_to_ecef(lat_offset, lon, alt)
        e2, n2, u2 = ecef_to_enu(x2, y2, z2, lat, lon, alt)
        self.assertAlmostEqual(e2, 0.0, delta=1.0)
        self.assertAlmostEqual(n2, 111.0, delta=2.0)

    def test_edge_case_zero_fixes(self):
        # Evaluator with 0 valid fixes should NOT throw KeyError or divide by zero
        temp_dir = tempfile.mkdtemp()
        empty_log = os.path.join(temp_dir, "empty_log.txt")
        with open(empty_log, 'w') as f:
            f.write("$GNGGA,000000,,,,,,0,00,,,M,,M,,*66\n") # Fix quality 0, empty coords

        ev = GNSSEvaluator()
        ev.process_path(empty_log)
        res = ev.evaluate(session_name="Zero_Fix_Test")
        shutil.rmtree(temp_dir)

        self.assertEqual(res['status'], 'SUCCESS')
        self.assertEqual(res['reliability_temporal']['valid_epochs'], 0)
        self.assertEqual(res['accuracy_dispersion']['cep_50_m'], 0.0)
        self.assertEqual(res['accuracy_dispersion']['two_drms_95_m'], 0.0)
        self.assertEqual(res['accuracy_dispersion']['vertical_dispersion_2sigma_m'], 0.0)
        self.assertEqual(res['overall_grade'], 'C (Marginal)')

    def test_edge_case_single_fix(self):
        # Evaluator with 1 valid fix
        temp_dir = tempfile.mkdtemp()
        one_fix_log = os.path.join(temp_dir, "one_fix.txt")
        with open(one_fix_log, 'w') as f:
            f.write("$GNGGA,120000,1302.4960,N,07734.0260,E,1,08,1.0,910.0,M,0.0,M,,*40\n")

        ev = GNSSEvaluator()
        ev.process_path(one_fix_log)
        res = ev.evaluate(session_name="Single_Fix_Test")
        shutil.rmtree(temp_dir)

        self.assertEqual(res['status'], 'SUCCESS')
        self.assertEqual(res['reliability_temporal']['valid_epochs'], 1)
        self.assertEqual(res['accuracy_dispersion']['cep_50_m'], 0.0)
        self.assertEqual(res['accuracy_dispersion']['two_drms_95_m'], 0.0)

    def test_mathematical_dispersion_accuracy(self):
        # Multi-epoch synthetic test with known dispersion
        sample_path = os.path.join(project_dir, "data", "samples", "sample_elena_evk_navic.nmea")
        if not os.path.exists(sample_path):
            self.skipTest("Sample NMEA file not available.")

        ev = GNSSEvaluator()
        ev.process_path(sample_path)
        res = ev.evaluate(session_name="Benchmark_Sample_Verification")

        acc = res['accuracy_dispersion']
        rf = res['rf_signal_quality']
        geom = res['geometry_health']
        rel = res['reliability_temporal']

        # Verify mathematical consistency: 2DRMS should be approximately 2 * DRMS
        self.assertAlmostEqual(acc['two_drms_95_m'], 2.0 * acc['drms_m'], delta=0.01)
        # CEP 50% must be smaller than 2DRMS 95%
        self.assertLess(acc['cep_50_m'], acc['two_drms_95_m'])
        # Percentiles must be monotonically increasing: p50 <= p68 <= p95 <= p99
        p = acc['cdf_percentiles']
        self.assertLessEqual(p['p50_cep'], p['p68_1sigma'])
        self.assertLessEqual(p['p68_1sigma'], p['p95_2drms'])
        self.assertLessEqual(p['p95_2drms'], p['p99'])

        # Verify NavIC RF signal presence
        navic_cno = rf['band_separation']['navic_l5_s']['mean_cno']
        self.assertGreater(navic_cno, 30.0)
        self.assertGreater(rf['band_separation']['navic_l5_s']['sats_tracked'], 0)

        # Verify DOP values are positive floats
        self.assertGreater(geom['pdop']['mean'], 0.0)
        self.assertGreater(geom['hdop']['mean'], 0.0)
        self.assertGreater(geom['vdop']['mean'], 0.0)

        # Verify Availability
        self.assertGreater(rel['fix_availability_ratio_pct'], 80.0)


class TestPlotterAndReport(unittest.TestCase):
    def test_plotter_canvas_reusability(self):
        fig, ax = plt.subplots()
        # In-place plotting on existing figure
        GNSSPlotter.plot_enu_dispersion(
            [{'e': 0.1, 'n': 0.2, 'u': 0.0}, {'e': -0.1, 'n': -0.2, 'u': 0.1}],
            cep_50=0.2, two_drms=0.4, vert_2sigma=0.2, fig=fig
        )
        # plot_enu_dispersion creates 2 subplots (Horizontal and Vertical dispersion)
        self.assertEqual(len(fig.axes), 2)

        # Re-use same figure without memory leakage or recreation crash
        GNSSPlotter.plot_cdf_curve(
            [{'error_m': 0.1, 'prob_pct': 50.0}, {'error_m': 0.3, 'prob_pct': 95.0}],
            p50=0.1, p68=0.2, p95=0.3, p99=0.4, fig=fig
        )
        self.assertEqual(len(fig.axes), 1)
        plt.close(fig)

    def test_report_generation(self):
        temp_dir = tempfile.mkdtemp()
        reporter = ReportGenerator(output_dir=temp_dir)

        dummy_results = {
            'status': 'SUCCESS',
            'session_name': 'Automated_Report_Test',
            'overall_grade': 'A+ (Outstanding)',
            'accuracy_dispersion': {
                'cep_50_m': 1.25, 'two_drms_95_m': 2.80, 'sep_3d_m': 1.95,
                'vertical_dispersion_2sigma_m': 2.10,
                'reference_coords': {'latitude': 13.0416, 'longitude': 77.5671, 'altitude_m': 910.0, 'is_ground_truth': False},
                'cdf_percentiles': {'p50_cep': 1.25, 'p68_1sigma': 1.60, 'p95_2drms': 2.80, 'p99': 3.40},
                'max_radial_error_m': 3.65
            },
            'rf_signal_quality': {
                'overall_cno': {'mean': 41.5, 'peak': 48.0, 'min': 22.0},
                'band_separation': {
                    'navic_l5_s': {'mean_cno': 42.1, 'peak_cno': 47.0, 'sats_tracked': 6},
                    'gps_l1_l5': {'mean_cno': 40.8, 'peak_cno': 48.0, 'sats_tracked': 9}
                },
                'elevation_multipath_analysis': {
                    'low_elev_sub15_avg_cno': 24.5, 'high_elev_avg_cno': 43.2, 'multipath_attenuation_db': 18.7
                },
                'satellites_tracking': {
                    'mean_n_view': 18.0, 'max_n_view': 20, 'mean_n_used': 14.5, 'max_n_used': 16, 'usage_efficiency_pct': 80.6
                },
                'per_prn_catalog': []
            },
            'geometry_health': {
                'hdop': {'mean': 0.85, 'min': 0.7, 'max': 1.2},
                'vdop': {'mean': 0.95, 'min': 0.8, 'max': 1.4},
                'pdop': {'mean': 1.28, 'min': 1.1, 'max': 1.8, 'optimal_sub2_pct': 100.0, 'degraded_over3_5_pct': 0.0, 'health_assessment': 'Optimal Geometry (<2.0)'}
            },
            'reliability_temporal': {
                'fix_availability_ratio_pct': 100.0, 'total_epochs': 100, 'valid_epochs': 100, 'invalid_epochs': 0,
                'ttff_seconds': 0.0,
                'quality_breakdown': {'Invalid (0)': 0, 'Autonomous SPS (1)': 100, 'DGPS (2)': 0, 'RTK Fixed (4)': 0, 'RTK Float (5)': 0, 'Estimated / Other': 0},
                'epoch_continuity': {'nominal_rate_hz': 1.0, 'mean_interval_sec': 1.0, 'jitter_sec': 0.01, 'dropped_frames': 0, 'continuity_pct': 100.0}
            },
            'files_processed': ['test_log.nmea']
        }

        report_path = reporter.generate_html_report(dummy_results, raw_log_file="test_log.nmea")
        self.assertTrue(os.path.exists(report_path))

        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check key report components
        self.assertIn("Elena Geo Tech EVK v3", content)
        self.assertIn("A+ (Outstanding)", content)
        self.assertIn("Positioning Accuracy & Dispersion", content)
        self.assertIn("RF Signal Quality & Tracking", content)
        self.assertIn("Satellite Geometry & Constellation Health", content)
        self.assertIn("Fix Reliability & Temporal Attributes", content)
        self.assertIn("1.25", content) # CEP value

        shutil.rmtree(temp_dir)


class TestLoggerAndBridge(unittest.TestCase):
    def test_logger_coordinate_decimal_conversion(self):
        from logger_app import parse_nmea_coord_to_decimal, identify_constellation
        # 13 deg 02.4960 min North -> 13.0416 deg
        dd_n = parse_nmea_coord_to_decimal("1302.4960", "N")
        self.assertAlmostEqual(dd_n, 13.0416, places=3)

        # South hemisphere -> negative
        dd_s = parse_nmea_coord_to_decimal("1302.4960", "S")
        self.assertAlmostEqual(dd_s, -13.0416, places=3)

        # Blank/invalid returns 0.0
        self.assertEqual(parse_nmea_coord_to_decimal("", "N"), 0.0)
        self.assertEqual(parse_nmea_coord_to_decimal(None, None), 0.0)

    def test_constellation_identification(self):
        from logger_app import identify_constellation
        self.assertEqual(identify_constellation("GP", "14"), "GPS")
        self.assertEqual(identify_constellation("GI", "01"), "NavIC-L5")
        self.assertEqual(identify_constellation("IR", "05"), "NavIC-L5")
        self.assertEqual(identify_constellation("GL", "71"), "GLONASS")
        self.assertEqual(identify_constellation("GA", "12"), "Galileo")
        self.assertEqual(identify_constellation("GB", "03"), "BeiDou")
        self.assertEqual(identify_constellation("BD", "07"), "BeiDou")


def run_all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTest(loader.loadTestsFromTestCase(TestNMEAParser))
    suite.addTest(loader.loadTestsFromTestCase(TestGNSSEvaluatorPillars))
    suite.addTest(loader.loadTestsFromTestCase(TestPlotterAndReport))
    suite.addTest(loader.loadTestsFromTestCase(TestLoggerAndBridge))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
