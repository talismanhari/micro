"""
Single-run HFSS simulation coordinator and dataset exporter.
Ensures resource-safe execution, timeout handling, and structured data persistence.
Supports both model-preparation-only mode and full electromagnetic solve.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import csv
import logging
import time

from src.system_monitor import SystemMonitor
from src.hfss_setup import HFSSAutomation

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Coordinates geometry build, adaptive solve, data extraction, and project saving."""

    def __init__(self, antenna_cfg: Dict[str, Any], sim_cfg: Dict[str, Any], output_root: str = "results"):
        self.antenna_cfg = antenna_cfg
        self.sim_cfg = sim_cfg
        self.output_root = Path(output_root)
        self.raw_dir = self.output_root / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.monitor = SystemMonitor(
            min_disk_gb=sim_cfg.get("hardware_safeguards", {}).get("min_disk_free_gb", 10.0),
            max_ram_percent=sim_cfg.get("hardware_safeguards", {}).get("max_memory_percent", 80.0)
        )

    def prepare_model_only(
        self,
        config_type: str = "Type_A",
        param: Optional[float] = None,
        project_dir: str = "hfss_projects"
    ) -> Dict[str, Any]:
        """
        Connects to HFSS, builds model geometry, assigns materials, port, and air box,
        and saves the project WITHOUT executing the electromagnetic solve or mesh.
        """
        tag = f"{config_type}" if param is None else f"{config_type}_{param}mm"
        aedt_path = Path(project_dir) / config_type / f"{tag}.aedt"

        logger.info(f"Connecting to HFSS and preparing model: {tag}")
        hfss_auto = HFSSAutomation(self.antenna_cfg, self.sim_cfg)

        try:
            hfss_app = hfss_auto.initialize_hfss(
                project_path=str(aedt_path),
                design_name=tag
            )
            hfss_auto.prepare_model(config_type=config_type, param=param)

            return {
                "config": config_type,
                "param": param,
                "status": "MODEL_PREPARED",
                "aedt_path": str(aedt_path),
                "project_name": hfss_app.project_name,
                "design_name": hfss_app.design_name
            }
        except Exception as e:
            logger.error(f"HFSS model preparation failed for {tag}: {e}")
            return {
                "config": config_type,
                "param": param,
                "status": "FAILED",
                "error": str(e)
            }
        finally:
            hfss_auto.close()

    def run_configuration(
        self,
        config_type: str,
        param: Optional[float] = None,
        project_dir: str = "hfss_projects",
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Executes a single simulation run for specified configuration and parameter.
        Returns execution record with status and exported CSV path.
        """
        tag = f"{config_type}" if param is None else f"{config_type}_{param}mm"
        csv_path = self.raw_dir / f"S11_{tag}.csv"
        aedt_path = Path(project_dir) / config_type / f"{tag}.aedt"

        if csv_path.exists() and not overwrite:
            logger.info(f"Existing simulation results found for {tag} at {csv_path}. Skipping solve.")
            return {
                "config": config_type,
                "param": param,
                "status": "CACHED",
                "csv_path": str(csv_path),
                "aedt_path": str(aedt_path)
            }

        # Verify system resources before proceeding
        safe, msg = self.monitor.check_safety_guards()
        if not safe:
            logger.error(f"Execution halted by resource monitor: {msg}")
            return {"config": config_type, "param": param, "status": "RESOURCE_BLOCKED", "message": msg}

        logger.info(f"Starting HFSS simulation for: {tag}")
        start_time = time.time()

        hfss_auto = HFSSAutomation(self.antenna_cfg, self.sim_cfg)
        try:
            hfss_app = hfss_auto.initialize_hfss(
                project_path=str(aedt_path),
                design_name=tag
            )

            # Build model
            hfss_auto.build_model(config_type=config_type, param=param)

            # Setup solution & sweep
            setup, sweep = hfss_auto.setup_solution_and_sweep()

            # Execute solve
            logger.info(f"Running adaptive meshing and frequency sweep for {tag}...")
            setup.analyze()

            # Export S11 results (handling both Terminal and Modal solution types)
            logger.info(f"Extracting S11 data to: {csv_path}")
            report_expressions = ["dB(St(P1_CPW,P1_CPW))", "dB(S(P1_CPW,P1_CPW))"]
            report_exported = False

            for expr in report_expressions:
                try:
                    report = hfss_app.post.create_report(
                        expressions=[expr],
                        setup_sweep_name=f"{setup.name} : {sweep.name}",
                        report_category="Standard",
                        plot_type="Rectangular Plot"
                    )
                    report.export_report_to_csv(str(csv_path))
                    report_exported = True
                    break
                except Exception as ex:
                    logger.debug(f"Expression {expr} export attempt: {ex}")

            if not report_exported:
                raise RuntimeError(f"Could not export S-parameter report for expressions: {report_expressions}")

            # Save project
            hfss_auto.save_project()
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"Simulation completed for {tag} in {elapsed}s.")

            return {
                "config": config_type,
                "param": param,
                "status": "COMPLETED",
                "csv_path": str(csv_path),
                "aedt_path": str(aedt_path),
                "duration_seconds": elapsed
            }

        except Exception as e:
            logger.error(f"HFSS execution failed for {tag}: {e}")
            return {
                "config": config_type,
                "param": param,
                "status": "FAILED",
                "error": str(e)
            }
        finally:
            hfss_auto.close()
