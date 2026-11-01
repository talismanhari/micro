"""
Tests for antenna geometry generation across Type A, Type B, and Type C.
"""

import json
from pathlib import Path
import pytest

from src.geometry import AntennaGeometry

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "antenna_parameters.json"


@pytest.fixture
def antenna_cfg():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_type_a_polygon(antenna_cfg):
    geom = AntennaGeometry(antenna_cfg)
    pts = geom.get_patch_polygon("Type_A")
    assert len(pts) == 4
    # Check width = 18.4, length = 18.4
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(18.4, 0.01)
    assert max(ys) - min(ys) == pytest.approx(18.4, 0.01)


def test_type_b_polygon(antenna_cfg):
    geom = AntennaGeometry(antenna_cfg)
    pts = geom.get_patch_polygon("Type_B", param=7.0)
    # Chamfering 2 bottom corners turns 4-vertex rectangle into 6-vertex polygon
    assert len(pts) == 6


def test_type_c_polygon(antenna_cfg):
    geom = AntennaGeometry(antenna_cfg)
    pts = geom.get_patch_polygon("Type_C", param=10.2, num_arc_pts=20)
    # Includes circular arc points
    assert len(pts) > 20
    # Boundary vertices must stay within [-9.2, +9.2] in X and [18.9, 37.3] in Y
    for x, y in pts:
        assert -9.21 <= x <= 9.21
        assert 18.89 <= y <= 37.31


def test_cpw_ground_and_feed_dimensions(antenna_cfg):
    geom = AntennaGeometry(antenna_cfg)
    assert len(geom.ground_planes) == 2
    g_left, g_right = geom.ground_planes

    # Ground widths
    assert g_left["size"][0] == 16.9
    assert g_right["size"][0] == 16.9

    # Feed width
    assert geom.feed_line["size"][0] == 3.1

    # Check gap between feed and grounds
    feed_left_edge = -geom.feed_wid / 2.0  # -1.55
    gnd_left_inner_edge = g_left["origin"][0] + g_left["size"][0]  # -2.10
    assert abs(feed_left_edge - gnd_left_inner_edge) == pytest.approx(0.55, 0.001)
