"""
Multi-stage parameter sweep coordinator for UWB Antenna Engineering.
Executes simulations strictly according to the specified 4-stage pipeline:
Stage 1: Type A baseline
Stage 2: Type C target (RAD = 10.2 mm)
Stage 3: Type B sweep (cuts = 3, 5, 7 mm)
Stage 4: Type C sweep (radii = 13, 12, 11, 10 mm)
"""

from typing import Dict, Any, List, Optional
import json
from pathlib import Path
import logging

from src.simulation import SimulationRunner

logger = logging.getLogger(__name__)


class ParameterSweepManager:
    """Manages sequential execution across all 4 stages with checkpoint persistence."""

    def __init__(self, antenna_cfg: Dict[str, Any], sim_cfg: Dict[str, Any], state_file: str = "results/simulation_state.json"):
        self.antenna_cfg = antenna_cfg
        self.sim_cfg = sim_cfg
        self.runner = SimulationRunner(antenna_cfg, sim_cfg)
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        """Loads sweep checkpoint state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not read state file: {e}. Starting fresh.")
        return {"completed_stages": [], "results": {}}

    def save_state(self):
        """Persists sweep progress to disk."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def run_stage(self, stage_num: int, config_type: str, params: Optional[List[float]] = None) -> bool:
        """Executes a single stage in sequence."""
        logger.info(f"========== Commencing Stage {stage_num}: {config_type} ==========")
        stage_tag = f"Stage_{stage_num}"
        if stage_tag in self.state["completed_stages"]:
            logger.info(f"{stage_tag} is already recorded as completed. Proceeding.")
            return True

        if params is None or len(params) == 0:
            res = self.runner.run_configuration(config_type=config_type, param=None)
            self.state["results"][config_type] = res
            if res.get("status") not in ["COMPLETED", "CACHED"]:
                logger.error(f"Stage {stage_num} failed or was blocked: {res}")
                return False
        else:
            for p in params:
                tag = f"{config_type}_{p}mm"
                logger.info(f"Running parameter variation: {tag}")
                res = self.runner.run_configuration(config_type=config_type, param=p)
                self.state["results"][tag] = res
                self.save_state()
                if res.get("status") not in ["COMPLETED", "CACHED"]:
                    logger.error(f"Variation {tag} failed or was blocked: {res}")
                    return False

        self.state["completed_stages"].append(stage_tag)
        self.save_state()
        logger.info(f"Stage {stage_num} successfully concluded.")
        return True

    def execute_full_pipeline(self) -> bool:
        """Runs Stage 1 through Stage 4 strictly in order."""
        # Stage 1: Type A baseline
        if not self.run_stage(1, "Type_A", params=None):
            return False

        # Stage 2: Type C target (RAD = 10.2 mm)
        if not self.run_stage(2, "Type_C", params=[10.2]):
            return False

        # Stage 3: Type B cuts (3, 5, 7 mm)
        type_b_cuts = self.antenna_cfg.get("configurations", {}).get("Type_B", {}).get("cut_dimensions_mm", [3.0, 5.0, 7.0])
        if not self.run_stage(3, "Type_B", params=type_b_cuts):
            return False

        # Stage 4: Type C radii (13, 12, 11, 10 mm)
        type_c_radii = [13.0, 12.0, 11.0, 10.0]
        if not self.run_stage(4, "Type_C", params=type_c_radii):
            return False

        logger.info("All 4 simulation stages completed successfully.")
        return True
