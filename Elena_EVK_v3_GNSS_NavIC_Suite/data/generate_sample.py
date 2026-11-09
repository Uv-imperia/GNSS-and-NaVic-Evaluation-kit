"""
Script to generate realistic test NMEA dataset representing Elena Geo Tech EVK v3
with NavIC ($GIGSV), GPS ($GPGSV), and GLONASS ($GLGSV) multi-constellation sentences.
"""

import math
import random
import os

def calculate_checksum(nmea_body: str) -> str:
    xor = 0
    for ch in nmea_body:
        xor ^= ord(ch)
    return f"{xor:02X}"

def generate_sample_nmea(filename: str, num_epochs: int = 60):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Bengaluru reference (Elena Geo Systems test site)
    base_lat_deg = 12.974200
    base_lon_deg = 77.593500
    base_alt = 915.0

    lines = []
    
    # Fixed NavIC Satellites (IRNSS GEO & GSO over India)
    # PRN, Elev, Azim, base_cno
    navic_sats = [
        (2, 58, 142, 43.5),
        (3, 64, 195, 45.0),
        (4, 52, 230, 42.0),
        (5, 48, 115, 41.5),
        (6, 62, 178, 44.0),
        (7, 39, 265, 38.5),
    ]

    # GPS Satellites
    gps_sats = [
        (10, 72, 85, 42.0),
        (12, 45, 310, 39.0),
        (15, 31, 140, 36.5),
        (23, 60, 215, 41.0),
        (24, 25, 45, 34.0),
        (32, 18, 290, 31.0),
    ]

    # GLONASS Satellites
    glonass_sats = [
        (65, 50, 160, 38.0),
        (71, 35, 70, 35.0),
        (72, 42, 320, 37.5),
        (80, 20, 220, 30.5),
    ]

    for epoch in range(num_epochs):
        # Small Gaussian noise in position (sub-2 meter accuracy)
        lat_noise = random.gauss(0, 0.000012)
        lon_noise = random.gauss(0, 0.000015)
        alt_noise = random.gauss(0, 0.8)

        cur_lat = base_lat_deg + lat_noise
        cur_lon = base_lon_deg + lon_noise
        cur_alt = base_alt + alt_noise

        # Convert to NMEA DDMM.MMMMM
        lat_d = int(cur_lat)
        lat_m = (cur_lat - lat_d) * 60.0
        lat_nmea = f"{lat_d:02d}{lat_m:07.4f}"

        lon_d = int(cur_lon)
        lon_m = (cur_lon - lon_d) * 60.0
        lon_nmea = f"{lon_d:03d}{lon_m:07.4f}"

        sec = epoch % 60
        minute = (epoch // 60) % 60
        time_nmea = f"09{minute:02d}{sec:02d}.00"

        # 1. $GNGGA
        # Quality: 1 (GNSS fix), Num sats: 16, HDOP: 0.85
        gga_body = f"GNGGA,{time_nmea},{lat_nmea},N,{lon_nmea},E,1,16,0.85,{cur_alt:.1f},M,-85.2,M,,"
        lines.append(f"${gga_body}*{calculate_checksum(gga_body)}")

        # 2. $GNRMC
        speed_knots = abs(random.gauss(0.02, 0.01))
        rmc_body = f"GNRMC,{time_nmea},A,{lat_nmea},N,{lon_nmea},E,{speed_knots:.2f},124.5,161026,,,A"
        lines.append(f"${rmc_body}*{calculate_checksum(rmc_body)}")

        # 3. $GNGSA
        gsa_body = f"GNGSA,A,3,10,12,15,23,24,32,02,03,04,05,06,07,1.40,0.85,1.10,1"
        lines.append(f"${gsa_body}*{calculate_checksum(gsa_body)}")

        # 4. NavIC GSV ($GIGSV) - 2 messages for 6 NavIC sats
        # Message 1 (sats 1-4)
        gsv_navic_1 = f"GIGSV,2,1,06,{navic_sats[0][0]:02d},{navic_sats[0][1]:02d},{navic_sats[0][2]:03d},{int(navic_sats[0][3]+random.uniform(-1,1)):02d}," \
                      f"{navic_sats[1][0]:02d},{navic_sats[1][1]:02d},{navic_sats[1][2]:03d},{int(navic_sats[1][3]+random.uniform(-1,1)):02d}," \
                      f"{navic_sats[2][0]:02d},{navic_sats[2][1]:02d},{navic_sats[2][2]:03d},{int(navic_sats[2][3]+random.uniform(-1,1)):02d}," \
                      f"{navic_sats[3][0]:02d},{navic_sats[3][1]:02d},{navic_sats[3][2]:03d},{int(navic_sats[3][3]+random.uniform(-1,1)):02d}"
        lines.append(f"${gsv_navic_1}*{calculate_checksum(gsv_navic_1)}")

        # Message 2 (sats 5-6)
        gsv_navic_2 = f"GIGSV,2,2,06,{navic_sats[4][0]:02d},{navic_sats[4][1]:02d},{navic_sats[4][2]:03d},{int(navic_sats[4][3]+random.uniform(-1,1)):02d}," \
                      f"{navic_sats[5][0]:02d},{navic_sats[5][1]:02d},{navic_sats[5][2]:03d},{int(navic_sats[5][3]+random.uniform(-1,1)):02d},,,,"
        lines.append(f"${gsv_navic_2}*{calculate_checksum(gsv_navic_2)}")

        # 5. GPS GSV ($GPGSV) - 2 messages for 6 GPS sats
        gsv_gps_1 = f"GPGSV,2,1,06,{gps_sats[0][0]:02d},{gps_sats[0][1]:02d},{gps_sats[0][2]:03d},{int(gps_sats[0][3]+random.uniform(-1,1)):02d}," \
                    f"{gps_sats[1][0]:02d},{gps_sats[1][1]:02d},{gps_sats[1][2]:03d},{int(gps_sats[1][3]+random.uniform(-1,1)):02d}," \
                    f"{gps_sats[2][0]:02d},{gps_sats[2][1]:02d},{gps_sats[2][2]:03d},{int(gps_sats[2][3]+random.uniform(-1,1)):02d}," \
                    f"{gps_sats[3][0]:02d},{gps_sats[3][1]:02d},{gps_sats[3][2]:03d},{int(gps_sats[3][3]+random.uniform(-1,1)):02d}"
        lines.append(f"${gsv_gps_1}*{calculate_checksum(gsv_gps_1)}")

        gsv_gps_2 = f"GPGSV,2,2,06,{gps_sats[4][0]:02d},{gps_sats[4][1]:02d},{gps_sats[4][2]:03d},{int(gps_sats[4][3]+random.uniform(-1,1)):02d}," \
                    f"{gps_sats[5][0]:02d},{gps_sats[5][1]:02d},{gps_sats[5][2]:03d},{int(gps_sats[5][3]+random.uniform(-1,1)):02d},,,,"
        lines.append(f"${gsv_gps_2}*{calculate_checksum(gsv_gps_2)}")

        # 6. GLONASS GSV ($GLGSV) - 1 message for 4 sats
        gsv_glonass = f"GLGSV,1,1,04,{glonass_sats[0][0]:02d},{glonass_sats[0][1]:02d},{glonass_sats[0][2]:03d},{int(glonass_sats[0][3]+random.uniform(-1,1)):02d}," \
                      f"{glonass_sats[1][0]:02d},{glonass_sats[1][1]:02d},{glonass_sats[1][2]:03d},{int(glonass_sats[1][3]+random.uniform(-1,1)):02d}," \
                      f"{glonass_sats[2][0]:02d},{glonass_sats[2][1]:02d},{glonass_sats[2][2]:03d},{int(glonass_sats[2][3]+random.uniform(-1,1)):02d}," \
                      f"{glonass_sats[3][0]:02d},{glonass_sats[3][1]:02d},{glonass_sats[3][2]:03d},{int(glonass_sats[3][3]+random.uniform(-1,1)):02d}"
        lines.append(f"${gsv_glonass}*{calculate_checksum(gsv_glonass)}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Generated {len(lines)} sentences across {num_epochs} epochs at {filename}")

if __name__ == "__main__":
    generate_sample_nmea("data/samples/sample_elena_evk_navic.nmea", 120)
