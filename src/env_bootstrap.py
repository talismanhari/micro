"""
Automated Python virtual environment bootstrapper and dependency synchronizer.
Ensures 'python main.py' automatically creates, configures, and invokes the project venv.
"""

import sys
import os
import venv
import subprocess
import platform
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EnvironmentBootstrapper:
    """Manages automatic virtual environment creation, package installation, and re-invocation."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        self.venv_dir = self.project_root / ".venv"
        self.requirements_file = self.project_root / "requirements.txt"

    @property
    def is_in_virtualenv(self) -> bool:
        """Determines if the active interpreter is running within a virtual environment."""
        return sys.prefix != sys.base_prefix

    @property
    def venv_python(self) -> Path:
        """Returns the platform-specific path to the virtual environment Python executable."""
        if platform.system() == "Windows":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    def ensure_virtualenv_exists(self) -> Path:
        """Creates .venv if it does not already exist."""
        if not self.venv_python.exists():
            print(f"[BOOTSTRAP] Virtual environment not found. Initializing at: {self.venv_dir}")
            builder = venv.EnvBuilder(with_pip=True, clear=False)
            builder.create(str(self.venv_dir))
            print("[BOOTSTRAP] Virtual environment created successfully.")
        return self.venv_python

    def check_and_install_dependencies(self, python_exec: Path) -> bool:
        """Installs dependencies into the virtual environment only if they are missing."""
        # Check core packages
        check_code = (
            "import sys, importlib.util; "
            "pkgs = ['numpy', 'matplotlib', 'reportlab', 'pytest', 'psutil']; "
            "pkgs += ['ansys.aedt.core'] if sys.platform == 'win32' else []; "
            "missing = [p for p in pkgs if importlib.util.find_spec(p) is None]; "
            "sys.exit(0 if not missing else 1)"
        )
        res = subprocess.run([str(python_exec), "-c", check_code], capture_output=True)
        if res.returncode == 0:
            # Dependencies already satisfied
            return True

        print(f"[BOOTSTRAP] Installing required dependencies into {python_exec}...")
        if self.requirements_file.exists():
            cmd = [str(python_exec), "-m", "pip", "install", "-r", str(self.requirements_file)]
            install_res = subprocess.run(cmd)
            if install_res.returncode != 0:
                print(f"[BOOTSTRAP][WARN] pip install -r requirements.txt exited with code {install_res.returncode}")

        # On Windows, guarantee PyAEDT is installed
        if platform.system() == "Windows":
            check_pyaedt = subprocess.run(
                [str(python_exec), "-c", "from ansys.aedt.core import Hfss"], capture_output=True
            )
            if check_pyaedt.returncode != 0:
                print("[BOOTSTRAP] Installing PyAEDT for Windows HFSS simulation...")
                subprocess.run([str(python_exec), "-m", "pip", "install", "pyaedt"])

        return True

    def bootstrap_and_reexec(self) -> None:
        """
        If not inside the project virtual environment, prepares it and re-executes main.py.
        Returns immediately if already running inside the active .venv.
        """
        if self.is_in_virtualenv:
            # Running inside a venv; verify dependencies in place
            self.check_and_install_dependencies(Path(sys.executable))
            return

        # Not in a venv; ensure .venv exists and is populated
        v_py = self.ensure_virtualenv_exists()
        self.check_and_install_dependencies(v_py)

        print(f"[BOOTSTRAP] Relaunching main.py under project virtual environment: {v_py}")
        # Run with the venv python and forward all arguments
        try:
            cmd = [str(v_py)] + sys.argv
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except Exception as e:
            print(f"[BOOTSTRAP][ERROR] Failed to invoke {v_py}: {e}")
            sys.exit(1)


