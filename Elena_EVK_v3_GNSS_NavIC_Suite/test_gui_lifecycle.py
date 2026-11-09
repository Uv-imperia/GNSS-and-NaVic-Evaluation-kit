"""
Automated GUI Lifecycle & Integration Test Suite.
Tests Tkinter Evaluator, PyQt6 Logger, and Integrated Mission Suite in automated/headless modes.
"""

import os
import sys
import unittest
import tkinter as tk

project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from evaluator_app import StandaloneEvaluatorApp
from logger_app import GNSSLoggerApp, GNSSWorker
from integrated_app import IntegratedGNSSApp
from core.evaluator import GNSSEvaluator

class TestEvaluatorGUILifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw() # Hide window during test
            cls.app = StandaloneEvaluatorApp(cls.root)
        except Exception as e:
            raise unittest.SkipTest(f"Display not available for Tkinter: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except:
            pass

    def test_evaluator_initial_state(self):
        self.assertIsNotNone(self.app.evaluator)
        self.assertIsNotNone(self.app.reporter)
        self.assertEqual(self.app.upload_btn['state'], tk.NORMAL)
        self.assertEqual(self.app.report_btn['state'], tk.DISABLED)

    def test_evaluator_validation_direct(self):
        sample = os.path.join(project_dir, "data", "samples", "sample_elena_evk_navic.nmea")
        val = GNSSEvaluator.validate_nmea_file(sample)
        self.assertTrue(val['is_valid'])
        self.assertIn("NavIC", val['constellations'])
        self.assertGreater(val['valid_nmea_sentences'], 100)


class TestPyQtLoggerAndIntegratedSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create single QApplication instance for PyQt tests
        cls.qt_app = QApplication.instance()
        if cls.qt_app is None:
            cls.qt_app = QApplication(sys.argv)

    def test_logger_app_creation(self):
        window = GNSSLoggerApp()
        self.assertIsNotNone(window.worker)
        self.assertEqual(window.tabs.count(), 3)
        self.assertIn("Dashboard", window.tabs.tabText(0))
        self.assertIn("Data Logger", window.tabs.tabText(1))
        self.assertIn("Reports", window.tabs.tabText(2))
        window.close()

    def test_integrated_app_bridge_injection(self):
        from PyQt6.QtWidgets import QMessageBox
        # Mock QMessageBox so the automated test does not block waiting for user click
        orig_info = QMessageBox.information
        orig_warning = QMessageBox.warning
        orig_critical = QMessageBox.critical
        QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        QMessageBox.warning = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        QMessageBox.critical = lambda *args, **kwargs: QMessageBox.StandardButton.Ok

        try:
            int_win = IntegratedGNSSApp()
            self.assertTrue(hasattr(int_win, 'btn_run_instant_eval'))
            self.assertTrue(hasattr(int_win, 'btn_launch_evaluator_gui'))
            self.assertIn("Integrated GNSS & NavIC Suite", int_win.windowTitle())

            # Test evaluation execution from integrated app
            sample = os.path.join(project_dir, "data", "samples", "sample_elena_evk_navic.nmea")
            int_win.run_full_evaluation(sample)

            # Verify that plots were generated
            plots_dir = os.path.join(project_dir, "data", "plots")
            self.assertTrue(os.path.exists(os.path.join(plots_dir, "enu_dispersion.png")))
            self.assertTrue(os.path.exists(os.path.join(plots_dir, "error_cdf.png")))
            self.assertTrue(os.path.exists(os.path.join(plots_dir, "cno_vs_elevation.png")))
            self.assertTrue(os.path.exists(os.path.join(plots_dir, "polar_skyplot.png")))

            int_win.close()
        finally:
            QMessageBox.information = orig_info
            QMessageBox.warning = orig_warning
            QMessageBox.critical = orig_critical


def run_gui_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTest(loader.loadTestsFromTestCase(TestEvaluatorGUILifecycle))
    suite.addTest(loader.loadTestsFromTestCase(TestPyQtLoggerAndIntegratedSuite))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_gui_tests()
    sys.exit(0 if success else 1)
