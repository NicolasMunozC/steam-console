"""The module is runnable: the installed launcher depends on it."""

import subprocess
import sys

from steam_console import __version__


def test_python_dash_m_runs_the_tool():
    done = subprocess.run([sys.executable, "-m", "steam_console", "--version"],
                          capture_output=True, text=True, check=False)

    assert done.returncode == 0
    assert __version__ in done.stdout


def test_python_dash_m_offers_the_same_flags():
    done = subprocess.run([sys.executable, "-m", "steam_console", "--help"],
                          capture_output=True, text=True, check=False)

    assert done.returncode == 0
    assert "--print-only" in done.stdout
