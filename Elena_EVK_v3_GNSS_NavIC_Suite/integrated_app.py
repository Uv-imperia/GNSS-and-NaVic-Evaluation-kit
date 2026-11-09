"""
Elena Geo Tech EVK v3 — Integrated Mission Suite: Logger + Evaluator
Integrates the PyQt6 GNSS Data Logger with the Tkinter Performance Evaluator.

Architecture:
- Completely preserves logger_app.py (PyQt6) untouched.
- Completely preserves evaluator_app.py (Tkinter) untouched.
- Extends GNSSLoggerApp with direct one-click integration to the 4-Pillars Benchmark Engine
  and launches the Standalone Evaluator App seamlessly.
"""

import os
import sys
import subprocess
import webbrowser
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QGroupBox, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt

from logger_app import GNSSLoggerApp, CONSTELLATION_CONFIG
from core.evaluator import GNSSEvaluator
from core.plotter import GNSSPlotter
from core.report_generator import ReportGenerator

class IntegratedGNSSApp(GNSSLoggerApp):
    """
    Seamless integration bridge extending the friend's GNSSLoggerApp
    without modifying a single line of logger_app.py or evaluator_app.py.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elena Geo Tech EVK v3 — Integrated GNSS & NavIC Suite (Logger + Evaluator)")

        # Inject the Evaluator Integration Controls into the Logger Tab
        self.add_evaluator_integration_panel()

    def add_evaluator_integration_panel(self):
        """Adds a dedicated Evaluator Launch & Benchmarking box to Tab 2."""
        eval_box = QGroupBox("⚡ Elena Geo Tech 4-Pillars Evaluator Bridge")
        eval_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12px; color: #1E3A8A; border: 1px solid #3B82F6; margin-top: 6px; padding-top: 10px; border-radius: 6px; }")
        eval_layout = QVBoxLayout(eval_box)

        desc_lbl = QLabel(
            "Seamlessly send captured NMEA streams directly to the 4-Pillars Benchmark Engine "
            "(CEP 50%, 2DRMS 95%, C/N₀ vs Elevation, PDOP Health, Fix Continuity & Engineering Reports)."
        )
        desc_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        eval_layout.addWidget(desc_lbl)

        btn_row = QHBoxLayout()

        self.btn_run_instant_eval = QPushButton("🚀 Run 4-Pillars Evaluation on Active/Recorded Log")
        self.btn_run_instant_eval.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; font-size: 12px; padding: 8px 16px; border-radius: 4px;"
        )
        self.btn_run_instant_eval.clicked.connect(self.evaluate_active_or_selected_log)
        btn_row.addWidget(self.btn_run_instant_eval)

        self.btn_launch_evaluator_gui = QPushButton("📈 Open Standalone Evaluator App (GUI)")
        self.btn_launch_evaluator_gui.setStyleSheet(
            "background-color: #0F172A; color: #38BDF8; font-weight: bold; font-size: 12px; padding: 8px 16px; border-radius: 4px;"
        )
        self.btn_launch_evaluator_gui.clicked.connect(self.launch_evaluator_window)
        btn_row.addWidget(self.btn_launch_evaluator_gui)

        eval_layout.addLayout(btn_row)

        # Insert right below the log controls in tab_logger layout
        logger_layout = self.tab_logger.layout()
        if logger_layout:
            logger_layout.insertWidget(1, eval_box)

    def stop_logging(self):
        """
        Extends the friend's stop_logging method:
        After saving the NMEA log file, it offers 1-click evaluation.
        """
        super().stop_logging()

        if self.log_filepath and os.path.exists(self.log_filepath):
            reply = QMessageBox.question(
                self,
                "Run Elena Performance Evaluation?",
                f"NMEA recording completed!\nFile saved at:\n{self.log_filepath}\n\n"
                "Would you like to immediately run the 4-Pillars Benchmark & generate the report for this session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.run_full_evaluation(self.log_filepath)

    def evaluate_active_or_selected_log(self):
        """
        Evaluates the currently recorded NMEA log file, or prompts the user
        to select any recorded .nmea/.txt/.log file to benchmark.
        """
        target_file = self.log_filepath
        if not target_file or not os.path.exists(target_file):
            target_file, _ = QFileDialog.getOpenFileName(
                self,
                "Select NMEA Data File (.nmea, .txt, .log) to Evaluate",
                "",
                "NMEA Files (*.nmea *.txt *.log *.dat);;All Files (*)"
            )
            if not target_file:
                return

        self.run_full_evaluation(target_file)

    def run_full_evaluation(self, file_path: str):
        """Runs the 4-pillar benchmark and opens the publication-grade HTML report."""
        try:
            val = GNSSEvaluator.validate_nmea_file(file_path)
            if not val.get('is_valid'):
                QMessageBox.warning(
                    self,
                    "Invalid NMEA File",
                    f"The file '{os.path.basename(file_path)}' could not be evaluated:\n{val.get('message')}"
                )
                return

            ev = GNSSEvaluator()
            res_load = ev.process_path(file_path)
            if not res_load.get('success'):
                QMessageBox.critical(self, "Load Error", res_load.get('message', 'Failed to load file.'))
                return

            session_name = os.path.splitext(os.path.basename(file_path))[0]
            res = ev.evaluate(session_name=session_name)
            if res.get('status') != 'SUCCESS':
                QMessageBox.critical(self, "Evaluation Error", res.get('message', 'Evaluation failed.'))
                return

            # Generate Report
            rep = ReportGenerator(output_dir="data/reports")
            report_path = rep.generate_html_report(res, raw_log_file=file_path)

            # Generate Companion Plots
            plot_dir = "data/plots"
            os.makedirs(plot_dir, exist_ok=True)
            acc = res['accuracy_dispersion']
            GNSSPlotter.plot_enu_dispersion(
                acc['enu_points'], acc['cep_50_m'], acc['two_drms_95_m'],
                acc['vertical_dispersion_2sigma_m'],
                save_path=os.path.join(plot_dir, "enu_dispersion.png")
            )
            GNSSPlotter.plot_cdf_curve(
                acc['cdf_curve'], acc['cdf_percentiles']['p50_cep'],
                acc['cdf_percentiles']['p68_1sigma'], acc['cdf_percentiles']['p95_2drms'],
                acc['cdf_percentiles']['p99'],
                save_path=os.path.join(plot_dir, "error_cdf.png")
            )
            GNSSPlotter.plot_cno_vs_elevation(
                ev.satellite_obs,
                save_path=os.path.join(plot_dir, "cno_vs_elevation.png")
            )
            GNSSPlotter.plot_polar_skyplot(
                ev.satellite_obs,
                save_path=os.path.join(plot_dir, "polar_skyplot.png")
            )

            # Open Report in Browser
            abs_url = "file:///" + os.path.abspath(report_path).replace("\\", "/")
            webbrowser.open(abs_url)

            rel = res['reliability_temporal']
            rf = res['rf_signal_quality']
            geom = res['geometry_health']

            QMessageBox.information(
                self,
                "Evaluation Complete! 🚀",
                f"Evaluation successfully completed for '{os.path.basename(file_path)}'!\n\n"
                f"• Overall Grade: {res.get('overall_grade')}\n"
                f"• CEP (50%): {acc['cep_50_m']} m | 2DRMS (95%): {acc['two_drms_95_m']} m\n"
                f"• NavIC Mean C/N₀: {rf['band_separation']['navic_l5_s']['mean_cno']} dB-Hz\n"
                f"• GPS Mean C/N₀: {rf['band_separation']['gps_l1_l5']['mean_cno']} dB-Hz\n"
                f"• Mean PDOP: {geom['pdop']['mean']} ({geom['pdop']['health_assessment']})\n"
                f"• Fix Availability: {rel['fix_availability_ratio_pct']}%\n\n"
                f"Full HTML Engineering Report opened in your browser:\n{report_path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", f"An error occurred during evaluation:\n{str(e)}")

    def launch_evaluator_window(self):
        """Launches the Standalone Evaluator Tkinter App in a separate process."""
        evaluator_script = os.path.join(os.path.dirname(__file__), "evaluator_app.py")
        try:
            subprocess.Popen([sys.executable, evaluator_script])
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Could not launch evaluator_app.py:\n{str(e)}")

def launch_suite():
    app = QApplication(sys.argv)
    window = IntegratedGNSSApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    launch_suite()
