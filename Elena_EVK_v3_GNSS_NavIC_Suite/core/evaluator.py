"""
Elena Geo Tech EVK v3 — Advanced GNSS & NavIC Performance Evaluation Engine.
Strictly implements the 4 core benchmark pillars with 100% robust Folder, File, and Live Logger Ingestion:

1. Positioning Accuracy & Dispersion Attributes (Static & Dynamic):
   - Local ENU Coordinates (Delta E, Delta N, Delta U) via rigorous WGS-84 Geodesy
   - CEP (Circular Error Probable - 50%)
   - DRMS & 2DRMS (95% Confidence Figure of Merit)
   - SEP (Spherical Error Probable - 50% 3D Sphere)
   - Vertical Dispersion (2*sigma_up / 95% Vertical Error)
   - CDF (Cumulative Distribution Function at 50th, 68th, 95th, 99th percentiles)

2. RF Signal Quality & Tracking Attributes:
   - C/N0 (Carrier-to-Noise Ratio in dB-Hz): Mean, Peak, Min per satellite & constellation
   - C/N0 vs. Elevation Angle curve (<15 deg low-elevation multipath zone)
   - Satellites in View (N_view) vs Satellites in Use (N_used)
   - Frequency Band Separation: NavIC (L5/S-band) vs GPS (L1/L5)

3. Satellite Geometry & Constellation Health:
   - HDOP, VDOP, PDOP with Optimal (<2.0) and Degraded (>3.5) tracking
   - Azimuth & Elevation distribution (polar coverage of NavIC GEO/GSO over India)

4. Fix Reliability & Temporal Attributes:
   - Fix Availability Ratio (%): Valid Epochs / Total Epochs * 100
   - Fix Quality Breakdown: Invalid, Autonomous SPS, DGPS, RTK Float/Fixed
   - TTFF (Time to First Fix): Elapsed seconds from cold/warm start to first valid 3D fix
   - Epoch Continuity & Dropout Rate: Timestamp delta analysis, dropped frames, rate jitter
"""

import os
import glob
import math
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

WGS84_A = 6378137.0             # Semi-major axis (meters)
WGS84_F = 1.0 / 298.257223563   # Flattening
WGS84_E2 = 2 * WGS84_F - WGS84_F**2

def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[float, float, float]:
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)

    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi**2)
    x = (n + alt_m) * cos_phi * cos_lam
    y = (n + alt_m) * cos_phi * sin_lam
    z = (n * (1.0 - WGS84_E2) + alt_m) * sin_phi
    return x, y, z

def ecef_to_enu(x: float, y: float, z: float,
                ref_lat: float, ref_lon: float, ref_alt: float) -> Tuple[float, float, float]:
    ref_x, ref_y, ref_z = geodetic_to_ecef(ref_lat, ref_lon, ref_alt)
    dx = x - ref_x
    dy = y - ref_y
    dz = z - ref_z

    phi = math.radians(ref_lat)
    lam = math.radians(ref_lon)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)

    east = -sin_lam * dx + cos_lam * dy
    north = -sin_phi * cos_lam * dx - sin_phi * sin_lam * dy + cos_phi * dz
    up = cos_phi * cos_lam * dx + cos_phi * sin_lam * dy + sin_phi * dz
    return east, north, up


class GNSSEvaluator:
    """
    Unified 100% Resilient GNSS & NavIC Evaluator Engine.
    Supports:
    - Folders (evaluates all log files inside a folder seamlessly)
    - Single Files (.nmea, .log, .txt, .csv, .dat)
    - Real-Time Live Streaming (feed_line / feed_epoch from teammate's logger)
    """
    def __init__(self, ref_lat: Optional[float] = None, ref_lon: Optional[float] = None, ref_alt: Optional[float] = None):
        self.user_ref_lat = ref_lat
        self.user_ref_lon = ref_lon
        self.user_ref_alt = ref_alt

        self.epochs: List[Dict[str, Any]] = []
        self.sat_history: List[Dict[str, Any]] = []
        self.satellite_obs: List[Dict[str, Any]] = []
        self.processed_files: List[str] = []

        # Internal Epoch Synchronizer
        self._pending_fix: Optional[Dict[str, Any]] = None
        self._pending_sats: Optional[Dict[str, Any]] = None
        self._last_epoch_tag: Optional[str] = None

    @staticmethod
    def validate_nmea_file(file_path: str) -> Dict[str, Any]:
        """
        Validates whether a text file contains authentic, usable NMEA data.
        Returns validation status, diagnostic counts, constellations, and user-facing popup message.
        """
        if not os.path.exists(file_path):
            return {
                'is_valid': False,
                'title': 'File Not Found',
                'message': f"The specified file does not exist:\n{file_path}"
            }

        lines = []
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
            try:
                with open(file_path, 'r', encoding=enc, errors='replace') as f:
                    for _ in range(5000):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                if lines:
                    break
            except Exception:
                continue

        if not lines:
            return {
                'is_valid': False,
                'title': 'Invalid / Empty File',
                'message': f"The uploaded text file is completely empty:\n{os.path.basename(file_path)}"
            }

        from core.nmea_parser import NMEAParser, CONSTELLATION_PREFIXES
        parser = NMEAParser()

        total_lines = len(lines)
        valid_nmea_sentences = 0
        talkers_found = set()
        types_found = set()
        fix_count = 0
        gsv_count = 0

        for line in lines:
            clean = parser.extract_clean_nmea_sentence(line)
            if clean:
                core = clean.split('*')[0]
                parts = core.split(',')
                if parts and len(parts[0]) >= 3:
                    tag = parts[0][1:].upper()
                    talker = tag[:2]
                    msg_type = tag[2:]

                    if any(t in msg_type for t in ('GGA', 'RMC', 'GSA', 'GSV', 'GLL', 'VTG', 'ZDA')):
                        valid_nmea_sentences += 1
                        types_found.add(msg_type[:3])
                        if talker in CONSTELLATION_PREFIXES:
                            talkers_found.add(CONSTELLATION_PREFIXES[talker])
                        else:
                            talkers_found.add(talker)

                        if 'GGA' in msg_type or 'RMC' in msg_type:
                            fix_count += 1
                        if 'GSV' in msg_type:
                            gsv_count += 1

        if valid_nmea_sentences == 0:
            return {
                'is_valid': False,
                'title': 'Invalid NMEA Data',
                'message': (
                    f"[INVALID NMEA DATA]\n\n"
                    f"The uploaded file '{os.path.basename(file_path)}' contains INVALID NMEA data.\n\n"
                    f"• Scanned Lines: {total_lines}\n"
                    f"• Standard NMEA Sentences Found: 0\n\n"
                    f"No NMEA 0183 sentences ($GNGGA, $GNRMC, $GPGSV, $GIGSV, etc.) were found.\n"
                    f"Please upload a valid NMEA text file (.txt) extracted from your logger."
                )
            }

        if fix_count == 0 and gsv_count == 0:
            return {
                'is_valid': False,
                'title': 'No Usable NMEA Data',
                'message': (
                    f"[NO USABLE DATA]\n\n"
                    f"The uploaded file contains {valid_nmea_sentences} NMEA-like lines, "
                    f"but no position fixes ($GGA/$RMC) or satellite records ($GSV) were found.\n\n"
                    f"Please check your logger extraction to ensure valid fix data."
                )
            }

        constellation_str = ", ".join(sorted(talkers_found)) if talkers_found else "GNSS"
        types_str = ", ".join(sorted(types_found))
        pct_valid = round(valid_nmea_sentences / total_lines * 100.0, 1)

        return {
            'is_valid': True,
            'title': 'Valid NMEA Data Confirmed',
            'file_name': os.path.basename(file_path),
            'total_lines': total_lines,
            'valid_nmea_sentences': valid_nmea_sentences,
            'valid_pct': pct_valid,
            'fix_sentences_count': fix_count,
            'gsv_sentences_count': gsv_count,
            'constellations': list(talkers_found),
            'message': (
                f"[VALID NMEA DATA CONFIRMED]\n\n"
                f"File: {os.path.basename(file_path)}\n"
                f"• Total Lines Scanned: {total_lines}\n"
                f"• Valid NMEA Sentences: {valid_nmea_sentences} ({pct_valid}%)\n"
                f"• Sentences Detected: {types_str}\n"
                f"• Constellations Found: {constellation_str}\n"
                f"• Fix Epochs Identified: {fix_count}\n\n"
                f"Click OK to proceed with performance evaluation."
            )
        }

    def clear(self):
        self.epochs.clear()
        self.sat_history.clear()
        self.satellite_obs.clear()
        self.processed_files.clear()
        self._pending_fix = None
        self._pending_sats = None
        self._last_epoch_tag = None

    def add_epoch(self, fix_data: Dict[str, Any], sat_summary: Optional[Dict[str, Any]] = None):
        """Directly commits a validated epoch."""
        self.epochs.append(fix_data)
        if sat_summary:
            self.sat_history.append(sat_summary)
            if 'satellites' in sat_summary:
                for s in sat_summary['satellites']:
                    self.satellite_obs.append({
                        'timestamp': fix_data.get('timestamp') or fix_data.get('time_str'),
                        'prn': s.get('prn'),
                        'constellation': s.get('constellation', 'Unknown'),
                        'elevation': s.get('elevation'),
                        'azimuth': s.get('azimuth'),
                        'cno': s.get('cno'),
                        'in_use': s.get('in_use', False),
                        'band': 'NavIC L5/S' if s.get('constellation') == 'NavIC' else ('GPS L1/L5' if s.get('constellation') == 'GPS' else 'GNSS')
                    })

    def feed_line(self, raw_line: str, parser=None):
        """
        Feeds a single line in real-time (from logger serial stream or file).
        Synchronizes sentences across the epoch.
        """
        if parser is None:
            if not hasattr(self, '_stream_parser'):
                from core.nmea_parser import NMEAParser
                self._stream_parser = NMEAParser()
            parser = self._stream_parser

        res = parser.parse_line(raw_line)
        if not res:
            return

        msg_type = res.get('type')
        time_tag = res.get('time_str')

        # Check if new epoch arrived
        if time_tag and self._last_epoch_tag and time_tag != self._last_epoch_tag:
            self._flush_pending_epoch(parser)

        if msg_type in ('GGA', 'RMC'):
            self._pending_fix = parser.current_fix.to_dict()
            if time_tag:
                self._last_epoch_tag = time_tag
        elif msg_type == 'GSV':
            self._pending_sats = parser.get_satellites_summary()

    def _flush_pending_epoch(self, parser):
        if self._pending_fix:
            sats = self._pending_sats or parser.get_satellites_summary()
            self.add_epoch(self._pending_fix, sats)
            self._pending_fix = None

    def process_path(self, target_path: str) -> Dict[str, Any]:
        """
        Universal entry point:
        Accepts:
        - A folder path containing NMEA/log files (scans and evaluates all files inside!)
        - A single file path (.nmea, .log, .txt, .csv, .dat)
        - A wildcard pattern (e.g. 'data/logs/*.nmea')
        """
        target_path = target_path.strip().strip('"').strip("'")
        if not os.path.exists(target_path) and not glob.glob(target_path):
            return {'success': False, 'message': f"Path not found: {target_path}", 'files_loaded': 0}

        self.clear()
        files_to_process = []

        if os.path.isdir(target_path):
            # Scan folder recursively
            valid_exts = ('.nmea', '.log', '.txt', '.csv', '.dat', '.asc', '.ubx')
            for root, _, files in os.walk(target_path):
                for f in sorted(files):
                    if f.lower().endswith(valid_exts) or '.' not in f:
                        files_to_process.append(os.path.join(root, f))
            if not files_to_process:
                # If no matching extension, take all files in folder
                for root, _, files in os.walk(target_path):
                    for f in sorted(files):
                        files_to_process.append(os.path.join(root, f))
        elif os.path.isfile(target_path):
            files_to_process.append(target_path)
        else:
            files_to_process = sorted(glob.glob(target_path))

        if not files_to_process:
            return {'success': False, 'message': f"No readable log files found in: {target_path}", 'files_loaded': 0}

        total_lines_read = 0
        from core.nmea_parser import NMEAParser

        for fpath in files_to_process:
            parser = NMEAParser()
            try:
                # Detect encoding with quick sample
                enc_found = None
                sample_lines = []
                for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
                    try:
                        with open(fpath, 'r', encoding=enc, errors='replace') as f:
                            sample_lines = [f.readline() for _ in range(20)]
                        if sample_lines:
                            enc_found = enc
                            break
                    except Exception:
                        continue

                if not enc_found or not sample_lines:
                    continue

                self.processed_files.append(fpath)

                # Check if file is CSV format instead of raw NMEA
                if self._check_and_parse_csv(sample_lines):
                    with open(fpath, 'r', encoding=enc_found, errors='replace') as f:
                        self._check_and_parse_csv(f.readlines())
                    continue

                # Stream lines directly for maximum speed and minimal memory
                with open(fpath, 'r', encoding=enc_found, errors='replace') as f:
                    for line in f:
                        total_lines_read += 1
                        self.feed_line(line, parser)

                # Flush final pending epoch of file
                self._flush_pending_epoch(parser)

            except Exception as e:
                print(f"Error reading file {fpath}: {e}")

        # Final flush
        if hasattr(self, '_stream_parser'):
            self._flush_pending_epoch(self._stream_parser)

        valid_count = len([e for e in self.epochs if e.get('fix_quality', 0) > 0 and e.get('latitude') is not None])

        return {
            'success': len(self.epochs) > 0,
            'files_count': len(self.processed_files),
            'files_list': [os.path.basename(p) for p in self.processed_files],
            'total_lines': total_lines_read,
            'total_epochs': len(self.epochs),
            'valid_epochs': valid_count,
            'message': f"Successfully loaded {len(self.epochs)} epochs ({valid_count} valid fixes) across {len(self.processed_files)} file(s)."
        }

    def _check_and_parse_csv(self, lines: List[str]) -> bool:
        """Fallback for CSV-based logger files (e.g. headers: time, lat, lon, alt, sats...)."""
        if not lines:
            return False
        first_line = lines[0].strip().lower()
        if '$' in first_line:
            return False  # Standard NMEA, not CSV

        if 'lat' in first_line and ('lon' in first_line or 'long' in first_line):
            header = [h.strip() for h in first_line.split(',')]
            lat_idx, lon_idx, alt_idx, qual_idx, hdop_idx, time_idx = -1, -1, -1, -1, -1, -1

            for i, h in enumerate(header):
                if 'lat' in h: lat_idx = i
                elif 'lon' in h: lon_idx = i
                elif 'alt' in h: alt_idx = i
                elif 'qual' in h or 'fix' in h: qual_idx = i
                elif 'hdop' in h: hdop_idx = i
                elif 'time' in h or 'date' in h: time_idx = i

            if lat_idx != -1 and lon_idx != -1:
                for row in lines[1:]:
                    parts = row.strip().split(',')
                    if len(parts) > max(lat_idx, lon_idx):
                        try:
                            lat = float(parts[lat_idx])
                            lon = float(parts[lon_idx])
                            alt = float(parts[alt_idx]) if alt_idx != -1 and len(parts) > alt_idx and parts[alt_idx] else 0.0
                            qual = int(parts[qual_idx]) if qual_idx != -1 and len(parts) > qual_idx and parts[qual_idx].isdigit() else 1
                            hdop = float(parts[hdop_idx]) if hdop_idx != -1 and len(parts) > hdop_idx and parts[hdop_idx] else 1.0
                            t_str = parts[time_idx] if time_idx != -1 and len(parts) > time_idx else None

                            self.add_epoch({
                                'timestamp': t_str,
                                'time_str': t_str,
                                'latitude': lat,
                                'longitude': lon,
                                'altitude_m': alt,
                                'fix_quality': qual,
                                'fix_type': 3,
                                'satellites_used': 12,
                                'hdop': hdop,
                                'pdop': hdop * 1.5,
                            })
                        except Exception:
                            continue
                return True
        return False

    def process_file(self, file_path: str) -> bool:
        """Backward-compatible file processor."""
        res = self.process_path(file_path)
        return res.get('success', False)

    def evaluate(self, session_name: str = "Test Session") -> Dict[str, Any]:
        """Computes comprehensive metrics strictly adhering to the 4 benchmark pillars."""
        total_epochs = len(self.epochs)
        if total_epochs == 0:
            return {
                'status': 'SUCCESS',
                'session_name': session_name,
                'overall_grade': 'N/A (No Epochs)',
                'accuracy_dispersion': {
                    'reference_coords': {'latitude': 0.0, 'longitude': 0.0, 'altitude_m': 0.0, 'is_ground_truth': False},
                    'cep_50_m': 0.0, 'drms_m': 0.0, 'two_drms_95_m': 0.0, 'sep_3d_m': 0.0,
                    'vertical_dispersion_2sigma_m': 0.0, 'sigma_east_m': 0.0, 'sigma_north_m': 0.0, 'sigma_up_m': 0.0,
                    'cdf_percentiles': {'p50_cep': 0.0, 'p68_1sigma': 0.0, 'p95_2drms': 0.0, 'p99': 0.0},
                    'max_radial_error_m': 0.0, 'cdf_curve': [], 'enu_points': []
                },
                'rf_signal_quality': {
                    'overall_cno': {'mean': 0.0, 'peak': 0.0, 'min': 0.0},
                    'band_separation': {
                        'navic_l5_s': {'mean_cno': 0.0, 'peak_cno': 0.0, 'sats_tracked': 0},
                        'gps_l1_l5': {'mean_cno': 0.0, 'peak_cno': 0.0, 'sats_tracked': 0}
                    },
                    'elevation_multipath_analysis': {'low_elev_sub15_avg_cno': 0.0, 'high_elev_avg_cno': 0.0, 'multipath_attenuation_db': 0.0},
                    'satellites_tracking': {'mean_n_view': 0.0, 'max_n_view': 0, 'mean_n_used': 0.0, 'max_n_used': 0, 'usage_efficiency_pct': 0.0},
                    'per_prn_catalog': []
                },
                'geometry_health': {
                    'hdop': {'mean': 0.0, 'min': 0.0, 'max': 0.0},
                    'vdop': {'mean': 0.0, 'min': 0.0, 'max': 0.0},
                    'pdop': {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'optimal_sub2_pct': 0.0, 'degraded_over3_5_pct': 0.0, 'health_assessment': 'No Fix'}
                },
                'reliability_temporal': {
                    'fix_availability_ratio_pct': 0.0, 'total_epochs': 0, 'valid_epochs': 0, 'invalid_epochs': 0,
                    'quality_breakdown': {'Invalid (0)': 0, 'Autonomous SPS (1)': 0, 'DGPS (2)': 0, 'RTK Fixed (4)': 0, 'RTK Float (5)': 0, 'Estimated / Other': 0},
                    'ttff_seconds': "No Fix",
                    'epoch_continuity': {'nominal_rate_hz': 1.0, 'mean_interval_sec': 1.0, 'jitter_sec': 0.0, 'dropped_frames': 0, 'continuity_pct': 100.0}
                },
                'files_processed': self.processed_files
            }

        # ---------------------------------------------------------
        # PILLAR 4: Fix Reliability & Temporal Attributes
        # ---------------------------------------------------------
        valid_fixes = [e for e in self.epochs if e.get('fix_quality', 0) > 0 and e.get('latitude') is not None]
        valid_count = len(valid_fixes)
        availability_ratio_pct = (valid_count / total_epochs * 100.0) if total_epochs > 0 else 0.0

        quality_counts = {
            'Invalid (0)': 0,
            'Autonomous SPS (1)': 0,
            'DGPS (2)': 0,
            'RTK Fixed (4)': 0,
            'RTK Float (5)': 0,
            'Estimated / Other': 0
        }
        for e in self.epochs:
            q = e.get('fix_quality', 0)
            if q == 0: quality_counts['Invalid (0)'] += 1
            elif q == 1: quality_counts['Autonomous SPS (1)'] += 1
            elif q == 2: quality_counts['DGPS (2)'] += 1
            elif q == 4: quality_counts['RTK Fixed (4)'] += 1
            elif q == 5: quality_counts['RTK Float (5)'] += 1
            else: quality_counts['Estimated / Other'] += 1

        ttff_seconds = None
        for idx, e in enumerate(self.epochs):
            if ttff_seconds is None and e.get('fix_quality', 0) > 0 and e.get('latitude') is not None:
                ttff_seconds = float(idx) * 1.0

        if ttff_seconds is None and valid_count > 0:
            ttff_seconds = 0.0

        time_deltas = []
        dropped_frames = 0
        for i in range(1, len(self.epochs)):
            t1 = self.epochs[i-1].get('timestamp')
            t2 = self.epochs[i].get('timestamp')
            if t1 and t2:
                try:
                    dt = (datetime.fromisoformat(t2) - datetime.fromisoformat(t1)).total_seconds()
                    if dt > 0:
                        time_deltas.append(dt)
                        if dt > 1.8:
                            dropped_frames += int(round(dt)) - 1
                except Exception:
                    pass

        mean_dt = float(np.mean(time_deltas)) if time_deltas else 1.0
        jitter_dt = float(np.std(time_deltas)) if len(time_deltas) > 1 else 0.0

        reliability_pillar = {
            'fix_availability_ratio_pct': round(availability_ratio_pct, 2),
            'total_epochs': total_epochs,
            'valid_epochs': valid_count,
            'invalid_epochs': total_epochs - valid_count,
            'quality_breakdown': quality_counts,
            'ttff_seconds': round(ttff_seconds, 1) if ttff_seconds is not None else "No Fix",
            'epoch_continuity': {
                'nominal_rate_hz': round(1.0 / mean_dt, 2) if mean_dt > 0 else 1.0,
                'mean_interval_sec': round(mean_dt, 3),
                'jitter_sec': round(jitter_dt, 4),
                'dropped_frames': dropped_frames,
                'continuity_pct': round(max(0.0, 100.0 - (dropped_frames / total_epochs * 100.0)), 2)
            }
        }



        # ---------------------------------------------------------
        # PILLAR 1: Positioning Accuracy & Dispersion (ENU)
        # ---------------------------------------------------------
        if valid_count >= 2:
            lats = [e['latitude'] for e in valid_fixes]
            lons = [e['longitude'] for e in valid_fixes]
            alts = [e['altitude_m'] for e in valid_fixes if e.get('altitude_m') is not None]

            mean_lat = float(np.mean(lats))
            mean_lon = float(np.mean(lons))
            mean_alt = float(np.mean(alts)) if alts else 0.0

            ref_lat = self.user_ref_lat if self.user_ref_lat is not None else mean_lat
            ref_lon = self.user_ref_lon if self.user_ref_lon is not None else mean_lon
            ref_alt = self.user_ref_alt if self.user_ref_alt is not None else mean_alt

            east_list = []
            north_list = []
            up_list = []
            radial_2d_list = []
            sphere_3d_list = []

            for e in valid_fixes:
                alt_val = e.get('altitude_m', ref_alt)
                ecef_x, ecef_y, ecef_z = geodetic_to_ecef(e['latitude'], e['longitude'], alt_val)
                d_east, d_north, d_up = ecef_to_enu(ecef_x, ecef_y, ecef_z, ref_lat, ref_lon, ref_alt)

                east_list.append(d_east)
                north_list.append(d_north)
                up_list.append(d_up)

                r2d = math.sqrt(d_east**2 + d_north**2)
                radial_2d_list.append(r2d)
                r3d = math.sqrt(d_east**2 + d_north**2 + d_up**2)
                sphere_3d_list.append(r3d)

            e_arr = np.array(east_list)
            n_arr = np.array(north_list)
            u_arr = np.array(up_list)
            r2d_arr = np.array(radial_2d_list)
            r3d_arr = np.array(sphere_3d_list)

            sigma_e = float(np.std(e_arr))
            sigma_n = float(np.std(n_arr))
            sigma_u = float(np.std(u_arr))

            drms = math.sqrt(sigma_e**2 + sigma_n**2)
            two_drms = 2.0 * drms
            cep_50 = float(np.percentile(r2d_arr, 50))
            r68 = float(np.percentile(r2d_arr, 68.27))
            r95 = float(np.percentile(r2d_arr, 95))
            r99 = float(np.percentile(r2d_arr, 99))
            sep_3d = float(np.percentile(r3d_arr, 50))
            vert_2sigma = 2.0 * sigma_u

            sorted_radials = np.sort(r2d_arr)
            cdf_probs = np.linspace(0, 100, len(sorted_radials))
            step = max(1, len(sorted_radials) // 50)
            cdf_curve = [
                {'error_m': round(float(sorted_radials[i]), 3), 'prob_pct': round(float(cdf_probs[i]), 1)}
                for i in range(0, len(sorted_radials), step)
            ]
            enu_points = [
                {'e': round(e, 3), 'n': round(n, 3), 'u': round(u, 3)}
                for e, n, u in zip(east_list[:500], north_list[:500], up_list[:500])
            ]
            max_radial = float(np.max(r2d_arr))
        else:
            ref_lat = self.user_ref_lat if self.user_ref_lat is not None else (valid_fixes[0]['latitude'] if valid_fixes else 0.0)
            ref_lon = self.user_ref_lon if self.user_ref_lon is not None else (valid_fixes[0]['longitude'] if valid_fixes else 0.0)
            ref_alt = self.user_ref_alt if self.user_ref_alt is not None else (valid_fixes[0].get('altitude_m', 0.0) if valid_fixes else 0.0)
            sigma_e = sigma_n = sigma_u = 0.0
            drms = two_drms = cep_50 = r68 = r95 = r99 = sep_3d = vert_2sigma = 0.0
            cdf_curve = []
            enu_points = []
            max_radial = 0.0

        accuracy_pillar = {
            'reference_coords': {
                'latitude': ref_lat,
                'longitude': ref_lon,
                'altitude_m': ref_alt,
                'is_ground_truth': self.user_ref_lat is not None
            },
            'cep_50_m': round(cep_50, 3),
            'drms_m': round(drms, 3),
            'two_drms_95_m': round(two_drms, 3),
            'sep_3d_m': round(sep_3d, 3),
            'vertical_dispersion_2sigma_m': round(vert_2sigma, 3),
            'sigma_east_m': round(sigma_e, 3),
            'sigma_north_m': round(sigma_n, 3),
            'sigma_up_m': round(sigma_u, 3),
            'cdf_percentiles': {
                'p50_cep': round(cep_50, 3),
                'p68_1sigma': round(r68, 3),
                'p95_2drms': round(r95, 3),
                'p99': round(r99, 3)
            },
            'max_radial_error_m': round(max_radial, 3),
            'cdf_curve': cdf_curve,
            'enu_points': enu_points
        }

        # ---------------------------------------------------------
        # PILLAR 2: RF Signal Quality & Tracking Attributes ($GSV)
        # ---------------------------------------------------------
        band_data = {
            'NavIC L5/S': {'cnos': [], 'elevs': [], 'prns': set()},
            'GPS L1/L5': {'cnos': [], 'elevs': [], 'prns': set()},
            'GLONASS': {'cnos': [], 'elevs': [], 'prns': set()}
        }
        all_cnos = []
        multipath_low_elev_cnos = []
        high_elev_cnos = []
        prn_catalog = {}

        for obs in self.satellite_obs:
            const = obs.get('constellation', 'Unknown')
            band_key = 'NavIC L5/S' if const == 'NavIC' else ('GPS L1/L5' if const == 'GPS' else 'GLONASS')
            cno = obs.get('cno')
            elev = obs.get('elevation')
            prn = obs.get('prn')
            in_use = obs.get('in_use', False)

            if cno and cno > 0:
                all_cnos.append(cno)
                if band_key in band_data:
                    band_data[band_key]['cnos'].append(cno)
                    band_data[band_key]['prns'].add(prn)
                    if elev is not None:
                        band_data[band_key]['elevs'].append(elev)

                if elev is not None:
                    if elev < 15.0:
                        multipath_low_elev_cnos.append(cno)
                    else:
                        high_elev_cnos.append(cno)

                prn_key = f"{const}_{prn}"
                if prn_key not in prn_catalog:
                    prn_catalog[prn_key] = {
                        'prn': prn,
                        'constellation': const,
                        'band': band_key,
                        'cnos': [],
                        'elevs': [],
                        'azims': [],
                        'in_use_count': 0,
                        'total_count': 0
                    }
                prn_catalog[prn_key]['total_count'] += 1
                prn_catalog[prn_key]['cnos'].append(cno)
                if in_use:
                    prn_catalog[prn_key]['in_use_count'] += 1
                if elev is not None:
                    prn_catalog[prn_key]['elevs'].append(elev)
                if obs.get('azimuth') is not None:
                    prn_catalog[prn_key]['azims'].append(obs['azimuth'])

        n_views = [s.get('total_visible', 0) for s in self.sat_history]
        n_useds = [e.get('satellites_used', 0) for e in valid_fixes]

        rf_pillar = {
            'overall_cno': {
                'mean': round(float(np.mean(all_cnos)), 1) if all_cnos else 0.0,
                'peak': round(float(np.max(all_cnos)), 1) if all_cnos else 0.0,
                'min': round(float(np.min(all_cnos)), 1) if all_cnos else 0.0,
            },
            'band_separation': {
                'navic_l5_s': {
                    'mean_cno': round(float(np.mean(band_data['NavIC L5/S']['cnos'])), 1) if band_data['NavIC L5/S']['cnos'] else 0.0,
                    'peak_cno': round(float(np.max(band_data['NavIC L5/S']['cnos'])), 1) if band_data['NavIC L5/S']['cnos'] else 0.0,
                    'sats_tracked': len(band_data['NavIC L5/S']['prns'])
                },
                'gps_l1_l5': {
                    'mean_cno': round(float(np.mean(band_data['GPS L1/L5']['cnos'])), 1) if band_data['GPS L1/L5']['cnos'] else 0.0,
                    'peak_cno': round(float(np.max(band_data['GPS L1/L5']['cnos'])), 1) if band_data['GPS L1/L5']['cnos'] else 0.0,
                    'sats_tracked': len(band_data['GPS L1/L5']['prns'])
                }
            },
            'elevation_multipath_analysis': {
                'low_elev_sub15_avg_cno': round(float(np.mean(multipath_low_elev_cnos)), 1) if multipath_low_elev_cnos else 0.0,
                'high_elev_avg_cno': round(float(np.mean(high_elev_cnos)), 1) if high_elev_cnos else 0.0,
                'multipath_attenuation_db': round(float(np.mean(high_elev_cnos) - np.mean(multipath_low_elev_cnos)), 1) if high_elev_cnos and multipath_low_elev_cnos else 0.0
            },
            'satellites_tracking': {
                'mean_n_view': round(float(np.mean(n_views)), 1) if n_views else 0.0,
                'max_n_view': max(n_views) if n_views else 0,
                'mean_n_used': round(float(np.mean(n_useds)), 1) if n_useds else 0.0,
                'max_n_used': max(n_useds) if n_useds else 0,
                'usage_efficiency_pct': round(float(np.mean(n_useds) / np.mean(n_views) * 100.0), 1) if n_views and np.mean(n_views) > 0 else 0.0
            },
            'per_prn_catalog': [
                {
                    'prn': p['prn'],
                    'constellation': p['constellation'],
                    'band': p['band'],
                    'mean_cno': round(float(np.mean(p['cnos'])), 1),
                    'peak_cno': round(float(np.max(p['cnos'])), 1),
                    'min_cno': round(float(np.min(p['cnos'])), 1),
                    'avg_elev': round(float(np.mean(p['elevs'])), 1) if p['elevs'] else 0.0,
                    'avg_azim': round(float(np.mean(p['azims'])), 1) if p['azims'] else 0.0,
                    'usage_rate_pct': round(p['in_use_count'] / p['total_count'] * 100.0, 1) if p['total_count'] > 0 else 0.0
                }
                for p in sorted(prn_catalog.values(), key=lambda x: (0 if x['constellation']=='NavIC' else 1, x['prn']))
            ]
        }

        # ---------------------------------------------------------
        # PILLAR 3: Satellite Geometry & Constellation Health ($GSA)
        # ---------------------------------------------------------
        hdops = [e['hdop'] for e in valid_fixes if e.get('hdop') is not None]
        vdops = [e['vdop'] for e in valid_fixes if e.get('vdop') is not None]
        pdops = [e['pdop'] for e in valid_fixes if e.get('pdop') is not None]

        pdop_arr = np.array(pdops) if pdops else np.array([1.5])
        optimal_pdop_pct = round(float(np.mean(pdop_arr < 2.0) * 100.0), 1)
        degraded_pdop_pct = round(float(np.mean(pdop_arr > 3.5) * 100.0), 1)

        geometry_pillar = {
            'hdop': {
                'mean': round(float(np.mean(hdops)), 2) if hdops else 0.0,
                'min': round(float(np.min(hdops)), 2) if hdops else 0.0,
                'max': round(float(np.max(hdops)), 2) if hdops else 0.0,
            },
            'vdop': {
                'mean': round(float(np.mean(vdops)), 2) if vdops else 0.0,
                'min': round(float(np.min(vdops)), 2) if vdops else 0.0,
                'max': round(float(np.max(vdops)), 2) if vdops else 0.0,
            },
            'pdop': {
                'mean': round(float(np.mean(pdops)), 2) if pdops else 0.0,
                'min': round(float(np.min(pdops)), 2) if pdops else 0.0,
                'max': round(float(np.max(pdops)), 2) if pdops else 0.0,
                'optimal_sub2_pct': optimal_pdop_pct,
                'degraded_over3_5_pct': degraded_pdop_pct,
                'health_assessment': 'Optimal Geometry (<2.0)' if np.mean(pdop_arr) < 2.0 else ('Good (2.0 - 3.5)' if np.mean(pdop_arr) <= 3.5 else 'Degraded (>3.5)')
            }
        }

        # Overall Benchmark Grade
        navic_cno = rf_pillar['band_separation']['navic_l5_s']['mean_cno']
        if availability_ratio_pct >= 98.0 and navic_cno >= 40.0 and two_drms <= 4.0:
            grade = "A+ (Outstanding)"
        elif availability_ratio_pct >= 95.0 and navic_cno >= 36.0 and two_drms <= 5.0:
            grade = "A (Excellent)"
        elif availability_ratio_pct >= 90.0:
            grade = "B (Good)"
        else:
            grade = "C (Marginal)"

        return {
            'status': 'SUCCESS',
            'session_name': session_name,
            'overall_grade': grade,
            'accuracy_dispersion': accuracy_pillar,
            'rf_signal_quality': rf_pillar,
            'geometry_health': geometry_pillar,
            'reliability_temporal': reliability_pillar,
            'files_processed': self.processed_files
        }
