"""
Tests for the one-command workflow orchestration, bootstrap logic, and mocked simulation pipeline.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.system_monitor import SystemMonitor
from src.env_bootstrap import EnvironmentBootstrapper
from src.parameter_sweep import ParameterSweepManager
import main


def test_system_monitor_inspection():
    """Verify system monitor inspects environment without raising exceptions."""
    info = SystemMonitor.inspect_environment()
    assert "os_name" in info
    assert "python_version" in info
    assert "disk_free_gb" in info
    assert "total_ram_gb" in info
    assert isinstance(info["aedt_installed"], list)
    assert isinstance(info["missing_dependencies"], list)


def test_bootstrapper_paths():
    """Verify bootstrapper locates project root and python executable path."""
    project_root = Path(__file__).resolve().parent.parent
    bs = EnvironmentBootstrapper(project_root)
    assert bs.project_root == project_root
    assert bs.venv_dir == project_root / ".venv"
    assert bs.requirements_file == project_root / "requirements.txt"
    assert bs.venv_python.name in ["python", "python.exe"]


def test_mocked_hfss_simulation_pipeline(tmp_path):
    """
    Mocks PyAEDT Hfss and tests that the 4-stage simulation pipeline
    runs, creates outputs, and records checkpoints cleanly without real HFSS.
    """
    antenna_cfg, sim_cfg = main.load_configurations()

    state_file = tmp_path / "sim_state.json"
    sweep_mgr = ParameterSweepManager(antenna_cfg, sim_cfg, state_file=str(state_file))

    # Mock SimulationRunner.run_configuration to simulate HFSS runs
    def mock_run_cfg(config_type, param=None, project_dir="hfss_projects", overwrite=False):
        tag = f"{config_type}" if param is None else f"{config_type}_{param}mm"
        dummy_csv = tmp_path / f"S11_{tag}.csv"
        dummy_csv.write_text("Frequency_GHz,S11_dB\n3.0,-12.0\n4.0,-15.0\n")
        return {
            "config": config_type,
            "param": param,
            "status": "COMPLETED",
            "csv_path": str(dummy_csv),
            "aedt_path": str(tmp_path / f"{tag}.aedt"),
            "duration_seconds": 1.2
        }

    with patch.object(sweep_mgr.runner, "run_configuration", side_effect=mock_run_cfg):
        success = sweep_mgr.execute_full_pipeline()
        assert success is True
        assert len(sweep_mgr.state["completed_stages"]) == 4
        assert "Stage_1" in sweep_mgr.state["completed_stages"]
        assert "Stage_2" in sweep_mgr.state["completed_stages"]
        assert "Stage_3" in sweep_mgr.state["completed_stages"]
        assert "Stage_4" in sweep_mgr.state["completed_stages"]


def test_one_command_main_workflow_execution():
    """Runs the main one-command workflow with auto-confirmation flag in test mode."""
    # Run one-command workflow with -y and verify it executes all phases without error
    main.run_one_command_workflow(auto_confirm=True, force_simulate=False)

    report_pdf = Path(__file__).resolve().parent.parent / "report" / "final_report.pdf"
    assert report_pdf.exists()
    assert report_pdf.stat().st_size > 100000  # Non-trivial PDF size > 100 KB
