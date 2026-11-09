import os
import sys
import tkinter as tk
from evaluator_app import StandaloneEvaluatorApp
from core.plotter import GNSSPlotter

def test_all_scenarios():
    root = tk.Tk()
    root.withdraw() # Headless GUI test
    app = StandaloneEvaluatorApp(root)

    # -------------------------------------------------------------
    # Scenario 1: Standard Valid NMEA Logger File (100+ fixes)
    # -------------------------------------------------------------
    file_standard = "data/samples/sample_logger_output.txt"
    print(f"\n[TEST 1] Testing standard file: {file_standard}")
    val1 = app.evaluator.validate_nmea_file(file_standard)
    assert val1["is_valid"] == True
    print("  Validation passed:", val1["title"])

    # Simulate upload processing
    app.current_loaded_file = file_standard
    app.evaluator.process_path(file_standard)
    res1 = app.evaluator.evaluate(session_name="Standard_Test")
    app.current_results = res1
    assert res1["status"] == "SUCCESS"
    print(f"  Evaluate passed: CEP={res1['accuracy_dispersion']['cep_50_m']}m, Grade={res1['overall_grade']}")

    # Render plots in-place
    acc = res1['accuracy_dispersion']
    GNSSPlotter.plot_enu_dispersion(acc['enu_points'], acc['cep_50_m'], acc['two_drms_95_m'], acc['vertical_dispersion_2sigma_m'], fig=app.fig_enu)
    app.canvas_enu.draw_idle()

    p = acc['cdf_percentiles']
    GNSSPlotter.plot_cdf_curve(acc['cdf_curve'], p['p50_cep'], p['p68_1sigma'], p['p95_2drms'], p['p99'], fig=app.fig_cdf)
    app.canvas_cdf.draw_idle()

    GNSSPlotter.plot_cno_vs_elevation(app.evaluator.satellite_obs, fig=app.fig_rf)
    app.canvas_rf.draw_idle()

    GNSSPlotter.plot_polar_skyplot(app.evaluator.satellite_obs, fig=app.fig_sky)
    app.canvas_sky.draw_idle()
    print("  All 4 plots rendered in-place successfully.")

    # Export Report
    report_file = app.reporter.generate_html_report(eval_results=res1, raw_log_file=file_standard)
    assert os.path.exists(report_file)
    print(f"  Report generated: {os.path.basename(report_file)}")

    # -------------------------------------------------------------
    # Scenario 2: File with 0 Position Fixes (GSV only / indoor)
    # -------------------------------------------------------------
    file_zero_fix = "data/samples/test_zero_fixes.txt"
    with open(file_zero_fix, "w", encoding="utf-8") as f:
        f.write("$GIGSV,2,1,06,02,58,142,44,03,64,195,45,04,52,230,41,05,48,115,42*6D\n")
        f.write("$GIGSV,2,2,06,06,62,178,43,07,39,265,38,,,,*6A\n")
        f.write("$GPGSV,2,1,06,10,72,085,42,12,45,310,38,15,31,140,36,23,60,215,41*7A\n")

    print(f"\n[TEST 2] Testing 0-fix file (GSV only): {file_zero_fix}")
    val2 = app.evaluator.validate_nmea_file(file_zero_fix)
    assert val2["is_valid"] == True
    print("  Validation passed:", val2["title"])

    app.current_loaded_file = file_zero_fix
    app.evaluator.process_path(file_zero_fix)
    res2 = app.evaluator.evaluate(session_name="Zero_Fix_Test")
    app.current_results = res2
    assert res2["status"] == "SUCCESS"
    print("  Evaluate 0-fix passed (no crash, zeroed accuracy pillar):", res2["accuracy_dispersion"]["cep_50_m"])

    # Render plots with 0 fixes
    acc2 = res2['accuracy_dispersion']
    GNSSPlotter.plot_enu_dispersion(acc2['enu_points'], acc2['cep_50_m'], acc2['two_drms_95_m'], acc2['vertical_dispersion_2sigma_m'], fig=app.fig_enu)
    app.canvas_enu.draw_idle()

    GNSSPlotter.plot_cno_vs_elevation(app.evaluator.satellite_obs, fig=app.fig_rf)
    app.canvas_rf.draw_idle()
    print("  Zero-fix plots handled gracefully.")

    # -------------------------------------------------------------
    # Scenario 3: File with exactly 1 Position Fix
    # -------------------------------------------------------------
    file_one_fix = "data/samples/test_one_fix.txt"
    with open(file_one_fix, "w", encoding="utf-8") as f:
        f.write("$GNGGA,090000.00,1258.4533,N,07735.6105,E,1,16,0.85,915.9,M,-85.2,M,,*6C\n")
        f.write("$GNRMC,090000.00,A,1258.4533,N,07735.6105,E,0.01,124.5,161026,,,A*73\n")
        f.write("$GIGSV,1,1,01,02,58,142,44*5F\n")

    print(f"\n[TEST 3] Testing 1-fix file: {file_one_fix}")
    val3 = app.evaluator.validate_nmea_file(file_one_fix)
    assert val3["is_valid"] == True
    app.evaluator.process_path(file_one_fix)
    res3 = app.evaluator.evaluate(session_name="One_Fix_Test")
    assert res3["status"] == "SUCCESS"
    print("  Evaluate 1-fix passed (no crash, zeroed dispersion):", res3["accuracy_dispersion"]["cep_50_m"])

    # -------------------------------------------------------------
    # Scenario 4: Invalid Text File
    # -------------------------------------------------------------
    file_invalid = "data/samples/test_invalid.txt"
    with open(file_invalid, "w", encoding="utf-8") as f:
        f.write("Some random non-nmea text content from another application\nJust lines without NMEA format.\n")

    print(f"\n[TEST 4] Testing invalid file: {file_invalid}")
    val4 = app.evaluator.validate_nmea_file(file_invalid)
    assert val4["is_valid"] == False
    print("  Validation correctly rejected invalid file:", val4["title"])

    print("\n==========================================")
    print("[SUCCESS] ALL STABILITY TESTS PASSED 100% WITHOUT CRASHING!")
    print("==========================================")
    root.destroy()

if __name__ == "__main__":
    test_all_scenarios()
