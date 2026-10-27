"""The local program must run independently of the company-PC API project."""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from participant_bench.config import Config, ModelConfig
from participant_bench.models import Unavailable, require_offline
from participant_bench.runner import run


def test_local_install_has_no_direct_api_sdk_dependency():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    assert not any(
        name.startswith(("openai", "httpx", "requests", "participant-bench-api")) for name in dependencies
    )
    assert "api" not in ModelConfig.model_fields


def test_local_help_works_when_company_package_import_is_blocked():
    code = """
import importlib.abc
import sys
class BlockCompany(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('participant_api', 'openai'):
            raise AssertionError('Company package imported by the local CLI')
sys.meta_path.insert(0, BlockCompany())
from participant_bench.cli import main
main(['--help'])
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    assert "ocr-calibrate" in completed.stdout and "api-check" not in completed.stdout


def test_unknown_backend_is_rejected_before_document_reading(tmp_path):
    config = Config(methods=["vlm"], models={"vlm": ModelConfig(backend="unregistered", options={"x": 1})})
    config.output_dir = str(tmp_path / "runs")
    with pytest.raises(Unavailable, match="nicht aktiviert"):
        run(config, tmp_path / "missing-pdfs")
    assert not (tmp_path / "runs").exists()
    with pytest.raises(ValueError, match="offline"):
        require_offline(config, True)
