"""
Hardware inspection, resource monitoring, and thermal/memory safeguards.
Designed to protect the Lenovo LOQ simulation laptop and log system status.
Includes deep Windows Ansys AEDT installation and process detection.
"""

import sys
import os
import platform
import shutil
from pathlib import Path
import logging
from typing import Dict, Any, Optional, Tuple, List

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitors system hardware resources, detects AEDT software, and enforces safety thresholds."""

    KNOWN_AEDT_VERSIONS = [
        "2024.2", "2024.1", "2023.2", "2023.1", "2022.2", "2022.1", "2021.2"
    ]

    def __init__(self, min_disk_gb: float = 10.0, max_ram_percent: float = 85.0):
        self.min_disk_gb = min_disk_gb
        self.max_ram_percent = max_ram_percent

    @classmethod
    def detect_installed_aedt_versions(cls) -> List[Dict[str, str]]:
        """
        Detects installed Ansys Electronics Desktop versions on the machine.
        Checks:
        1. Environment variables (ANSYSEM_ROOT*)
        2. Standard Windows installation directories (C:\\Program Files\\AnsysEM\\...)
        3. Windows Registry (if on Windows)
        """
        detected = []

        # 1. Environment variables
        for ver in cls.KNOWN_AEDT_VERSIONS:
            env_key = f"ANSYSEM_ROOT{ver.replace('.', '')}"
            val = os.environ.get(env_key)
            if val and Path(val).exists():
                detected.append({"version": ver, "path": str(Path(val).resolve()), "source": "environment_variable"})

        # 2. Standard Windows Installation Paths
        if platform.system() == "Windows":
            base_candidates = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "AnsysEM",
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "AnsysEM"
            ]
            for base in base_candidates:
                if base.exists():
                    for ver in cls.KNOWN_AEDT_VERSIONS:
                        ver_folder = f"v{ver.replace('.', '')}"
                        full_p = base / ver_folder / "Win64"
                        if full_p.exists() and not any(d["version"] == ver for d in detected):
                            detected.append({"version": ver, "path": str(full_p.resolve()), "source": "filesystem"})

            # 3. Windows Registry
            try:
                import winreg
                reg_paths = [
                    r"SOFTWARE\Ansys\Electronics Desktop",
                    r"SOFTWARE\Ansys\AnsysEM"
                ]
                for reg_p in reg_paths:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_p)
                        sub_count, _, _ = winreg.QueryInfoKey(key)
                        for i in range(sub_count):
                            subkey_name = winreg.EnumKey(key, i)
                            if subkey_name.startswith("v"):
                                v_num = subkey_name[1:]
                                ver_formatted = f"20{v_num[:2]}.{v_num[2:]}" if len(v_num) >= 3 else subkey_name
                                if not any(d["version"] == ver_formatted for d in detected):
                                    detected.append({"version": ver_formatted, "path": "Registry Registered", "source": "winreg"})
                        winreg.CloseKey(key)
                    except Exception:
                        pass
            except ImportError:
                pass

        return detected

    @classmethod
    def check_running_aedt_processes(cls) -> List[Dict[str, Any]]:
        """Checks if Ansys Electronics Desktop (ansysedt.exe) is currently executing."""
        running = []
        if not psutil:
            return running

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                p_name = proc.info.get("name", "").lower()
                if "ansysedt" in p_name or "ansoft" in p_name:
                    running.append({
                        "pid": proc.info.get("pid"),
                        "name": proc.info.get("name")
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return running

    @classmethod
    def check_license_environment(cls) -> Dict[str, Any]:
        """Inspects Ansys license environment variables."""
        ansys_lic = os.environ.get("ANSYSLMD_LICENSE_FILE")
        ansys_li = os.environ.get("ANSYSLI_SERVERS")
        return {
            "license_configured": bool(ansys_lic or ansys_li),
            "ANSYSLMD_LICENSE_FILE": ansys_lic,
            "ANSYSLI_SERVERS": ansys_li
        }

    @classmethod
    def check_missing_dependencies(cls) -> List[str]:
        """Checks for required Python runtime libraries."""
        missing = []
        core_packages = ["numpy", "matplotlib", "reportlab", "pytest", "psutil"]
        if platform.system() == "Windows":
            core_packages.append("pyaedt")

        for pkg in core_packages:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        return missing

    @classmethod
    def inspect_environment(cls) -> Dict[str, Any]:
        """Gathers machine OS, CPU, RAM, Python, AEDT, license, and processes."""
        info = {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
            "in_virtualenv": (sys.prefix != sys.base_prefix),
        }

        # Memory & Disk info
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
            info["cpu_logical_cores"] = 1
            info["cpu_physical_cores"] = 1

        total_b, used_b, free_b = shutil.disk_usage(".")
        info["disk_total_gb"] = round(total_b / (1024 ** 3), 2)
        info["disk_free_gb"] = round(free_b / (1024 ** 3), 2)

        # PyAEDT check
        try:
            import pyaedt
            info["pyaedt_version"] = pyaedt.__version__
        except ImportError:
            info["pyaedt_version"] = "Not Installed"

        # AEDT software detection
        info["aedt_installed"] = cls.detect_installed_aedt_versions()
        info["aedt_running_processes"] = cls.check_running_aedt_processes()
        info["license_info"] = cls.check_license_environment()
        info["missing_dependencies"] = cls.check_missing_dependencies()

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
