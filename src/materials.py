"""
Material definitions and validation module for UWB Antenna Engineering.
Compatible with both standalone verification and PyAEDT 1.9.0 material assignment.
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

    @staticmethod
    def material_exists(materials, mat_name: str) -> bool:
        """
        Checks if a material exists in the PyAEDT Materials library or active project.
        Supports PyAEDT 1.9.0 collection/dictionary interface and legacy fallbacks.
        Avoids calling obsolete methods like checkifmaterialexists.
        """
        # 1. Direct collection membership: `mat_name in materials` (PyAEDT 1.x standard)
        try:
            if mat_name in materials:
                return True
        except (TypeError, AttributeError):
            pass

        # 2. Case-insensitive lookup in material_keys
        try:
            if hasattr(materials, "material_keys") and materials.material_keys:
                keys_lower = [str(k).lower() for k in materials.material_keys]
                if mat_name.lower() in keys_lower:
                    return True
        except Exception:
            pass

        # 3. Check materials dictionary / mapping
        try:
            if hasattr(materials, "materials") and materials.materials:
                if mat_name in materials.materials or mat_name.lower() in [str(m).lower() for m in materials.materials]:
                    return True
        except Exception:
            pass

        # 4. Check check_material_exists method (if available in some PyAEDT versions)
        if hasattr(materials, "check_material_exists") and callable(materials.check_material_exists):
            try:
                return bool(materials.check_material_exists(mat_name))
            except Exception:
                pass

        # 5. Legacy checkifmaterialexists (pre-1.0 fallback)
        if hasattr(materials, "checkifmaterialexists") and callable(materials.checkifmaterialexists):
            try:
                return bool(materials.checkifmaterialexists(mat_name))
            except Exception:
                pass

        return False

    def assign_pyaedt_materials(self, hfss_app) -> bool:
        """
        Create and assign materials in native HFSS project via PyAEDT 1.9.0.
        Preserves FR4_epoxy (eps=4.4, tand=0.02) and copper properties.
        Avoids duplicate material creation.
        """
        try:
            materials = hfss_app.materials
            mat_name = self.substrate_name

            if not self.material_exists(materials, mat_name):
                logger.info(f"Adding custom substrate material '{mat_name}' in HFSS...")
                mat = materials.add_material(mat_name)
                mat.permittivity = self.relative_permittivity
                mat.dielectric_loss_tangent = self.dielectric_loss_tangent
                logger.info(f"Configured '{mat_name}': eps_r={self.relative_permittivity}, tand={self.dielectric_loss_tangent}")
            else:
                logger.info(f"Material '{mat_name}' already exists in HFSS. Avoiding duplicate creation.")

            # Conductor material (copper)
            met_name = self.metallization_name
            if not self.material_exists(materials, met_name):
                logger.info(f"Adding conductor material '{met_name}' in HFSS...")
                cop = materials.add_material(met_name)
                cop.conductivity = self.copper_conductivity
            else:
                logger.info(f"Conductor material '{met_name}' exists in HFSS.")

            return True
        except Exception as e:
            logger.warning(f"PyAEDT material assignment encountered warning/error: {e}")
            return False
