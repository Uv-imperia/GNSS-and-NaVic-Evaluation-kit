"""
Test script to verify the validation logic for valid and invalid NMEA text files.
"""

import os
from core.evaluator import GNSSEvaluator

def test_validation():
    # 1. Test Valid File
    valid_file = "data/samples/sample_logger_output.txt"
    if not os.path.exists(valid_file):
        source = "data/samples/sample_elena_evk_navic.nmea"
        with open(source, 'r', encoding='utf-8') as s, open(valid_file, 'w', encoding='utf-8') as d:
            d.write(s.read())

    res_valid = GNSSEvaluator.validate_nmea_file(valid_file)
    print("--- Test 1: Valid NMEA Text File ---")
    print(f"is_valid: {res_valid['is_valid']}")
    print(f"Title   : {res_valid['title']}")
    print(f"Message :\n{res_valid['message']}")
    assert res_valid['is_valid'] == True

    # 2. Test Invalid File
    invalid_file = "data/samples/invalid_logger_data.txt"
    with open(invalid_file, 'w', encoding='utf-8') as f:
        f.write("Elena Geo Tech Receiver Test Log\nLogger started at 12:00:00\nNo NMEA lines here\nJust random diagnostic logs\n")

    res_invalid = GNSSEvaluator.validate_nmea_file(invalid_file)
    print("\n--- Test 2: Invalid NMEA Text File ---")
    print(f"is_valid: {res_invalid['is_valid']}")
    print(f"Title   : {res_invalid['title']}")
    print(f"Message :\n{res_invalid['message']}")
    assert res_invalid['is_valid'] == False

    print("\n[ALL VALIDATION TESTS PASSED 100%]")

if __name__ == "__main__":
    test_validation()
