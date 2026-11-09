import os
import sys

project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

def test_integration():
    print("Testing Integration between Logger and Evaluator...")

    # 1. Test Logger import
    import logger_app
    print("[OK] logger_app imported successfully.")

    # 2. Test Evaluator import
    from core.evaluator import GNSSEvaluator
    from core.plotter import GNSSPlotter
    from core.report_generator import ReportGenerator
    print("[OK] Core evaluator components imported successfully.")

    # 3. Test Integrated Suite import
    import integrated_app
    print("[OK] integrated_app imported successfully.")

    # 4. Test evaluation on sample file
    sample_path = os.path.join(project_dir, "data", "samples", "sample_elena_evk_navic.nmea")
    assert os.path.exists(sample_path), f"Sample file not found: {sample_path}"

    ev = GNSSEvaluator()
    res_load = ev.process_path(sample_path)
    assert res_load.get('success'), f"Failed to load sample: {res_load}"
    res = ev.evaluate(session_name="Integration_Test")
    assert res.get('status') == 'SUCCESS', f"Evaluation failed: {res}"

    print(f"[OK] Evaluation succeeded:")
    print(f"     * Overall Grade: {res['overall_grade']}")
    print(f"     * CEP 50%: {res['accuracy_dispersion']['cep_50_m']} m")
    print(f"     * 2DRMS 95%: {res['accuracy_dispersion']['two_drms_95_m']} m")
    print(f"     * NavIC C/N0: {res['rf_signal_quality']['band_separation']['navic_l5_s']['mean_cno']} dB-Hz")
    print(f"     * Availability: {res['reliability_temporal']['fix_availability_ratio_pct']}%")

    print("\n[ALL INTEGRATION TESTS PASSED 100%]")

if __name__ == "__main__":
    test_integration()
