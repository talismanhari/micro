"""
Electromagnetic data processing, bandwidth calculation, VSWR, and discrepancy evaluation.
Computes genuine S11 crossings (< -10 dB) and multi-band parameters from simulation data.
"""

from typing import Dict, Any, List, Tuple, Optional
import csv
import json
from pathlib import Path
import logging

import numpy as np

logger = logging.getLogger(__name__)


class PostProcessor:
    """Processes simulated S-parameter datasets, extracts bands, and evaluates discrepancies."""

    def __init__(self, s11_threshold_db: float = -10.0):
        self.s11_threshold_db = s11_threshold_db

    @staticmethod
    def load_s11_csv(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """Loads frequency (GHz) and S11 (dB) columns from CSV."""
        freqs = []
        s11_vals = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header
            for row in reader:
                if len(row) >= 2:
                    try:
                        freqs.append(float(row[0].strip()))
                        s11_vals.append(float(row[1].strip()))
                    except ValueError:
                        continue
        return np.array(freqs), np.array(s11_vals)

    def calculate_vswr(self, s11_db: np.ndarray) -> np.ndarray:
        """Calculates Voltage Standing Wave Ratio (VSWR) from return loss (dB)."""
        gamma = 10.0 ** (s11_db / 20.0)
        # Prevent division by zero near gamma = 1.0
        gamma = np.clip(gamma, 0.0, 0.99999)
        return (1.0 + gamma) / (1.0 - gamma)

    def extract_operating_bands(self, freqs: np.ndarray, s11_db: np.ndarray) -> List[Dict[str, float]]:
        """
        Extracts contiguous frequency intervals where S11 <= threshold (-10 dB).
        Uses linear interpolation to pinpoint exact -10 dB boundary crossings.
        """
        bands = []
        in_band = False
        f_start = None

        for i in range(len(freqs) - 1):
            f1, f2 = freqs[i], freqs[i + 1]
            s1, s2 = s11_db[i], s11_db[i + 1]

            # Downward crossing into band (S11 falls below -10 dB)
            if not in_band and s1 > self.s11_threshold_db and s2 <= self.s11_threshold_db:
                # Interpolate crossing frequency
                f_cross = f1 + (self.s11_threshold_db - s1) * (f2 - f1) / (s2 - s1)
                f_start = f_cross
                in_band = True
            elif not in_band and s1 <= self.s11_threshold_db:
                f_start = f1
                in_band = True

            # Upward crossing out of band (S11 rises above -10 dB)
            if in_band and s1 <= self.s11_threshold_db and s2 > self.s11_threshold_db:
                f_cross = f1 + (self.s11_threshold_db - s1) * (f2 - f1) / (s2 - s1)
                f_end = f_cross
                in_band = False

                bw_ghz = f_end - f_start
                f_center = (f_start + f_end) / 2.0
                fbw_percent = (bw_ghz / f_center) * 100.0 if f_center > 0 else 0.0

                bands.append({
                    "f_lower_ghz": round(float(f_start), 4),
                    "f_upper_ghz": round(float(f_end), 4),
                    "bandwidth_mhz": round(float(bw_ghz * 1000.0), 2),
                    "fractional_bw_percent": round(float(fbw_percent), 2)
                })

        # Handle case where sweep terminates while still below threshold
        if in_band and f_start is not None:
            f_end = freqs[-1]
            bw_ghz = f_end - f_start
            f_center = (f_start + f_end) / 2.0
            fbw_percent = (bw_ghz / f_center) * 100.0 if f_center > 0 else 0.0
            bands.append({
                "f_lower_ghz": round(float(f_start), 4),
                "f_upper_ghz": round(float(f_end), 4),
                "bandwidth_mhz": round(float(bw_ghz * 1000.0), 2),
                "fractional_bw_percent": round(float(fbw_percent), 2)
            })

        return bands

    @staticmethod
    def compare_with_published(sim_bands: List[Dict[str, float]], pub_bands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compares simulated bands with published research reference data."""
        comparisons = []
        for i, pub in enumerate(pub_bands):
            f_l_pub = pub.get("f_lower_ghz", 0.0)
            f_u_pub = pub.get("f_upper_ghz", 0.0)
            bw_pub = pub.get("published_bw_mhz", (f_u_pub - f_l_pub) * 1000.0)
            bw_calc = round((f_u_pub - f_l_pub) * 1000.0, 2)

            comp = {
                "band_index": i + 1,
                "published_f_lower_ghz": f_l_pub,
                "published_f_upper_ghz": f_u_pub,
                "published_bw_mhz": bw_pub,
                "calculated_from_limits_bw_mhz": bw_calc,
                "published_vs_calculated_discrepancy_mhz": round(bw_pub - bw_calc, 2)
            }

            if i < len(sim_bands):
                sim = sim_bands[i]
                comp["simulated_f_lower_ghz"] = sim["f_lower_ghz"]
                comp["simulated_f_upper_ghz"] = sim["f_upper_ghz"]
                comp["simulated_bw_mhz"] = sim["bandwidth_mhz"]
                comp["sim_vs_published_diff_mhz"] = round(sim["bandwidth_mhz"] - bw_pub, 2)
            else:
                comp["simulated_status"] = "No corresponding band found in simulation"

            comparisons.append(comp)
        return comparisons

    @staticmethod
    def export_summary_table(comparison_data: List[Dict[str, Any]], out_csv_path: str):
        """Writes structured validation comparison table to CSV."""
        out_p = Path(out_csv_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if not comparison_data:
            return

        headers = list(comparison_data[0].keys())
        with open(out_p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(comparison_data)
        logger.info(f"Exported validation table: {out_p}")
