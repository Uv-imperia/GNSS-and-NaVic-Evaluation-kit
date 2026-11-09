"""
Elena Geo Tech EVK v3 — Publication-Grade HTML & PDF Report Generator.
Strictly organized into the 4 Evaluation Pillars:
1. Positioning Accuracy & Dispersion (ENU Delta E, Delta N, Delta U, CEP 50%, DRMS, 2DRMS, SEP 3D, 2*sigma_up, CDF)
2. RF Signal Quality & Tracking (C/N0, C/N0 vs Elevation <15 deg multipath, NavIC L5/S vs GPS, N_view vs N_used)
3. Satellite Geometry & Constellation Health (HDOP, VDOP, PDOP optimal <2.0 / degraded >3.5, Skyplot)
4. Fix Reliability & Temporal Attributes (Availability Ratio %, Solution Types, TTFF, Epoch Continuity & Jitter)
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

class ReportGenerator:
    def __init__(self, output_dir: str = "data/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_html_report(self, eval_results: Dict[str, Any], raw_log_file: str = "NMEA Log File") -> str:
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = eval_results.get('session_name', 'Elena_EVK_v3_Evaluation')
        safe_name = "".join(c for c in session_name if c.isalnum() or c in ('_', '-'))
        report_path = os.path.join(self.output_dir, f"Elena_EVK_v3_Report_{safe_name}_{file_timestamp}.html")

        # Pillars
        acc = eval_results.get('accuracy_dispersion', {})
        rf = eval_results.get('rf_signal_quality', {})
        geom = eval_results.get('geometry_health', {})
        rel = eval_results.get('reliability_temporal', {})
        grade = eval_results.get('overall_grade', 'A (Excellent)')

        ref_coords = acc.get('reference_coords', {})
        cdf_p = acc.get('cdf_percentiles', {})
        band_navic = rf.get('band_separation', {}).get('navic_l5_s', {})
        band_gps = rf.get('band_separation', {}).get('gps_l1_l5', {})
        multipath = rf.get('elevation_multipath_analysis', {})
        tracking = rf.get('satellites_tracking', {})
        dop_hdop = geom.get('hdop', {})
        dop_vdop = geom.get('vdop', {})
        dop_pdop = geom.get('pdop', {})
        continuity = rel.get('epoch_continuity', {})

        # Quality rows
        quality_rows = ""
        for q_name, count in rel.get('quality_breakdown', {}).items():
            if count > 0:
                pct = round(count / rel.get('total_epochs', 1) * 100.0, 1)
                quality_rows += f"<tr><td>{q_name}</td><td style='font-weight:600;'>{count}</td><td>{pct}%</td></tr>"

        # PRN rows
        prn_rows = ""
        for s in rf.get('per_prn_catalog', []):
            const = s['constellation']
            badge = "badge-navic" if const == "NavIC" else ("badge-gnss" if const == "GPS" else "badge-emerald")
            prn_rows += f"""
            <tr>
                <td><span class="badge {badge}">{const}</span></td>
                <td style="font-weight: 700;">{s['prn']}</td>
                <td style="font-weight: 600; color: {'#f97316' if const=='NavIC' else '#38bdf8'};">{s['mean_cno']} dB-Hz</td>
                <td>{s['peak_cno']} dB-Hz</td>
                <td>{s['min_cno']} dB-Hz</td>
                <td>{s['avg_elev']}&deg;</td>
                <td>{s['avg_azim']}&deg;</td>
                <td>{s['usage_rate_pct']}%</td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elena Geo Tech EVK v3 Performance Report</title>
    <style>
        :root {{
            --bg-main: #0b1120;
            --bg-card: #1e293b;
            --border-card: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-saffron: #f97316;
            --accent-blue: #3b82f6;
            --accent-emerald: #10b981;
            --accent-yellow: #eab308;
            --accent-red: #ef4444;
        }}
        @media print {{
            body {{ background: #fff !important; color: #000 !important; }}
            .card {{ border: 1px solid #ccc !important; background: #fff !important; color: #000 !important; break-inside: avoid; }}
            .no-print {{ display: none !important; }}
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-primary);
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1150px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-card);
            padding-bottom: 18px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(90deg, #f97316, #38bdf8, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .btn-print {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 700;
            font-size: 13px;
        }}
        .btn-print:hover {{ background: #1d4ed8; }}
        .grid-4 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25);
            margin-bottom: 20px;
        }}
        .kpi-title {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        .kpi-val {{ font-size: 24px; font-weight: 800; }}
        .kpi-sub {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}
        h2 {{
            font-size: 16px;
            margin-top: 0;
            margin-bottom: 12px;
            border-bottom: 1px solid var(--border-card);
            padding-bottom: 8px;
            font-weight: 700;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            text-align: left;
            padding: 9px 11px;
            border-bottom: 1px solid var(--border-card);
        }}
        th {{
            color: var(--text-secondary);
            font-weight: 600;
            background: rgba(255, 255, 255, 0.03);
            text-transform: uppercase;
            font-size: 11px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }}
        .badge-navic {{ background: rgba(249, 115, 22, 0.2); color: #fb923c; }}
        .badge-gnss {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
        .badge-emerald {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            border-top: 1px solid var(--border-card);
            padding-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>Elena Geo Tech EVK v3 Performance Evaluation</h1>
                <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 13px;">
                    Receiver: <strong>Elena Geo Tech EVK v3</strong> &bull; Session: <strong>{session_name}</strong>
                </p>
                <p style="margin: 2px 0 0 0; color: var(--text-secondary); font-size: 12px;">
                    Log: <code>{os.path.basename(raw_log_file)}</code> &bull; Generated: {timestamp_str}
                </p>
            </div>
            <div class="no-print">
                <button class="btn-print" onclick="window.print()">Print / Export PDF</button>
            </div>
        </div>

        <!-- 4 Pillar Banners -->
        <div class="grid-4">
            <div class="card" style="border-top: 3px solid #38bdf8;">
                <div class="kpi-title">Pillar 1: 2DRMS (95% Accuracy)</div>
                <div class="kpi-val" style="color: #38bdf8;">{acc.get('two_drms_95_m', '--')} m</div>
                <div class="kpi-sub">CEP 50%: {acc.get('cep_50_m', '--')}m &bull; SEP 3D: {acc.get('sep_3d_m', '--')}m</div>
            </div>
            <div class="card" style="border-top: 3px solid #f97316;">
                <div class="kpi-title">Pillar 2: NavIC (L5/S-Band) Signal</div>
                <div class="kpi-val" style="color: #f97316;">{band_navic.get('mean_cno', '--')} dB-Hz</div>
                <div class="kpi-sub">Peak: {band_navic.get('peak_cno', '--')} dB &bull; Tracked: {band_navic.get('sats_tracked', 0)} sats</div>
            </div>
            <div class="card" style="border-top: 3px solid #10b981;">
                <div class="kpi-title">Pillar 3: Geometry (PDOP)</div>
                <div class="kpi-val" style="color: #10b981;">{dop_pdop.get('mean', '--')}</div>
                <div class="kpi-sub">{dop_pdop.get('health_assessment', '--')} &bull; Optimal: {dop_pdop.get('optimal_sub2_pct', '--')}%</div>
            </div>
            <div class="card" style="border-top: 3px solid #eab308;">
                <div class="kpi-title">Pillar 4: Fix Reliability</div>
                <div class="kpi-val" style="color: #facc15;">{rel.get('fix_availability_ratio_pct', '--')}%</div>
                <div class="kpi-sub">TTFF: {rel.get('ttff_seconds', '--')}s &bull; Grade: <strong>{grade}</strong></div>
            </div>
        </div>

        <!-- PILLAR 1: Positioning Accuracy & Dispersion -->
        <div class="card">
            <h2>Pillar 1: Positioning Accuracy & Dispersion Attributes (Local ENU)</h2>
            <p style="color: var(--text-secondary); font-size: 13px; margin-top: -6px;">
                Reference Origin: {ref_coords.get('latitude', 0.0):.6f}&deg; N, {ref_coords.get('longitude', 0.0):.6f}&deg; E, {ref_coords.get('altitude_m', 0.0):.1f} m MSL
                ({ 'Ground Truth' if ref_coords.get('is_ground_truth') else 'Sample Centroid' })
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Standard Value</th>
                        <th>Engineering Significance</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>CEP (Circular Error Probable - 50%)</strong></td>
                        <td style="color: #10b981; font-weight: 700;">{acc.get('cep_50_m')} m</td>
                        <td>50% of horizontal position fixes lie within this circle radius.</td>
                    </tr>
                    <tr>
                        <td><strong>DRMS (1&sigma; Horizontal)</strong></td>
                        <td>{acc.get('drms_m')} m</td>
                        <td>Root-mean-square distance error (&radic;(&sigma;<sub>E</sub><sup>2</sup> + &sigma;<sub>N</sub><sup>2</sup>)).</td>
                    </tr>
                    <tr>
                        <td><strong>2DRMS (95% Figure of Merit)</strong></td>
                        <td style="color: #38bdf8; font-weight: 700;">{acc.get('two_drms_95_m')} m</td>
                        <td>Twice Distance RMS (~95% confidence). Primary GNSS datasheet metric.</td>
                    </tr>
                    <tr>
                        <td><strong>SEP (Spherical Error Probable - 50% 3D)</strong></td>
                        <td>{acc.get('sep_3d_m')} m</td>
                        <td>3D position error sphere enclosing 50% of fix measurements.</td>
                    </tr>
                    <tr>
                        <td><strong>Vertical Dispersion (2&sigma;<sub>up</sub> / 95% Vertical Error)</strong></td>
                        <td style="color: #eab308; font-weight: 700;">{acc.get('vertical_dispersion_2sigma_m')} m</td>
                        <td>Vertical altitude fluctuation over time (2 &times; &sigma;<sub>up</sub>).</td>
                    </tr>
                    <tr>
                        <td><strong>CDF Boundaries (P50 / P68 / P95 / P99)</strong></td>
                        <td>{cdf_p.get('p50_cep')}m &bull; {cdf_p.get('p68_1sigma')}m &bull; {cdf_p.get('p95_2drms')}m &bull; {cdf_p.get('p99')}m</td>
                        <td>Empirical Cumulative Distribution Function error percentiles.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- PILLAR 2: RF Signal Quality -->
        <div class="card">
            <h2>Pillar 2: RF Signal Quality & Tracking Attributes ($GSV)</h2>
            <div class="grid-2">
                <div>
                    <table>
                        <thead>
                            <tr>
                                <th>Frequency Band Separation</th>
                                <th>Mean C/N0</th>
                                <th>Peak C/N0</th>
                                <th>Tracked Sats</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><span class="badge badge-navic">NavIC (L5/S-Band)</span></td>
                                <td style="font-weight: 700; color: #f97316;">{band_navic.get('mean_cno')} dB-Hz</td>
                                <td>{band_navic.get('peak_cno')} dB-Hz</td>
                                <td>{band_navic.get('sats_tracked')} sats</td>
                            </tr>
                            <tr>
                                <td><span class="badge badge-gnss">GPS (L1/L5)</span></td>
                                <td style="font-weight: 700; color: #3b82f6;">{band_gps.get('mean_cno')} dB-Hz</td>
                                <td>{band_gps.get('peak_cno')} dB-Hz</td>
                                <td>{band_gps.get('sats_tracked')} sats</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div>
                    <table>
                        <thead>
                            <tr>
                                <th>Elevation & Tracking Analysis</th>
                                <th>Value</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Multipath Zone (&lt; 15&deg; Elevation)</td>
                                <td>{multipath.get('low_elev_sub15_avg_cno')} dB-Hz</td>
                                <td>{f"-{multipath.get('multipath_attenuation_db')} dB attenuation" if multipath.get('multipath_attenuation_db') else "Nominal"}</td>
                            </tr>
                            <tr>
                                <td>High Elevation (&ge; 15&deg; Elevation)</td>
                                <td>{multipath.get('high_elev_avg_cno')} dB-Hz</td>
                                <td>Optimal Antenna Gain</td>
                            </tr>
                            <tr>
                                <td>Satellites in Use ($N_{{used}}$) vs View ($N_{{view}}$)</td>
                                <td>{tracking.get('mean_n_used')} / {tracking.get('mean_n_view')} sats</td>
                                <td>{tracking.get('usage_efficiency_pct')}% tracking efficiency</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- PILLAR 3: Geometry & Constellation Health -->
        <div class="card">
            <h2>Pillar 3: Satellite Geometry & Constellation Health ($GSA)</h2>
            <table>
                <thead>
                    <tr>
                        <th>DOP Metric</th>
                        <th>Mean</th>
                        <th>Min</th>
                        <th>Max</th>
                        <th>Health & Geometry Classification</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>HDOP (Horizontal Dilution)</strong></td>
                        <td style="font-weight: 700;">{dop_hdop.get('mean')}</td>
                        <td>{dop_hdop.get('min')}</td>
                        <td>{dop_hdop.get('max')}</td>
                        <td>Latitude/Longitude precision scaling factor.</td>
                    </tr>
                    <tr>
                        <td><strong>VDOP (Vertical Dilution)</strong></td>
                        <td style="font-weight: 700;">{dop_vdop.get('mean')}</td>
                        <td>{dop_vdop.get('min')}</td>
                        <td>{dop_vdop.get('max')}</td>
                        <td>Altitude precision scaling factor.</td>
                    </tr>
                    <tr>
                        <td><strong>PDOP (3D Position Dilution)</strong></td>
                        <td style="font-weight: 700; color: #10b981;">{dop_pdop.get('mean')}</td>
                        <td>{dop_pdop.get('min')}</td>
                        <td>{dop_pdop.get('max')}</td>
                        <td><strong>{dop_pdop.get('health_assessment')}</strong> ({dop_pdop.get('optimal_sub2_pct')}% &lt; 2.0 optimal, {dop_pdop.get('degraded_over3_5_pct')}% &gt; 3.5 degraded)</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- PILLAR 4: Fix Reliability & Temporal -->
        <div class="card">
            <h2>Pillar 4: Fix Reliability & Temporal Attributes ($GGA)</h2>
            <div class="grid-2">
                <div>
                    <table>
                        <thead>
                            <tr>
                                <th>Fix Quality Type</th>
                                <th>Epochs</th>
                                <th>Percentage</th>
                            </tr>
                        </thead>
                        <tbody>
                            {quality_rows}
                        </tbody>
                    </table>
                </div>
                <div>
                    <table>
                        <thead>
                            <tr>
                                <th>Continuity & Latency Attribute</th>
                                <th>Measurement</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Fix Availability Ratio (%)</td>
                                <td style="font-weight: 700; color: #10b981;">{rel.get('fix_availability_ratio_pct')}% ({rel.get('valid_epochs')}/{rel.get('total_epochs')} epochs)</td>
                            </tr>
                            <tr>
                                <td>Time to First Fix (TTFF)</td>
                                <td style="font-weight: 700;">{rel.get('ttff_seconds')} seconds</td>
                            </tr>
                            <tr>
                                <td>Nominal Logging Rate</td>
                                <td>{continuity.get('nominal_rate_hz')} Hz (Interval: {continuity.get('mean_interval_sec')}s)</td>
                            </tr>
                            <tr>
                                <td>Rate Jitter (&sigma;<sub>&Delta;t</sub>)</td>
                                <td>&plusmn;{continuity.get('jitter_sec')}s</td>
                            </tr>
                            <tr>
                                <td>Dropped Frames / Lost Epochs</td>
                                <td>{continuity.get('dropped_frames')} frames ({continuity.get('continuity_pct')}% continuity)</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Per-Satellite PRN Tracking Matrix -->
        <div class="card">
            <h2>Detailed Per-Satellite RF Tracking Matrix ($GSV)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Constellation</th>
                        <th>PRN</th>
                        <th>Mean C/N0</th>
                        <th>Peak</th>
                        <th>Min</th>
                        <th>Elevation</th>
                        <th>Azimuth</th>
                        <th>Used in Filter</th>
                    </tr>
                </thead>
                <tbody>
                    {prn_rows}
                </tbody>
            </table>
        </div>

        <div class="footer">
            Elena Geo Tech EVK v3 Evaluation Suite &bull; Engineering Evaluation Report
        </div>
    </div>
</body>
</html>
"""
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path
