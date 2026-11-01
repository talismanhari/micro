"""
Unit tests for Ansys Student 2025 R2 (v252) version detection,
PyAEDT (ansys.aedt.core) package detection and connection parameters,
and safe desktop release behavior.
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


def test_pyaedt_package_detection_via_ansys_aedt_core():
    """
    Verifies that SystemMonitor detects PyAEDT using ansys.aedt.core
    and extracts version via importlib.metadata.version('pyaedt').
    """
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec), \
         patch("importlib.metadata.version", return_value="1.9.0"):
        info = SystemMonitor.inspect_environment()
        assert info["pyaedt_version"] == "1.9.0"


def test_pyaedt_package_not_installed():
    """Verifies that SystemMonitor correctly reports 'Not Installed' when ansys.aedt.core is absent."""
    with patch("importlib.util.find_spec", return_value=None):
        info = SystemMonitor.inspect_environment()
        assert info["pyaedt_version"] == "Not Installed"


def test_missing_dependencies_checks_ansys_aedt_core():
    """Verifies that check_missing_dependencies verifies ansys.aedt.core on Windows."""
    with patch("platform.system", return_value="Windows"), \
         patch("importlib.util.find_spec", return_value=None):
        missing = SystemMonitor.check_missing_dependencies()
        assert any("ansys.aedt.core" in m for m in missing)


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

    # Mock Hfss class and settings
    mock_hfss_cls = MagicMock()
    mock_settings = MagicMock()

    # Mock running process to trigger session reuse (new_desktop=False)
    mock_proc = [{"pid": 12345, "name": "ansysedt.exe"}]

    with patch("src.hfss_setup.Hfss", mock_hfss_cls), \
         patch("src.hfss_setup.settings", mock_settings), \
         patch("src.hfss_setup.pyaedt_available", True), \
         patch.object(SystemMonitor, "check_running_aedt_processes", return_value=mock_proc), \
         patch.object(SystemMonitor, "detect_installed_aedt_versions", return_value=[{"version": "2025.2", "source": "test", "is_student": True}]):

        hfss_auto.initialize_hfss(project_path="Project1", design_name="HFSSDesign1")

        # Verify environment & gRPC mode
        assert os.environ.get("PYAEDT_USE_PRE_GRPC_ARGS") == "True"
        assert mock_settings.grpc_secure_mode is False

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


def test_create_box_pyaedt_190_signature():
    """Verifies that _create_box passes origin, sizes, name, and material to PyAEDT 1.9.0 modeler."""
    mock_modeler = MagicMock()
    HFSSAutomation._create_box(
        mock_modeler,
        origin=[0, 0, 0],
        sizes=[10, 20, 1.6],
        name="TestBox",
        material="FR4_epoxy"
    )
    mock_modeler.create_box.assert_called_once_with(
        [0, 0, 0],
        [10, 20, 1.6],
        name="TestBox",
        material="FR4_epoxy"
    )


def test_main_reports_preparation_failure_as_failure():
    """Verifies that main workflow fails immediately if HFSS preparation fails."""
    with patch("platform.system", return_value="Windows"), \
         patch("src.system_monitor.SystemMonitor.detect_installed_aedt_versions", return_value=[{"version": "2025.2", "is_student": True}]), \
         patch("src.system_monitor.SystemMonitor.check_running_aedt_processes", return_value=[{"pid": 12345}]), \
         patch("importlib.util.find_spec", return_value=MagicMock()), \
         patch("src.simulation.SimulationRunner.prepare_model_only", return_value={"status": "FAILED", "error": "PyAEDT Connection Timeout"}), \
         pytest.raises(SystemExit) as exc_info:

        main.run_one_command_workflow(force_simulate=True)

    assert exc_info.value.code == 1



def test_material_exists_pyaedt_190_collection():
    """Verifies that MaterialManager.material_exists correctly detects materials via PyAEDT 1.9.0 collection."""
    from src.materials import MaterialManager

    # Case 1: Collection membership (`name in materials`)
    mock_materials_coll = {"fr4_epoxy": MagicMock(), "copper": MagicMock()}
    assert MaterialManager.material_exists(mock_materials_coll, "FR4_epoxy") is False  # case check
    assert MaterialManager.material_exists(mock_materials_coll, "copper") is True

    # Case 2: material_keys attribute
    class MockMaterialsObj:
        material_keys = ["FR4_epoxy", "copper"]
    mock_materials_keys = MockMaterialsObj()
    assert MaterialManager.material_exists(mock_materials_keys, "FR4_epoxy") is True
    assert MaterialManager.material_exists(mock_materials_keys, "fr4_epoxy") is True
    assert MaterialManager.material_exists(mock_materials_keys, "aluminum") is False


def test_assign_pyaedt_materials_avoids_duplicate():
    """Verifies assign_pyaedt_materials avoids duplicate material creation."""
    from src.materials import MaterialManager

    mat_mgr = MaterialManager({
        "substrate": {"material": "FR4_epoxy", "relative_permittivity": 4.4, "dielectric_loss_tangent": 0.02},
        "metallization": {"material": "copper", "conductivity_siemens_per_m": 5.8e7}
    })

    mock_app = MagicMock()
    mock_materials = MagicMock()
    mock_materials.__contains__.side_effect = lambda item: item in ["FR4_epoxy", "copper"]
    mock_app.materials = mock_materials

    success = mat_mgr.assign_pyaedt_materials(mock_app)
    assert success is True
    mock_materials.add_material.assert_not_called()


def test_create_rectangle_pyaedt_190_signature():
    """Verifies that _create_rectangle passes orientation, origin, sizes, and name to PyAEDT 1.9.0 modeler."""
    mock_modeler = MagicMock()
    HFSSAutomation._create_rectangle(
        mock_modeler,
        orientation="Y",
        origin=[-2.1, 0.0, -1.53],
        sizes=[4.2, 1.53],
        name="Port_P1"
    )
    mock_modeler.create_rectangle.assert_called_once_with(
        orientation="Y",
        origin=[-2.1, 0.0, -1.53],
        sizes=[4.2, 1.53],
        name="Port_P1"
    )


def test_lumped_port_geometry_spans_substrate_and_conductors():
    """
    Verifies that lumped_port_sheet in AntennaGeometry:
    - Origin at [-2.1, 0.0, -1.53] (bottom edge of substrate at feed end)
    - Sizes [4.2, 1.53] (spans X in [-2.1, 2.1] and Z from -1.53 to 0.0)
    - Normal orientation is 'Y' (ZX plane at Y=0)
    """
    from src.geometry import AntennaGeometry
    antenna_cfg, _ = main.load_configurations()
    geom = AntennaGeometry(antenna_cfg)
    port = geom.lumped_port_sheet

    assert port["name"] == "Port_P1"
    assert port["orientation"] == "Y"
    assert port["plane"] == "ZX"
    assert port["origin"] == [-2.1, 0.0, -1.53]
    assert port["sizes"] == [4.2, 1.53]


def test_terminal_lumped_port_assignment_in_build_model():
    """
    Verifies that build_model invokes hfss.lumped_port with assignment='Port_P1'
    and references matching the ground planes when solution_type is Terminal.
    """
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.solution_type = "Terminal"
    mock_modeler = MagicMock()
    mock_hfss.modeler = mock_modeler

    # Mock sheet and box returns
    mock_sheet = MagicMock()
    mock_sheet.name = "Port_P1"
    mock_box = MagicMock()
    mock_box.name = "AirBox"
    mock_modeler.create_rectangle.return_value = mock_sheet
    mock_modeler.create_box.return_value = mock_box
    mock_modeler.create_polyline.return_value = MagicMock(name="Polyline")

    hfss_auto.hfss = mock_hfss

    with patch.object(hfss_auto.materials, "assign_pyaedt_materials", return_value=True):
        hfss_auto.build_model(config_type="Type_A")

    # Verify rectangle creation for Port_P1
    mock_modeler.create_rectangle.assert_called_with(
        orientation="Y",
        origin=[-2.1, 0.0, -1.53],
        sizes=[4.2, 1.53],
        name="Port_P1"
    )

    # Verify Terminal port assignment
    mock_hfss.lumped_port.assert_called_once_with(
        assignment="Port_P1",
        reference=["Ground_Left", "Ground_Right"],
        name="P1_CPW"
    )


def test_setup_solution_and_sweep_pyaedt_190_signature():
    """
    Verifies that setup_solution_and_sweep:
    - Creates Setup_UWB at 7.5 GHz, max_passes=12, delta_s=0.02
    - Calls setup.update()
    - Invokes setup.create_frequency_sweep with verified PyAEDT 1.9.0 signature:
      unit="GHz", start_frequency=1.0, stop_frequency=14.0,
      num_of_freq_points=1301, sweep_type="Interpolating", save_fields=False, save_rad_fields=False
    - Does NOT pass unexpected keyword argument 'step_size'
    """
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_setup = MagicMock()
    mock_setup.props = {}
    mock_sweep = MagicMock()
    mock_setup.create_frequency_sweep.return_value = mock_sweep
    mock_hfss.create_setup.return_value = mock_setup

    hfss_auto.hfss = mock_hfss

    setup, sweep = hfss_auto.setup_solution_and_sweep()

    # Verify setup creation and properties
    mock_hfss.create_setup.assert_called_once_with(name="Setup_UWB")
    assert mock_setup.props["Frequency"] == "7.5GHz"
    assert mock_setup.props["MaximumPasses"] == 12
    assert mock_setup.props["MaxDeltaS"] == 0.02
    mock_setup.update.assert_called_once()

    # Verify sweep call arguments
    mock_setup.create_frequency_sweep.assert_called_once_with(
        unit="GHz",
        name="Sweep_1to14GHz",
        start_frequency=1.0,
        stop_frequency=14.0,
        num_of_freq_points=1301,
        sweep_type="Interpolating",
        save_fields=False,
        save_rad_fields=False
    )
    assert sweep == mock_sweep


def test_validate_prepared_model_success():
    """Verifies that validate_prepared_model passes when all components exist."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiatingPatch", "Port_P1", "RadiationBox"
    ]
    mock_hfss.excitation_names = ["P1_CPW"]
    mock_rad_b = MagicMock()
    mock_rad_b.type = "Radiation"
    mock_rad_b.name = "RadiationBox"
    mock_hfss.boundaries = [mock_rad_b]
    mock_hfss.setup_names = ["Setup_UWB"]
    mock_hfss.setup_sweeps_names = {"Setup_UWB": ["Sweep_1to14GHz"]}

    hfss_auto.hfss = mock_hfss

    assert hfss_auto.validate_prepared_model(
        config_type="Type_A",
        setup_name="Setup_UWB",
        sweep_name="Sweep_1to14GHz"
    ) is True


def test_validate_prepared_model_missing_geometry_raises():
    """Verifies that validate_prepared_model raises RuntimeError if a geometry object is missing."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    # Missing 'Port_P1'
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiationBox"
    ]
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="missing geometry objects.*Port_P1"):
        hfss_auto.validate_prepared_model(config_type="Type_A")


def test_validate_prepared_model_missing_port_raises():
    """Verifies that validate_prepared_model raises RuntimeError if port excitation is missing."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiatingPatch", "Port_P1", "RadiationBox"
    ]
    mock_hfss.excitation_names = []  # No excitations
    mock_hfss.boundaries = []
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="excitation port 'P1_CPW' not found"):
        hfss_auto.validate_prepared_model(config_type="Type_A")


def test_validate_prepared_model_missing_radiation_boundary_raises():
    """Verifies that validate_prepared_model raises RuntimeError if radiation boundary is missing."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiatingPatch", "Port_P1", "RadiationBox"
    ]
    mock_hfss.excitation_names = ["P1_CPW"]
    mock_hfss.boundaries = []  # No radiation boundary
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="radiation boundary not found"):
        hfss_auto.validate_prepared_model(config_type="Type_A")


def test_validate_prepared_model_missing_setup_raises():
    """Verifies that validate_prepared_model raises RuntimeError if setup is missing."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiatingPatch", "Port_P1", "RadiationBox"
    ]
    mock_hfss.excitation_names = ["P1_CPW"]
    mock_rad_b = MagicMock()
    mock_rad_b.type = "Radiation"
    mock_hfss.boundaries = [mock_rad_b]
    mock_hfss.setup_names = ["OtherSetup"]  # Missing Setup_UWB
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="setup 'Setup_UWB' not found"):
        hfss_auto.validate_prepared_model(config_type="Type_A", setup_name="Setup_UWB")


def test_validate_prepared_model_missing_sweep_raises():
    """Verifies that validate_prepared_model raises RuntimeError if sweep is missing."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.modeler.object_names = [
        "Substrate", "Ground_Left", "Ground_Right", "FeedLine", "RadiatingPatch", "Port_P1", "RadiationBox"
    ]
    mock_hfss.excitation_names = ["P1_CPW"]
    mock_rad_b = MagicMock()
    mock_rad_b.type = "Radiation"
    mock_hfss.boundaries = [mock_rad_b]
    mock_hfss.setup_names = ["Setup_UWB"]
    mock_hfss.setup_sweeps_names = {"Setup_UWB": ["OtherSweep"]}  # Missing Sweep_1to14GHz
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="sweep 'Sweep_1to14GHz' not found"):
        hfss_auto.validate_prepared_model(config_type="Type_A", setup_name="Setup_UWB", sweep_name="Sweep_1to14GHz")


def test_save_project_failure_raises():
    """Verifies that save_project raises RuntimeError when hfss.save_project returns False."""
    antenna_cfg, sim_cfg = main.load_configurations()
    hfss_auto = HFSSAutomation(antenna_cfg, sim_cfg)

    mock_hfss = MagicMock()
    mock_hfss.save_project.return_value = False
    hfss_auto.hfss = mock_hfss

    with pytest.raises(RuntimeError, match="HFSS.save_project\\(\\) returned False"):
        hfss_auto.save_project()



