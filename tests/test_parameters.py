"""
Tests for configuration file integrity, parameter validity, and material constants.
"""

import json
from pathlib import Path
import pytest

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


def test_antenna_parameters_file_exists():
    p = CONFIG_DIR / "antenna_parameters.json"
    assert p.exists(), f"Missing configuration file: {p}"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "substrate" in data
    assert "feed" in data
    assert "patch" in data
    assert "ground" in data
    assert "configurations" in data


def test_simulation_settings_file_exists():
    p = CONFIG_DIR / "simulation_settings.json"
    assert p.exists(), f"Missing configuration file: {p}"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "simulation_environment" in data
    assert "solution_setup" in data
    assert "frequency_sweep" in data
    assert "hardware_safeguards" in data


def test_material_constants():
    p = CONFIG_DIR / "antenna_parameters.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    sub = data["substrate"]
    assert sub["relative_permittivity"] == 4.4
    assert sub["dielectric_loss_tangent"] == 0.02
    assert sub["thickness_mm"] == 1.53

    met = data["metallization"]
    assert met["material"] == "copper"
    assert met["thickness_mm"] == 0.1
    assert met["conductivity_siemens_per_m"] > 1e7


def test_dimensional_hierarchy():
    p = CONFIG_DIR / "antenna_parameters.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    sub = data["substrate"]
    pat = data["patch"]
    feed = data["feed"]
    gnd = data["ground"]

    # Substrate width must be >= 2*gnd_width + 2*gap + feed_width
    cpw_width = 2 * gnd["width_mm"] + 2 * feed["feed_to_ground_gap_mm"] + feed["width_mm"]
    assert sub["width_mm"] >= cpw_width
    assert sub["length_mm"] >= (gnd["length_mm"] + feed["patch_to_ground_gap_mm"] + pat["length_mm"])
