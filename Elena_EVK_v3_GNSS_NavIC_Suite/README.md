# Elena Geo Tech EVK v3 — Integrated GNSS & NavIC Mission Suite (Logger + Evaluator)

An end-to-end mission engineering suite developed for the **Elena Geo Tech EVK v3** evaluation kit, providing real-time data acquisition, live satellite tracking, multi-constellation isolation, and comprehensive post-run evaluation across 4 international GNSS benchmark pillars.

---

## 🏗️ Architecture Overview

```
gnss_navic_logger/
├── logger_app.py               # Standalone PyQt6 Data Logger (EVK v3 COM / Replay / Sim)
├── evaluator_app.py            # Standalone Tkinter Performance Evaluator (4 Pillars Benchmark)
├── integrated_app.py           # Integrated Mission Suite (Connects Logger directly to Evaluator)
├── main.py                     # Master CLI / GUI Dispatcher
├── core/
│   ├── nmea_parser.py          # Multi-constellation NMEA 0183 parser ($GP, $GI/$IR, $GL, $GA, $GB)
│   ├── evaluator.py            # 4-Pillar calculation engine (CEP 50, 2DRMS 95, C/N0, PDOP, TTFF)
│   ├── plotter.py              # In-place Matplotlib figure generation (ENU, CDF, C/N0, Skyplot)
│   └── report_generator.py     # HTML & Print-ready CSS report generator
├── data/
│   ├── samples/                # Sample NMEA files for testing
│   ├── plots/                  # Exported publication figures (PNG)
│   └── reports/                # Generated evaluation reports (HTML)
└── requirements.txt            # Python dependencies (PyQt6, pandas, matplotlib, numpy, pyserial)
```

---

## 🚀 How to Run in PyCharm

Open the project in **PyCharm**. You have 3 ready-to-run configurations in the top-right toolbar:

1. **`Run Integrated Suite`** *(Recommended)*:
   - Runs `integrated_app.py`.
   - Gives you live COM logging, polar skyplot, and SNR bars.
   - When you click **⏹ Stop Recording** or **🚀 Run 4-Pillars Evaluation**, it immediately benchmarks the recorded data and generates the publication report.
2. **`Run Logger App`**:
   - Runs `logger_app.py` independently.
3. **`Run Evaluator App`**:
   - Runs `evaluator_app.py` independently with the dark engineering UI, instant validation pop-up, and 4 benchmark tabs.

---

## 💻 Running via Terminal / Command Prompt

```powershell
# 1. Run the Integrated Mission Suite (Default)
py main.py

# 2. Run only the Standalone Logger
py main.py --logger
# (or directly: py logger_app.py)

# 3. Run only the Standalone Evaluator
py main.py --evaluator
# (or directly: py evaluator_app.py)

# 4. Quick CLI benchmark on any recorded NMEA file
py main.py --evaluate "data/samples/sample_elena_evk_navic.nmea"
```

---

## 🛰️ The 4 Core Evaluation Pillars

| Pillar | Benchmarks & Attributes Evaluated |
| :--- | :--- |
| **1. Positioning Accuracy & Dispersion** | Local ENU ($\Delta E, \Delta N, \Delta U$), CEP 50%, DRMS, 2DRMS (95% Figure of Merit), SEP 3D, Vertical Dispersion ($2\sigma_{up}$), CDF Error Percentiles (50th, 68th, 95th, 99th). |
| **2. RF Signal Quality & Tracking** | Mean/Peak/Min $C/N_0$ per satellite, $C/N_0$ vs Elevation curve (<15° multipath zone vs high elevation gain), Satellites in Use ($N_{used}$) vs View ($N_{view}$), Frequency Band Separation (NavIC L5/S vs GPS L1/L5). |
| **3. Satellite Geometry & Constellation Health** | HDOP, VDOP, PDOP (Optimal <2.0 vs Degraded >3.5), Polar Skyplot (NavIC GEO/GSO coverage over India vs GPS orbits). |
| **4. Fix Reliability & Temporal Attributes** | Fix Availability Ratio (%), Solution Type Breakdown, TTFF (Time to First Fix), Epoch Continuity, Dropped Frames, Rate Jitter ($\pm \sigma_{\Delta t}$). |
