"""
Automated quality assurance and validation module for UWB Antenna Engineering.
Verifies dimensions, materials, geometric integrity, boundary enclosures, and simulation output.
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging
import numpy as np

from src.geometry import AntennaGeometry
from src.materials import MaterialManager

logger = logging.getLogger(__name__)


class AntennaValidator:
    """Performs static checks and dynamic post-simulation validation."""

    def __init__(self, antenna_cfg: Dict[str, Any], sim_cfg: Dict[str, Any]):
        self.antenna_cfg = antenna_cfg
        self.sim_cfg = sim_cfg
        self.geom = AntennaGeometry(antenna_cfg)
        self.mat = MaterialManager(antenna_cfg)

    def validate_all_static(self) -> Tuple[bool, List[str]]:
        """Runs complete suite of platform-independent static checks."""
        messages = []
        all_passed = True

        # 1. Material checks
        if not self.mat.validate_properties():
            all_passed = False
            messages.append("FAIL: Material property validation failed.")
        else:
            messages.append("PASS: Substrate and copper properties are physically valid.")

        # 2. Dimensional hierarchy checks
        if self.geom.sub_wid <= self.geom.patch_wid:
            all_passed = False
            messages.append("FAIL: Substrate width must strictly exceed patch width.")
        else:
            messages.append(f"PASS: Substrate width ({self.geom.sub_wid} mm) accommodates patch ({self.geom.patch_wid} mm).")

        if self.geom.sub_len <= (self.geom.gnd_len + self.geom.patch_to_gnd_gap + self.geom.patch_len):
            all_passed = False
            messages.append("FAIL: Substrate length cannot accommodate ground, gap, and patch.")
        else:
            total_y = self.geom.gnd_len + self.geom.patch_to_gnd_gap + self.geom.patch_len
            messages.append(f"PASS: Substrate length ({self.geom.sub_len} mm) fits CPW metallization ({total_y} mm).")

        # 3. CPW feed geometry
        cpw_total_w = self.geom.feed_wid + 2 * self.geom.feed_to_gnd_gap + 2 * self.geom.gnd_wid
        if cpw_total_w > self.geom.sub_wid:
            all_passed = False
            messages.append(f"FAIL: Total CPW width ({cpw_total_w} mm) exceeds substrate width ({self.geom.sub_wid} mm).")
        else:
            margin_x = (self.geom.sub_wid - cpw_total_w) / 2.0
            messages.append(f"PASS: CPW structure fits substrate with {margin_x:.2f} mm lateral dielectric margin.")

        # 4. Geometry polygons validity
        for cfg in ["Type_A", "Type_B", "Type_C"]:
            p = 7.0 if cfg == "Type_B" else (10.2 if cfg == "Type_C" else None)
            poly = self.geom.get_patch_polygon(cfg, p)
            if len(poly) < 3:
                all_passed = False
                messages.append(f"FAIL: {cfg} polygon has insufficient vertices ({len(poly)}).")
            else:
                # Area check via Shoelace formula
                x = [pt[0] for pt in poly]
                y = [pt[1] for pt in poly]
                area = 0.5 * abs(sum(x[i] * y[i + 1] - x[i + 1] * y[i] for i in range(len(poly) - 1)) + (x[-1] * y[0] - x[0] * y[-1]))
                if area <= 0:
                    all_passed = False
                    messages.append(f"FAIL: {cfg} polygon has non-positive area ({area:.2f} mm²).")
                else:
                    messages.append(f"PASS: {cfg} polygon valid with positive area {area:.2f} mm².")

        # 5. Air Box Enclosure check
        ab = self.geom.get_air_box(self.sim_cfg.get("air_box", {}).get("margin_mm", 25.0))
        if ab["size"][0] <= self.geom.sub_wid or ab["size"][1] <= self.geom.sub_len:
            all_passed = False
            messages.append("FAIL: Radiation air box does not fully enclose substrate.")
        else:
            messages.append(f"PASS: Radiation air box provides adequate open-space buffer.")

        return all_passed, messages

    @staticmethod
    def validate_simulation_csv(csv_path: str) -> Tuple[bool, str]:
        """Validates that simulated S11 CSV file exists, is non-empty, and contains valid numbers."""
        p = Path(csv_path)
        if not p.exists():
            return False, f"File does not exist: {p}"
        try:
            freqs = []
            s11_vals = []
            with open(p, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if len(lines) < 10:
                return False, f"CSV contains too few data points ({len(lines)} lines)."

            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 2:
                    freqs.append(float(parts[0]))
                    s11_vals.append(float(parts[1]))

            if any(np.isnan(s11_vals)) or any(np.isinf(s11_vals)):
                return False, "CSV contains NaN or Infinite values."

            return True, f"Valid S11 dataset with {len(freqs)} points spanning {min(freqs)} to {max(freqs)} GHz."
        except Exception as e:
            return False, f"Error parsing CSV: {e}"
