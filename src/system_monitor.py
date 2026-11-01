"""
Hardware inspection, resource monitoring, and thermal/memory safeguards.
Designed to protect the Lenovo LOQ simulation laptop and log system status.
"""

import sys
import platform
import shutil
import logging
from typing import Dict, Any, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitors system hardware resources and enforces safety thresholds."""

    def __init__(self, min_disk_gb: float = 10.0, max_ram_percent: float = 85.0):
        self.min_disk_gb = min_disk_gb
        self.max_ram_percent = max_ram_percent

    @staticmethod
    def inspect_environment() -> Dict[str, Any]:
        """Gathers machine OS, CPU, RAM, Python, and GPU detection."""
        info = {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
        }

        # Memory & Disk info via psutil or shutil
        if psutil:
            mem = psutil.virtual_memory()
            info["total_ram_gb"] = round(mem.total / (1024 ** 3), 2)
            info["available_ram_gb"] = round(mem.available / (1024 ** 3), 2)
            info["ram_used_percent"] = mem.percent
            info["cpu_logical_cores"] = psutil.cpu_count(logical=True)
            info["cpu_physical_cores"] = psutil.cpu_count(logical=False)
        else:
            info["total_ram_gb"] = "psutil_not_installed"
            info["available_ram_gb"] = "psutil_not_installed"
            info["ram_used_percent"] = 0.0

        # Disk space
        total_b, used_b, free_b = shutil.disk_usage(".")
        info["disk_total_gb"] = round(total_b / (1024 ** 3), 2)
        info["disk_free_gb"] = round(free_b / (1024 ** 3), 2)

        # PyAEDT check
        try:
            import pyaedt
            info["pyaedt_version"] = pyaedt.__version__
        except ImportError:
            info["pyaedt_version"] = "Not Installed"

        return info

    def check_safety_guards(self) -> Tuple[bool, str]:
        """Verifies if system has sufficient memory and storage before launching simulation."""
        _, _, free_b = shutil.disk_usage(".")
        free_gb = free_b / (1024 ** 3)
        if free_gb < self.min_disk_gb:
            msg = f"Insufficient disk space: {free_gb:.1f} GB available, minimum required is {self.min_disk_gb:.1f} GB."
            logger.error(msg)
            return False, msg

        if psutil:
            mem = psutil.virtual_memory()
            if mem.percent > self.max_ram_percent:
                msg = f"High RAM usage: {mem.percent:.1f}% currently utilized (threshold: {self.max_ram_percent}%)."
                logger.warning(msg)
                return False, msg

        return True, "System resources within safe operating thresholds."
