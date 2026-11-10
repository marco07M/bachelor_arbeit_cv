"""Ensure tests run from software/ and use a writable local pytest basetemp directory."""

import os
from pathlib import Path

SOFTWARE_ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    os.chdir(SOFTWARE_ROOT)
    if not config.option.basetemp:
        config.option.basetemp = str(SOFTWARE_ROOT / ".cache/pytest_tmp")
