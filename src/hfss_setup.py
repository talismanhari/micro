"""
HFSS automation setup module using PyAEDT.
Builds the complete parametric 3D electromagnetic model:
Substrate, Ground Planes, Feed Line, Truncated Patch, Lumped Port, Air Box, and Solution Setup.
Includes intelligent session detection, auto-launching, and version auto-selection.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from src.geometry import AntennaGeometry
from src.materials import MaterialManager
from src.system_monitor import SystemMonitor

logger = logging.getLogger(__name__)


class HFSSAutomation:
    """Manages PyAEDT connection, model synthesis, boundary assignment, and project persistence."""

    def __init__(self, antenna_cfg: Dict[str, Any], sim_cfg: Dict[str, Any]):
        self.antenna_cfg = antenna_cfg
        self.sim_cfg = sim_cfg
        self.geom = AntennaGeometry(antenna_cfg)
        self.materials = MaterialManager(antenna_cfg)
        self.hfss = None

    @staticmethod
    def get_preferred_aedt_version() -> Optional[str]:
        """Detects installed AEDT version from system monitor."""
        detected = SystemMonitor.detect_installed_aedt_versions()
        if detected:
            ver = detected[0]["version"]
            logger.info(f"Targeting installed AEDT version: {ver} ({detected[0]['source']})")
            return ver
        return None

    def initialize_hfss(self, project_path: str, design_name: str = "UWB_Antenna", non_graphical: Optional[bool] = None):
        """
        Connects to an existing AEDT session or launches a new one automatically.
        Executed on Windows Simulation Machine.
        """
        try:
            from pyaedt import Hfss
        except ImportError as e:
            raise RuntimeError(
                "PyAEDT is not installed.\n"
                "To fix: Run 'pip install pyaedt' on the Windows simulation machine."
            ) from e

        project_file = Path(project_path).resolve()
        project_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if AEDT is already running
        running = SystemMonitor.check_running_aedt_processes()
        reuse_session = len(running) > 0
        if reuse_session:
            logger.info(f"Active AEDT process detected (PID: {running[0]['pid']}). Connecting to existing session.")
        else:
            logger.info("No active AEDT session detected. Launching Ansys Electronics Desktop automatically...")

        if non_graphical is None:
            non_graphical = self.sim_cfg.get("simulation_environment", {}).get("non_graphical", True)

        aedt_version = self.get_preferred_aedt_version()

        try:
            self.hfss = Hfss(
                projectname=str(project_file),
                designname=design_name,
                solution_type=self.sim_cfg.get("simulation_environment", {}).get("solution_type", "DrivenModal"),
                specified_version=aedt_version,
                non_graphical=non_graphical,
                new_desktop_session=(not reuse_session),
                close_on_exit=False
            )
        except Exception as err:
            err_str = str(err)
            if "license" in err_str.lower():
                raise RuntimeError(
                    f"Ansys License Error: {err}\n"
                    "Action: Verify Ansys license server configuration (ANSYSLMD_LICENSE_FILE / ANSYSLI_SERVERS)."
                ) from err
            elif "version" in err_str.lower():
                raise RuntimeError(
                    f"AEDT Version Mismatch: {err}\n"
                    f"Action: Ensure PyAEDT version matches installed AEDT ({aedt_version})."
                ) from err
            else:
                raise RuntimeError(f"Failed to connect to Ansys Electronics Desktop: {err}") from err

        self.hfss.modeler.model_units = "mm"
        logger.info(f"HFSS connected. Project: {project_file.name}, Design: {design_name}, Units: mm")
        return self.hfss

    def build_model(self, config_type: str = "Type_A", param: Optional[float] = None):
        """Builds substrate, grounds, feed line, patch, air box, boundaries, and ports."""
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized.")

        m = self.hfss.modeler

        # 1. Substrate
        sub = self.geom.substrate_box
        sub_obj = m.create_box(
            position=sub["origin"],
            dimensions_list=sub["size"],
            name="Substrate",
            matname=self.materials.substrate_name
        )
        logger.info("Created Substrate box.")

        # 2. Coplanar Ground Planes
        for g in self.geom.ground_planes:
            m.create_box(
                position=g["origin"],
                dimensions_list=g["size"],
                name=g["name"],
                matname=self.materials.metallization_name
            )
        logger.info("Created CPW Ground Planes.")

        # 3. Feed Line
        fl = self.geom.feed_line
        m.create_box(
            position=fl["origin"],
            dimensions_list=fl["size"],
            name=fl["name"],
            matname=self.materials.metallization_name
        )
        logger.info("Created CPW Feed Line.")

        # 4. Radiating Patch
        poly_pts = self.geom.get_patch_polygon(config_type, param)
        pts_3d = [[p[0], p[1], 0.0] for p in poly_pts]

        patch_sheet = m.create_polyline(
            position_list=pts_3d,
            cover_surface=True,
            name=f"Patch_{config_type}"
        )
        m.thicken_sheet(patch_sheet.name, self.geom.copper_t)
        patch_sheet.material_name = self.materials.metallization_name
        logger.info(f"Created Radiating Patch: {config_type} (param={param}).")

        # 5. Radiation Air Box & Boundary
        ab = self.geom.get_air_box(margin_mm=self.sim_cfg.get("air_box", {}).get("margin_mm", 25.0))
        air_obj = m.create_box(
            position=ab["origin"],
            dimensions_list=ab["size"],
            name=ab["name"],
            matname="air"
        )
        self.hfss.assign_radiation_boundary_to_objects(air_obj.name)
        logger.info("Created Air Box and assigned Radiation Boundary.")

        # 6. Lumped Port Excitation
        port_info = self.geom.lumped_port_sheet
        port_sheet = m.create_rectangle(
            csPlane=port_info["plane"],
            position=port_info["origin"],
            dimension_list=[port_info["size"][0], port_info["size"][2]],
            name=port_info["name"]
        )
        self.hfss.create_lumped_port_to_sheet(
            sheet_name=port_sheet.name,
            axisdir=0,
            portname=self.sim_cfg.get("excitation", {}).get("port_name", "P1_CPW"),
            impedance=self.sim_cfg.get("excitation", {}).get("reference_impedance_ohm", 50.0),
            renormalize=True
        )
        logger.info("Assigned 50-Ohm CPW Lumped Port.")

    def setup_solution_and_sweep(self):
        """Creates adaptive mesh setup and interpolating frequency sweep."""
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized.")

        setup_cfg = self.sim_cfg.get("solution_setup", {})
        sweep_cfg = self.sim_cfg.get("frequency_sweep", {})

        setup_name = setup_cfg.get("setup_name", "Setup_UWB")
        f_center = setup_cfg.get("solution_frequency_ghz", 7.5)
        max_passes = setup_cfg.get("max_passes", 12)
        delta_s = setup_cfg.get("max_delta_s", 0.02)

        setup = self.hfss.create_setup(name=setup_name)
        setup.props["Frequency"] = f"{f_center}GHz"
        setup.props["MaximumPasses"] = max_passes
        setup.props["MaxDeltaS"] = delta_s
        logger.info(f"Created Setup '{setup_name}' at {f_center} GHz (MaxPasses={max_passes}, DeltaS={delta_s}).")

        sweep_name = sweep_cfg.get("sweep_name", "Sweep_1to14GHz")
        f_start = sweep_cfg.get("start_freq_ghz", 1.0)
        f_stop = sweep_cfg.get("stop_freq_ghz", 14.0)
        step = sweep_cfg.get("step_size_ghz", 0.01)

        sweep = setup.create_frequency_sweep(
            unit="GHz",
            name=sweep_name,
            start_frequency=f_start,
            stop_frequency=f_stop,
            step_size=step,
            sweep_type=sweep_cfg.get("sweep_type", "Interpolating")
        )
        logger.info(f"Configured Sweep '{sweep_name}' ({f_start} to {f_stop} GHz, step {step} GHz).")
        return setup, sweep

    def save_project(self):
        """Saves native .aedt project file."""
        if self.hfss:
            self.hfss.save_project()
            logger.info("HFSS project successfully saved.")

    def close(self):
        """Closes HFSS design session cleanly without terminating background AEDT desktop if shared."""
        if self.hfss:
            try:
                self.hfss.release_desktop(close_projects=True, close_desktop=False)
            except Exception as e:
                logger.warning(f"Error releasing HFSS desktop: {e}")
            self.hfss = None
            logger.info("HFSS design session released.")
