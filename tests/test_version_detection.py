"""
Unit tests for Ansys Student 2025 R2 (v252) version detection,
PyAEDT 1.9.0 connection parameters, and safe desktop release behavior.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.system_monitor import SystemMonitor
from src.hfss_setup import HFSSAutomation
from src.simulation import SimulationRunner
import main


def test_known_versions_includes_2025_r2():
    """Verify 2025.2 is present at highest priority in KNOWN_AEDT_VERSIONS."""
    assert "2025.2" in SystemMonitor.KNOWN_AEDT_VERSIONS
    assert SystemMonitor.KNOWN_AEDT_VERSIONS[0] == "2025.2"


def test_student_2025_r2_path_detection(tmp_path):
    """
    Simulates Windows filesystem with Ansys Student 2025 R2:
    C:\\Program Files\\ANSYS Inc\\ANSYS Student\\v252\\AnsysEM
    and verifies detection.
    """
    mock_student_path = tmp_path / "Program Files" / "ANSYS Inc" / "ANSYS Student" / "v252" / "AnsysEM"
    mock_student_path.mkdir(parents=True, exist_ok=True)

    with patch.dict(os.environ, {
        "ProgramFiles": str(tmp_path / "Program Files"),
        "MOCK_WINDOWS_AEDT_CHECK": "1"
    }):
        detected = SystemMonitor.detect_installed_aedt_versions()
        matching = [d for d in detected if d["version"] == "2025.2"]
        assert len(matching) > 0
        assert matching[0]["is_student"] is True
        assert "ANSYS Student" in matching[0]["path"]


def test_ansys_root252_env_detection(tmp_path):
    """Verifies ANSYSEM_ROOT252 environment variable detection."""
    mock_em = tmp_path / "AnsysEM_Custom"
    mock_em.mkdir()

    with patch.dict(os.environ, {"ANSYSEM_ROOT252": str(mock_em)}):
        detected = SystemMonitor.detect_installed_aedt_versions()
        matching = [d for d in detected if d["version"] == "2025.2"]
        assert len(matching) > 0
        assert matching[0]["path"] == str(mock_em.resolve())


def test_hfss_setup_uses_student_grpc_settings():
    """
    Verifies that HFSSAutomation applies:
    - PYAEDT_USE_PRE_GRPC_ARGS = True
    - settings.grpc_secure_mode = False
    - version = 2025.2
    - student_version = True
    - new_desktop = False when reusing existing session
    """
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    # Mock pyaedt
    mock_pyaedt = MagicMock()
    mock_hfss_cls = MagicMock()
    mock_pyaedt.Hfss = mock_hfss_cls
    mock_pyaedt.settings = MagicMock()

    # Mock running process to trigger session reuse (new_desktop=False)
    mock_proc = [{"pid": 12345, "name": "ansysedt.exe"}]

    with patch("src.hfss_setup.pyaedt", mock_pyaedt), \
         patch.object(SystemMonitor, "check_running_aedt_processes", return_value=mock_proc), \
         patch.object(SystemMonitor, "detect_installed_aedt_versions", return_value=[{"version": "2025.2", "source": "test", "is_student": True}]):

        hfss_auto.initialize_hfss(project_path="Project1", design_name="HFSSDesign1")

        # Verify environment & gRPC mode
        assert os.environ.get("PYAEDT_USE_PRE_GRPC_ARGS") == "True"
        assert mock_pyaedt.settings.grpc_secure_mode is False

        # Verify Hfss call kwargs
        assert mock_hfss_cls.called
        called_kwargs = mock_hfss_cls.call_args[1]
        assert called_kwargs.get("version") == "2025.2" or called_kwargs.get("specified_version") == "2025.2"
        assert called_kwargs.get("student_version") is True
        assert called_kwargs.get("new_desktop") is False or called_kwargs.get("new_desktop_session") is False
        assert called_kwargs.get("close_on_exit") is False
        assert called_kwargs.get("solution_type") == "Terminal"


def test_hfss_cleanup_never_closes_desktop_or_projects():
    """Verifies that release_desktop strictly passes close_projects=False and close_desktop=False."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_app = MagicMock()
    hfss_auto.hfss = mock_app

    hfss_auto.close()
    mock_app.release_desktop.assert_called_once_with(close_projects=False, close_desktop=False)
    assert hfss_auto.hfss is None


def test_prepare_model_only_does_not_call_analyze():
    """Verifies prepare_model_only builds model and saves project without invoking solve/mesh."""
    antenna_cfg, sim_cfg = main.load_configurations()
    runner = SimulationRunner(antenna_cfg, sim_cfg)

    with patch.object(HFSSAutomation, "initialize_hfss") as mock_init, \
         patch.object(HFSSAutomation, "prepare_model") as mock_prep, \
         patch.object(HFSSAutomation, "close") as mock_close:

        mock_app = MagicMock()
        mock_app.project_name = "Project1"
        mock_app.design_name = "HFSSDesign1"
        mock_init.return_value = mock_app

        res = runner.prepare_model_only(config_type="Type_A")

        assert res["status"] == "MODEL_PREPARED"
        mock_prep.assert_called_once()
        mock_close.assert_called_once()
        # Verify setup.analyze was never called
        mock_app.analyze.assert_not_called()
