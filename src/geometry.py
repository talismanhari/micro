"""
Geometry modeling module for UWB Antenna Engineering.
Defines parametric layout for Type A, Type B, and Type C antennas.
Provides exact coordinate definitions for cross-platform simulation and static verification.
"""

from typing import Dict, Any, List, Tuple, Optional
import math
import logging

logger = logging.getLogger(__name__)


class AntennaGeometry:
    """Computes exact coordinate geometry for CPW-fed planar monopole antenna."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sub_cfg = config.get("substrate", {})
        self.patch_cfg = config.get("patch", {})
        self.feed_cfg = config.get("feed", {})
        self.ground_cfg = config.get("ground", {})
        self.met_cfg = config.get("metallization", {})

        # Primary dimensions (mm)
        self.sub_len = float(self.sub_cfg.get("length_mm", 38.0))
        self.sub_wid = float(self.sub_cfg.get("width_mm", 43.0))
        self.sub_h = float(self.sub_cfg.get("thickness_mm", 1.53))

        self.patch_len = float(self.patch_cfg.get("length_mm", 18.4))
        self.patch_wid = float(self.patch_cfg.get("width_mm", 18.4))

        self.feed_wid = float(self.feed_cfg.get("width_mm", 3.1))
        self.feed_to_gnd_gap = float(self.feed_cfg.get("feed_to_ground_gap_mm", 0.55))
        self.patch_to_gnd_gap = float(self.feed_cfg.get("patch_to_ground_gap_mm", 0.50))

        self.gnd_len = float(self.ground_cfg.get("length_mm", 18.4))
        self.gnd_wid = float(self.ground_cfg.get("width_mm", 16.9))

        self.copper_t = float(self.met_cfg.get("thickness_mm", 0.1))

    # --- Substrate Bounds ---
    @property
    def substrate_box(self) -> Dict[str, Any]:
        """Substrate origin (X, Y, Z) and size (dX, dY, dZ)."""
        return {
            "origin": [-self.sub_wid / 2.0, 0.0, -self.sub_h],
            "size": [self.sub_wid, self.sub_len, self.sub_h]
        }

    # --- CPW Ground Planes ---
    @property
    def ground_planes(self) -> List[Dict[str, Any]]:
        """Left and right coplanar ground planes."""
        left_gnd_x = -(self.feed_wid / 2.0 + self.feed_to_gnd_gap + self.gnd_wid)
        right_gnd_x = self.feed_wid / 2.0 + self.feed_to_gnd_gap
        return [
            {
                "name": "Ground_Left",
                "origin": [left_gnd_x, 0.0, 0.0],
                "size": [self.gnd_wid, self.gnd_len, self.copper_t]
            },
            {
                "name": "Ground_Right",
                "origin": [right_gnd_x, 0.0, 0.0],
                "size": [self.gnd_wid, self.gnd_len, self.copper_t]
            }
        ]

    # --- Central Feed Line ---
    @property
    def feed_line(self) -> Dict[str, Any]:
        """Central CPW feed strip connecting input port at Y=0 to patch bottom."""
        feed_length = self.gnd_len + self.patch_to_gnd_gap
        return {
            "name": "FeedLine",
            "origin": [-self.feed_wid / 2.0, 0.0, 0.0],
            "size": [self.feed_wid, feed_length, self.copper_t]
        }

    # --- Radiating Patch Geometries ---
    def get_patch_polygon(self, config_type: str = "Type_A", param: Optional[float] = None, num_arc_pts: int = 30) -> List[Tuple[float, float]]:
        """
        Calculates 2D planar (X, Y) vertices for the radiating patch.
        Bottom edge of patch is at y_bot = gnd_len + patch_to_gnd_gap = 18.9 mm.
        Top edge of patch is at y_top = y_bot + patch_len = 37.3 mm.
        Left edge is at x_left = -patch_wid / 2 = -9.2 mm.
        Right edge is at x_right = +patch_wid / 2 = +9.2 mm.
        """
        y_bot = self.gnd_len + self.patch_to_gnd_gap
        y_top = y_bot + self.patch_len
        x_left = -self.patch_wid / 2.0
        x_right = self.patch_wid / 2.0

        if config_type == "Type_A":
            # Baseline rectangle
            return [
                (x_left, y_bot),
                (x_right, y_bot),
                (x_right, y_top),
                (x_left, y_top)
            ]

        elif config_type == "Type_B":
            # Straight-edge corner cut (c mm) on lower corners
            c = float(param if param is not None else 7.0)
            c = min(c, self.patch_wid / 2.0 - 0.1, self.patch_len - 0.1)

            return [
                (x_left + c, y_bot),
                (x_right - c, y_bot),
                (x_right, y_bot + c),
                (x_right, y_top),
                (x_left, y_top),
                (x_left, y_bot + c)
            ]

        elif config_type == "Type_C":
            # Circular-edge corner truncation (radius R mm)
            r = float(param if param is not None else 10.2)
            pts = []

            # Bottom center straight section between arcs
            # For corner rounding with circle tangent to bottom and side:
            # If r exceeds half-width, effective blend uses arc spanning between tangent points
            r_eff = min(r, self.patch_wid / 2.0 - 0.2, self.patch_len - 0.2)

            # Left corner arc: from (x_left, y_bot + r_eff) to (x_left + r_eff, y_bot)
            # Center of curvature is at (x_left + r_eff, y_bot + r_eff)
            cx_l = x_left + r_eff
            cy_l = y_bot + r_eff

            # Right corner arc: center at (x_right - r_eff, y_bot + r_eff)
            cx_r = x_right - r_eff
            cy_r = y_bot + r_eff

            # 1. Bottom straight edge between fillets
            pts.append((cx_l, y_bot))
            pts.append((cx_r, y_bot))

            # 2. Right fillet: angle -90 to 0 deg
            for i in range(num_arc_pts + 1):
                theta = -math.pi / 2.0 + (math.pi / 2.0) * (i / num_arc_pts)
                pts.append((cx_r + r_eff * math.cos(theta), cy_r + r_eff * math.sin(theta)))

            # 3. Top right and top left corners
            pts.append((x_right, y_top))
            pts.append((x_left, y_top))

            # 4. Left fillet: angle 180 to 270 deg
            for i in range(num_arc_pts + 1):
                theta = math.pi + (math.pi / 2.0) * (i / num_arc_pts)
                pts.append((cx_l + r_eff * math.cos(theta), cy_l + r_eff * math.sin(theta)))

            return pts

        else:
            raise ValueError(f"Unknown configuration type: {config_type}")

    # --- Radiation Air Box ---
    def get_air_box(self, margin_mm: float = 25.0) -> Dict[str, Any]:
        """Calculates radiation air box surrounding the entire antenna."""
        x_min = -self.sub_wid / 2.0 - margin_mm
        y_min = -margin_mm
        z_min = -self.sub_h - margin_mm

        dx = self.sub_wid + 2 * margin_mm
        dy = self.sub_len + 2 * margin_mm
        dz = self.sub_h + self.copper_t + 2 * margin_mm

        return {
            "name": "AirBox",
            "origin": [x_min, y_min, z_min],
            "size": [dx, dy, dz]
        }

    # --- Port Geometry ---
    @property
    def lumped_port_sheet(self) -> Dict[str, Any]:
        """
        CPW Lumped Port excitation sheet at input edge (y = 0).
        Spans across ground-gap-feed-gap-ground at y = 0,
        covering the full substrate thickness from z = -sub_h to z = 0,
        touching the central feed conductor and coplanar ground planes.
        """
        total_span = round(self.feed_wid + 2 * self.feed_to_gnd_gap, 4)
        return {
            "name": "Port_P1",
            "origin": [-total_span / 2.0, 0.0, -self.sub_h],
            "sizes": [total_span, self.sub_h],
            "size": [total_span, 0.0, self.sub_h],
            "orientation": "Y",
            "plane": "ZX"
        }
