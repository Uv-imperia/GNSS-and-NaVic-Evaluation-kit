"""
Elena Geo Tech EVK v3 — Performance Visualization Suite.
Implements the 4 visual pillars with robust in-place figure reuse:
1. Local ENU Dispersion Scatter (Delta E vs Delta N) with CEP 50% & 2DRMS circles + Delta Up dispersion
2. CDF (Cumulative Distribution Function) curve showing 50%, 68%, 95%, 99%
3. RF Signal Analysis: C/N0 vs Elevation angle (<15 deg multipath zone) & C/N0 bar chart per PRN
4. Satellite Geometry: Polar Skyplot (NavIC GEO/GSO vs GPS) & DOP timeline (<2.0 optimal vs >3.5 degraded)
"""

import math
from typing import List, Dict, Any, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

COLOR_NAVIC = '#F97316'    # Saffron / Orange for NavIC
COLOR_GPS = '#2563EB'      # Blue for GPS
COLOR_GLONASS = '#10B981'  # Green for GLONASS
COLOR_OTHER = '#64748B'

class GNSSPlotter:
    @staticmethod
    def plot_enu_dispersion(enu_points: List[Dict[str, float]], cep_50: float, two_drms: float,
                            vert_2sigma: float, fig: Optional[plt.Figure] = None, save_path: Optional[str] = None) -> plt.Figure:
        """Plots Local ENU Dispersion: Horizontal (Delta E vs Delta N) with CEP & 2DRMS circles."""
        if fig is not None:
            fig.clf()
        else:
            fig = plt.figure(figsize=(10, 5), facecolor='#0b1120')

        fig.set_facecolor('#0b1120')
        ax_h = fig.add_subplot(1, 2, 1)
        ax_v = fig.add_subplot(1, 2, 2)
        ax_h.set_facecolor('#1e293b')
        ax_v.set_facecolor('#1e293b')

        if not enu_points:
            ax_h.text(0.5, 0.5, "No 3D Fix Data Available\n(Antenna needs sky view)", color='#94a3b8',
                      ha='center', va='center', transform=ax_h.transAxes)
            ax_v.text(0.5, 0.5, "No Vertical Fix Data", color='#94a3b8',
                      ha='center', va='center', transform=ax_v.transAxes)
        else:
            easts = [p['e'] for p in enu_points]
            norths = [p['n'] for p in enu_points]
            ups = [p['u'] for p in enu_points]

            ax_h.scatter(easts, norths, c='#38bdf8', s=14, alpha=0.6, edgecolors='none', label='ENU Fixes')

            theta = np.linspace(0, 2 * np.pi, 200)
            if cep_50 > 0:
                ax_h.plot(cep_50 * np.cos(theta), cep_50 * np.sin(theta), color='#10b981', linewidth=2,
                          label=f'CEP 50% ({cep_50:.2f} m)')
            if two_drms > 0:
                ax_h.plot(two_drms * np.cos(theta), two_drms * np.sin(theta), color='#f97316', linewidth=2, linestyle='--',
                          label=f'2DRMS 95% ({two_drms:.2f} m)')

            ax_h.scatter([0], [0], c='#ffffff', s=50, marker='+', linewidth=2, label='Reference (0,0)')

            max_span = max(max(abs(e) for e in easts), max(abs(n) for n in norths), two_drms * 1.3, 3.0)
            ax_h.set_xlim(-max_span, max_span)
            ax_h.set_ylim(-max_span, max_span)
            ax_h.set_aspect('equal')
            ax_h.set_xlabel(r"$\Delta$ East Error (m)", color='#f8fafc', fontsize=10)
            ax_h.set_ylabel(r"$\Delta$ North Error (m)", color='#f8fafc', fontsize=10)
            ax_h.tick_params(colors='#94a3b8')
            ax_h.grid(color='#334155', linestyle='--', alpha=0.7)
            ax_h.legend(loc='lower right', facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=8)
            ax_h.set_title("Horizontal Dispersion (ENU)", color='#f8fafc', fontsize=11, fontweight='bold')

            epochs = np.arange(len(ups))
            ax_v.plot(ups, epochs, color='#a855f7', linewidth=1.2, alpha=0.8)
            ax_v.axvline(0, color='#ffffff', linestyle=':', alpha=0.6)
            if vert_2sigma > 0:
                ax_v.axvline(-vert_2sigma, color='#eab308', linestyle='--', linewidth=1.2, label=r'-2$\sigma_u$')
                ax_v.axvline(vert_2sigma, color='#eab308', linestyle='--', linewidth=1.2, label=rf'+2$\sigma_u$ ({vert_2sigma:.2f}m)')

            v_span = max(max(abs(u) for u in ups), vert_2sigma * 1.3, 2.0)
            ax_v.set_xlim(-v_span, v_span)
            ax_v.set_xlabel(r"$\Delta$ Up Error (m)", color='#f8fafc', fontsize=10)
            ax_v.set_ylabel("Epoch Index", color='#f8fafc', fontsize=10)
            ax_v.tick_params(colors='#94a3b8')
            ax_v.grid(color='#334155', linestyle='--', alpha=0.7)
            ax_v.legend(loc='upper right', facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=7.5)
            ax_v.set_title(r"Vertical ($\Delta$U)", color='#f8fafc', fontsize=11, fontweight='bold')

        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        return fig

    @staticmethod
    def plot_cdf_curve(cdf_points: List[Dict[str, float]], p50: float, p68: float, p95: float, p99: float,
                       fig: Optional[plt.Figure] = None, save_path: Optional[str] = None) -> plt.Figure:
        """Plots the Empirical Error CDF with 50%, 68%, 95%, 99% threshold markings."""
        if fig is not None:
            fig.clf()
        else:
            fig = plt.figure(figsize=(7, 4.5), facecolor='#0b1120')

        fig.set_facecolor('#0b1120')
        ax = fig.add_subplot(1, 1, 1)
        ax.set_facecolor('#1e293b')

        if not cdf_points:
            ax.text(0.5, 0.5, "No Data for Error CDF\n(Requires valid position fixes)", color='#94a3b8',
                    ha='center', va='center', transform=ax.transAxes)
        else:
            errors = [p['error_m'] for p in cdf_points]
            probs = [p['prob_pct'] for p in cdf_points]

            ax.plot(errors, probs, color='#38bdf8', linewidth=2.5, label='Horizontal Error CDF')

            if p50 > 0:
                ax.axhline(50, color='#10b981', linestyle='--', alpha=0.7, label=f'50% (CEP: {p50:.2f}m)')
                ax.axvline(p50, color='#10b981', linestyle='--', alpha=0.7)

            if p68 > 0:
                ax.axhline(68.27, color='#3b82f6', linestyle=':', alpha=0.7, label=rf'68% (1$\sigma$: {p68:.2f}m)')
                ax.axvline(p68, color='#3b82f6', linestyle=':', alpha=0.7)

            if p95 > 0:
                ax.axhline(95, color='#f97316', linestyle='--', alpha=0.7, label=f'95% (2DRMS: {p95:.2f}m)')
                ax.axvline(p95, color='#f97316', linestyle='--', alpha=0.7)

            if p99 > 0:
                ax.axhline(99, color='#ef4444', linestyle=':', alpha=0.7, label=f'99% ({p99:.2f}m)')
                ax.axvline(p99, color='#ef4444', linestyle=':', alpha=0.7)

            ax.set_xlim(0, max(p99 * 1.25, 4.0))
            ax.set_ylim(0, 105)
            ax.set_xlabel("Horizontal Radial Error (meters)", color='#f8fafc', fontsize=10)
            ax.set_ylabel("Cumulative Probability (%)", color='#f8fafc', fontsize=10)
            ax.tick_params(colors='#94a3b8')
            ax.grid(color='#334155', linestyle='--', alpha=0.7)
            ax.legend(loc='lower right', facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=8.5)

        ax.set_title("Cumulative Distribution Function (Error CDF)", color='#f8fafc', fontsize=11, fontweight='bold')
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        return fig

    @staticmethod
    def plot_cno_vs_elevation(satellite_obs: List[Dict[str, Any]],
                              fig: Optional[plt.Figure] = None, save_path: Optional[str] = None) -> plt.Figure:
        """Plots C/N0 vs Elevation angle highlighting the < 15 deg multipath zone."""
        if fig is not None:
            fig.clf()
        else:
            fig = plt.figure(figsize=(7.5, 4.5), facecolor='#0b1120')

        fig.set_facecolor('#0b1120')
        ax = fig.add_subplot(1, 1, 1)
        ax.set_facecolor('#1e293b')

        ax.axvspan(0, 15, color='#ef4444', alpha=0.15, label='<15° Multipath Zone')

        navic_elevs, navic_cnos = [], []
        gps_elevs, gps_cnos = [], []

        for s in satellite_obs:
            e = s.get('elevation')
            c = s.get('cno')
            if e is not None and c is not None and c > 0:
                if s.get('constellation') == 'NavIC':
                    navic_elevs.append(e)
                    navic_cnos.append(c)
                elif s.get('constellation') == 'GPS':
                    gps_elevs.append(e)
                    gps_cnos.append(c)

        # Cap scatter points to 3,000 max to ensure instantaneous rendering
        if len(gps_elevs) > 3000:
            step = len(gps_elevs) // 3000
            gps_elevs = gps_elevs[::step]
            gps_cnos = gps_cnos[::step]

        if len(navic_elevs) > 3000:
            step = len(navic_elevs) // 3000
            navic_elevs = navic_elevs[::step]
            navic_cnos = navic_cnos[::step]

        if gps_elevs:
            ax.scatter(gps_elevs, gps_cnos, color='#3b82f6', s=16, alpha=0.6, label='GPS (L1/L5)')
        if navic_elevs:
            ax.scatter(navic_elevs, navic_cnos, color='#f97316', s=24, alpha=0.8, edgecolors='#ffffff',
                       linewidth=0.5, label='NavIC (L5/S-Band)')

        if not gps_elevs and not navic_elevs:
            ax.text(0.5, 0.5, "No Satellite Signal Data Available", color='#94a3b8',
                    ha='center', va='center', transform=ax.transAxes)

        ax.set_xlim(0, 90)
        ax.set_ylim(15, 55)
        ax.set_xlabel("Satellite Elevation Angle (°)", color='#f8fafc', fontsize=10)
        ax.set_ylabel("C/N0 (dB-Hz)", color='#f8fafc', fontsize=10)
        ax.tick_params(colors='#94a3b8')
        ax.grid(color='#334155', linestyle='--', alpha=0.7)
        ax.legend(loc='lower right', facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=9)
        ax.set_title("RF Signal Quality: C/N0 vs Elevation Angle", color='#f8fafc', fontsize=11, fontweight='bold')

        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        return fig

    @staticmethod
    def plot_polar_skyplot(satellites: List[Dict[str, Any]],
                           fig: Optional[plt.Figure] = None, save_path: Optional[str] = None) -> plt.Figure:
        """Plots standard polar skyplot displaying NavIC GEO/GSO coverage vs GPS orbits."""
        if fig is not None:
            fig.clf()
        else:
            fig = plt.figure(figsize=(5.5, 5.5), facecolor='#0b1120')

        fig.set_facecolor('#0b1120')
        ax = fig.add_subplot(1, 1, 1, polar=True)
        ax.set_facecolor('#1e293b')

        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 90)
        ax.set_yticks([0, 30, 60, 90])
        ax.set_yticklabels(['90°', '60°', '30°', '0°'], color='#94a3b8', fontsize=8)
        ax.set_rlim(90, 0)
        ax.tick_params(colors='#94a3b8')
        ax.grid(color='#334155', linestyle='--', linewidth=0.8)

        theta_rim = np.linspace(0, 2*np.pi, 200)
        ax.plot(theta_rim, np.full_like(theta_rim, 15), color='#ef4444', linestyle=':', alpha=0.6, label='15° Mask')

        # Deduplicate satellites by (constellation, prn) to display each unique satellite once
        # Keeps the highest C/N0 observation coordinates for a clean, instant skyplot
        unique_sats = {}
        for sat in satellites:
            prn = sat.get('prn')
            const = sat.get('constellation', 'GNSS')
            azim = sat.get('azimuth')
            elev = sat.get('elevation')
            if prn is not None and azim is not None and elev is not None:
                key = (const, prn)
                if key not in unique_sats or (sat.get('cno') or 0) > (unique_sats[key].get('cno') or 0):
                    unique_sats[key] = sat

        legend_added = set()
        has_sats = False
        for sat in unique_sats.values():
            azim = sat.get('azimuth')
            elev = sat.get('elevation')
            prn = sat.get('prn')
            const = sat.get('constellation', 'GNSS')
            cno = sat.get('cno') or 0

            has_sats = True
            theta = math.radians(azim)
            color = COLOR_NAVIC if const == 'NavIC' else (COLOR_GPS if const == 'GPS' else COLOR_GLONASS)
            size = max(55, min(180, cno * 2.8))

            label = const if const not in legend_added else None
            if label:
                legend_added.add(const)

            ax.scatter(theta, elev, c=color, s=size, edgecolors='#ffffff', linewidth=1, alpha=0.9, label=label, zorder=5)
            ax.text(theta, max(2.0, elev - 5), f"{prn}", color='#f8fafc', fontsize=8, fontweight='bold', ha='center', va='center', zorder=6)

        if not has_sats:
            ax.text(0, 45, "No Satellite Coordinates", color='#94a3b8', ha='center', va='center', fontsize=9)

        ax.set_title("Polar Skyplot (NavIC GEO/GSO vs GPS)", color='#f8fafc', fontsize=11, fontweight='bold', pad=15)
        if legend_added:
            ax.legend(loc='lower left', bbox_to_anchor=(-0.15, -0.12), facecolor='#1e293b',
                      edgecolor='#334155', labelcolor='#f8fafc', fontsize=8.5)

        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        return fig
