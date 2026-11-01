#!/usr/bin/env python3
"""
Environment inspection and diagnostic tool for UWB Antenna Engineering.
Executes on both macOS development machine and Windows Lenovo LOQ simulation laptop.
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


def run_check():
    print("=" * 65)
    print("   UWB ANTENNA ENGINEERING — ENVIRONMENT & HARDWARE CHECK")
    print("=" * 65)

    info = SystemMonitor.inspect_environment()

    print(f" Operating System  : {info['os_name']} {info['os_release']} ({info['os_version'][:30]}...)")
    print(f" Architecture      : {info['machine']} ({info['processor'] or 'ARM64/x86_64'})")
    print(f" Python Version    : {info['python_version']} ({info['python_executable']})")
    print(f" PyAEDT Version    : {info['pyaedt_version']}")
    print(f" Total RAM (GB)    : {info['total_ram_gb']}")
    print(f" Available RAM (GB): {info['available_ram_gb']}")
    print(f" RAM Usage (%)     : {info['ram_used_percent']}%")
    print(f" Disk Total (GB)   : {info['disk_total_gb']}")
    print(f" Disk Free (GB)    : {info['disk_free_gb']}")
    print("-" * 65)

    # Status assessments
    is_windows = (info["os_name"] == "Windows")
    has_pyaedt = (info["pyaedt_version"] != "Not Installed")
    disk_ok = (isinstance(info["disk_free_gb"], (int, float)) and info["disk_free_gb"] >= 10.0)

    print("\n[DIAGNOSTIC STATUS]")
    if is_windows:
        print("  ✓ Platform: Windows simulation host detected.")
        if has_pyaedt:
            print("  ✓ PyAEDT: Installed and ready for HFSS automation.")
        else:
            print("  ✗ PyAEDT: NOT installed. Run 'pip install pyaedt' in virtual environment.")
    else:
        print("  ℹ Platform: macOS/Linux development host detected.")
        print("    Native Ansys HFSS simulations must run on the Windows machine.")
        print("    Static validation, geometry generation, testing, and report compilation are available here.")

    if disk_ok:
        print(f"  ✓ Storage: Sufficient disk space ({info['disk_free_gb']} GB available >= 10.0 GB).")
    else:
        print(f"  ⚠ Storage: Low disk space ({info['disk_free_gb']} GB). Minimum 10 GB recommended for HFSS mesh.")

    print("=" * 65)


if __name__ == "__main__":
    run_check()
