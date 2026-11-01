"""
Material definitions and validation module for UWB Antenna Engineering.
Compatible with both standalone verification and PyAEDT material assignment.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MaterialManager:
    """Manages dielectric and metallic material parameters."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sub_cfg = config.get("substrate", {})
        self.met_cfg = config.get("metallization", {})

    @property
    def substrate_name(self) -> str:
        return self.sub_cfg.get("material", "FR4_epoxy")

    @property
    def relative_permittivity(self) -> float:
        return float(self.sub_cfg.get("relative_permittivity", 4.4))

    @property
    def dielectric_loss_tangent(self) -> float:
        return float(self.sub_cfg.get("dielectric_loss_tangent", 0.02))

    @property
    def metallization_name(self) -> str:
        return self.met_cfg.get("material", "copper")

    @property
    def copper_conductivity(self) -> float:
        return float(self.met_cfg.get("conductivity_siemens_per_m", 5.8e7))

    def validate_properties(self) -> bool:
        """Validate material properties are physically reasonable for microwave FR4/Copper."""
        if not (1.0 <= self.relative_permittivity <= 10.0):
            logger.error(f"Invalid permittivity: {self.relative_permittivity}")
            return False
        if not (0.0 <= self.dielectric_loss_tangent <= 0.1):
            logger.error(f"Invalid loss tangent: {self.dielectric_loss_tangent}")
            return False
        if self.copper_conductivity <= 1.0e6:
            logger.error(f"Invalid copper conductivity: {self.copper_conductivity}")
            return False
        logger.info(
            f"Materials verified: Substrate={self.substrate_name} (eps={self.relative_permittivity}, tand={self.dielectric_loss_tangent}), Metal={self.metallization_name}"
        )
        return True

    def assign_pyaedt_materials(self, hfss_app) -> bool:
        """
        Create and assign materials in native HFSS project via PyAEDT.
        Safe to call on Windows HFSS environment.
        """
        try:
            mat_name = self.substrate_name
            if not hfss_app.materials.checkifmaterialexists(mat_name):
                logger.info(f"Adding custom substrate material '{mat_name}' in HFSS...")
                mat = hfss_app.materials.add_material(mat_name)
                mat.permittivity = self.relative_permittivity
                mat.dielectric_loss_tangent = self.dielectric_loss_tangent
            return True
        except Exception as e:
            logger.warning(f"PyAEDT material assignment encountered warning/error: {e}")
            return False
