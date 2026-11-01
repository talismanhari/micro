#!/usr/bin/env python3
"""
Comprehensive environment inspection and diagnostic tool for UWB Antenna Engineering.
Executes on both macOS development machine and Windows Lenovo LOQ simulation laptop.
Detects operating system, Python, PyAEDT, installed Ansys AEDT / Student versions (including 2025 R2), license, and processes.
"""

import sys
import platform
import shutil
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.system_monitor import SystemMonitor


def run_check(verbose: bool = True) -> bool:
    """
    Runs complete diagnostic evaluation.
    Returns True if system is fully ready for HFSS simulation, False otherwise.
    """
    info = SystemMonitor.inspect_environment()
    is_windows = (info["os_name"] == "Windows")
    has_pyaedt = (info["pyaedt_version"] != "Not Installed")
    aedt_installs = info.get("aedt_installed", [])
    running_aedt = info.get("aedt_running_processes", [])
    lic_info = info.get("license_info", {})
    missing_deps = info.get("missing_dependencies", [])
    disk_free = info["disk_free_gb"]
    disk_ok = (isinstance(disk_free, (int, float)) and disk_free >= 10.0)

    # Check project directories and configuration files
    configs_ok = (ROOT / "configs" / "antenna_parameters.json").exists() and (ROOT / "configs" / "simulation_settings.json").exists()

    # Check existing results
    raw_results = list((ROOT / "results" / "raw").glob("*.csv")) if (ROOT / "results" / "raw").exists() else []
    existing_aedt = list((ROOT / "hfss_projects").rglob("*.aedt")) if (ROOT / "hfss_projects").exists() else []

    if verbose:
        print("=" * 70)
        print("   UWB ANTENNA ENGINEERING — SYSTEM DIAGNOSTIC & PRE-FLIGHT CHECK")
        print("=" * 70)
        print(f" Operating System       : {info['os_name']} {info['os_release']} ({info['machine']})")
        print(f" Python Version         : {info['python_version']} ({'Virtualenv' if info['in_virtualenv'] else 'Global System'})")
        print(f" Python Executable      : {info['python_executable']}")
        print(f" PyAEDT Version         : {info['pyaedt_version']}")

        install_labels = []
        for d in aedt_installs:
            stud_tag = " [Student Edition]" if d.get("is_student") else ""
            install_labels.append(f"{d['version']}{stud_tag} ({d['source']})")
        aedt_summary = ', '.join(install_labels) if install_labels else 'None Detected'
        active_proc_summary = f"Running (PID {running_aedt[0]['pid']})" if running_aedt else 'None (will auto-launch)'

        print(f" Installed Ansys AEDT   : {aedt_summary}")
        print(f" Active AEDT Processes  : {active_proc_summary}")
        print(f" License Configured     : {'Yes' if lic_info.get('license_configured') else 'Default / Student Built-in'}")
        print(f" System RAM             : {info['available_ram_gb']} GB available / {info['total_ram_gb']} GB total ({info['ram_used_percent']}% used)")
        print(f" Free Storage           : {disk_free} GB available / {info['disk_total_gb']} GB total")
        print(f" Config Files Valid     : {'Yes' if configs_ok else 'Missing configs/'}")
        print(f" Previous Results Found : {len(raw_results)} CSV datasets, {len(existing_aedt)} .aedt projects")
        print("-" * 70)

    # Readiness Assessment
    remediations = []
    ready_for_hfss = True

    if not is_windows:
        ready_for_hfss = False
        remediations.append(
            "Platform Note: macOS development machine detected.\n"
            "   Ansys HFSS simulations must run natively on the Windows Lenovo LOQ laptop.\n"
            "   macOS is used for static geometry checks, test suite, and report compilation."
        )

    if missing_deps:
        ready_for_hfss = False
        remediations.append(
            f"Missing Python Packages: {', '.join(missing_deps)}\n"
            f"   Remediation: Run '{sys.executable} -m pip install -r requirements.txt'"
        )

    if is_windows and not has_pyaedt:
        ready_for_hfss = False
        remediations.append(
            "PyAEDT Not Installed:\n"
            f"   Remediation: Run '{sys.executable} -m pip install pyaedt'"
        )

    if is_windows and not aedt_installs and not running_aedt:
        ready_for_hfss = False
        remediations.append(
            "Ansys Electronics Desktop / Student Edition Not Detected:\n"
            "   Remediation: Ensure Ansys AEDT or Ansys Student (v252 / 2025 R2 or 2021.2-2025.2+) is installed or running."
        )

    if not disk_ok:
        ready_for_hfss = False
        remediations.append(
            f"Low Disk Space: {disk_free} GB free (minimum required is 10.0 GB for HFSS mesh).\n"
            "   Remediation: Free up storage on current volume before meshing."
        )

    if verbose:
        if ready_for_hfss:
            print("  ✓ STATUS: SYSTEM FULLY READY FOR HFSS SIMULATION")
        else:
            print("  ℹ STATUS: PRE-FLIGHT NOTICES / REMEDIATION REQUIRED:")
            for r in remediations:
                print(f"    • {r}")
        print("=" * 70)

    return ready_for_hfss


if __name__ == "__main__":
    ready = run_check(verbose=True)
    sys.exit(0 if ready else 1)
