# Research Analysis & Electromagnetic Validation Framework

## 1. Operating Mechanism of CPW-Fed Planar Monopole

The antenna designed by J. R. Arunkumar et al. (2020) employs a Coplanar Waveguide (CPW) feed rather than a microstrip backplane line.

### Key advantages of CPW in UWB planar monopoles:
1. **Single-Layer Metallization:** Both signal feed line and ground reference reside on the top substrate interface, drastically reducing dielectric surface-wave excitation and eliminating spurious radiation from vias.
2. **Wideband Impedance Matching:** The coupling gap between the central feed conductor ($W_f = 3.1\text{ mm}$) and symmetrical lateral ground planes ($g_f = 0.55\text{ mm}$) creates an intrinsic quasi-TEM mode exhibiting low dispersion across multi-octave frequencies.
3. **Corner Tapering Transition:** The abrupt right-angle transition between the ground plane and radiating patch causes capacitive and inductive discontinuity reactance. Truncating the patch corners (straight-cut Type B or smooth circular-cut Type C) provides a gradual impedance tapering, suppressing reflections across higher-order resonant modes.

---

## 2. Published Results vs. Independent Mathematical Verification

The table below catalogs the raw data published in the source paper, the calculated difference ($f_{upper} - f_{lower}$), and the discrepancy.

| Config | Variation | Published Lower ($f_L$) | Published Upper ($f_H$) | Published BW ($\Delta f_{pub}$) | Calculated BW ($f_H - f_L$) | Discrepancy ($\Delta f_{pub} - \Delta f_{calc}$) | Status |
|---|---|---:|---:|---:|---:|---:|---|
| **Type A** | Baseline Rectangular | 3.0526 GHz | 3.8877 GHz | 835.10 MHz | 835.10 MHz | 0.00 MHz | Exact match in Table; prose reports 847.8 MHz (+12.7 MHz error in text) |
| **Type B** | Cut = 3 mm | 3.0825 GHz | 4.0667 GHz | 984.20 MHz | 984.20 MHz | 0.00 MHz | Exact match |
| **Type B** | Cut = 5 mm | 3.0526 GHz | 4.2754 GHz | 1222.80 MHz | 1222.80 MHz | 0.00 MHz | Exact match |
| **Type B** | Cut = 7 mm | 2.9333 GHz | 8.0035 GHz | 5070.20 MHz | 5070.20 MHz | 0.00 MHz | Exact match |
| **Type C** | RAD = 13 mm | 2.9632 GHz | 3.7982 GHz | 835.10 MHz | 835.00 MHz | +0.10 MHz | Rounding artifact |
| **Type C** | RAD = 12 mm | 3.0228 GHz | 3.8877 GHz | 864.90 MHz | 864.90 MHz | 0.00 MHz | Exact match |
| **Type C** | RAD = 11 mm (Band 1) | 3.0526 GHz | 4.0965 GHz | 1445.90 MHz | 1043.90 MHz | +402.00 MHz | **Major Discrepancy:** $4.0965 - 3.0526 = 1.0439\text{ GHz}$; table reports 1445.9 MHz |
| **Type C** | RAD = 11 mm (Band 2) | 7.7649 GHz | 11.9702 GHz | 4545.30 MHz | 4205.30 MHz | +340.00 MHz | **Major Discrepancy:** $11.9702 - 7.7649 = 4.2053\text{ GHz}$; table reports 4545.3 MHz |
| **Type C** | RAD = 10 mm (Band 1) | 3.0228 GHz | 4.6632 GHz | 2640.40 MHz | 1640.40 MHz | +1000.00 MHz | **Major Discrepancy:** $4.6632 - 3.0228 = 1.6404\text{ GHz}$; table reports 2640.4 MHz |
| **Type C** | RAD = 10 mm (Band 2) | 6.0649 GHz | 12.0000 GHz | 6935.10 MHz | 5935.10 MHz | +1000.00 MHz | **Major Discrepancy:** $12.0 - 6.0649 = 5.9351\text{ GHz}$; table reports 6935.1 MHz |
| **Type C** | **RAD = 10.2 mm (Target)** | **3.0526 GHz** | **12.0000 GHz** | **9124.70 MHz** | **8947.40 MHz** | **+177.30 MHz** | **Critical Discrepancy:** $12.0000 - 3.0526 = 8.9474\text{ GHz}$ ($8947.4\text{ MHz}$), not $9124.7\text{ MHz}$ |

### Engineering Decision Rules:
1. **Never fabricate or force HFSS simulation results to match flawed published values.**
2. HFSS simulation results will be evaluated strictly by computing $S_{11} < -10\text{ dB}$ crossings directly on the simulated dataset.
3. Automated validation will output side-by-side comparison tables highlighting both the literature-reported figures and genuine electromagnetic simulation results.
