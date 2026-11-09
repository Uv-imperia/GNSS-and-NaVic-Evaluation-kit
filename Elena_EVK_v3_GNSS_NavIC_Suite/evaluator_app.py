"""
Elena Geo Tech EVK v3 — Standalone GNSS & NavIC Performance Evaluator App.

Workflow:
1. User clicks "📤 Upload NMEA Data File (.txt)" to select the text file extracted from the logger.
2. Evaluator automatically inspects and validates the uploaded file.
3. Displays a pop-up modal informing the user whether the text file contains VALID or INVALID NMEA data.
4. If valid, proceeds immediately to evaluate the 4 core benchmark pillars and updates all KPI cards and plots.
5. User can click "📄 Export PDF / HTML Report" anytime to export the final deliverable.
"""

import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.evaluator import GNSSEvaluator
from core.plotter import GNSSPlotter
from core.report_generator import ReportGenerator

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

class StandaloneEvaluatorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Elena Geo Tech EVK v3 — GNSS & NavIC Performance Evaluator")
        self.root.geometry("1240x860")
        self.root.minsize(1050, 720)
        self.root.configure(bg="#0b1120")

        self.evaluator = GNSSEvaluator()
        self.reporter = ReportGenerator(output_dir="data/reports")
        self.current_loaded_file = None
        self.current_results = None

        self._setup_theme()
        self._build_header_and_controls()
        self._build_kpi_cards()
        self._build_tabs()

        # Check if default sample txt exists or generate one for instant first-time testing
        demo_txt = "data/samples/sample_logger_output.txt"
        if not os.path.exists(demo_txt):
            source_sample = "data/samples/sample_elena_evk_navic.nmea"
            if os.path.exists(source_sample):
                with open(source_sample, 'r', encoding='utf-8') as src, open(demo_txt, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())

    def _setup_theme(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="#0b1120", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e293b", foreground="#94a3b8",
                        padding=[18, 9], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", "#2563eb")],
                  foreground=[("selected", "#ffffff")])

        style.configure("Treeview", background="#1e293b", foreground="#f8fafc",
                        fieldbackground="#1e293b", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#334155", foreground="#f8fafc",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#3b82f6")])

    def _build_header_and_controls(self):
        # Top Action Bar
        header = tk.Frame(self.root, bg="#1e293b", padx=20, pady=12)
        header.pack(fill=tk.X)

        t_box = tk.Frame(header, bg="#1e293b")
        t_box.pack(side=tk.LEFT)
        tk.Label(t_box, text="Elena EVK v3 Evaluator", font=("Segoe UI", 16, "bold"),
                 fg="#f97316", bg="#1e293b").pack(side=tk.LEFT, padx=(0, 12))

        self.status_badge = tk.Label(t_box, text="Waiting for NMEA .txt upload", font=("Segoe UI", 9, "bold"),
                                     bg="#334155", fg="#94a3b8", padx=10, pady=3)
        self.status_badge.pack(side=tk.LEFT)

        b_box = tk.Frame(header, bg="#1e293b")
        b_box.pack(side=tk.RIGHT)

        # Primary Upload Button for NMEA .txt file
        self.upload_btn = tk.Button(b_box, text="📤 Upload NMEA Data File (.txt)", font=("Segoe UI", 10, "bold"),
                                    bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
                                    padx=16, pady=6, relief=tk.FLAT, cursor="hand2", command=self.on_upload_file)
        self.upload_btn.pack(side=tk.LEFT, padx=6)

        # Report Export Button
        self.report_btn = tk.Button(b_box, text="📄 Export PDF / HTML Report", font=("Segoe UI", 9, "bold"),
                                    bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
                                    padx=14, pady=6, relief=tk.FLAT, cursor="hand2", state=tk.DISABLED,
                                    command=self.on_export_report)
        self.report_btn.pack(side=tk.LEFT, padx=6)

        # Secondary info bar
        info_bar = tk.Frame(self.root, bg="#111827", padx=20, pady=6)
        info_bar.pack(fill=tk.X)

        self.file_info_lbl = tk.Label(info_bar, text="Please upload a .txt file containing NMEA data extracted from the logger.",
                                      font=("Segoe UI", 9), fg="#94a3b8", bg="#111827")
        self.file_info_lbl.pack(side=tk.LEFT)

    def _build_kpi_cards(self):
        dash = tk.Frame(self.root, bg="#0b1120", padx=18, pady=8)
        dash.pack(fill=tk.X)

        self.card_acc_val, self.card_acc_sub = self._create_card(
            dash, "1. POSITIONING ACCURACY (ENU)", "CEP 50%: --", "2DRMS: -- | 2-Sigma: --", "#38bdf8"
        )
        self.card_acc = self.card_acc_val

        self.card_rf_val, self.card_rf_sub = self._create_card(
            dash, "2. RF SIGNAL QUALITY ($GSV)", "NavIC: -- dB-Hz", "GPS: -- dB-Hz | In Use: --", "#f97316"
        )
        self.card_rf = self.card_rf_val

        self.card_geom_val, self.card_geom_sub = self._create_card(
            dash, "3. SATELLITE GEOMETRY ($GSA)", "PDOP: --", "HDOP: -- | VDOP: --", "#10b981"
        )
        self.card_geom = self.card_geom_val

        self.card_rel_val, self.card_rel_sub = self._create_card(
            dash, "4. RELIABILITY & TEMPORAL", "Availability: --", "TTFF: -- | Grade: --", "#facc15"
        )
        self.card_rel = self.card_rel_val

    def _create_card(self, parent, title: str, default_val: str, default_sub: str, color: str):
        card = tk.Frame(parent, bg="#1e293b", padx=12, pady=7, relief=tk.FLAT,
                        highlightbackground="#334155", highlightthickness=1)
        card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=4)

        t_lbl = tk.Label(card, text=title, font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b")
        t_lbl.pack(anchor="w")

        v_lbl = tk.Label(card, text=default_val, font=("Segoe UI", 12, "bold"), fg=color, bg="#1e293b")
        v_lbl.pack(anchor="w", pady=(1, 0))

        s_lbl = tk.Label(card, text=default_sub, font=("Segoe UI", 8), fg="#cbd5e1", bg="#1e293b")
        s_lbl.pack(anchor="w", pady=(1, 0))

        return v_lbl, s_lbl

    def _build_tabs(self):
        tab_frame = tk.Frame(self.root, bg="#0b1120", padx=18, pady=4)
        tab_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(tab_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Positioning Accuracy & Dispersion (ENU)
        self.tab_acc = tk.Frame(self.notebook, bg="#0b1120")
        self.notebook.add(self.tab_acc, text="  1. Positioning & Dispersion (ENU)  ")
        self._build_accuracy_tab()

        # Tab 2: RF Signal Quality ($GSV)
        self.tab_rf = tk.Frame(self.notebook, bg="#0b1120")
        self.notebook.add(self.tab_rf, text="  2. RF Signal & Multipath  ")
        self._build_rf_tab()

        # Tab 3: Satellite Geometry & Skyplot ($GSA)
        self.tab_geom = tk.Frame(self.notebook, bg="#0b1120")
        self.notebook.add(self.tab_geom, text="  3. Geometry & Skyplot  ")
        self._build_geom_tab()

        # Tab 4: Fix Reliability & Temporal Attributes ($GGA)
        self.tab_rel = tk.Frame(self.notebook, bg="#0b1120")
        self.notebook.add(self.tab_rel, text="  4. Reliability & Temporal  ")
        self._build_reliability_tab()

    def _build_accuracy_tab(self):
        container = tk.Frame(self.tab_acc, bg="#0b1120", padx=6, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        self.fig_enu = plt.figure(figsize=(6, 5), facecolor='#0b1120')
        GNSSPlotter.plot_enu_dispersion([], 0.0, 0.0, 0.0, fig=self.fig_enu)
        self.canvas_enu = FigureCanvasTkAgg(self.fig_enu, master=container)
        self.canvas_enu.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.fig_cdf = plt.figure(figsize=(4.5, 5), facecolor='#0b1120')
        GNSSPlotter.plot_cdf_curve([], 0.0, 0.0, 0.0, 0.0, fig=self.fig_cdf)
        self.canvas_cdf = FigureCanvasTkAgg(self.fig_cdf, master=container)
        self.canvas_cdf.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4)

    def _build_rf_tab(self):
        container = tk.Frame(self.tab_rf, bg="#0b1120", padx=6, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        self.fig_rf = plt.figure(figsize=(5.5, 5), facecolor='#0b1120')
        GNSSPlotter.plot_cno_vs_elevation([], fig=self.fig_rf)
        self.canvas_rf = FigureCanvasTkAgg(self.fig_rf, master=container)
        self.canvas_rf.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        right_panel = tk.Frame(container, bg="#1e293b", padx=10, pady=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4)

        tk.Label(right_panel, text="Per-Satellite RF Tracking Matrix ($GSV)", font=("Segoe UI", 10, "bold"),
                 fg="#f8fafc", bg="#1e293b").pack(anchor="w", pady=(0, 6))

        cols = ("PRN", "Band", "Mean C/N0", "Peak", "Elev", "Used %")
        self.prn_tree = ttk.Treeview(right_panel, columns=cols, show="headings", height=14)
        for c in cols:
            self.prn_tree.heading(c, text=c)
            self.prn_tree.column(c, width=70, anchor="center")

        scroll = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=self.prn_tree.yview)
        self.prn_tree.configure(yscroll=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.prn_tree.pack(fill=tk.BOTH, expand=True)

    def _build_geom_tab(self):
        container = tk.Frame(self.tab_geom, bg="#0b1120", padx=6, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        self.fig_sky = plt.figure(figsize=(5.5, 5), facecolor='#0b1120')
        GNSSPlotter.plot_polar_skyplot([], fig=self.fig_sky)
        self.canvas_sky = FigureCanvasTkAgg(self.fig_sky, master=container)
        self.canvas_sky.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        right_panel = tk.Frame(container, bg="#1e293b", padx=16, pady=16)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4)

        tk.Label(right_panel, text="Dilution of Precision (DOP) Geometry", font=("Segoe UI", 12, "bold"),
                 fg="#f8fafc", bg="#1e293b").pack(anchor="w", pady=(0, 10))

        self.dop_text = tk.Label(right_panel, text="Upload a valid NMEA text file to view DOP statistics.",
                                 font=("Segoe UI", 10), fg="#94a3b8", bg="#1e293b", justify=tk.LEFT)
        self.dop_text.pack(anchor="w")

    def _build_reliability_tab(self):
        container = tk.Frame(self.tab_rel, bg="#0b1120", padx=16, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        self.rel_text = tk.Label(container, text="Upload a valid NMEA text file to view Fix Reliability & Continuity.",
                                 font=("Consolas", 11), fg="#38bdf8", bg="#0b1120", justify=tk.LEFT)
        self.rel_text.pack(anchor="nw", fill=tk.BOTH, expand=True)

    def on_upload_file(self):
        """
        Prompts user to select an NMEA data file (.txt).
        Validates content and displays a popup message whether valid or invalid.
        Proceeds with evaluation only if valid.
        Runs background ingestion to ensure the GUI remains 100% responsive.
        """
        file_path = filedialog.askopenfilename(
            title="Select NMEA Data File (.txt) Extracted from Logger",
            filetypes=[
                ("NMEA Text Files (*.txt)", "*.txt"),
                ("NMEA Files (*.nmea, *.log)", "*.nmea;*.log"),
                ("All Supported Files", "*.txt;*.nmea;*.log;*.dat"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        # 1. VALIDATION STEP
        val = GNSSEvaluator.validate_nmea_file(file_path)

        if not val['is_valid']:
            # POPUP INVALID MESSAGE
            self.status_badge.config(text="❌ Invalid NMEA File", bg="#7f1d1d", fg="#fca5a5")
            self.file_info_lbl.config(
                text=f"Upload Failed: '{os.path.basename(file_path)}' contains invalid NMEA data.",
                fg="#f87171"
            )
            messagebox.showerror(val['title'], val['message'])
            return

        # POPUP VALID MESSAGE
        messagebox.showinfo(val['title'], val['message'])

        # 2. ASYNC EVALUATION STEP (Non-blocking background thread)
        self.current_loaded_file = file_path
        self.upload_btn.config(state=tk.DISABLED, text="⏳ Processing...")
        self.status_badge.config(
            text="⏳ Evaluating NMEA Benchmarks...",
            bg="#1e3a8a", fg="#93c5fd"
        )
        self.file_info_lbl.config(
            text=f"Ingesting & evaluating '{val['file_name']}' across 4 pillars... UI active.",
            fg="#93c5fd"
        )
        self.root.update_idletasks()

        def worker():
            try:
                self.evaluator.process_path(file_path)
                session_name = os.path.splitext(os.path.basename(file_path))[0]
                res = self.evaluator.evaluate(session_name=session_name)
                self.root.after(0, lambda: self._apply_evaluation_results(res, val, file_path))
            except Exception as e:
                self.root.after(0, lambda: self._on_evaluation_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_evaluation_results(self, res: dict, val: dict, file_path: str):
        try:
            self.current_results = res
            self.upload_btn.config(state=tk.NORMAL, text="📤 Upload NMEA Data File (.txt)")
            self.report_btn.config(state=tk.NORMAL)

            self.status_badge.config(
                text=f"✅ Valid NMEA Data: {val['file_name']}",
                bg="#065f46", fg="#34d399"
            )
            self.file_info_lbl.config(
                text=f"Loaded File: {val['file_name']} | {val['valid_nmea_sentences']} valid sentences | Constellations: {', '.join(val['constellations'])}",
                fg="#34d399"
            )

            # 3. UPDATE KPI CARDS & PLOTS
            acc = res.get('accuracy_dispersion', {})
            rf = res.get('rf_signal_quality', {})
            geom = res.get('geometry_health', {})
            rel = res.get('reliability_temporal', {})

            cep_val = acc.get('cep_50_m', 0.0)
            two_drms_val = acc.get('two_drms_95_m', 0.0)
            vert_val = acc.get('vertical_dispersion_2sigma_m', 0.0)
            self.card_acc_val.config(text=f"CEP 50%: {cep_val} m")
            self.card_acc_sub.config(text=f"2DRMS: {two_drms_val}m | 2-Sigma: {vert_val}m")

            nav_cno = rf.get('band_separation', {}).get('navic_l5_s', {}).get('mean_cno', 0.0)
            gps_cno = rf.get('band_separation', {}).get('gps_l1_l5', {}).get('mean_cno', 0.0)
            used_sats = rf.get('satellites_tracking', {}).get('mean_n_used', 0.0)
            self.card_rf_val.config(text=f"NavIC: {nav_cno} dB-Hz")
            self.card_rf_sub.config(text=f"GPS: {gps_cno} dB-Hz | {used_sats} Sats")

            pdop_mean = geom.get('pdop', {}).get('mean', 0.0)
            pdop_health = geom.get('pdop', {}).get('health_assessment', 'N/A')
            health_tag = "Optimal" if "Optimal" in pdop_health else ("Good" if "Good" in pdop_health else "Degraded")
            hdop_mean = geom.get('hdop', {}).get('mean', 0.0)
            vdop_mean = geom.get('vdop', {}).get('mean', 0.0)
            self.card_geom_val.config(text=f"PDOP: {pdop_mean} ({health_tag})")
            self.card_geom_sub.config(text=f"HDOP: {hdop_mean} | VDOP: {vdop_mean}")

            avail_pct = rel.get('fix_availability_ratio_pct', 0.0)
            ttff = rel.get('ttff_seconds', 'N/A')
            grade = res.get('overall_grade', 'N/A')
            grade_short = grade.split()[0] if grade else "N/A"
            self.card_rel_val.config(text=f"{avail_pct}% Availability")
            self.card_rel_sub.config(text=f"TTFF: {ttff}s | Grade: {grade_short}")

            # In-place Plot Updating (Zero Tkinter canvas corruption & instant rendering)
            GNSSPlotter.plot_enu_dispersion(
                acc.get('enu_points', []),
                cep_val,
                two_drms_val,
                vert_val,
                fig=self.fig_enu
            )
            self.canvas_enu.draw_idle()

            p = acc.get('cdf_percentiles', {})
            GNSSPlotter.plot_cdf_curve(
                acc.get('cdf_curve', []),
                p.get('p50_cep', 0.0),
                p.get('p68_1sigma', 0.0),
                p.get('p95_2drms', 0.0),
                p.get('p99', 0.0),
                fig=self.fig_cdf
            )
            self.canvas_cdf.draw_idle()

            # RF Signal Plot
            GNSSPlotter.plot_cno_vs_elevation(self.evaluator.satellite_obs, fig=self.fig_rf)
            self.canvas_rf.draw_idle()

            # PRN Table
            for item in self.prn_tree.get_children():
                self.prn_tree.delete(item)
            for s in rf.get('per_prn_catalog', []):
                self.prn_tree.insert("", tk.END, values=(
                    f"{s.get('constellation', '')[:3]}-{s.get('prn', '')}",
                    s.get('band', ''),
                    f"{s.get('mean_cno', 0.0)} dB",
                    f"{s.get('peak_cno', 0.0)} dB",
                    f"{s.get('avg_elev', 0.0)}°",
                    f"{s.get('usage_rate_pct', 0.0)}%"
                ))

            # Geometry Skyplot
            GNSSPlotter.plot_polar_skyplot(self.evaluator.satellite_obs, fig=self.fig_sky)
            self.canvas_sky.draw_idle()

            hdop = geom.get('hdop', {})
            vdop = geom.get('vdop', {})
            pdop = geom.get('pdop', {})
            self.dop_text.config(text=f"""
HDOP (Horizontal Dilution):
  • Mean: {hdop.get('mean', 0.0)}  (Min: {hdop.get('min', 0.0)}, Max: {hdop.get('max', 0.0)})

VDOP (Vertical Dilution):
  • Mean: {vdop.get('mean', 0.0)}  (Min: {vdop.get('min', 0.0)}, Max: {vdop.get('max', 0.0)})

PDOP (3D Position Dilution):
  • Mean: {pdop.get('mean', 0.0)}  (Min: {pdop.get('min', 0.0)}, Max: {pdop.get('max', 0.0)})
  • Optimal (< 2.0): {pdop.get('optimal_sub2_pct', 0.0)}% of epochs
  • Degraded (> 3.5): {pdop.get('degraded_over3_5_pct', 0.0)}% of epochs
  • Health Assessment: {pdop.get('health_assessment', 'N/A')}
            """)

            # Reliability Text
            qb = rel.get('quality_breakdown', {})
            q_lines = "\n".join([f"  • {k}: {v} epochs" for k, v in qb.items() if v > 0]) or "  • None"
            ec = rel.get('epoch_continuity', {})
            self.rel_text.config(text=f"""
========================================================================
 PILLAR 4: FIX RELIABILITY & TEMPORAL ATTRIBUTES
========================================================================

1. Evaluated File:
   • {os.path.basename(file_path)}

2. Fix Availability:
   • Total Epochs Logged : {rel.get('total_epochs', 0)}
   • Valid Fix Epochs    : {rel.get('valid_epochs', 0)} ({rel.get('fix_availability_ratio_pct', 0.0)}%)
   • Time to First Fix   : {rel.get('ttff_seconds', 'No Fix')} seconds

3. Fix Quality Breakdown ($GGA Fix Indicator):
{q_lines}

4. Epoch Continuity & Rate Jitter:
   • Nominal Rate        : {ec.get('nominal_rate_hz', 1.0)} Hz (Interval: {ec.get('mean_interval_sec', 1.0)}s)
   • Rate Jitter (StdDev): ±{ec.get('jitter_sec', 0.0)}s
   • Dropped Frames      : {ec.get('dropped_frames', 0)} frames
   • Continuity Score    : {ec.get('continuity_pct', 100.0)}%
            """)

        except Exception as e:
            self._on_evaluation_error(e)

    def _on_evaluation_error(self, err: Exception):
        import traceback
        traceback.print_exc()
        self.upload_btn.config(state=tk.NORMAL, text="📤 Upload NMEA Data File (.txt)")
        self.status_badge.config(text="❌ Evaluation Failed", bg="#7f1d1d", fg="#fca5a5")
        messagebox.showerror("Evaluation Error", f"An error occurred while evaluating the file:\n{str(err)}")

    def on_export_report(self):
        if not self.current_results:
            messagebox.showwarning("No Data", "Please upload and evaluate an NMEA text file first.")
            return

        report_path = self.reporter.generate_html_report(
            eval_results=self.current_results,
            raw_log_file=self.current_loaded_file or "NMEA Upload"
        )
        abs_url = "file:///" + os.path.abspath(report_path).replace("\\", "/")
        webbrowser.open(abs_url)
        messagebox.showinfo("Report Ready", f"Engineering Evaluation Report successfully generated!\n\nLocation:\n{report_path}")

def launch():
    root = tk.Tk()
    app = StandaloneEvaluatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    launch()
