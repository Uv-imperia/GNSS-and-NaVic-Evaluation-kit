"""
Elena Geo Tech EVK v3 — Standalone GNSS & NavIC Performance Evaluator.
"""

import os
import sys
import argparse
import webbrowser

from core.evaluator import GNSSEvaluator
from core.plotter import GNSSPlotter
from core.report_generator import ReportGenerator

def run_cli_evaluation(target_path: str, ref_lat: float = None, ref_lon: float = None, ref_alt: float = None):
    print("\n" + "="*70)
    print(f" Elena Geo Tech EVK v3 Evaluation: {os.path.basename(target_path.rstrip(os.sep))}")
    print("="*70)

    ev = GNSSEvaluator(ref_lat=ref_lat, ref_lon=ref_lon, ref_alt=ref_alt)
    res_load = ev.process_path(target_path)

    if not res_load.get('success'):
        print(f"Error: {res_load.get('message')}")
        sys.exit(1)

    print(f"[OK] {res_load.get('message')}")

    res = ev.evaluate(session_name=os.path.basename(target_path.rstrip(os.sep)))
    if res.get('status') != 'SUCCESS':
        print(f"Evaluation failed: {res.get('message')}")
        sys.exit(1)

    acc = res['accuracy_dispersion']
    rf = res['rf_signal_quality']
    geom = res['geometry_health']
    rel = res['reliability_temporal']

    print(f"\n1. POSITIONING ACCURACY & DISPERSION (Local ENU):")
    print(f"   * CEP (50% Radius)      : {acc['cep_50_m']:.3f} meters")
    print(f"   * 2DRMS (95% Figure)    : {acc['two_drms_95_m']:.3f} meters")
    print(f"   * SEP (50% 3D Sphere)   : {acc['sep_3d_m']:.3f} meters")
    print(f"   * Vertical Dispersion   : {acc['vertical_dispersion_2sigma_m']:.3f} meters (2-sigma up)")
    print(f"   * CDF Boundaries        : P50={acc['cdf_percentiles']['p50_cep']}m, P68={acc['cdf_percentiles']['p68_1sigma']}m, P95={acc['cdf_percentiles']['p95_2drms']}m, P99={acc['cdf_percentiles']['p99']}m")

    print(f"\n2. RF SIGNAL QUALITY & TRACKING:")
    print(f"   * NavIC (L5/S-Band)     : Mean {rf['band_separation']['navic_l5_s']['mean_cno']} dB-Hz | Peak {rf['band_separation']['navic_l5_s']['peak_cno']} dB-Hz")
    print(f"   * GPS (L1/L5)           : Mean {rf['band_separation']['gps_l1_l5']['mean_cno']} dB-Hz | Peak {rf['band_separation']['gps_l1_l5']['peak_cno']} dB-Hz")
    print(f"   * <15 deg Multipath Zone: {rf['elevation_multipath_analysis']['low_elev_sub15_avg_cno']} dB-Hz (Attenuation: {rf['elevation_multipath_analysis']['multipath_attenuation_db']} dB)")
    print(f"   * Satellites (Used/View): {rf['satellites_tracking']['mean_n_used']} / {rf['satellites_tracking']['mean_n_view']} sats ({rf['satellites_tracking']['usage_efficiency_pct']}% usage)")

    print(f"\n3. SATELLITE GEOMETRY & CONSTELLATION HEALTH:")
    print(f"   * PDOP (3D Geometry)    : Mean {geom['pdop']['mean']} ({geom['pdop']['health_assessment']})")
    print(f"   * HDOP (Horizontal)     : Mean {geom['hdop']['mean']} | VDOP (Vertical): Mean {geom['vdop']['mean']}")
    print(f"   * Optimal (<2.0)        : {geom['pdop']['optimal_sub2_pct']}% of epochs")

    print(f"\n4. FIX RELIABILITY & TEMPORAL ATTRIBUTES:")
    print(f"   * Fix Availability      : {rel['fix_availability_ratio_pct']}% ({rel['valid_epochs']}/{rel['total_epochs']} epochs)")
    print(f"   * Time to First Fix     : {rel['ttff_seconds']} seconds")
    print(f"   * Rate & Jitter         : {rel['epoch_continuity']['nominal_rate_hz']} Hz (Jitter: +/-{rel['epoch_continuity']['jitter_sec']}s)")
    print(f"   * Dropped Frames        : {rel['epoch_continuity']['dropped_frames']} frames")
    print(f"   * Overall Grade         : {res['overall_grade']}")

    # Report
    rep = ReportGenerator(output_dir="data/reports")
    rep_path = rep.generate_html_report(res, raw_log_file=target_path)
    print(f"\n[OK] Report Generated: file:///{os.path.abspath(rep_path).replace(chr(92), '/')}")

    # Companion Plots
    plot_dir = "data/plots"
    os.makedirs(plot_dir, exist_ok=True)
    GNSSPlotter.plot_enu_dispersion(acc['enu_points'], acc['cep_50_m'], acc['two_drms_95_m'],
                                   acc['vertical_dispersion_2sigma_m'],
                                   save_path=os.path.join(plot_dir, "enu_dispersion.png"))
    GNSSPlotter.plot_cdf_curve(acc['cdf_curve'], acc['cdf_percentiles']['p50_cep'],
                               acc['cdf_percentiles']['p68_1sigma'], acc['cdf_percentiles']['p95_2drms'],
                               acc['cdf_percentiles']['p99'],
                               save_path=os.path.join(plot_dir, "error_cdf.png"))
    GNSSPlotter.plot_cno_vs_elevation(ev.satellite_obs,
                                      save_path=os.path.join(plot_dir, "cno_vs_elevation.png"))
    GNSSPlotter.plot_polar_skyplot(ev.satellite_obs,
                                   save_path=os.path.join(plot_dir, "polar_skyplot.png"))
    print(f"     Plots saved to {plot_dir}/")

    webbrowser.open("file:///" + os.path.abspath(rep_path).replace("\\", "/"))

def main():
    parser = argparse.ArgumentParser(description="Elena Geo Tech EVK v3 — Integrated Logger & Performance Evaluator")
    parser.add_argument("--logger", "-l", action="store_true", help="Launch Standalone PyQt6 NMEA Logger")
    parser.add_argument("--evaluator", action="store_true", help="Launch Standalone Tkinter 4-Pillars Evaluator App")
    parser.add_argument("--suite", "-s", action="store_true", help="Launch Integrated Mission Suite (Logger + Evaluator)")
    parser.add_argument("--evaluate", "-e", type=str, help="Path to NMEA file OR folder of files to evaluate")
    parser.add_argument("--ref-lat", type=float, help="Reference latitude for absolute accuracy")
    parser.add_argument("--ref-lon", type=float, help="Reference longitude for absolute accuracy")
    parser.add_argument("--ref-alt", type=float, help="Reference altitude (m) for absolute accuracy")
    parser.add_argument("--test", action="store_true", help="Run evaluation on sample Elena EVK v3 log")

    args = parser.parse_args()

    if args.test:
        sample = "data/samples/sample_elena_evk_navic.nmea"
        if not os.path.exists(sample):
            from data.generate_sample import generate_sample_nmea
            generate_sample_nmea(sample, 120)
        run_cli_evaluation(sample)
    elif args.evaluate:
        run_cli_evaluation(args.evaluate, ref_lat=args.ref_lat, ref_lon=args.ref_lon, ref_alt=args.ref_alt)
    elif args.logger:
        import sys
        from PyQt6.QtWidgets import QApplication
        from logger_app import GNSSLoggerApp
        app = QApplication(sys.argv)
        win = GNSSLoggerApp()
        win.show()
        sys.exit(app.exec())
    elif args.evaluator:
        from evaluator_app import launch
        launch()
    else:
        # Default: Launch Integrated Suite
        try:
            from integrated_app import launch_suite
            launch_suite()
        except ImportError:
            from evaluator_app import launch
            launch()

if __name__ == "__main__":
    main()
