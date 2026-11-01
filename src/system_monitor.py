"""
Hardware inspection, resource monitoring, and thermal/memory safeguards.
Designed to protect the Lenovo LOQ simulation laptop and log system status.
Includes deep Windows Ansys AEDT installation and process detection,
with full support for Ansys Electronics Desktop Student 2025 R2 (v252).
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
        "2025.2", "2025.1", "2024.2", "2024.1", "2023.2", "2023.1", "2022.2", "2022.1", "2021.2"
    ]

    def __init__(self, min_disk_gb: float = 10.0, max_ram_percent: float = 85.0):
        self.min_disk_gb = min_disk_gb
        self.max_ram_percent = max_ram_percent

    @classmethod
    def detect_installed_aedt_versions(cls) -> List[Dict[str, Any]]:
        """
        Detects installed Ansys Electronics Desktop versions on the machine.
        Supports Ansys Student 2025 R2 (v252) and standard commercial installations.
        Checks:
        1. Environment variables (ANSYSEM_ROOT*, ANSYS_ROOT*)
        2. Standard Windows installation directories including:
           - C:\\Program Files\\ANSYS Inc\\ANSYS Student\\v252\\AnsysEM
           - C:\\Program Files\\ANSYS Inc\\v*\\AnsysEM
           - C:\\Program Files\\AnsysEM\\v*\\Win64
        3. Windows Registry (if on Windows)
        """
        detected: List[Dict[str, Any]] = []

        def _add_if_new(version: str, path: str, source: str, is_student: bool = False):
            if not any(d["version"] == version and d["path"] == path for d in detected):
                detected.append({
                    "version": version,
                    "path": path,
                    "source": source,
                    "is_student": is_student
                })

        # 1. Environment variables
        for ver in cls.KNOWN_AEDT_VERSIONS:
            ver_clean = ver.replace(".", "")
            # Check e.g. ANSYSEM_ROOT252 or ANSYSEM_ROOT20252
            env_candidates = [
                f"ANSYSEM_ROOT{ver_clean}",
                f"ANSYSEM_ROOT{ver_clean[2:]}" if len(ver_clean) == 5 else f"ANSYSEM_ROOT{ver_clean}",
                f"ANSYS_ROOT{ver_clean}",
            ]
            for env_key in env_candidates:
                val = os.environ.get(env_key)
                if val and Path(val).exists():
                    is_stud = "student" in val.lower()
                    _add_if_new(ver, str(Path(val).resolve()), f"env:{env_key}", is_student=is_stud)

        # 2. Windows Filesystem Paths
        if platform.system() == "Windows" or os.environ.get("MOCK_WINDOWS_AEDT_CHECK"):
            prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

            search_roots = [
                Path(prog_files) / "ANSYS Inc",
                Path(prog_files) / "AnsysEM",
                Path(prog_files_x86) / "ANSYS Inc",
                Path(prog_files_x86) / "AnsysEM",
            ]

            for ver in cls.KNOWN_AEDT_VERSIONS:
                ver_code = f"v{ver.replace('.', '')[2:]}" if len(ver.replace('.', '')) == 5 else f"v{ver.replace('.', '')}"
                # e.g. v252, v242, v232

                specific_paths = [
                    # Verified Student installation path:
                    Path(prog_files) / "ANSYS Inc" / "ANSYS Student" / ver_code / "AnsysEM",
                    Path(prog_files) / "ANSYS Inc" / "ANSYS Student" / ver_code / "AnsysEM" / "Win64",
                    # Commercial / Standard paths:
                    Path(prog_files) / "ANSYS Inc" / ver_code / "AnsysEM",
                    Path(prog_files) / "AnsysEM" / ver_code / "Win64",
                    Path(prog_files) / "AnsysEM" / ver_code,
                    # x86 fallbacks:
                    Path(prog_files_x86) / "ANSYS Inc" / "ANSYS Student" / ver_code / "AnsysEM",
                    Path(prog_files_x86) / "ANSYS Inc" / ver_code / "AnsysEM",
                ]

                for p in specific_paths:
                    if p.exists():
                        is_stud = "student" in str(p).lower()
                        _add_if_new(ver, str(p.resolve()), "filesystem", is_student=is_stud)

            # Broad directory scan under ANSYS Inc
            ansys_inc = Path(prog_files) / "ANSYS Inc"
            if ansys_inc.exists():
                try:
                    for student_dir in ansys_inc.glob("*Student*/v*/AnsysEM"):
                        if student_dir.exists():
                            # Extract version from e.g. v252
                            v_folder = student_dir.parent.name
                            if v_folder.startswith("v") and len(v_folder) >= 4:
                                num = v_folder[1:]
                                ver_str = f"20{num[:2]}.{num[2:]}"
                                _add_if_new(ver_str, str(student_dir.resolve()), "filesystem_student", is_student=True)
                except Exception:
                    pass

            # 3. Windows Registry
            try:
                import winreg
                reg_paths = [
                    r"SOFTWARE\Ansys\Electronics Desktop",
                    r"SOFTWARE\Ansys\AnsysEM",
                    r"SOFTWARE\Ansys\Student"
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
                                is_stud = "student" in reg_p.lower() or "student" in subkey_name.lower()
                                _add_if_new(ver_formatted, f"Registry: {reg_p}\\{subkey_name}", "winreg", is_student=is_stud)
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

        # Student status
        info["has_student_version"] = any(d.get("is_student") for d in info["aedt_installed"])

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
