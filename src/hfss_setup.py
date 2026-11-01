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
        self.created_objects: Dict[str, str] = {}
        self.created_boundaries: Dict[str, str] = {}

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
            return modeler.create_box(origin, sizes, name=name, material=material)
        except TypeError:
            try:
                return modeler.create_box(origin=origin, sizes=sizes, name=name, material=material)
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
    def _create_rectangle(modeler, orientation: str, origin: list, sizes: list, name: str):
        """
        Creates a 2D rectangle sheet using verified PyAEDT 1.9.0 signature:
        modeler.create_rectangle(orientation, origin, sizes, name=name)
        """
        return modeler.create_rectangle(
            orientation=orientation,
            origin=origin,
            sizes=sizes,
            name=name
        )

    def cleanup_previous_automation_items(self):
        """
        Removes previously generated automation objects, boundaries,
        and setups from prior runs in this design to ensure idempotency.
        Never touches unrelated user-defined objects.
        """
        if not self.hfss:
            return

        # 1. Clean up known automation boundaries / excitations
        known_boundary_prefixes = ("P1_CPW", "RadiationBox", "RadiationBoundary")
        try:
            boundaries = getattr(self.hfss, "boundaries", [])
            for b in list(boundaries):
                b_name = getattr(b, "name", "")
                if any(b_name == p or b_name.startswith(f"{p}_") or b_name.startswith(f"{p}:") for p in known_boundary_prefixes):
                    try:
                        b.delete()
                        logger.info(f"Cleaned up previous boundary/port: {b_name}")
                    except Exception as be:
                        logger.debug(f"Boundary delete note ({b_name}): {be}")
        except Exception as e:
            logger.debug(f"Boundary cleanup note: {e}")

        # 2. Clean up known automation geometry objects
        known_object_prefixes = (
            "Substrate", "Ground_Left", "Ground_Right", "FeedLine",
            "Patch_", "RadiatingPatch", "Port_P1", "AirBox", "RadiationBox"
        )
        try:
            modeler_objects = getattr(self.hfss.modeler, "object_names", [])
            to_delete = [
                obj for obj in modeler_objects
                if any(obj == p or obj.startswith(f"{p}_") for p in known_object_prefixes)
            ]
            if to_delete:
                self.hfss.modeler.delete(to_delete)
                logger.info(f"Cleaned up previous automation geometry objects: {to_delete}")
        except Exception as e:
            logger.debug(f"Geometry cleanup note: {e}")

        # 3. Clean up setup if already exists
        setup_name = self.sim_cfg.get("solution_setup", {}).get("setup_name", "Setup_UWB")
        try:
            active_setups = getattr(self.hfss, "setup_names", [])
            if setup_name in active_setups:
                self.hfss.delete_setup(setup_name)
                logger.info(f"Cleaned up previous setup: {setup_name}")
        except Exception as e:
            logger.debug(f"Setup cleanup note: {e}")

    def build_model(self, config_type: str = "Type_A", param: Optional[float] = None):
        """Builds substrate, grounds, feed line, patch, port, air box, and boundaries."""
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized.")

        # Cleanup any previous run artifacts to ensure repeatable, idempotent builds
        self.cleanup_previous_automation_items()
        self.created_objects.clear()
        self.created_boundaries.clear()

        m = self.hfss.modeler

        # 1. Assign materials
        self.materials.assign_pyaedt_materials(self.hfss)

        # 2. Substrate
        sub = self.geom.substrate_box
        sub_obj = self._create_box(
            m,
            origin=sub["origin"],
            sizes=sub["size"],
            name="Substrate",
            material=self.materials.substrate_name
        )
        self.created_objects["substrate"] = sub_obj.name
        logger.info(f"Created Substrate box '{sub_obj.name}'.")

        # 3. Coplanar Ground Planes
        for g in self.geom.ground_planes:
            g_obj = self._create_box(
                m,
                origin=g["origin"],
                sizes=g["size"],
                name=g["name"],
                material=self.materials.metallization_name
            )
            self.created_objects[g["name"]] = g_obj.name
        logger.info("Created CPW Ground Planes.")

        # 4. Feed Line
        fl = self.geom.feed_line
        feed_obj = self._create_box(
            m,
            origin=fl["origin"],
            sizes=fl["size"],
            name=fl["name"],
            material=self.materials.metallization_name
        )
        self.created_objects["feed"] = feed_obj.name
        logger.info(f"Created CPW Feed Line '{feed_obj.name}'.")

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
        self.created_objects["patch"] = patch_sheet.name
        logger.info(f"Created Radiating Patch '{patch_sheet.name}': {config_type} (param={param}).")

        # 6. Lumped Port Excitation (created on antenna structure before enclosing in air box)
        port_info = self.geom.lumped_port_sheet
        orientation = port_info.get("orientation", "Y")
        port_sheet = self._create_rectangle(
            m,
            orientation=orientation,
            origin=port_info["origin"],
            sizes=port_info["sizes"],
            name=port_info["name"]
        )
        self.created_objects["port_sheet"] = port_sheet.name
        logger.info(f"Created Port Sheet '{port_sheet.name}' on {orientation} plane (origin={port_info['origin']}, sizes={port_info['sizes']}).")

        port_name = self.sim_cfg.get("excitation", {}).get("port_name", "P1_CPW")
        port_z0 = self.sim_cfg.get("excitation", {}).get("reference_impedance_ohm", 50.0)

        # Check solution type: Terminal vs DrivenModal
        is_terminal = "terminal" in str(getattr(self.hfss, "solution_type", "Terminal")).lower()
        if is_terminal:
            ref_grounds = [g["name"] for g in self.geom.ground_planes]
            try:
                self.hfss.lumped_port(
                    assignment=port_sheet.name,
                    reference=ref_grounds,
                    name=port_name
                )
                logger.info(f"Assigned CPW Terminal Port '{port_name}' with reference grounds {ref_grounds}.")
            except Exception as te:
                logger.warning(f"Multi-reference port assignment notice: {te}. Retrying with primary ground reference...")
                self.hfss.lumped_port(
                    assignment=port_sheet.name,
                    reference=ref_grounds[0],
                    name=port_name
                )
                logger.info(f"Assigned CPW Terminal Port '{port_name}' with primary reference '{ref_grounds[0]}'.")
        else:
            self.hfss.create_lumped_port_to_sheet(
                sheet_name=port_sheet.name,
                axisdir=0,
                portname=port_name,
                impedance=port_z0,
                renormalize=True
            )
            logger.info(f"Assigned CPW Modal Lumped Port '{port_name}'.")
        self.created_boundaries["port"] = port_name

        # 7. Radiation Air Box & Boundary
        ab = self.geom.get_air_box(margin_mm=self.sim_cfg.get("air_box", {}).get("margin_mm", 25.0))
        air_obj = self._create_box(
            m,
            origin=ab["origin"],
            sizes=ab["size"],
            name=ab["name"],
            material="air"
        )
        self.created_objects["air_box"] = air_obj.name

        rad_b_name = self.sim_cfg.get("air_box", {}).get("boundary_name", "RadiationBox")
        try:
            self.hfss.assign_radiation_boundary_to_objects(air_obj.name, name=rad_b_name)
        except Exception as rbe:
            logger.warning(f"Named radiation boundary assignment notice: {rbe}. Retrying with default naming...")
            self.hfss.assign_radiation_boundary_to_objects(air_obj.name)
        self.created_boundaries["radiation"] = rad_b_name
        logger.info(f"Created Air Box '{air_obj.name}' and assigned Radiation Boundary '{rad_b_name}'.")

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
        if not setup:
            raise RuntimeError(f"PyAEDT failed to create setup '{setup_name}'.")
        setup.props["Frequency"] = f"{f_center}GHz"
        setup.props["MaximumPasses"] = max_passes
        setup.props["MaxDeltaS"] = delta_s
        setup.update()
        logger.info(f"Created Setup '{setup_name}' at {f_center} GHz (MaxPasses={max_passes}, DeltaS={delta_s}).")

        sweep_name = sweep_cfg.get("sweep_name", "Sweep_1to14GHz")
        f_start = sweep_cfg.get("start_freq_ghz", 1.0)
        f_stop = sweep_cfg.get("stop_freq_ghz", 14.0)
        step = sweep_cfg.get("step_size_ghz", 0.01)
        sweep_type = sweep_cfg.get("sweep_type", "Interpolating")
        save_fields = sweep_cfg.get("save_fields", False)

        # PyAEDT 1.9.0 SetupHFSS.create_frequency_sweep uses num_of_freq_points (int)
        # For 1.0 - 14.0 GHz with 0.01 GHz step: (14.0 - 1.0) / 0.01 + 1 = 1301 points
        num_of_freq_points = int(round((f_stop - f_start) / step)) + 1

        sweep = setup.create_frequency_sweep(
            unit="GHz",
            name=sweep_name,
            start_frequency=f_start,
            stop_frequency=f_stop,
            num_of_freq_points=num_of_freq_points,
            sweep_type=sweep_type,
            save_fields=save_fields,
            save_rad_fields=False
        )
        if not sweep:
            raise RuntimeError(f"PyAEDT failed to create frequency sweep '{sweep_name}' on setup '{setup_name}'.")

        logger.info(
            f"Configured Sweep '{sweep_name}' ({f_start} to {f_stop} GHz, "
            f"{num_of_freq_points} points, step {step} GHz, type={sweep_type})."
        )
        return setup, sweep

    def validate_prepared_model(
        self,
        config_type: str = "Type_A",
        setup_name: str = "Setup_UWB",
        sweep_name: str = "Sweep_1to14GHz"
    ) -> bool:
        """
        Validates that all required geometry objects, excitation port, radiation
        boundary, solution setup, and frequency sweep are properly instantiated.
        Raises RuntimeError if any critical component is missing or duplicated.
        """
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized.")

        # 1. Verify Model Objects using actual created object names
        modeler_obj_attr = getattr(self.hfss.modeler, "object_names", None)
        if isinstance(modeler_obj_attr, list):
            if self.created_objects:
                required_objects = list(self.created_objects.values())
            else:
                required_objects = [
                    "Substrate", "Ground_Left", "Ground_Right", "FeedLine",
                    f"Patch_{config_type}", "Port_P1", "AirBox"
                ]

            missing_objects = [obj for obj in required_objects if obj not in modeler_obj_attr]
            if missing_objects:
                raise RuntimeError(
                    f"HFSS model validation failed: missing geometry objects {missing_objects}. "
                    f"Available model objects: {modeler_obj_attr}"
                )
            logger.info(f"Validated all required geometry objects: {required_objects}")

        # 2. Verify Port Excitation (exactly one intended port)
        port_name = self.created_boundaries.get("port", self.sim_cfg.get("excitation", {}).get("port_name", "P1_CPW"))
        excitations = getattr(self.hfss, "excitation_names", None)
        boundaries = getattr(self.hfss, "boundaries", None)

        if isinstance(excitations, list) and isinstance(boundaries, list):
            b_names = [getattr(b, "name", str(b)) for b in boundaries]
            matching_ports = [e for e in excitations if port_name in e] or [b for b in b_names if port_name in b]
            if not matching_ports:
                raise RuntimeError(
                    f"HFSS model validation failed: excitation port '{port_name}' not found. "
                    f"Active excitations: {excitations}, boundaries: {b_names}"
                )
            if len(matching_ports) > 1:
                raise RuntimeError(
                    f"HFSS model validation failed: multiple port excitations found {matching_ports}. "
                    f"Expected exactly 1."
                )
            logger.info(f"Validated exactly one excitation port: '{matching_ports[0]}'.")

        # 3. Verify Radiation Boundary (assigned to actual air-box object)
        if isinstance(boundaries, list):
            air_box_name = self.created_objects.get("air_box", "AirBox")
            rad_b_name = self.created_boundaries.get("radiation", self.sim_cfg.get("air_box", {}).get("boundary_name", "RadiationBox"))

            matching_rad = []
            for b in boundaries:
                b_name = getattr(b, "name", str(b))
                b_type = getattr(b, "type", "")
                if b_type == "Radiation" or rad_b_name in b_name or "rad" in b_name.lower():
                    props = getattr(b, "props", {})
                    assigned_objs = props.get("Objects", []) if isinstance(props, dict) else []
                    if assigned_objs and air_box_name not in assigned_objs:
                        continue
                    matching_rad.append(b)

            if not matching_rad:
                raise RuntimeError(
                    f"HFSS model validation failed: radiation boundary not found for air box '{air_box_name}'. "
                    f"Active boundaries: {[getattr(b, 'name', str(b)) for b in boundaries]}"
                )
            if len(matching_rad) > 1:
                raise RuntimeError(
                    f"HFSS model validation failed: duplicate radiation boundaries found: {[getattr(b, 'name', str(b)) for b in matching_rad]}"
                )
            logger.info(f"Validated exactly one radiation boundary: '{getattr(matching_rad[0], 'name', str(matching_rad[0]))}'.")

        # 4. Verify Solution Setup (exactly one setup)
        setups = getattr(self.hfss, "setup_names", None)
        if isinstance(setups, list):
            if setup_name not in setups:
                raise RuntimeError(f"HFSS model validation failed: setup '{setup_name}' not found in active setups {setups}.")
            matching_setups = [s for s in setups if s == setup_name]
            if len(matching_setups) > 1:
                raise RuntimeError(f"HFSS model validation failed: duplicate setups found {matching_setups}.")
            logger.info(f"Validated exactly one solution setup: '{setup_name}'.")

        # 5. Verify Frequency Sweep (exactly one sweep in setup)
        setup_sweeps = getattr(self.hfss, "setup_sweeps_names", None)
        if isinstance(setup_sweeps, dict) and setup_name in setup_sweeps:
            sweeps_in_setup = setup_sweeps.get(setup_name, [])
            if sweep_name not in sweeps_in_setup:
                raise RuntimeError(f"HFSS model validation failed: sweep '{sweep_name}' not found in setup '{setup_name}' sweeps {sweeps_in_setup}.")
            if len(sweeps_in_setup) > 1:
                raise RuntimeError(f"HFSS model validation failed: duplicate sweeps found {sweeps_in_setup} in setup '{setup_name}'.")
            logger.info(f"Validated exactly one frequency sweep: '{sweep_name}'.")

        return True

    def prepare_model(self, config_type: str = "Type_A", param: Optional[float] = None) -> bool:
        """
        Builds geometry, materials, boundaries, and solution setup without running solve.
        Validates model completeness and safely saves the model in HFSS.
        """
        logger.info(f"Preparing HFSS model for {config_type} (param={param})...")
        self.build_model(config_type=config_type, param=param)
        setup, sweep = self.setup_solution_and_sweep()
        s_name = getattr(setup, "name", "Setup_UWB")
        sw_name = getattr(sweep, "name", "Sweep_1to14GHz")
        self.validate_prepared_model(config_type=config_type, setup_name=s_name, sweep_name=sw_name)
        self.save_project()
        logger.info(f"HFSS model prepared, verified, and project saved: {config_type}")
        return True

    def save_project(self):
        """Saves native .aedt project file."""
        if not self.hfss:
            raise RuntimeError("HFSS instance is not initialized; cannot save project.")
        try:
            saved = self.hfss.save_project()
            if saved is False:
                raise RuntimeError("HFSS.save_project() returned False.")
            logger.info("HFSS project successfully saved.")
        except Exception as e:
            logger.error(f"Failed to save HFSS project: {e}")
            raise

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
