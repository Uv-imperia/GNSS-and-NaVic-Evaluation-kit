import sys
import os
import time
import random
import threading
from datetime import datetime

import serial
import serial.tools.list_ports
import pandas as pd
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QGroupBox, QSplitter, QMessageBox, QFrame,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QColor, QFont

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Constellation palettes matching Elena Logger specifications
CONSTELLATION_CONFIG = {
    'GPS': {'color': '#D32F2F', 'label': 'GPS', 'badge': 'GPS'},
    'NavIC-L5': {'color': '#1976D2', 'label': 'NavIC-L5', 'badge': 'NavIC-L5'},
    'NavIC-S': {'color': '#2E7D32', 'label': 'NavIC-S', 'badge': 'NavIC-S'},
    'GLONASS': {'color': '#7B1FA2', 'label': 'GLONASS', 'badge': 'GLONASS'},
    'BeiDou': {'color': '#E65100', 'label': 'BeiDou', 'badge': 'BeiDou'},
    'Galileo': {'color': '#00838F', 'label': 'Galileo', 'badge': 'Galileo'},
    'SBAS': {'color': '#F9A825', 'label': 'SBAS', 'badge': 'SBAS'}
}

def parse_nmea_coord_to_decimal(raw_val, direction):
    """Converts NMEA ddmm.mmmm / dddmm.mmmm format to decimal degrees."""
    try:
        if not raw_val or not direction:
            return 0.0
        val = float(raw_val)
        deg = int(val / 100)
        minutes = val - (deg * 100)
        decimal = deg + (minutes / 60.0)
        if direction.upper() in ['S', 'W']:
            decimal = -decimal
        return decimal
    except (ValueError, TypeError):
        return 0.0

def identify_constellation(talker, prn_val, sentence_raw=""):
    """
    Standard Talker IDs:
    - GP : GPS
    - GI / IR : NavIC (IRNSS)
    - GL : GLONASS
    - GA : Galileo
    - GB / BD : BeiDou
    - GN : Multi-constellation solution
    """
    try:
        prn = int(prn_val)
    except (ValueError, TypeError):
        prn = 0

    if talker in ['GI', 'IR']:
        if ",S" in sentence_raw or prn > 7:
            return 'NavIC-S'
        return 'NavIC-L5'
    elif talker == 'GP':
        return 'GPS'
    elif talker == 'GL':
        return 'GLONASS'
    elif talker == 'GA':
        return 'Galileo'
    elif talker in ['GB', 'BD']:
        return 'BeiDou'
    elif talker == 'GN':
        if 1 <= prn <= 14:
            return 'NavIC-L5'
        elif 65 <= prn <= 96:
            return 'GLONASS'
        elif 101 <= prn <= 136:
            return 'Galileo'
        elif 141 <= prn <= 180 or 201 <= prn <= 237:
            return 'BeiDou'
        elif prn >= 120:
            return 'SBAS'
        return 'GPS'
    elif prn >= 120 or talker == 'SB':
        return 'SBAS'
    return 'GPS'


class GNSSWorker(QObject):
    sentence_received = pyqtSignal(str)
    connection_changed = pyqtSignal(bool, str)
    file_progress = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.running = False
        self.ser = None
        self.file_path = None
        self.playback_speed = 5.0

    def start_serial(self, port, baud):
        self.running = True
        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=1.0)
            self.connection_changed.emit(True, f"Live COM: {port} @ {baud}")
            threading.Thread(target=self._run_serial, daemon=True).start()
        except Exception as e:
            self.running = False
            self.connection_changed.emit(False, f"COM Error: {e}")

    def start_file_stream(self, filepath, speed=5.0):
        self.file_path = filepath
        self.playback_speed = speed
        self.running = True
        self.connection_changed.emit(True, f"Streaming: {os.path.basename(filepath)}")
        threading.Thread(target=self._run_file, daemon=True).start()

    def start_simulator(self):
        self.running = True
        self.connection_changed.emit(True, "Simulator Mode Active")
        threading.Thread(target=self._run_simulator, daemon=True).start()

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        self.connection_changed.emit(False, "Disconnected / Idle")

    def _run_serial(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode('ascii', errors='replace').strip()
                if line and '$' in line:
                    sentence = line[line.find('$'):]
                    self.sentence_received.emit(sentence)
            except Exception:
                break
        self.stop()

    def _run_file(self):
        if not self.file_path or not os.path.exists(self.file_path):
            self.stop()
            return

        with open(self.file_path, 'r', errors='replace') as f:
            lines = [l.strip() for l in f if l.strip()]

        total = len(lines)
        delay = max(0.002, 0.08 / self.playback_speed)
        idx = 0

        while self.running and idx < total:
            line = lines[idx]
            idx += 1
            if '$' in line:
                sentence = line[line.find('$'):]
                self.sentence_received.emit(sentence)
                time.sleep(delay)

            if idx % 20 == 0:
                self.file_progress.emit(idx, total)
        self.stop()

    def _run_simulator(self):
        base_lat, base_lon = 13.0416, 77.5671
        while self.running:
            now = datetime.utcnow().strftime("%H%M%S.00")
            lat_off = (random.random() - 0.5) * 0.00004
            lon_off = (random.random() - 0.5) * 0.00004
            lat = base_lat + lat_off
            lon = base_lon + lon_off

            lat_nmea = f"{int(lat):02d}{((lat - int(lat)) * 60):07.4f}"
            lon_nmea = f"{int(lon):03d}{((lon - int(lon)) * 60):07.4f}"

            sim_burst = [
                f"$GNGGA,{now},{lat_nmea},N,{lon_nmea},E,1,18,0.67,910.2,M,-87.0,M,,*41",
                f"$GNGSA,A,3,02,04,05,08,11,14,22,28,01,02,05,,,1.03,0.67,0.78*22",
                f"$GNRMC,{now},A,{lat_nmea},N,{lon_nmea},E,0.08,259.59,231026,,,A*77",
                # GPS SVs
                "$GPGSV,2,1,08,02,45,120,42,04,30,045,25,08,70,210,44,11,15,310,26*7A",
                "$GPGSV,2,2,08,14,60,090,36,22,20,180,28,28,55,270,38,30,35,015,33*78",
                # NavIC (IRNSS) SVs
                "$GIGSV,1,1,04,01,62,140,42,02,40,230,30,05,25,080,27,06,75,320,40*7A",
                # BeiDou SVs
                "$GBGSV,1,1,03,03,50,060,39,07,38,135,35,11,62,305,41*77",
                # GLONASS SVs
                "$GLGSV,1,1,03,71,55,045,37,72,32,150,23,85,18,290,16*6D"
            ]
            for s in sim_burst:
                if not self.running:
                    break
                self.sentence_received.emit(s)
                time.sleep(0.04)
            time.sleep(0.5)


class GNSSLoggerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elena GNSS & NavIC Mission Logger Pro")
        self.resize(1400, 900)

        self.satellites = {}
        self.is_logging = False
        self.log_file = None
        self.log_filepath = ""
        self.log_records_count = 0
        self.log_error_count = 0
        self.logging_start_time = None

        # Active Constellation Filter
        self.selected_filter = "ALL"

        # Evaluator records buffer
        self.evaluator_records = []
        self.latest_dop = {"pdop": 1.0, "hdop": 0.8, "vdop": 0.9}

        self.worker = GNSSWorker()
        self.worker.sentence_received.connect(self.process_nmea_sentence)
        self.worker.connection_changed.connect(self.on_connection_changed)
        self.worker.file_progress.connect(self.on_file_progress)

        self.init_ui()
        self.setup_refresh_timers()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { font-size: 13px; font-weight: bold; padding: 7px 16px; }")
        main_layout.addWidget(self.tabs)

        self.tab_dashboard = QWidget()
        self.init_dashboard_tab()
        self.tabs.addTab(self.tab_dashboard, "📡 Dashboard & Sky Monitor")

        self.tab_logger = QWidget()
        self.init_logger_tab()
        self.tabs.addTab(self.tab_logger, "💾 Data Logger & Raw Stream")

        self.tab_reports = QWidget()
        self.init_reports_tab()
        self.tabs.addTab(self.tab_reports, "📊 Reports & Post-Analysis")

    def init_dashboard_tab(self):
        layout = QVBoxLayout(self.tab_dashboard)

        # 1. Source Connection Toolbar
        src_box = QGroupBox("GNSS Input Interface (Automatic Detection / File Replay / Simulator)")
        src_layout = QHBoxLayout(src_box)

        src_layout.addWidget(QLabel("COM Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(110)
        self.refresh_serial_ports()
        src_layout.addWidget(self.port_combo)

        src_layout.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "921600"])
        self.baud_combo.setCurrentText("115200")
        src_layout.addWidget(self.baud_combo)

        self.btn_refresh_ports = QPushButton("⟳")
        self.btn_refresh_ports.setToolTip("Auto-Scan COM Ports")
        self.btn_refresh_ports.clicked.connect(self.refresh_serial_ports)
        src_layout.addWidget(self.btn_refresh_ports)

        self.btn_connect = QPushButton("Connect Live")
        self.btn_connect.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 5px 12px;")
        self.btn_connect.clicked.connect(self.toggle_live_connection)
        src_layout.addWidget(self.btn_connect)

        src_layout.addWidget(self.create_vsep())

        self.btn_stream_file = QPushButton("📁 Upload / Stream NMEA File")
        self.btn_stream_file.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold; padding: 5px 12px;")
        self.btn_stream_file.clicked.connect(self.toggle_stream_file)
        src_layout.addWidget(self.btn_stream_file)

        src_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["1x (Real-Time)", "2x", "5x (Fast)", "Max Speed"])
        self.speed_combo.setCurrentText("5x (Fast)")
        src_layout.addWidget(self.speed_combo)

        src_layout.addWidget(self.create_vsep())

        self.btn_sim = QPushButton("▶ Run Sim")
        self.btn_sim.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 5px 12px;")
        self.btn_sim.clicked.connect(self.toggle_simulator)
        src_layout.addWidget(self.btn_sim)

        src_layout.addStretch()
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #555;")
        src_layout.addWidget(self.lbl_status)
        layout.addWidget(src_box)

        # 2. Constellation Filter Selector Bar
        filter_box = QGroupBox("Constellation Filter & Isolation Mode")
        filter_layout = QHBoxLayout(filter_box)
        filter_layout.setContentsMargins(10, 4, 10, 4)

        self.filter_group = QButtonGroup(self)
        filter_options = [
            ("All Constellations", "ALL"),
            ("NavIC (IRNSS) Only", "NAVIC"),
            ("GPS Only", "GPS"),
            ("BeiDou Only", "BEIDOU"),
            ("GLONASS Only", "GLONASS"),
            ("Galileo Only", "GALILEO")
        ]

        for text, key in filter_options:
            rb = QRadioButton(text)
            if key == "ALL":
                rb.setChecked(True)
            rb.setStyleSheet("font-weight: bold; font-size: 11px; padding: 2px 6px;")
            rb.toggled.connect(lambda checked, k=key: self.set_constellation_filter(k) if checked else None)
            self.filter_group.addButton(rb)
            filter_layout.addWidget(rb)

        filter_layout.addStretch()
        layout.addWidget(filter_box)

        # 3. Main Splitter View
        center_split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(center_split)

        # Left Column: Coordinates & Satellite Details Table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        metrics_box = QGroupBox("Navigation & Solution Status (Decimal Degrees)")
        grid = QGridLayout(metrics_box)
        grid.setSpacing(6)

        self.val_fix = self.create_metric_cell("GNSS Fix Status", "No Fix", "#C0392B")
        self.val_coords_dd = self.create_metric_cell("Coordinates (Decimal Degrees)", "Lat: 0.000000°   Lon: 0.000000°", "#2C3E50")
        self.val_coords_dms = self.create_metric_cell("Coordinates (Deg / Min)", "00° 00.0000' N   00° 00.0000' E", "#2C3E50")
        self.val_used = self.create_metric_cell("Sats in Solution", "0", "#2C3E50")
        self.val_dop = self.create_metric_cell("PDOP / VDOP / HDOP", "- / - / -", "#2C3E50")

        grid.addWidget(self.val_fix[0], 0, 0)
        grid.addWidget(self.val_coords_dd[0], 0, 1)
        grid.addWidget(self.val_coords_dms[0], 1, 1)
        grid.addWidget(self.val_used[0], 1, 0)
        grid.addWidget(self.val_dop[0], 2, 0, 1, 2)
        left_layout.addWidget(metrics_box)

        self.sat_table = QTableWidget(0, 6)
        self.sat_table.setHorizontalHeaderLabels(["Constellation", "PRN", "Elev(°)", "Azim(°)", "SNR / C/N₀", "Health"])
        self.sat_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sat_table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.sat_table)
        center_split.addWidget(left_widget)

        # Right Column: Polar Sky View & SNR Bars
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Dedicated Color-Coded Satellite Legend Bar
        legend_frame = QFrame()
        legend_frame.setStyleSheet("background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 4px; padding: 2px;")
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(6, 2, 6, 2)

        self.legend_labels = {}
        for const, cfg in CONSTELLATION_CONFIG.items():
            lbl = QLabel(f"● {cfg['badge']}: 0")
            lbl.setStyleSheet(f"color: {cfg['color']}; font-weight: bold; font-size: 11px;")
            legend_layout.addWidget(lbl)
            self.legend_labels[const] = lbl
        legend_layout.addStretch()
        right_layout.addWidget(legend_frame)

        self.fig_sky = Figure(facecolor="#F8F9FA")
        self.canvas_sky = FigureCanvas(self.fig_sky)
        self.ax_sky = self.fig_sky.add_subplot(111, polar=True)
        self.setup_polar_plot()
        right_layout.addWidget(self.canvas_sky, stretch=3)

        self.fig_snr = Figure(facecolor="#F8F9FA")
        self.canvas_snr = FigureCanvas(self.fig_snr)
        self.ax_snr = self.fig_snr.add_subplot(111)
        self.setup_snr_plot()
        right_layout.addWidget(self.canvas_snr, stretch=2)

        center_split.addWidget(right_widget)
        center_split.setSizes([580, 680])

    def set_constellation_filter(self, key):
        self.selected_filter = key
        self.update_live_ui()

    def create_vsep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def create_metric_cell(self, title, default_val, text_color):
        frame = QFrame()
        frame.setStyleSheet("background-color: #ECF0F1; border-radius: 4px; padding: 4px;")
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(4, 4, 4, 4)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #7F8C8D;")
        lbl_val = QLabel(default_val)
        lbl_val.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {text_color};")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)
        return frame, lbl_val

    def init_logger_tab(self):
        layout = QVBoxLayout(self.tab_logger)

        log_box = QGroupBox("NMEA Data Logger & Evaluator Output")
        log_layout = QGridLayout(log_box)

        log_layout.addWidget(QLabel("Save Directory:"), 0, 0)
        self.txt_out_dir = QLineEdit(os.path.expanduser("~"))
        log_layout.addWidget(self.txt_out_dir, 0, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_output_dir)
        log_layout.addWidget(self.btn_browse, 0, 2)

        self.btn_start_log = QPushButton("▶ Start Recording NMEA")
        self.btn_start_log.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 7px;")
        self.btn_start_log.clicked.connect(self.start_logging)
        log_layout.addWidget(self.btn_start_log, 1, 0)

        self.btn_stop_log = QPushButton("⏹ Stop Recording")
        self.btn_stop_log.setStyleSheet("background-color: #C0392B; color: white; font-weight: bold; padding: 7px;")
        self.btn_stop_log.setEnabled(False)
        self.btn_stop_log.clicked.connect(self.stop_logging)
        log_layout.addWidget(self.btn_stop_log, 1, 1)

        self.btn_export_evaluator = QPushButton("📋 Generate Evaluator Report (Decimal Degrees)")
        self.btn_export_evaluator.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 7px;")
        self.btn_export_evaluator.clicked.connect(self.generate_evaluator_file)
        log_layout.addWidget(self.btn_export_evaluator, 1, 2)

        self.lbl_log_stats = QLabel("Records Saved: 0 | Evaluator Records: 0 | Elapsed: 00:00:00")
        self.lbl_log_stats.setStyleSheet("font-weight: bold; font-size: 13px; color: #2C3E50;")
        log_layout.addWidget(self.lbl_log_stats, 2, 0, 1, 3)
        layout.addWidget(log_box)

        raw_box = QGroupBox("Live NMEA Feed Stream")
        raw_layout = QVBoxLayout(raw_box)
        self.txt_terminal = QTextEdit()
        self.txt_terminal.setReadOnly(True)
        self.txt_terminal.setStyleSheet("background-color: #121212; color: #00E676; font-family: Consolas, monospace; font-size: 11px;")
        raw_layout.addWidget(self.txt_terminal)
        layout.addWidget(raw_box)

    def init_reports_tab(self):
        layout = QVBoxLayout(self.tab_reports)

        top_bar = QHBoxLayout()
        self.btn_load_csv = QPushButton("📂 Load Logged NMEA File")
        self.btn_load_csv.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_load_csv.clicked.connect(self.load_dataset_for_analysis)
        top_bar.addWidget(self.btn_load_csv)

        self.lbl_dataset_name = QLabel("No dataset loaded.")
        self.lbl_dataset_name.setStyleSheet("color: #7F8C8D; font-style: italic;")
        top_bar.addWidget(self.lbl_dataset_name)

        top_bar.addStretch()

        self.btn_export_plots = QPushButton("Export Publication Plots")
        self.btn_export_plots.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold; padding: 6px 14px;")
        self.btn_export_plots.clicked.connect(self.export_plots)
        top_bar.addWidget(self.btn_export_plots)
        layout.addLayout(top_bar)

        self.report_stats_box = QGroupBox("Mission Analytical Summary")
        stats_layout = QHBoxLayout(self.report_stats_box)
        self.lbl_stat_avail = QLabel("Availability: --%")
        self.lbl_stat_sats = QLabel("Avg NavIC/GPS Sats: --")
        self.lbl_stat_pdop = QLabel("Mean HDOP: --")
        self.lbl_stat_cno = QLabel("Constellation Mode: --")

        for lbl in [self.lbl_stat_avail, self.lbl_stat_sats, self.lbl_stat_pdop, self.lbl_stat_cno]:
            lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #34495E;")
            stats_layout.addWidget(lbl)
        layout.addWidget(self.report_stats_box)

        self.fig_report = Figure(figsize=(10, 6), facecolor="#FFFFFF")
        self.canvas_report = FigureCanvas(self.fig_report)
        layout.addWidget(self.canvas_report)

    # --- Plot Layout Setups ---
    def setup_polar_plot(self):
        self.ax_sky.clear()
        self.ax_sky.set_theta_zero_location('N')
        self.ax_sky.set_theta_direction(-1)
        self.ax_sky.set_ylim(0, 90)
        self.ax_sky.set_yticks([30, 60, 90])
        self.ax_sky.set_yticklabels(['60°', '30°', '0°'], fontsize=8)
        self.ax_sky.set_title("Polar Sky View (Azimuth vs Elevation)", fontsize=11, fontweight='bold', pad=12)
        self.ax_sky.grid(True, linestyle="--", alpha=0.6)

    def setup_snr_plot(self):
        self.ax_snr.clear()
        self.ax_snr.set_title("Carrier-to-Noise Density (SNR / C/N₀)", fontsize=10, fontweight='bold')
        self.ax_snr.set_ylim(0, 55)
        self.ax_snr.set_ylabel("C/N₀ (dB-Hz)", fontsize=8)
        self.ax_snr.grid(True, axis='y', linestyle=":", alpha=0.7)

    # --- Hardware & Streaming Handlers ---
    def refresh_serial_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
        if not ports:
            self.port_combo.addItem("No COM Ports Found")

    def toggle_live_connection(self):
        if not self.worker.running:
            selected_port = self.port_combo.currentText().strip()
            if selected_port == "No COM Ports Found" or not selected_port:
                QMessageBox.warning(
                    self, "No COM Port Detected",
                    "No hardware serial ports found.\n"
                    "1. Connect your receiver USB cable.\n"
                    "2. Click ⟳ to refresh.\n"
                    "3. Or use 'Upload / Stream NMEA File' to test your collected data."
                )
                return

            baud = int(self.baud_combo.currentText())
            self.worker.start_serial(selected_port, baud)
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setStyleSheet("background-color: #E74C3C; color: white;")
            self.btn_stream_file.setEnabled(False)
            self.btn_sim.setEnabled(False)
        else:
            self.worker.stop()
            self.reset_source_buttons()

    def toggle_stream_file(self):
        if not self.worker.running:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Select Recorded NMEA Data to Stream", "", "NMEA/Logs (*.nmea *.log *.txt *.csv);;All Files (*)"
            )
            if not filepath:
                return

            speed_map = {"1x (Real-Time)": 1.0, "2x": 2.0, "5x (Fast)": 5.0, "Max Speed": 35.0}
            speed = speed_map.get(self.speed_combo.currentText(), 5.0)

            self.worker.start_file_stream(filepath, speed)
            self.btn_stream_file.setText("⏹ Stop Stream")
            self.btn_stream_file.setStyleSheet("background-color: #E74C3C; color: white;")
            self.btn_connect.setEnabled(False)
            self.btn_sim.setEnabled(False)
        else:
            self.worker.stop()
            self.reset_source_buttons()

    def toggle_simulator(self):
        if not self.worker.running:
            self.worker.start_simulator()
            self.btn_sim.setText("⏹ Stop Sim")
            self.btn_sim.setStyleSheet("background-color: #E74C3C; color: white;")
            self.btn_connect.setEnabled(False)
            self.btn_stream_file.setEnabled(False)
        else:
            self.worker.stop()
            self.reset_source_buttons()

    def reset_source_buttons(self):
        self.btn_connect.setText("Connect Live")
        self.btn_connect.setStyleSheet("background-color: #27AE60; color: white;")
        self.btn_connect.setEnabled(True)

        self.btn_stream_file.setText("📁 Upload / Stream NMEA File")
        self.btn_stream_file.setStyleSheet("background-color: #8E44AD; color: white;")
        self.btn_stream_file.setEnabled(True)

        self.btn_sim.setText("▶ Run Sim")
        self.btn_sim.setStyleSheet("background-color: #2980B9; color: white;")
        self.btn_sim.setEnabled(True)

    def on_connection_changed(self, connected, msg):
        self.lbl_status.setText(f"Status: {msg}")
        if not connected:
            self.reset_source_buttons()

    def on_file_progress(self, current, total):
        self.lbl_status.setText(f"Streaming File: {current}/{total} ({(current/total)*100:.0f}%)")

    # --- Live Sentence Parsing Engine ---
    def process_nmea_sentence(self, sentence):
        self.txt_terminal.append(sentence)
        if len(self.txt_terminal.toPlainText()) > 15000:
            self.txt_terminal.clear()

        # Immediate stream recording into NMEA file
        if self.is_logging and self.log_file:
            try:
                self.log_file.write(f"{sentence}\n")
                self.log_file.flush()
                os.fsync(self.log_file.fileno())
                self.log_records_count += 1
            except Exception:
                self.log_error_count += 1

        if len(sentence) < 6 or not sentence.startswith('$'):
            return

        talker = sentence[1:3]
        msg_type = sentence[3:6]

        try:
            if msg_type == 'GGA':
                parts = sentence.split('*')[0].split(',')
                utc_raw = parts[1] if len(parts) > 1 else ""
                lat_raw, lat_dir = (parts[2], parts[3]) if len(parts) > 3 else ("", "")
                lon_raw, lon_dir = (parts[4], parts[5]) if len(parts) > 5 else ("", "")
                fix_val = int(parts[6]) if len(parts) > 6 and parts[6] else 0
                num_sats = int(parts[7]) if len(parts) > 7 and parts[7] else 0
                hdop_val = float(parts[8]) if len(parts) > 8 and parts[8] else np.nan
                alt_val = float(parts[9]) if len(parts) > 9 and parts[9] else np.nan

                lat_dd = parse_nmea_coord_to_decimal(lat_raw, lat_dir)
                lon_dd = parse_nmea_coord_to_decimal(lon_raw, lon_dir)

                fix_map = {0: "Invalid", 1: "GNSS SPS (Standalone)", 2: "DGPS Fix", 4: "RTK Fixed", 5: "RTK Float"}
                self.val_fix[1].setText(fix_map.get(fix_val, "Fix Acquired"))
                self.val_fix[1].setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#27AE60' if fix_val > 0 else '#C0392B'};")

                # Decimal Degrees and DMS update
                self.val_coords_dd[1].setText(f"Lat: {lat_dd:0.6f}°   Lon: {lon_dd:0.6f}°")
                if lat_raw and lon_raw:
                    lat_deg = int(lat_raw[:2])
                    lat_min = float(lat_raw[2:])
                    lon_deg = int(lon_raw[:3])
                    lon_min = float(lon_raw[3:])
                    self.val_coords_dms[1].setText(f"{lat_deg}° {lat_min:06.4f}' {lat_dir}   {lon_deg}° {lon_min:06.4f}' {lon_dir}")

                self.val_used[1].setText(str(num_sats))

                navic_count = sum(1 for v in self.satellites.values() if "NavIC" in v['constellation'])
                gps_count = sum(1 for v in self.satellites.values() if v['constellation'] == 'GPS')
                beidou_count = sum(1 for v in self.satellites.values() if v['constellation'] == 'BeiDou')

                self.evaluator_records.append({
                    'timestamp_utc': utc_raw,
                    'latitude_decimal_deg': lat_dd,
                    'longitude_decimal_deg': lon_dd,
                    'fix_status': fix_map.get(fix_val, "Fix"),
                    'fix_valid': 1 if fix_val > 0 else 0,
                    'total_satellites': num_sats,
                    'navic_satellites': navic_count,
                    'gps_satellites': gps_count,
                    'beidou_satellites': beidou_count,
                    'hdop': hdop_val,
                    'vdop': self.latest_dop['vdop'],
                    'pdop': self.latest_dop['pdop'],
                    'altitude_meters': alt_val
                })

            elif msg_type == 'GSA':
                parts = sentence.split('*')[0].split(',')
                if len(parts) >= 18:
                    pdop = parts[15] if parts[15] else "-"
                    hdop = parts[16] if parts[16] else "-"
                    vdop = parts[17] if parts[17] else "-"
                    self.val_dop[1].setText(f"P: {pdop} | H: {hdop} | V: {vdop}")
                    try:
                        self.latest_dop['pdop'] = float(pdop) if pdop != "-" else np.nan
                        self.latest_dop['hdop'] = float(hdop) if hdop != "-" else np.nan
                        self.latest_dop['vdop'] = float(vdop) if vdop != "-" else np.nan
                    except:
                        pass

            elif msg_type == 'GSV':
                parts = sentence.split('*')[0].split(',')
                idx = 4
                while idx + 3 < len(parts):
                    prn = parts[idx]
                    elev = parts[idx + 1]
                    azim = parts[idx + 2]
                    snr = parts[idx + 3]
                    idx += 4

                    if prn and prn.strip():
                        constellation = identify_constellation(talker, prn, sentence)
                        key = (constellation, prn)
                        self.satellites[key] = {
                            'prn': prn,
                            'talker': talker,
                            'constellation': constellation,
                            'elev': float(elev) if elev and elev.strip() else 0.0,
                            'azim': float(azim) if azim and azim.strip() else 0.0,
                            'snr': float(snr) if snr and snr.strip() else 0.0,
                            'health': 'OK' if (snr and float(snr) > 15) else 'Degraded',
                            'updated': time.time()
                        }
        except Exception:
            self.log_error_count += 1

    # --- Live Render Loop with Constellation Filtering ---
    def setup_refresh_timers(self):
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_live_ui)
        self.ui_timer.start(1000)

    def update_live_ui(self):
        current_time = time.time()
        # Keep satellites active if seen within the last 10 seconds
        active_sats = {k: v for k, v in self.satellites.items() if current_time - v['updated'] < 10.0}
        self.satellites = active_sats

        # Update dedicated constellation counts in legend
        counts = {const: 0 for const in CONSTELLATION_CONFIG}
        for sat in active_sats.values():
            if sat['constellation'] in counts:
                counts[sat['constellation']] += 1

        for const, lbl in self.legend_labels.items():
            badge = CONSTELLATION_CONFIG[const]['badge']
            lbl.setText(f"● {badge}: {counts[const]}")

        # Apply constellation filter
        filtered_sats = {}
        for k, v in active_sats.items():
            if self.selected_filter == "ALL":
                filtered_sats[k] = v
            elif self.selected_filter == "NAVIC" and "NavIC" in v['constellation']:
                filtered_sats[k] = v
            elif self.selected_filter == "GPS" and v['constellation'] == "GPS":
                filtered_sats[k] = v
            elif self.selected_filter == "BEIDOU" and v['constellation'] == "BeiDou":
                filtered_sats[k] = v
            elif self.selected_filter == "GLONASS" and v['constellation'] == "GLONASS":
                filtered_sats[k] = v
            elif self.selected_filter == "GALILEO" and v['constellation'] == "Galileo":
                filtered_sats[k] = v

        # 1. Update Satellite Table
        self.sat_table.setRowCount(len(filtered_sats))
        for row, (k, sat) in enumerate(filtered_sats.items()):
            self.sat_table.setItem(row, 0, QTableWidgetItem(sat['constellation']))
            self.sat_table.setItem(row, 1, QTableWidgetItem(str(sat['prn'])))
            self.sat_table.setItem(row, 2, QTableWidgetItem(f"{sat['elev']:.0f}"))
            self.sat_table.setItem(row, 3, QTableWidgetItem(f"{sat['azim']:.0f}"))
            self.sat_table.setItem(row, 4, QTableWidgetItem(f"{sat['snr']:.1f}"))
            h_item = QTableWidgetItem(sat['health'])
            h_item.setForeground(QColor("#27AE60") if sat['health'] == 'OK' else QColor("#E67E22"))
            self.sat_table.setItem(row, 5, h_item)

        # 2. Update Sky View Plot
        self.setup_polar_plot()
        for k, sat in filtered_sats.items():
            if sat['elev'] > 0:
                theta = np.deg2rad(sat['azim'])
                r = 90.0 - sat['elev']
                cfg = CONSTELLATION_CONFIG.get(sat['constellation'], {'color': '#333333'})
                self.ax_sky.scatter(theta, r, c=cfg['color'], s=150, edgecolors='black', alpha=0.85, zorder=5)
                self.ax_sky.text(theta, r, f" {sat['prn']}", fontsize=8, fontweight='bold', color='#111', zorder=6)
        self.canvas_sky.draw_idle()

        # 3. Update SNR Bars
        self.setup_snr_plot()
        if filtered_sats:
            labels = [f"{v['constellation'][0]}:{v['prn']}" for v in filtered_sats.values()]
            snrs = [v['snr'] for v in filtered_sats.values()]
            colors = [CONSTELLATION_CONFIG.get(v['constellation'], {}).get('color', '#34495E') for v in filtered_sats.values()]

            bars = self.ax_snr.bar(labels, snrs, color=colors, width=0.6, edgecolor='#2C3E50', linewidth=0.5)
            self.ax_snr.tick_params(axis='x', rotation=45, labelsize=8)
            for bar, snr in zip(bars, snrs):
                if snr > 0:
                    self.ax_snr.text(bar.get_x() + bar.get_width() / 2, snr + 1, f"{int(snr)}",
                                     ha='center', va='bottom', fontsize=7, fontweight='bold')
        self.canvas_snr.draw_idle()

        # 4. Update Logging Stats
        if self.is_logging and self.logging_start_time:
            elapsed = int(time.time() - self.logging_start_time)
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            self.lbl_log_stats.setText(
                f"Records Saved: {self.log_records_count:,} | Evaluator Records: {len(self.evaluator_records)} | Elapsed: {h:02d}:{m:02d}:{s:02d}"
            )

    # --- Live File Logging ---
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if directory:
            self.txt_out_dir.setText(directory)

    def start_logging(self):
        out_dir = self.txt_out_dir.text().strip()
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        filename = f"GNSS_NavIC_Raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.nmea"
        self.log_filepath = os.path.join(out_dir, filename)

        try:
            self.log_file = open(self.log_filepath, "w", buffering=1, encoding="ascii", errors="replace")
            self.is_logging = True
            self.log_records_count = 0
            self.log_error_count = 0
            self.evaluator_records.clear()
            self.logging_start_time = time.time()
            self.btn_start_log.setEnabled(False)
            self.btn_stop_log.setEnabled(True)
            QMessageBox.information(self, "Logging Started", f"Recording live NMEA stream to:\n{self.log_filepath}")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Unable to create log file:\n{e}")

    def stop_logging(self):
        self.is_logging = False
        if self.log_file:
            self.log_file.flush()
            os.fsync(self.log_file.fileno())
            self.log_file.close()
            self.log_file = None
        self.btn_start_log.setEnabled(True)
        self.btn_stop_log.setEnabled(False)
        QMessageBox.information(
            self, "Log Saved",
            f"Successfully recorded {self.log_records_count} sentences.\n"
            f"Evaluator records ready: {len(self.evaluator_records)}.\n"
            "Click 'Generate Evaluator Report' to export decimal degrees."
        )

    # --- Evaluator File Exporter in Decimal Degrees ---
    def generate_evaluator_file(self):
        if not self.evaluator_records:
            QMessageBox.warning(self, "No Records", "No streamed or recorded records to evaluate yet. Run a stream or simulation first.")
            return

        df = pd.DataFrame(self.evaluator_records)
        default_name = f"GNSS_NavIC_Evaluator_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Evaluator Data File", default_name, "CSV Spreadsheet (*.csv);;Text Report (*.txt)")

        if not filepath:
            return

        total_epochs = len(df)
        valid_fixes = int(df['fix_valid'].sum())
        avail = (valid_fixes / total_epochs * 100) if total_epochs > 0 else 0
        avg_hdop = df['hdop'].mean()
        avg_sats = df['total_satellites'].mean()
        avg_navic = df['navic_satellites'].mean()
        avg_gps = df['gps_satellites'].mean()

        header_lines = [
            "# ========================================================",
            "# PROJECT EVALUATION REPORT: GNSS & NavIC MISSION ANALYSIS",
            f"# Generated Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total Positioning Epochs: {total_epochs}",
            f"# Solution Availability: {avail:.2f}%",
            f"# Mean HDOP Dilution: {avg_hdop:.2f}",
            f"# Mean Satellites Tracked: {avg_sats:.1f} (NavIC Mean: {avg_navic:.1f}, GPS Mean: {avg_gps:.1f})",
            "# Coordinate Format: Pure Decimal Degrees (DD.dddddd)",
            "# ========================================================\n"
        ]

        try:
            with open(filepath, 'w') as f:
                f.write("\n".join(header_lines))
                df.to_csv(f, index=False, float_format="%.6f")

            QMessageBox.information(
                self, "Evaluator File Created",
                f"Evaluator report saved successfully to:\n{filepath}\n\n"
                f"Metrics:\n- Availability: {avail:.2f}%\n- Mean HDOP: {avg_hdop:.2f}\n- Coordinates: Decimal Degrees (DD)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save evaluator file:\n{e}")

    # --- Post Analysis Report Tab ---
    def load_dataset_for_analysis(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Recorded NMEA Log", "", "NMEA/Logs (*.nmea *.log *.csv *.txt);;All Files (*)"
        )
        if not filepath:
            return

        self.lbl_dataset_name.setText(os.path.basename(filepath))
        records = []
        with open(filepath, 'r', errors='replace') as f:
            for line in f:
                line = line.strip()
                if '$' in line:
                    sentence = line[line.find('$'):]
                    self.process_nmea_sentence(sentence)

                    if 'GGA' in sentence:
                        parts = sentence.split('*')[0].split(',')
                        try:
                            records.append({
                                'time': parts[1],
                                'valid': 1 if int(parts[6]) > 0 else 0,
                                'sats': int(parts[7]) if parts[7] else 0,
                                'hdop': float(parts[8]) if parts[8] else np.nan,
                                'alt': float(parts[9]) if len(parts) > 9 and parts[9] else np.nan
                            })
                        except:
                            continue

        if records:
            df = pd.DataFrame(records)
            self.render_academic_report(df)
            self.tabs.setCurrentIndex(2)

    def render_academic_report(self, df):
        self.fig_report.clear()
        total = len(df)
        valid_cnt = df['valid'].sum()
        avail = (valid_cnt / total * 100) if total > 0 else 0.0

        self.lbl_stat_avail.setText(f"Positioning Availability: {avail:.2f}%")
        self.lbl_stat_sats.setText(f"Avg Satellites: {df['sats'].mean():.1f}")
        self.lbl_stat_pdop.setText(f"Mean HDOP: {df['hdop'].mean():.2f}")
        self.lbl_stat_cno.setText("Multi-Constellation Solution Active")

        axs = self.fig_report.subplots(2, 2)
        self.fig_report.subplots_adjust(hspace=0.35, wspace=0.25)

        axs[0, 0].plot(df.index, df['sats'], color='#1976D2', lw=1.5)
        axs[0, 0].set_title("Satellites Used in Solution Over Time", fontsize=9, fontweight='bold')
        axs[0, 0].grid(True, linestyle=":")

        hdop_clean = df['hdop'].dropna()
        if not hdop_clean.empty:
            axs[0, 1].hist(hdop_clean, bins=20, color='#2E7D32', edgecolor='black', alpha=0.7)
        axs[0, 1].set_title("HDOP Precision Distribution", fontsize=9, fontweight='bold')
        axs[0, 1].grid(True, linestyle=":")

        axs[1, 0].plot(df.index, df['alt'], color='#E65100', lw=1.2)
        axs[1, 0].set_title("Reported Altitude Profile (m)", fontsize=9, fontweight='bold')
        axs[1, 0].grid(True, linestyle=":")

        axs[1, 1].pie([valid_cnt, max(0, total - valid_cnt)], labels=['Valid Fix', 'No Fix'],
                      colors=['#2ECC71', '#E74C3C'], autopct='%1.1f%%', startangle=90)
        axs[1, 1].set_title("Solution Availability Ratio", fontsize=9, fontweight='bold')

        self.canvas_report.draw()

    def export_plots(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Report Graph", "Mission_Analysis_Plots.png", "PNG Image (*.png);;PDF (*.pdf)")
        if filepath:
            self.fig_report.savefig(filepath, dpi=300)
            QMessageBox.information(self, "Export Complete", f"Saved high-res figures to:\n{filepath}")

    def closeEvent(self, event):
        self.worker.stop()
        if self.log_file:
            self.log_file.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GNSSLoggerApp()
    window.show()
    sys.exit(app.exec())
