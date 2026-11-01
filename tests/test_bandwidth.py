"""
Tests for bandwidth extraction, interpolation across -10 dB threshold, and discrepancy detection.
"""

import numpy as np
import pytest

from src.postprocessing import PostProcessor


def test_bandwidth_extraction_single_notch():
    """Verify linear interpolation and extraction of single resonance notch below -10 dB."""
    processor = PostProcessor(s11_threshold_db=-10.0)

    # Frequency from 2.0 to 5.0 GHz with V-notch between 3.0 and 4.0 GHz
    freqs = np.array([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
    s11 = np.array([0.0, -5.0, -10.0, -25.0, -10.0, -5.0, 0.0])

    bands = processor.extract_operating_bands(freqs, s11)
    assert len(bands) == 1
    band = bands[0]
    assert np.isclose(band["f_lower_ghz"], 3.0, atol=0.01)
    assert np.isclose(band["f_upper_ghz"], 4.0, atol=0.01)
    assert np.isclose(band["bandwidth_mhz"], 1000.0, atol=10.0)


def test_fractional_bandwidth():
    """Verify fractional bandwidth formula."""
    processor = PostProcessor()
    freqs = np.array([3.0, 3.5, 4.0])
    s11 = np.array([-15.0, -20.0, -15.0])
    bands = processor.extract_operating_bands(freqs, s11)
    assert len(bands) == 1
    # Center = 3.5 GHz, BW = 1.0 GHz -> FBW = 1.0 / 3.5 * 100 = 28.57%
    assert np.isclose(bands[0]["fractional_bw_percent"], 28.57, atol=0.1)


def test_discrepancy_detection_published_data():
    """Verify discrepancy logic on Type C 10.2mm published figures."""
    processor = PostProcessor()
    pub_data = [
        {
            "f_lower_ghz": 3.0526,
            "f_upper_ghz": 12.0000,
            "published_bw_mhz": 9124.70
        }
    ]
    # Synthetic simulated band that matches exact physical limits
    sim_data = [
        {
            "f_lower_ghz": 3.0526,
            "f_upper_ghz": 12.0000,
            "bandwidth_mhz": 8947.40,
            "fractional_bw_percent": 118.88
        }
    ]

    comp = processor.compare_with_published(sim_data, pub_data)
    assert len(comp) == 1
    c = comp[0]
    # Discrepancy between paper table and arithmetic: 9124.70 - 8947.40 = 177.30 MHz
    assert np.isclose(c["published_vs_calculated_discrepancy_mhz"], 177.30, atol=0.05)
