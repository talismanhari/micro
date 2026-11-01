"""
Plotting and visual analysis module for UWB Antenna Engineering.
Generates publication-quality S11, VSWR, multi-curve comparisons, and geometry layouts.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging

import matplotlib
matplotlib.use("Agg")  # Headless cross-platform rendering
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from src.geometry import AntennaGeometry

logger = logging.getLogger(__name__)


class AntennaPlotter:
    """Creates engineering figures and diagrams for reports and validation."""

    def __init__(self, output_dir: str = "results/figures"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_s11(
        self,
        freqs: np.ndarray,
        s11_db: np.ndarray,
        title: str,
        filename: str,
        bands: Optional[List[Dict[str, float]]] = None,
        published_bands: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """Plots S11 (return loss) vs Frequency with -10 dB threshold and operating band highlights."""
        fig, ax = plt.subplots(figsize=(8, 5), dpi=300)

        ax.plot(freqs, s11_db, color="#1f77b4", linewidth=2.0, label="Simulated $S_{11}$ (HFSS)")
        ax.axhline(-10.0, color="#d62728", linestyle="--", linewidth=1.5, label="Threshold ($S_{11} = -10\\text{ dB}$)")

        # Highlight detected operating bands
        if bands:
            for b in bands:
                ax.axvspan(b["f_lower_ghz"], b["f_upper_ghz"], color="#2ca02c", alpha=0.15,
                           label=f"Sim Band: {b['f_lower_ghz']}–{b['f_upper_ghz']} GHz ({b['bandwidth_mhz']} MHz)")

        # Mark published bands if provided
        if published_bands:
            for pb in published_bands:
                f_l = pb.get("f_lower_ghz", 0.0)
                f_u = pb.get("f_upper_ghz", 0.0)
                ax.axvspan(f_l, f_u, color="#ff7f0e", alpha=0.1, linestyle=":",
                           label=f"Published Band: {f_l}–{f_u} GHz")

        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.set_xlabel("Frequency (GHz)", fontsize=11)
        ax.set_ylabel("Return Loss $S_{11}$ (dB)", fontsize=11)
        ax.set_xlim(min(freqs), max(freqs))
        ax.set_ylim(-35, 0)
        ax.grid(True, linestyle=":", alpha=0.6)

        # Clean duplicate labels
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc="lower right", fontsize=8)

        plt.tight_layout()
        out_file = self.output_dir / filename
        fig.savefig(out_file)
        plt.close(fig)
        logger.info(f"Saved S11 plot: {out_file}")
        return out_file

    def plot_vswr(self, freqs: np.ndarray, vswr: np.ndarray, title: str, filename: str) -> Path:
        """Plots VSWR vs Frequency with VSWR = 2.0 reference line."""
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)

        ax.plot(freqs, vswr, color="#9467bd", linewidth=2.0, label="Simulated VSWR")
        ax.axhline(2.0, color="#d62728", linestyle="--", linewidth=1.5, label="VSWR = 2.0 (Matched Criterion)")

        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.set_xlabel("Frequency (GHz)", fontsize=11)
        ax.set_ylabel("VSWR (:1)", fontsize=11)
        ax.set_xlim(min(freqs), max(freqs))
        ax.set_ylim(1.0, 5.0)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper right", fontsize=9)

        plt.tight_layout()
        out_file = self.output_dir / filename
        fig.savefig(out_file)
        plt.close(fig)
        logger.info(f"Saved VSWR plot: {out_file}")
        return out_file

    def plot_multi_comparison(
        self,
        datasets: Dict[str, Tuple[np.ndarray, np.ndarray]],
        title: str,
        filename: str
    ) -> Path:
        """Plots comparative S11 curves across Type A, Type B, and Type C configurations."""
        fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)

        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
        for idx, (label, (freqs, s11)) in enumerate(datasets.items()):
            c = colors[idx % len(colors)]
            ax.plot(freqs, s11, label=label, color=c, linewidth=1.8)

        ax.axhline(-10.0, color="black", linestyle="--", linewidth=1.2, label="$S_{11} = -10\\text{ dB}$ Threshold")

        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.set_xlabel("Frequency (GHz)", fontsize=11)
        ax.set_ylabel("Return Loss $S_{11}$ (dB)", fontsize=11)
        ax.set_xlim(1.0, 14.0)
        ax.set_ylim(-35, 0)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="lower right", fontsize=8)

        plt.tight_layout()
        out_file = self.output_dir / filename
        fig.savefig(out_file)
        plt.close(fig)
        logger.info(f"Saved multi-comparison plot: {out_file}")
        return out_file

    def plot_geometry_layout(self, antenna_cfg: Dict[str, Any], config_type: str, param: Optional[float], filename: str) -> Path:
        """Draws exact 2D antenna layout showing substrate, CPW grounds, feed, and patch."""
        geom = AntennaGeometry(antenna_cfg)
        fig, ax = plt.subplots(figsize=(6, 6.5), dpi=300)

        # 1. Substrate
        sub = geom.substrate_box
        sub_rect = patches.Rectangle(
            (sub["origin"][0], sub["origin"][1]),
            sub["size"][0], sub["size"][1],
            linewidth=1.2, edgecolor="#555555", facecolor="#e0e8d0", label="FR4 Substrate"
        )
        ax.add_patch(sub_rect)

        # 2. Grounds
        for g in geom.ground_planes:
            g_rect = patches.Rectangle(
                (g["origin"][0], g["origin"][1]),
                g["size"][0], g["size"][1],
                linewidth=1, edgecolor="#b87333", facecolor="#d4af37", alpha=0.75, label="CPW Ground Plane"
            )
            ax.add_patch(g_rect)

        # 3. Feed Line
        fl = geom.feed_line
        fl_rect = patches.Rectangle(
            (fl["origin"][0], fl["origin"][1]),
            fl["size"][0], fl["size"][1],
            linewidth=1, edgecolor="#b87333", facecolor="#d4af37", alpha=0.9, label="CPW Feed Line (50 $\\Omega$)"
        )
        ax.add_patch(fl_rect)

        # 4. Patch Polygon
        patch_pts = geom.get_patch_polygon(config_type, param)
        patch_poly = patches.Polygon(
            patch_pts,
            closed=True, linewidth=1.5, edgecolor="#8b0000", facecolor="#b87333", alpha=0.85,
            label=f"Patch ({config_type} {f'param={param}' if param else ''})"
        )
        ax.add_patch(patch_poly)

        param_str = f" ({param} mm)" if param else ""
        ax.set_title(f"Antenna Layout — {config_type}{param_str}", fontsize=11, fontweight="bold")
        ax.set_xlabel("X Position (mm)", fontsize=10)
        ax.set_ylabel("Y Position (mm)", fontsize=10)

        pad = 4.0
        ax.set_xlim(-geom.sub_wid / 2.0 - pad, geom.sub_wid / 2.0 + pad)
        ax.set_ylim(-pad, geom.sub_len + pad)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, linestyle=":", alpha=0.4)

        # Remove duplicate legend entries
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc="upper right", fontsize=7)

        plt.tight_layout()
        out_file = self.output_dir / filename
        fig.savefig(out_file)
        plt.close(fig)
        logger.info(f"Saved layout diagram: {out_file}")
        return out_file
