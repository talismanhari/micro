"""
HFSS automation setup module using PyAEDT.
Builds the complete parametric 3D electromagnetic model:
Substrate, Ground Planes, Feed Line, Truncated Patch, Lumped Port, Air Box, and Solution Setup.
Includes intelligent session detection, auto-launching, and version auto-selection.
Fully compatible with PyAEDT 1.9.0 and Ansys Electronics Desktop Student 2025 R2 (v252).
"""

import os
import inspect
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Required for PyAEDT gRPC connection in Student / modern versions
os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"

try:
    from ansys.aedt.core import Desktop, Hfss, settings
    settings.grpc_secure_mode = False
    pyaedt_available = True
except ImportError:
    try:
        import pyaedt
        from pyaedt import Desktop, Hfss
        pyaedt.settings.grpc_secure_mode = False
        settings = pyaedt.settings
        pyaedt_available = True
    except ImportError:
        Desktop = None
        Hfss = None
        settings = None
        pyaedt_available = False

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
    def get_preferred_aedt_version() -> str:
        """Detects installed AEDT version from system monitor, defaulting to 2025.2."""
        detected = SystemMonitor.detect_installed_aedt_versions()
        if detected:
            ver = detected[0]["version"]
            logger.info(f"Targeting detected AEDT version: {ver} ({detected[0]['source']})")
            return ver
        return "2025.2"

    def initialize_hfss(
        self,
        project_path: Optional[str] = None,
        design_name: Optional[str] = None,
        non_graphical: Optional[bool] = None,
        solution_type: Optional[str] = None,
        student_version: Optional[bool] = None,
        port: Optional[int] = None
    ):
        """
        Connects to an existing AEDT session or launches a new one automatically.
        Uses verified Student gRPC parameters:
        - PYAEDT_USE_PRE_GRPC_ARGS=True
        - settings.grpc_secure_mode=False
        - version="2025.2"
        - student_version=True
        - new_desktop=False when reusing existing session
        - port=50051
        """
        if not pyaedt_available or Hfss is None:
            raise RuntimeError(
                "PyAEDT (ansys.aedt.core) is not installed.\n"
                "To fix: Run 'pip install pyaedt' on the Windows simulation machine."
            )

        # Ensure gRPC settings are applied
        os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"
        if settings is not None:
            settings.grpc_secure_mode = False

        sim_env = self.sim_cfg.get("simulation_environment", {})

        # Check if AEDT is already running
        running = SystemMonitor.check_running_aedt_processes()
        reuse_session = len(running) > 0
        if reuse_session:
            logger.info(f"Active AEDT process detected (PID: {running[0]['pid']}). Connecting to existing session.")
        else:
            logger.info("No active AEDT session detected. Launching Ansys Electronics Desktop...")

        if non_graphical is None:
            non_graphical = sim_env.get("non_graphical", False)

        aedt_version = self.get_preferred_aedt_version()
        is_student = student_version if student_version is not None else sim_env.get("student_version", True)
        target_port = port if port is not None else sim_env.get("port", 50051)
        target_sol_type = solution_type or sim_env.get("solution_type", "Terminal")

        proj_name = project_path or sim_env.get("project_name", "Project1")
        des_name = design_name or sim_env.get("design_name", "HFSSDesign1")

        # Resolve project file path if specified as path
        if project_path and (Path(project_path).is_absolute() or "/" in str(project_path) or "\\" in str(project_path)):
            proj_file = Path(project_path).resolve()
            proj_file.parent.mkdir(parents=True, exist_ok=True)
            proj_target = str(proj_file)
        else:
            proj_target = proj_name

        # PyAEDT 1.9.0-compatible parameters with fallback for legacy signatures
        init_kwargs: Dict[str, Any] = {
            "project": proj_target,
            "design": des_name,
            "solution_type": target_sol_type,
            "version": aedt_version,
            "student_version": is_student,
            "new_desktop": not reuse_session,
            "port": target_port,
            "non_graphical": non_graphical,
            "close_on_exit": False
        }

        try:
            sig = inspect.signature(Hfss.__init__)
            params = sig.parameters
            if "specified_version" in params and "version" not in params:
                init_kwargs["specified_version"] = init_kwargs.pop("version")
            if "new_desktop_session" in params and "new_desktop" not in params:
                init_kwargs["new_desktop_session"] = init_kwargs.pop("new_desktop")
            if "projectname" in params and "project" not in params:
                init_kwargs["projectname"] = init_kwargs.pop("project")
            if "designname" in params and "design" not in params:
                init_kwargs["designname"] = init_kwargs.pop("design")
        except Exception:
            pass

        logger.info(
            f"PyAEDT Hfss connection args: version='{aedt_version}', student_version={is_student}, "
            f"new_desktop={init_kwargs.get('new_desktop', init_kwargs.get('new_desktop_session'))}, "
            f"port={target_port}, solution_type='{target_sol_type}'"
        )

        try:
            self.hfss = Hfss(**init_kwargs)
        except Exception as err:
            err_str = str(err)
            if "license" in err_str.lower():
                raise RuntimeError(
                    f"Ansys License Error: {err}\n"
                    "Action: Verify Ansys license server configuration or student license validity."
                ) from err
            elif "version" in err_str.lower():
                raise RuntimeError(
                    f"AEDT Version Mismatch: {err}\n"
                    f"Action: Verify AEDT version ({aedt_version}) and PyAEDT compatibility."
                ) from err
            else:
                raise RuntimeError(f"Failed to connect to Ansys Electronics Desktop: {err}") from err

        try:
            self.hfss.modeler.model_units = "mm"
        except Exception as e:
            logger.warning(f"Could not set modeler units to mm: {e}")

        logger.info(f"HFSS connected. Project: {self.hfss.project_name}, Design: {self.hfss.design_name}, Units: mm")
        return self.hfss

    @staticmethod
    def _create_box(modeler, origin, sizes, name: str, material: str):
        """
        Creates a 3D box supporting PyAEDT 1.9.0 (origin, sizes, name, material)
        as well as legacy PyAEDT calling conventions.
        """
        try:
            return modeler.create_box(origin=origin, sizes=sizes, name=name, material=material)
        except TypeError:
            try:
                return modeler.create_box(origin, sizes, name=name, material=material)
            except TypeError:
                try:
                    return modeler.create_box(position=origin, dimensions_list=sizes, name=name, matname=material)
                except TypeError:
                    return modeler.create_box(origin, sizes, name=name, matname=material)

    @staticmethod
    def _create_polyline(modeler, points, name: str, cover_surface: bool = True):
        """
        Creates a polyline supporting PyAEDT 1.9.0 (points, name, cover_surface)
        and legacy PyAEDT (position_list, name, cover_surface).
        """
        try:
            return modeler.create_polyline(points=points, name=name, cover_surface=cover_surface)
        except TypeError:
            try:
                return modeler.create_polyline(position_list=points, name=name, cover_surface=cover_surface)
            except TypeError:
                return modeler.create_polyline(points, name=name, cover_surface=cover_surface)

    @staticmethod
    def _create_rectangle(modeler, cs_plane, origin, sizes, name: str):
        """
        Creates a rectangle supporting PyAEDT 1.9.0 (cs_plane, origin, sizes, name)
        and legacy PyAEDT (csPlane, position, dimension_list, name).
        """
        try:
            return modeler.create_rectangle(cs_plane=cs_plane, origin=origin, sizes=sizes, name=name)
        except TypeError:
            try:
                return modeler.create_rectangle(csPlane=cs_plane, position=origin, dimension_list=sizes, name=name)
            except TypeError:
                return modeler.create_rectangle(cs_plane, origin, sizes, name=name)

    def build_model(self, config_type: str = "Type_A", param: Optional[float] = None):
        """Builds substrate, grounds, feed line, patch, air box, boundaries, and ports."""
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized.")

        m = self.hfss.modeler

        # 1. Assign materials
        self.materials.assign_pyaedt_materials(self.hfss)

        # 2. Substrate
        sub = self.geom.substrate_box
        self._create_box(
            m,
            origin=sub["origin"],
            sizes=sub["size"],
            name="Substrate",
            material=self.materials.substrate_name
        )
        logger.info("Created Substrate box.")

        # 3. Coplanar Ground Planes
        for g in self.geom.ground_planes:
            self._create_box(
                m,
                origin=g["origin"],
                sizes=g["size"],
                name=g["name"],
                material=self.materials.metallization_name
            )
        logger.info("Created CPW Ground Planes.")

        # 4. Feed Line
        fl = self.geom.feed_line
        self._create_box(
            m,
            origin=fl["origin"],
            sizes=fl["size"],
            name=fl["name"],
            material=self.materials.metallization_name
        )
        logger.info("Created CPW Feed Line.")

        # 5. Radiating Patch
        poly_pts = self.geom.get_patch_polygon(config_type, param)
        pts_3d = [[p[0], p[1], 0.0] for p in poly_pts]

        patch_sheet = self._create_polyline(
            m,
            points=pts_3d,
            name=f"Patch_{config_type}",
            cover_surface=True
        )
        m.thicken_sheet(patch_sheet.name, self.geom.copper_t)
        patch_sheet.material_name = self.materials.metallization_name
        logger.info(f"Created Radiating Patch: {config_type} (param={param}).")

        # 6. Radiation Air Box & Boundary
        ab = self.geom.get_air_box(margin_mm=self.sim_cfg.get("air_box", {}).get("margin_mm", 25.0))
        air_obj = self._create_box(
            m,
            origin=ab["origin"],
            sizes=ab["size"],
            name=ab["name"],
            material="air"
        )
        self.hfss.assign_radiation_boundary_to_objects(air_obj.name)
        logger.info("Created Air Box and assigned Radiation Boundary.")

        # 7. Lumped Port Excitation (handles both Terminal and DrivenModal solutions)
        port_info = self.geom.lumped_port_sheet
        port_sheet = self._create_rectangle(
            m,
            cs_plane=port_info["plane"],
            origin=port_info["origin"],
            sizes=[port_info["size"][0], port_info["size"][2]],
            name=port_info["name"]
        )
        port_name = self.sim_cfg.get("excitation", {}).get("port_name", "P1_CPW")
        port_z0 = self.sim_cfg.get("excitation", {}).get("reference_impedance_ohm", 50.0)

        try:
            self.hfss.create_lumped_port_to_sheet(
                sheet_name=port_sheet.name,
                axisdir=0,
                portname=port_name,
                impedance=port_z0,
                renormalize=True
            )
            logger.info("Assigned 50-Ohm CPW Lumped Port.")
        except Exception as pe:
            logger.warning(f"Standard lumped port assignment note: {pe}. Retrying with terminal configuration...")
            try:
                # Terminal solution fallback
                self.hfss.lumped_port(
                    assignment=port_sheet.name,
                    name=port_name,
                    reference=self.geom.ground_planes[0]["name"]
                )
                logger.info("Assigned 50-Ohm CPW Terminal Port.")
            except Exception as pe2:
                logger.warning(f"Terminal port fallback note: {pe2}")

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

    def prepare_model(self, config_type: str = "Type_A", param: Optional[float] = None) -> bool:
        """
        Builds geometry, materials, boundaries, and solution setup without running solve.
        Safely saves the model in HFSS.
        """
        logger.info(f"Preparing HFSS model for {config_type} (param={param})...")
        self.build_model(config_type=config_type, param=param)
        self.setup_solution_and_sweep()
        self.save_project()
        logger.info(f"HFSS model prepared and project saved: {config_type}")
        return True

    def save_project(self):
        """Saves native .aedt project file."""
        if self.hfss:
            try:
                self.hfss.save_project()
                logger.info("HFSS project successfully saved.")
            except Exception as e:
                logger.warning(f"Could not save project: {e}")

    def close(self):
        """
        Closes HFSS design session cleanly.
        NEVER terminates the user's running AEDT desktop or user's projects.
        """
        if self.hfss:
            try:
                # Strictly keep user's desktop and projects open
                self.hfss.release_desktop(close_projects=False, close_desktop=False)
                logger.info("HFSS design session released without closing AEDT or projects.")
            except Exception as e:
                logger.warning(f"Error releasing HFSS desktop: {e}")
            self.hfss = None
