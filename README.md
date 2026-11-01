# UWB ANTENNA ENGINEERING
## Cross-Platform Engineering Project: MacBook Development → GitHub → Windows Ansys HFSS Simulation

Automated computational electromagnetics project for the reconstruction, numerical simulation, bandwidth optimization, and validation of an **Ultra-Wideband (UWB) Coplanar Waveguide (CPW)-Fed Planar Monopole Patch Antenna**.

Based on published research:
> **"ULTRA HIGH BAND IMPROVEMENT OF PATCH ANTENNA"**  
> *J.R. Arunkumar, R. Anusuya, M. Sundarrajan, M. Ramkumar Prabhu*  
> *Journal of Engineering Sciences*, Vol. 11, Issue 2, Feb 2020. ISSN: 0377-9254.

---

## 1. System Architecture

| Role | Computer 1: MacBook (Development) | Computer 2: Lenovo LOQ (Simulation) |
|---|---|---|
| **OS** | macOS (Apple Silicon / Intel) | Windows 11 |
| **Hardware** | Portable workstation | Intel Core i5, NVIDIA RTX 3050 (6GB VRAM), 16GB RAM |
| **Tasks** | Code development, static validation, geometry math, test suite, plotting, report generation | PyAEDT automation, native Ansys HFSS 3D EM solve, native `.aedt` generation |
| **Safety** | Static checks only (no HFSS solver) | Resource monitor (CPU limit, RAM guard, disk space verification, sequential execution) |

---

## 2. Antenna Topologies & Parameter Summary

All physical dimensions are stored centrally in [`configs/antenna_parameters.json`](configs/antenna_parameters.json).

- **Dielectric Substrate:** FR4 Epoxy ($\epsilon_r = 4.4$, $\tan \delta = 0.02$), $L_{sub} = 38.0\text{ mm}$, $W_{sub} = 43.0\text{ mm}$, $h = 1.53\text{ mm}$.
- **Metallization:** Copper ($t = 0.1\text{ mm}$, single-sided top layer).
- **CPW Feed Line:** Width $W_f = 3.1\text{ mm}$ ($50\ \Omega$ reference).
- **Coplanar Grounds:** Two symmetrical planes, $L_g = 18.4\text{ mm}$, $W_g = 16.9\text{ mm}$.
- **Gaps:** Feed-to-ground $g_f = 0.55\text{ mm}$, Patch-to-ground $g_p = 0.50\text{ mm}$.
- **Radiating Patch:** Base square $18.4\text{ mm} \times 18.4\text{ mm}$.

### Implemented Configurations:
- **Type A:** Baseline square patch. Operating band: 3.05–3.89 GHz ($BW = 835.1\text{ MHz}$).
- **Type B:** Straight-edge corner chamfer (cuts: 3 mm, 5 mm, 7 mm). At 7 mm, bandwidth broadens to 5.07 GHz.
- **Type C:** Circular-edge corner truncation (radii: 13, 12, 11, 10, 10.2 mm). Target design at $\text{RAD} = 10.2\text{ mm}$ achieves continuous UWB coverage from 3.05 GHz to 12.00 GHz.

---

## 3. Literature Discrepancy Findings

Independent mathematical analysis revealed published arithmetic errors:
1. **Type A:** Text states 847.8 MHz, but table limits ($3.8877 - 3.0526\text{ GHz}$) calculate to 835.1 MHz (+12.7 MHz error in text).
2. **Type C (RAD = 10.2 mm Target):** Published bandwidth is **9124.70 MHz**, but $12.0000 - 3.0526 = 8.9474\text{ GHz}$ (**8947.40 MHz**). The paper overstates bandwidth by **+177.30 MHz**.
3. **Core Rule:** Never force simulated HFSS results to artificially match published errors.

---

## 4. Quick Start — MacBook (Development)

```bash
# 1. Clone repository
git clone <your-github-repo-url>
cd UWB_ANTENNA_ENGINEERING

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run static validation & test suite
pytest -v

# 5. Run full pipeline (validation, layouts, benchmark plots, PDF report)
python3 main.py --mode all
```

Output deliverables generated on MacBook:
- `report/final_report.pdf`: Professional engineering college PDF report.
- `results/figures/`: High-resolution antenna geometry layouts and S11/VSWR comparison plots.

---

## 5. Quick Start — Windows Lenovo LOQ (HFSS Simulation)

### Prerequisites on Windows
1. Ansys Electronics Desktop (AEDT) installed (2022.2 or later).
2. Python 3.10+ and Git for Windows.
3. HFSS license active.

### Execution Steps
```powershell
# 1. Open PowerShell / Command Prompt and clone
git clone <your-github-repo-url>
cd UWB_ANTENNA_ENGINEERING

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install PyAEDT and dependencies
pip install -r requirements.txt
pip install pyaedt

# 4. Run environment & hardware safety check
python environment_check.py

# 5. Execute 4-Stage Simulation Pipeline in HFSS
python main.py --mode simulate --stage all
```

### 4-Stage Execution Order
- **Stage 1:** Type A baseline.
- **Stage 2:** Type C Target ($\text{RAD} = 10.2\text{ mm}$).
- **Stage 3:** Type B straight cuts ($3\text{ mm}, 5\text{ mm}, 7\text{ mm}$).
- **Stage 4:** Type C full parameter sweep ($\text{RAD} = 13\text{ mm}, 12\text{ mm}, 11\text{ mm}, 10\text{ mm}$).

---

## 6. Hardware Safety Features (Laptop Protection)
- **Strict Single Solve:** One simulation at a time; avoids thermal throttling on Core i5.
- **RAM Check:** Halts solve if free memory < 20%.
- **Disk Guard:** Requires ≥ 10 GB free space before meshing.
- **Save Intermediate:** Checkpoint progress in `results/simulation_state.json`.

---

## 7. Git Workflow & Safety
- **Clean Commits:** Do not commit temporary `.aedtresults`, `.asol`, `.mesh`, or `__pycache__`.
- **Protected Files:** Checked `.gitignore` excludes temporary solver cache while preserving source, configs, and deliverables.
